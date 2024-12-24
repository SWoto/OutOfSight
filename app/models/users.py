from sqlalchemy import Column, String, Boolean, DateTime, select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.models.base import BaseModel


class UserModel(BaseModel):
    __tablename__ = "users"

    nickname = Column(String(256), nullable=False)
    email = Column(String(256), unique=True, index=True)
    password = Column(String(256), nullable=False)
    confirmed = Column(Boolean, default=False)
    confirmed_on = Column(DateTime, nullable=True)

    def __init__(self, *args, **kwargs):
        super(UserModel, self).__init__(*args, **kwargs)

    @classmethod
    async def find_by_email(cls, email: str, db: AsyncSession) -> Optional["UserModel"]:
        query = select(cls).filter_by(email=email)
        result = await db.execute(query)
        return result.scalars().unique().one_or_none()
