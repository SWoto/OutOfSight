from enum import Enum
from typing import Dict, List, Optional
from pydantic import UUID4
from sqlalchemy import UUID, Column, String, Numeric, ForeignKey, and_, desc, or_, select
from sqlalchemy.orm import relationship, mapped_column
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Self

from app.models.base import BaseModel


class FileStatus(Enum):
    RECEIVED = {"name": "received",
                "description": "File has been received by the server."}
    UPLOADING = {"name": "uploading",
                 "description": "File is being uploaded to S3."}
    UPLOADED = {"name": "uploaded",
                "description": "File was successfully uploaded to S3."}
    PROCESSED = {"name": "processed",
                 "description": "File was processed through a lambda function in AWS."}
    FAILED = {"name": "failed", "description": "Failed to upload file to S3."}
    DELETED = {"name": "deleted", "description": "File was deleted from S3."}


class FilesModel(BaseModel):
    __tablename__ = "files"

    filename = Column(String(256), nullable=False)
    path = Column(String(256))
    filetype = Column(String(15))
    size_kB = Column(Numeric(precision=10, scale=2))

    user_id = mapped_column(ForeignKey("users.id"),
                            unique=False, nullable=False)
    user = relationship("UsersModel", back_populates="files", lazy='selectin')

    status_history = relationship(
        "FileStatusHistoryModel", back_populates="file", lazy='selectin')

    @hybrid_property
    def last_status(self) -> Optional[str]:
        if not self.status_history:
            return None

        last_status_history = max(
            self.status_history,
            key=lambda x: x.created_on,
            default=None
        )
        return last_status_history.status.name if last_status_history else None

    def __init__(self, *args, **kwargs):
        super(FilesModel, self).__init__(*args, **kwargs)

    @classmethod
    async def find_by_id_removing_deleted_or_failed(cls, id: UUID4, db: AsyncSession, remove_deleted: bool = True, remove_failed: bool = True) -> Self | None:
        if remove_deleted and remove_failed:
            query = (
                select(cls)
                .join(FileStatusHistoryModel, FileStatusHistoryModel.file_id == cls.id)
                .join(FileStatusModel, FileStatusHistoryModel.status_id == FileStatusModel.id)
                .filter(and_(cls.id == id, or_(FileStatusModel.name == "deleted", FileStatusModel.name == "failed")))
            )
        elif remove_deleted:
            query = (
                select(cls)
                .join(FileStatusHistoryModel, FileStatusHistoryModel.file_id == cls.id)
                .join(FileStatusModel, FileStatusHistoryModel.status_id == FileStatusModel.id)
                .filter(and_(cls.id == id, FileStatusModel.name == "deleted"))
            )
        elif remove_failed:
            query = (
                select(cls)
                .join(FileStatusHistoryModel, FileStatusHistoryModel.file_id == cls.id)
                .join(FileStatusModel, FileStatusHistoryModel.status_id == FileStatusModel.id)
                .filter(and_(cls.id == id, FileStatusModel.name == "failed"))
            )
        else:
            return await cls.find_by_id(id, db)

        result = await db.execute(query)
        return result.scalars().all()

    @classmethod
    async def find_by_user_id(cls, user_id: UUID, db: AsyncSession, include_deleted=True) -> List[Self] | None:
        if not include_deleted:
            query = (
                select(cls)
                .join(FileStatusHistoryModel, FileStatusHistoryModel.file_id == cls.id)
                .join(FileStatusModel, FileStatusHistoryModel.status_id == FileStatusModel.id)
                .filter(and_(cls.user_id == user_id, FileStatusModel.name == "deleted"))
            )
        else:
            query = select(cls).filter_by(user_id=user_id)

        result = await db.execute(query)
        return result.scalars().all()

    async def add_status(self, status: FileStatus, db: AsyncSession):
        status_obj = await FileStatusModel().find_by_name(status.value['name'], db)
        if not status_obj:
            return

        file_status_history = await FileStatusHistoryModel().find_by_fileid_and_statusid(self.id, status_obj.id, db)
        if file_status_history:
            return file_status_history

        status_history_obj = FileStatusHistoryModel(
            file_id=self.id, status_id=status_obj.id)
        db.add(status_history_obj)
        await db.commit()
        return status_history_obj


class FileStatusModel(BaseModel):
    __tablename__ = "files_status"

    name = Column(String(60), nullable=False, unique=True)
    description = Column(String(256))

    def __init__(self, *args, **kwargs):
        super(FileStatusModel, self).__init__(*args, **kwargs)
        if kwargs.get('name'):
            self.name = kwargs['name'].lower()

    @classmethod
    async def find_by_name(cls, name: str, db: AsyncSession) -> Self | None:
        query = select(cls).filter_by(name=name)
        result = await db.execute(query)
        return result.scalars().unique().one_or_none()

    @classmethod
    async def initialize_default(cls, db: AsyncSession, statuses: List[Dict]):
        if statuses:
            for status_data in statuses:
                status = await cls.find_by_name(status_data["name"], db)
                if not status:
                    db.add(cls(**status_data))
            await db.commit()


class FileStatusHistoryModel(BaseModel):
    __tablename__ = "files_status_history"

    file_id = mapped_column(ForeignKey("files.id"),
                            unique=False, nullable=False)
    status_id = mapped_column(ForeignKey("files_status.id"),
                              unique=False, nullable=False)

    file = relationship(
        "FilesModel", back_populates="status_history", lazy='selectin')
    status = relationship("FileStatusModel", lazy='selectin')

    def __init__(self, *args, **kwargs):
        super(FileStatusHistoryModel, self).__init__(*args, **kwargs)

    @classmethod
    async def find_by_fileid_and_statusid(cls, file_id: UUID, status_id: UUID, db: AsyncSession) -> Self | None:
        query = select(cls).filter_by(file_id=file_id, status_id=status_id)
        result = await db.execute(query)
        return result.scalars().unique().one_or_none()
