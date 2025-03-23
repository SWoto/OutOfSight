from sqlalchemy import Column, String, Boolean, DateTime, select, LargeBinary, ForeignKey
from sqlalchemy.orm import relationship, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, List, Self
from datetime import datetime

from app.core.configs import GlobalConfig
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

    role_id = mapped_column(ForeignKey("roles.id"),
                            unique=False, nullable=False)
    role = relationship("RolesModel", back_populates="users", lazy='selectin')

    def __init__(self, *args, **kwargs):
        super(UsersModel, self).__init__(*args, **kwargs)
        self.password = get_hashed_password(kwargs['password'])

    @classmethod
    async def find_by_email(cls, email: str, db: AsyncSession) -> Self | None:
        query = select(cls).filter_by(email=email)
        result = await db.execute(query)
        return result.scalars().unique().one_or_none()

    @classmethod
    async def initialize_default(cls, db: AsyncSession, users: List[Dict]):
        if users:
            for new_user in users:
                existing_user = await cls.find_by_email(new_user.get("email"), db)
                if not existing_user:
                    db.add(cls(**new_user))
            await db.commit()

    def get_confirmed(self) -> bool:
        return self.confirmed

    def confirm_register(self) -> None:
        self.confirmed = True
        self.confirmed_on = datetime.now()
