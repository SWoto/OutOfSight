from typing import List
from sqlalchemy import UUID, Column, String, Numeric, ForeignKey, select
from sqlalchemy.orm import relationship, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Self

from app.models.base import BaseModel


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

    def __init__(self, *args, **kwargs):
        super(FilesModel, self).__init__(*args, **kwargs)

    @classmethod
    async def find_by_user_id(cls, user_id: UUID, db: AsyncSession) -> List[Self] | None:
        query = select(cls).filter_by(user_id=user_id)
        result = await db.execute(query)
        return result.scalars().all()

    async def add_status(self, status_name, db: AsyncSession):
        status_obj = await FileStatusModel().find_by_name(status_name, db)
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
    async def initialize_default_statuses(cls, db: AsyncSession):
        default_statuses = [
            {"name": "uploaded", "description": "File has been uploaded to backend."},
            {"name": "processing",
                "description": "File is being zipped, encrypted and uploaded to S3."},
            {"name": "completed",
                "description": "zipped and encrypted file was successfully uploaded to S3."},
            {"name": "failed", "description": "Failed to process."},
        ]
        for status_data in default_statuses:
            status = await db.execute(select(cls).filter_by(name=status_data["name"]))
            if not status.scalar_one_or_none():
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
