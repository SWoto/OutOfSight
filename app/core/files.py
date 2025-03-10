import io
import os
import shutil
from typing import Self, Tuple
import uuid
import pyzipper
import logging
import tempfile
import aiofiles
import asyncio
from fastapi import UploadFile
from pydantic import UUID4, SecretStr


import boto3
from boto3.s3.transfer import S3UploadFailedError
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError

from app.core.configs import settings
from app.models import FilesModel
from app.core.database import Session

logger = logging.getLogger(__name__)

# TODO: Add aiobotocore?


class S3Handler():
    def __init__(self, settings):
        self.resource = boto3.resource('s3',
                                       aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                                       aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                                       region_name=settings.AWS_REGION)

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
            file_key = parts[1]
            bucket_name = parts[0]
        else:
            file_key = full_s3_uri

        parts = file_key.split("/")
        file_name = parts[-1]

        return bucket_name, file_key, file_name

    def delete_from_s3(self, file_key: str) -> bool:
        bucket_name, file_key, _ = self.extract_s3_key(file_key)

        bucket = self.resource().Bucket(bucket_name)
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

    def download_from_s3(self, file_key: str, dir: str) -> str | None:
        bucket_name, file_key, file_name = self.extract_s3_key(file_key)

        bucket = self.resource().Bucket(bucket_name)
        obj = bucket.Object(file_key)

        try:
            saved_path = os.path.join(dir, file_name)
            obj.download_file(saved_path)
            logger.debug(f"Successfully downloaded {obj.key} to {saved_path}.")
            return saved_path
        except ClientError as err:
            logger.warning(f"Couldn't download {obj.key}.")
            logger.warning(
                f"\t{err.response['Error']['Code']}:{err.response['Error']['Message']}"
            )

        return

    async def upload_to_s3(self, bucket_name: str = "treme-s3-demo-bucket-36e710ab-c1be-4653-9d80-3c9cae24a71e", file_path: str, user_id: uuid.UUID, filename: str) -> str:
        """Upload file to S3 and return object path"""

        resource = self.resource()

        print("*"*100)
        print(resource.__class__)
        print("*"*100)

        file_key = f"{user_id}/{filename}.zip"

        try:
            await asyncio.to_thread(
                resource.meta.client.upload_file,
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

        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_msg = f"S3 upload failed: {error_code}"
            logger.error(error_msg,
                         extra={
                             "s3_bucket": bucket_name,
                             "error_code": error_code,
                             "error_details": str(e)
                         })
            raise
        except (NoCredentialsError, PartialCredentialsError) as e:
            logger.error("AWS credential error", extra={
                "error_type": type(e).__name__})
            raise
        except FileNotFoundError as e:
            logger.error("File not found during upload",
                         extra={"file_path": file_path, "error": str(e)})
        except Exception as e:
            logger.error("Unexpected upload error",
                         extra={"error_type": type(e).__name__, "details": str(e)})
            raise


class FileProcessor():
    CHUNK_SIZE_BYTES: int = 1024 * 1024  # 1MB Chunks

    id: UUID4
    owner_id: UUID4

    file: io.BytesIO
    filename: str
    size_byte: int
    temp_dir: tempfile.TemporaryDirectory
    file_path: str

    encryption_key: SecretStr
    compression_method: int

    def __init__(self, file: UploadFile, id: UUID4, owner_id: UUID4, encryption_key: SecretStr, compression_method: int = pyzipper.ZIP_LZMA, encryption_method=pyzipper.WZ_AES):
        self.filename = file.filename
        self.size_byte = file.size
        self.temp_dir = tempfile.TemporaryDirectory()
        self.file_path = os.path.join(self.temp_dir.name, self.filename)

        self.encryption_key = encryption_key
        self.compression_method = compression_method
        self.encryption_method = encryption_method

        self.id = id
        self.owner_id = owner_id

    # TODO: Add something to check file_written_error
    @classmethod
    async def create(cls, file: UploadFile, id: UUID4, owner_id: UUID4, encryption_key: SecretStr) -> Self | None:
        self = cls(file, id, owner_id, encryption_key)
        file_written_error = not await self.write_to_file(file)

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

    def _compress_and_encrypt(self):
        zip_path = os.path.join(self.temp_dir.name, f"{str(self.id)}.zip")
        logger.debug(f"Calling AESZipFile", extra={
            "input_file": self.file_path, "zip_file": zip_path, "encryption_key": self.encryption_key, "arcname": self.file_path.split("/")[-1]})
        with pyzipper.AESZipFile(zip_path, 'w', compression=self.compression_method, encryption=self.encryption_method) as zf:
            zf.setpassword(self.encryption_key.get_secret_value().encode())
            zf.write(self.file_path, arcname=self.file_path.split("/")[-1])
        logger.debug(f"Encrypted ZIP created: {zip_path}")

        return zip_path

    @staticmethod
    def is_safe_path(basedir, path, follow_symlinks: bool = True):
        if follow_symlinks:
            return os.path.realpath(path).startswith(basedir)
        return os.path.abspath(path).startswith(basedir)

    # TODO: Remove parameters not from self
    def _decompress_and_decrypt(self, zip_file: str, output_folder: str):
        with pyzipper.AESZipFile(zip_file, 'r', encryption=pyzipper.WZ_AES) as zf:
            zf.setpassword(self.encryption_key.get_secret_value().encode())
            for file in zf.namelist():
                if not self.is_safe_path(output_folder, os.path.join(output_folder, file)):
                    raise ValueError("Potential Zip Slip attack detected")
            zf.extractall(output_folder)
            logger.debug(f"Files extracted to {output_folder}")
        return output_folder

    async def encrypt_file(self) -> str | None:
        """Encrypt and zip file and return path to encrypted ZIP"""
        try:
            zip_path = await asyncio.to_thread(
                self._compress_and_encrypt,
            )
            return zip_path
        except Exception as e:
            logger.error("File compression and encryption failed",
                         extra={"error": str(e),
                                }
                         )
            raise

    # TODO: Remove parameters not from self
    async def decrypt_zip(self, zip_file: str, output_folder: str) -> str | None:
        """Decrypt and unzip file and return path to file"""
        try:
            file_path = await asyncio.to_thread(
                self._decompress_and_decrypt,
                zip_file,
                output_folder,
            )
            return file_path
        except Exception as e:
            logger.error("File decompression and decryption failed",
                         extra={"error": str(e),
                                }
                         )
            raise


async def process_file_upload(
    file: FileProcessor
) -> None:
    """
    Process file upload with encryption and S3 storage
    Returns S3 object path if successful
    """
    s3_path = None

    async with Session() as db:
        file_obj = await FilesModel.find_by_id(file.id, db)
        await file_obj.add_status("processing", db)

    try:
        # file_path = await save_uploaded_file(file, tmp_dir)

        zip_path = await encrypt_file(file.file_path, file.temp_dir.name, str(file.id), file.encryption_key)

        s3_path = await upload_to_s3(
            file_path=zip_path,
            user_id=file.owner_id,
            filename=str(file.id),
        )

        logger.info("File processing completed successfully",
                    extra={
                        "user_id": file.owner_id,
                        "original_filename": file.filename,
                        "s3_path": s3_path
                    })

    except Exception as e:
        logger.error("File processing failed",
                     exc_info=True,
                     extra={
                         "user_id": file.owner_id,
                         "original_filename": file.filename,
                         "error": str(e)
                     })

    file.clean()
    async with Session() as db:
        file_obj = await FilesModel.find_by_id(file.id, db)

        if not s3_path:
            await file_obj.add_status("failed", db)
            return

        await file_obj.add_status("completed", db)
        file_obj.path = s3_path
        await db.commit()


async def process_file_download(file_id: uuid.UUID, tmp_dir: str, encryption_key: SecretStr):

    file_obj = FilesModel()
    async with Session() as db:
        file_obj = await FilesModel.find_by_id(file_id, db)

    zip_path = await download_from_s3(s3_key=file_obj.path, dir=tmp_dir)

    if not zip_path:
        return

    decrypt_zip(zip_path, tmp_dir, encryption_key)
    path = os.path.join(tmp_dir, file_obj.filename)
    return path
