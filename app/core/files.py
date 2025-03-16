import os
from typing import Self, Tuple
import uuid
import logging
import tempfile
import aiofiles
import asyncio
from fastapi import UploadFile


import boto3
from boto3.s3.transfer import S3UploadFailedError
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError

from app.core.configs import settings
from app.models import FilesModel
from app.core.database import Session

logger = logging.getLogger(__name__)


class FileHandler():
    CHUNK_SIZE_BYTES: int = 1024 * 1024  # 1MB Chunks

    def __init__(self, file_model: FilesModel, file_up: UploadFile | None = None):
        logger.debug("Creating file handler", extra={
                     "file_model": file_model, "file_up": file_up})
        self.filename = file_up.filename if file_up else file_model.filename
        self.size_byte = file_model.size_kB
        self.owner_id = file_model.user_id
        self.id = file_model.id
        self.temp_dir = tempfile.TemporaryDirectory()
        self.file_path = os.path.join(self.temp_dir.name, self.filename)

    @classmethod
    async def create(cls, file_model: FilesModel, file_up: UploadFile | None = None) -> Self | None:
        self = cls(file_model, file_up)
        if file_up:
            if not await self.write_to_file(file_up):
                logger.error("Failed to write file to temporary location")
                return None
        return self

    def clean(self):
        self.temp_dir.cleanup()

    async def write_to_file(self, file):
        try:
            async with aiofiles.open(self.file_path, "wb") as f:
                while chunk := await file.read(self.CHUNK_SIZE_BYTES):
                    await f.write(chunk)
            logger.debug(
                f"Saved file '{self.filename}' with {self.size_byte} kB to temporary location '{self.temp_dir.name}'")

            return True

        except IOError as e:
            logger.error("Failed to save temporary file",
                         extra={"path": self.file_path, "error": str(e)})
            return False


# TODO: Add aiobotocore?
class S3Handler():

    def __init__(self, settings):
        self.resource = boto3.resource('s3',
                                       aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                                       aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                                       region_name=settings.AWS_REGION)
        self.file_hdlr: FileHandler | None = None
        self.s3_key: str | None = None

    async def create_upload_file_handler(self, file_db: FilesModel, file_uploaded: UploadFile):
        self.file_hdlr = await FileHandler.create(file_model=file_db, file_up=file_uploaded)

    async def create_download_file_handler(self, file_db: FilesModel):
        self.s3_key = file_db.path
        self.file_hdlr = await FileHandler.create(file_model=file_db)

    def clean(self):
        self.s3_key = None
        if self.file_hdlr:
            self.file_hdlr.clean()
            self.file_hdlr = None

    @staticmethod
    def extract_s3_key(full_s3_uri: str) -> Tuple[str | None, str, str]:
        """
        Extracts the S3 key and bucket name from a full S3 URI.

        Args:
            full_s3_uri (str): The full S3 URI (e.g., s3://bucket-name/path/to/file).

        Returns:
            str: The bucket name (e.g., s3-demo-bucket-36e710ab-c1be)
            str: The S3 file key (e.g., path/to/file.txt).
            str: The file name at the end of the S3 file key (e.g., file.txt).
        """
        file_key = None
        bucket_name = None
        file_name = None

        if full_s3_uri.startswith("s3://"):
            parts = full_s3_uri[5:].split("/", 1)
            bucket_name, file_key = parts[0], parts[1]
        else:
            file_key = full_s3_uri

        file_name = file_key.split("/")[-1]

        return bucket_name, file_key, file_name

    def delete_from_s3(self, file_key: str) -> bool:
        bucket_name, file_key, _ = self.extract_s3_key(file_key)
        if not bucket_name:
            logger.error("Bucket name not found in S3 URI")
            return False

        bucket = self.resource.Bucket(bucket_name)
        obj = bucket.Object(file_key)

        try:
            obj.delete()
            logger.info(f"Successfully deleted {file_key} from {bucket.name}.")
            return True
        except ClientError as err:
            logger.warning(f"Couldn't deleted {file_key} from {bucket.name}.")
            logger.warning(
                f"\t{err.response['Error']['Code']}:{err.response['Error']['Message']}"
            )

        return False

    async def download_from_s3(self, file_key: str, save_in_path: str) -> str | None:
        bucket_name, file_key, _ = self.extract_s3_key(file_key)
        if not bucket_name:
            logger.error("Bucket name not found in S3 URI")
            return None

        logger.info("Trying to download file from s3",
                    extra={
                        "file_key": file_key,
                        "bucket_name": bucket_name,
                        "save_in_path": save_in_path,
                    })

        bucket = self.resource.Bucket(bucket_name)
        obj = bucket.Object(file_key)
        try:
            await asyncio.to_thread(obj.download_file, save_in_path)
            logger.debug(
                f"Successfully downloaded {obj.key} to {save_in_path}.")
            return save_in_path
        except ClientError as err:
            logger.warning(f"Couldn't download {obj.key}.")
            logger.warning(
                f"\t{err.response['Error']['Code']}:{err.response['Error']['Message']}"
            )

        return

    async def upload_to_s3(self, bucket_name: str, file_path: str, user_id: uuid.UUID, filename: str) -> str:
        """Upload file to S3 and return object path"""
        file_key = f"{user_id}/{filename}"

        try:
            await asyncio.to_thread(
                self.resource.meta.client.upload_file,
                Filename=file_path,
                Bucket=bucket_name,
                Key=file_key
            )
            logger.info("File uploaded to S3 successfully",
                        extra={
                            "user_id": user_id,
                            "s3_bucket": bucket_name,
                            "s3_key": file_key
                        })
            return f"s3://{bucket_name}/{file_key}"

        except (ClientError, NoCredentialsError, PartialCredentialsError, FileNotFoundError) as e:
            logger.error("Failed to upload file to S3",
                         extra={
                             "s3_bucket": bucket_name,
                             "error_type": type(e).__name__,
                             "error_details": str(e)
                         })
            raise
        except Exception as e:
            logger.error("Unexpected upload error",
                         extra={"error_type": type(e).__name__, "details": str(e)})
            raise

    async def process_file_upload(self) -> None:
        """Process file upload to S3 storage"""
        s3_path = None

        async with Session() as db:
            file_obj = await FilesModel.find_by_id(self.file_hdlr.id, db)
            await file_obj.add_status("processing", db)

        try:
            self.s3_key = await self.upload_to_s3(
                bucket_name="treme-s3-demo-bucket-36e710ab-c1be-4653-9d80-3c9cae24a71e",
                file_path=self.file_hdlr.file_path,
                user_id=self.file_hdlr.owner_id,
                filename=f"{self.file_hdlr.id}/{self.file_hdlr.filename}",
            )

            logger.info("File processing completed successfully",
                        extra={
                            "user_id": self.file_hdlr.owner_id,
                            "file_name": self.file_hdlr.filename,
                            "s3_path": self.s3_key,
                        })

        except Exception as e:
            logger.error("File processing failed",
                         exc_info=True,
                         extra={
                             "user_id": self.file_hdlr.owner_id,
                             "file_name": self.file_hdlr.filename,
                             "error": str(e),
                         })

        async with Session() as db:
            file_obj = await FilesModel.find_by_id(self.file_hdlr.id, db)
            if not self.s3_key:
                await file_obj.add_status("failed", db)
            else:
                await file_obj.add_status("completed", db)
                file_obj.path = self.s3_key
                await db.commit()

        self.clean()

    async def process_file_download(self):
        return await self.download_from_s3(file_key=self.s3_key, save_in_path=self.file_hdlr.file_path)


async def get_s3_handler():
    return S3Handler(settings)
