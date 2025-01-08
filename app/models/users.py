from sqlalchemy import Column, String, Boolean, DateTime, select, LargeBinary
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime

from sqlalchemy.orm import relationship

from app.core.security import get_hashed_password
from app.models.base import BaseModel


class UsersModel(BaseModel):
    __tablename__ = "users"

    nickname: str = Column(String(256), nullable=False)
    email: str = Column(String(256), unique=True, index=True)
    password: bytes = Column(LargeBinary, nullable=False)
    confirmed: bool = Column(Boolean, default=False)
    confirmed_on: datetime = Column(DateTime, nullable=True)

    files = relationship("FilesModel", back_populates="user",
                         cascade="all, delete-orphan", lazy='selectin')

    def __init__(self, *args, **kwargs):
        super(UsersModel, self).__init__(*args, **kwargs)
        self.password = get_hashed_password(kwargs['password'])

    @classmethod
    async def find_by_email(cls, email: str, db: AsyncSession) -> Optional["UserModel"]:
        query = select(cls).filter_by(email=email)
        result = await db.execute(query)
        return result.scalars().unique().one_or_none()


    def get_confirmed(self) -> bool:
        return self.confirmed
    
    def confirm_register(self) -> None:
        self.confirmed = True
        self.confirmed_on = datetime.now()