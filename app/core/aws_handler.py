import json
from typing import AsyncGenerator, Optional, Tuple
import uuid
import logging
import asyncio
from fastapi import UploadFile

from aiobotocore.session import get_session
from aiobotocore.client import AioBaseClient
from botocore.exceptions import ClientError
from pydantic import UUID4

from app.core.configs import settings
from app.models import FilesModel
from app.core.database import Session
from app.models.files import FileStatus

logger = logging.getLogger(__name__)


class S3FileNotFoundError(Exception):
    """Raised when the requested file is not found in S3."""
    pass


class S3DownloadError(Exception):
    """Raised for other S3 download errors."""
    pass


class BaseAIOBotoHandler():
    @staticmethod
    async def get_client(service: str) -> AioBaseClient:
        session = get_session()
        return session.create_client(
            service,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )


class SQSHandler(BaseAIOBotoHandler):
    @classmethod
    async def get_client(cls) -> AioBaseClient:
        return await super().get_client('sqs')

    @classmethod
    async def send_message_to_sqs(cls, queue_url: str, body: dict, attributes: Optional[dict] = None):
        async with await cls.get_client() as client:
            logger.debug("Sending confirmation email.", extra={'body':
                                                               body, 'MessageAttributes': attributes, 'queue_url': queue_url})
            if attributes:
                response = await client.send_message(
                    QueueUrl=queue_url,
                    MessageBody=json.dumps(body),
                    MessageAttributes=json.dumps(attributes),
                )
            else:
                response = await client.send_message(
                    QueueUrl=queue_url,
                    MessageBody=json.dumps(body),
                )

            logger.info("Message sent successfully.", extra={
                        "MessageId": response.get('MessageId', None)})


class S3Handler(BaseAIOBotoHandler):
    CHUNK_SIZE_BYTES: int = 8 * 1024 * 1024  # 8MB Chunks

    def __init__(self, settings):
        self.upload_bucket_name = settings.S3_BUCKET_NAME
        self.client = None
        self.s3_key: str | None = None

    @classmethod
    async def get_client(cls) -> AioBaseClient:
        return await super().get_client('s3')

    @classmethod
    async def verify_or_create_bucket(cls, bucket_name, region):
        async with await cls.get_client() as client:
            try:
                await client.head_bucket(Bucket=bucket_name)
                logger.debug(
                    f"Bucket '{bucket_name}' already exists in region{region}.")
                return True
            except ClientError as e:
                if e.response['Error']['Code'] == '404':
                    logger.warning(
                        f"Bucket '{bucket_name}' not found. Creating...")
                    try:
                        create_params = {'Bucket': bucket_name,
                                         'CreateBucketConfiguration': {
                                             'LocationConstraint': region,
                                         },
                                         }

                        await client.create_bucket(**create_params)
                        logger.info(
                            f"Bucket '{bucket_name}' successfully created in region{region}.")
                        return True
                    except ClientError as e:
                        logger.error(
                            f"Failed to create bucket '{bucket_name}': {e}")
                        return False
                else:
                    logger.error(f"Error checking bucket '{bucket_name}': {e}")
                    return False

    @staticmethod
    def extract_s3_key(full_s3_uri: str) -> Tuple[Optional[str], str, str]:
        file_key = None
        bucket_name = None

        if full_s3_uri.startswith("s3://"):
            parts = full_s3_uri[5:].split("/", 1)
            bucket_name, file_key = parts[0], parts[1]
        else:
            file_key = full_s3_uri

        file_name = file_key.split("/")[-1]
        return bucket_name, file_key, file_name

    async def _delete_s3_object(self, client, bucket: str, key: str):
        await client.delete_object(Bucket=bucket, Key=key)
        logger.info(f"Successfully deleted {key} from {bucket}.")

    async def delete_from_s3(self, file_key: str, file_id: UUID4) -> bool:
        bucket_name, file_key, _ = self.extract_s3_key(file_key)
        if not bucket_name:
            logger.error("Bucket name not found in S3 URI")
            return False

        try:
            async with await self.get_client() as client:
                await self._delete_s3_object(client, bucket_name, file_key)
                async with Session() as db:
                    file_obj = await FilesModel.find_by_id(file_id, db)
                    await file_obj.add_status(FileStatus.DELETED, db)

                return True
        except S3DownloadError:
            raise
        except Exception as e:
            logger.error("Couldn't delete file.",
                         extra={
                             "s3_bucket": bucket_name,
                             "s3_key": file_key,
                             "error_type": type(e).__name__,
                             "error_details": str(e),
                         })
            return False

    async def upload_to_s3(self, bucket_name: str, file_up: UploadFile, user_id: uuid.UUID, filename: str) -> str:
        """Upload file to S3 and return object path"""
        file_key = f"{user_id}/{filename}"

        try:
            async with await self.get_client() as client:
                try:
                    resp = await client.create_multipart_upload(
                        Bucket=bucket_name,
                        Key=file_key,
                    )
                    upload_id = resp['UploadId']

                    parts = []
                    part_number = 1
                    while chunk := await file_up.read(self.CHUNK_SIZE_BYTES):
                        resp = await client.upload_part(
                            Bucket=bucket_name,
                            Key=file_key,
                            PartNumber=part_number,
                            UploadId=upload_id,
                            Body=chunk,
                        )
                        parts.append({
                            'PartNumber': part_number,
                            'ETag': resp['ETag'],
                        })
                        part_number += 1

                    await client.complete_multipart_upload(
                        Bucket=bucket_name,
                        Key=file_key,
                        UploadId=upload_id,
                        MultipartUpload={'Parts': parts},
                    )
                    return f"s3://{bucket_name}/{file_key}"
                except Exception as e:
                    logger.error("Failed to upload file to S3",
                                 extra={
                                     "s3_bucket": bucket_name,
                                     "error_type": type(e).__name__,
                                     "error_details": str(e),
                                 })

                    await client.abort_multipart_upload(
                        Bucket=bucket_name,
                        Key=file_key,
                        UploadId=upload_id
                    )

        except Exception as e:
            logger.error("Failed to create client",
                         extra={
                             "error_type": type(e).__name__,
                             "error_details": str(e),
                         })

    async def handle_file_upload(self, file_id: UUID4, file_up: UploadFile) -> None:
        """Handle file upload to S3 storage"""
        self.s3_key = None

        async with Session() as db:
            file_obj = await FilesModel.find_by_id(file_id, db)
            await file_obj.add_status(FileStatus.UPLOADING, db)

        self.s3_key = await self.upload_to_s3(
            bucket_name=self.upload_bucket_name,
            file_up=file_up,
            user_id=file_obj.user_id,
            filename=f"{file_obj.id}/{file_up.filename}",
        )

        async with Session() as db:
            file_obj = await FilesModel.find_by_id(file_obj.id, db)
            if not self.s3_key:
                await file_obj.add_status(FileStatus.FAILED, db)
            else:
                await file_obj.add_status(FileStatus.UPLOADED, db)
                file_obj.path = self.s3_key
                await db.commit()

    async def handle_file_download(self, file_key: str) -> AsyncGenerator[bytes, None]:
        bucket_name, file_key, _ = self.extract_s3_key(file_key)
        try:
            async with await self.get_client() as client:
                resp = await client.get_object(Bucket=bucket_name, Key=file_key)
                async for chunk in resp['Body'].content.iter_chunked(self.CHUNK_SIZE_BYTES):
                    yield chunk
        except client.exceptions.NoSuchKey:
            raise S3FileNotFoundError("File not found in S3.")
        except Exception as e:
            raise S3DownloadError(f"Error retrieving file: {str(e)}")


async def get_s3_handler():
    yield S3Handler(settings)
