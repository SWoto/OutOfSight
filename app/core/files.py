import os
import shutil
from typing import Tuple
import uuid
import pyzipper
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


async def get_temp_dir() -> str:
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


def encrypt_zip(input_file: str, zip_file: str, password: str):
    """
    Encrypts a file into a password-protected ZIP using AES-256 and BZIP2 compression.

    :param input_file: Path to the file to be encrypted.
    :param zip_file: Path to the output encrypted ZIP file.
    :param password: Password to protect the ZIP file.
    """
    with pyzipper.AESZipFile(zip_file, 'w', compression=pyzipper.ZIP_LZMA, encryption=pyzipper.WZ_AES) as zf:
        zf.setpassword(password.encode())  # Set password
        zf.write(input_file, arcname=input_file.split("/")[-1])  # Add file
    logger.debug(f"Encrypted ZIP created: {zip_file}")


def is_safe_path(basedir, path, follow_symlinks=True):
    if follow_symlinks:
        return os.path.realpath(path).startswith(basedir)
    return os.path.abspath(path).startswith(basedir)


def decrypt_zip(zip_file: str, output_folder: str, password: str):
    with pyzipper.AESZipFile(zip_file, 'r', encryption=pyzipper.WZ_AES) as zf:
        zf.setpassword(password.encode())
        for file in zf.namelist():
            if not is_safe_path(output_folder, os.path.join(output_folder, file)):
                raise ValueError("Potential Zip Slip attack detected")
        zf.extractall(output_folder)
        logger.debug(f"Files extracted to {output_folder}")


async def save_uploaded_file(file: UploadFile, tmp_dir: str) -> str:
    """Save uploaded file to temporary directory"""
    file_path = os.path.join(tmp_dir, file.filename)
    try:
        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                await f.write(chunk)
        logger.debug("File saved temporarily",
                     extra={"path": file_path, "size": os.path.getsize(file_path)})
        return file_path
    except IOError as e:
        logger.error("Failed to save temporary file",
                     extra={"path": file_path, "error": str(e)})
        raise


async def encrypt_file(source_path: str, tmp_dir: str, new_filename: str, encryption_key: str) -> str:
    """Encrypt and zip file and return path to encrypted ZIP"""
    zip_path = os.path.join(tmp_dir, f"{new_filename}.zip")
    try:
        await asyncio.to_thread(
            encrypt_zip,
            source_path,
            zip_path,
            encryption_key
        )
        logger.debug("File encrypted successfully",
                     extra={"source": source_path, "target": zip_path})
        return zip_path
    except Exception as e:
        logger.error("File encryption failed",
                     extra={"source_path": source_path, "error": str(e)})
        raise


def extract_s3_key(full_s3_uri: str) -> Tuple[str | None, str, str]:
    """
    Extracts the S3 key and bucket name from a full S3 URI.

    Args:
        full_s3_uri (str): The full S3 URI (e.g., s3://bucket-name/path/to/file).

    Returns:
        str: The bucket name (e.g., s3-demo-bucket-36e710ab-c1be)
        str: The S3 key (e.g., path/to/file).
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


def s3_resource():
    return boto3.resource('s3',
                          aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                          aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                          region_name=settings.AWS_REGION)


async def delete_from_s3(s3_key: str) -> bool:
    bucket_name, file_key, file_name = extract_s3_key(s3_key)

    bucket = s3_resource().Bucket(bucket_name)
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

    return


async def download_from_s3(s3_key: str, dir: str) -> str | None:
    bucket_name, file_key, file_name = extract_s3_key(s3_key)

    bucket = s3_resource().Bucket(bucket_name)
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


async def upload_to_s3(file_path: str, user_id: uuid.UUID, filename: str) -> str:
    """Upload file to S3 and return object path"""

    bucket_name = "treme-s3-demo-bucket-36e710ab-c1be-4653-9d80-3c9cae24a71e"
    bucket = s3_resource()

    object_key = f"{user_id}/{filename}.zip"

    try:
        await asyncio.to_thread(
            bucket.meta.client.upload_file,
            Filename=file_path,
            Bucket=bucket_name,
            Key=object_key
        )
        logger.info("File uploaded to S3 successfully",
                    extra={
                        "user_id": user_id,
                        "s3_bucket": bucket_name,
                        "s3_key": object_key
                    })
        return f"s3://{bucket_name}/{object_key}"

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


async def process_file_upload(
    file: UploadFile,
    user_id: uuid.UUID,
    new_file_id: uuid.UUID,
    encryption_key: str,
    chunk_size: int = 1024 * 1024
) -> None:
    """
    Process file upload with encryption and S3 storage
    Returns S3 object path if successful
    """
    s3_path = None

    async with Session() as db:
        file_obj = await FilesModel.find_by_id(new_file_id, db)
        await file_obj.add_status("processing", db)

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = await save_uploaded_file(file, tmp_dir)

            zip_path = await encrypt_file(file_path, tmp_dir, str(new_file_id), encryption_key)

            s3_path = await upload_to_s3(
                file_path=zip_path,
                user_id=user_id,
                filename=str(new_file_id)
            )

            logger.info("File processing completed successfully",
                        extra={
                            "user_id": user_id,
                            "original_filename": file.filename,
                            "s3_path": s3_path
                        })

    except Exception as e:
        logger.error("File processing failed",
                     exc_info=True,
                     extra={
                         "user_id": user_id,
                         "original_filename": file.filename,
                         "error": str(e)
                     })

    async with Session() as db:
        file_obj = await FilesModel.find_by_id(new_file_id, db)

        if not s3_path:
            await file_obj.add_status("failed", db)
            return

        await file_obj.add_status("completed", db)
        file_obj.path = s3_path
        await db.commit()


async def process_file_download(file_id: uuid.UUID, tmp_dir: str, encryption_key: str):

    file_obj = FilesModel()
    async with Session() as db:
        file_obj = await FilesModel.find_by_id(file_id, db)

    zip_path = await download_from_s3(s3_key=file_obj.path, dir=tmp_dir)

    if not zip_path:
        return

    decrypt_zip(zip_path, tmp_dir, encryption_key)
    path = os.path.join(tmp_dir, file_obj.filename)
    return path
