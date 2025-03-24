import os
import logging
from typing import Annotated, List
import uuid
from fastapi import Form, APIRouter, status, Depends, HTTPException, BackgroundTasks, File, UploadFile, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.aws_handler import get_s3_handler, S3Handler, S3FileNotFoundError, S3DownloadError
from app.models import FilesModel, UsersModel
from app.core.auth import get_current_user
from app.models.files import FileStatus
from app.schemas import ReturnFileSchema, ReturnNestedHistoricalFileSchema


router = APIRouter()

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 100 * 1024 * 1024  # 10 MB


async def check_file_and_user(file_id, user_id, db, remove_deleted: bool = False, remove_failed: bool = False) -> FilesModel:
    obj = await FilesModel().find_by_id(file_id, db) if remove_deleted or remove_failed else await FilesModel().find_by_id_removing_deleted_or_failed(file_id, db, remove_deleted, remove_failed)

    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"File does not exists")

    if obj.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=f"Not allowed")

    return obj


@router.post('/', status_code=status.HTTP_202_ACCEPTED, response_model=ReturnNestedHistoricalFileSchema, tags=["Files"], summary="Upload any file and encrypt it", description="Upload any file for encrypt data backup.")
async def post_file(file: Annotated[UploadFile, File(...)], current_user: Annotated[UsersModel, Depends(get_current_user)], background_tasks: BackgroundTasks, db: Annotated[AsyncSession, Depends(get_db_session)], s3_handler: S3Handler = Depends(get_s3_handler)):

    if not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="File has not been received.")

    logger.info(
        f"Received file: {file.filename}, ({file.content_type}), {file.size} bytes")

    if file.size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds the maximum allowed size of {MAX_FILE_SIZE} bytes."
        )

    _, file_extension = os.path.splitext(file.filename)
    new_file_model = FilesModel(filename=file.filename, filetype=file_extension,
                                size_kB=file.size/1024, user_id=current_user.id)
    db.add(new_file_model)
    await db.commit()

    await new_file_model.add_status(FileStatus.RECEIVED, db)
    await db.refresh(new_file_model)

    await s3_handler.handle_file_upload(new_file_model.id, file)

    return new_file_model


@router.get('/download/{id}', status_code=status.HTTP_200_OK, tags=["Files"], summary="Download target file and decrypt it", description="Get target file from S3 Bucket, decrypt it and sends it raw to the user")
async def download_file(id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db_session)], current_user: Annotated[UsersModel, Depends(get_current_user)], s3_handler: S3Handler = Depends(get_s3_handler)):

    obj = await check_file_and_user(id, current_user.id, db, remove_deleted=True, remove_failed=True)

    try:
        return StreamingResponse(
            s3_handler.handle_file_download(obj.path),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f"attachment; filename={obj.filename}"},
        )
    except S3FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found in S3 server. Check file status.")
    except S3DownloadError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# TODO: Add query param to include or exclude deleted
@router.get('/{id}', response_model=ReturnFileSchema, status_code=status.HTTP_200_OK, tags=["Files"], summary="Return file information", description="Check if user is file owner and return the file information.")
async def get_file_info(id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db_session)], current_user: Annotated[UsersModel, Depends(get_current_user)], remove_failed: bool = False, remove_deleted: bool = False):

    return await check_file_and_user(id, current_user.id, db, remove_deleted, remove_failed)


# TODO: Add query param to include or exclude deleted
@router.get('/status/{id}', response_model=ReturnNestedHistoricalFileSchema, status_code=status.HTTP_200_OK, tags=["Files"], summary="Return file information", description="Check if user is file owner and return the file information.")
async def get_file_info_with_status(id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db_session)], current_user: Annotated[UsersModel, Depends(get_current_user)], remove_failed: bool = False, remove_deleted: bool = False):

    return await check_file_and_user(id, current_user.id, db, remove_deleted, remove_failed)


# TODO: Add query param to include or exclude deleted
@router.get('/', response_model=List[ReturnFileSchema], tags=["Files"], summary="Download target file and decrypt it", description="Get target file from S3 Bucket, decrypt it and sends it raw to the user")
async def get_all_files_info(db: Annotated[AsyncSession, Depends(get_db_session)], current_user: Annotated[UsersModel, Depends(get_current_user)], remove_failed: bool = False, remove_deleted: bool = False):
    return await FilesModel().find_by_id_removing_deleted_or_failed(current_user.id, db, remove_deleted, remove_failed)


# TODO: Handle failed when requested to delete
@router.delete('/{id}')
async def delete_file(id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db_session)], current_user: Annotated[UsersModel, Depends(get_current_user)], s3_handler: S3Handler = Depends(get_s3_handler)):
    obj = await check_file_and_user(id, current_user.id, db, remove_deleted=True, remove_failed=False)

    if obj.last_status == "failed":
        await obj.add_status(FileStatus.DELETED, db)
        return

    try:
        if not await s3_handler.delete_from_s3(obj.path, obj.id):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete file. Try again later.")
    except S3DownloadError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found in the S3 bucket.")
