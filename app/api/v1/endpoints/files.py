import io
import os
import logging
import copy
from typing import Annotated, List
import uuid
from fastapi import Form, APIRouter, status, Depends, HTTPException, BackgroundTasks, File, UploadFile, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask

from app.core.database import get_db_session
from app.core.files import get_s3_handler, S3Handler
from app.models import FilesModel, UsersModel
from app.core.auth import get_current_user
from app.schemas import ReturnFileSchema, ReturnNestedFileSchema, ReturnNestedHistoricalFileSchema


router = APIRouter()

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


async def check_file_and_user(file_id, user_id, db) -> FilesModel:
    obj = await FilesModel().find_by_id(file_id, db)
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
    new_file = FilesModel(filename=file.filename, filetype=file_extension,
                          size_kB=file.size/1024, user_id=current_user.id)
    db.add(new_file)
    await db.commit()

    await new_file.add_status("uploaded", db)
    await db.refresh(new_file)

    # Previously was used deepcopy to send the file to the background task
    # as a way to do all the processing after returning the request.
    # However, for larger files, around 800kB or more, it starts to get
    # really slowish and close to 1MB or more, is fails and throw errors.
    # previous: copy.deepcopy(file)
    await s3_handler.create_upload_file_handler(new_file, file)

    # TODO: Add task for message brokers
    background_tasks.add_task(
        s3_handler.process_file_upload,
    )

    return new_file


@router.get('/download/{id}', status_code=status.HTTP_200_OK, tags=["Files"], summary="Download target file and decrypt it", description="Get target file from S3 Bucket, decrypt it and sends it raw to the user")
async def download_file(id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db_session)], current_user: Annotated[UsersModel, Depends(get_current_user)], s3_handler: S3Handler = Depends(get_s3_handler)):

    obj = await check_file_and_user(id, current_user.id, db)

    await s3_handler.create_download_file_handler(obj)
    file_path = await s3_handler.process_file_download()

    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to download file. Try again later.")

    with open(file_path, "rb") as file:
        file_data = file.read()

    file_like = io.BytesIO(file_data)

    # Uses StreamingResponse with io.BytesIO because tempfile.TemporaryDirectory will
    # close the context before FileResponse is sent, thus having to save the file
    # without using TemporaryDirectory, which is not good. As a way to solve this,
    # the file is loaded from the TemporaryDirectory into memory and them sent to the user.
    return StreamingResponse(
        file_like,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={obj.filename}"},
        background=BackgroundTask(file_like.close)
    )


@router.get('/{id}', response_model=ReturnFileSchema, status_code=status.HTTP_200_OK, tags=["Files"], summary="Return file information", description="Check if user is file owner and return the file information.")
async def get_file_info(id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db_session)], current_user: Annotated[UsersModel, Depends(get_current_user)]):

    return await check_file_and_user(id, current_user.id, db)


@router.get('/status/{id}', response_model=ReturnNestedHistoricalFileSchema, status_code=status.HTTP_200_OK, tags=["Files"], summary="Return file information", description="Check if user is file owner and return the file information.")
async def get_file_info_with_status(id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db_session)], current_user: Annotated[UsersModel, Depends(get_current_user)]):

    return await check_file_and_user(id, current_user.id, db)


@router.get('/', response_model=List[ReturnFileSchema], tags=["Files"], summary="Download target file and decrypt it", description="Get target file from S3 Bucket, decrypt it and sends it raw to the user")
async def get_all_files_info(db: Annotated[AsyncSession, Depends(get_db_session)], current_user: Annotated[UsersModel, Depends(get_current_user)]):
    return await FilesModel().find_by_user_id(current_user.id, db)


@router.delete('/{id}')
async def delete_file(id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db_session)], current_user: Annotated[UsersModel, Depends(get_current_user)], s3_handler: S3Handler = Depends(get_s3_handler)):
    obj = await check_file_and_user(id, current_user.id, db)

    if not s3_handler.delete_from_s3(obj.path):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete file. Try again later.")
