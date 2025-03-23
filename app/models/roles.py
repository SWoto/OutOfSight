from sqlalchemy import Column, String, select, Integer
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, List, Self

from sqlalchemy.orm import relationship, validates

from app.models.base import BaseModel
from app.core.configs import settings


class RolesModel(BaseModel):
    __tablename__ = "roles"

    # From 99=superuser to 0=owner of itself (with restrictions)
    authority: int = Column(Integer, unique=True)
    name: str = Column(String(256), nullable=False)

    users = relationship("UsersModel", back_populates="role", lazy="selectin")

    def __init__(self, *args, **kwargs):
        super(RolesModel, self).__init__(*args, **kwargs)

    @validates('authority')
    def validate_age(self, key, value):
        if not settings.MIN_ROLE <= value <= settings.MAX_ROLE:
            raise ValueError(f'Invalid role authority: {value}')
        return value

    @classmethod
    async def find_by_authority(cls, authority: int, db: AsyncSession) -> Self | None:
        query = select(cls).filter_by(authority=authority)
        result = await db.execute(query)
        return result.scalars().unique().one_or_none()

    @classmethod
    async def initialize_default(cls, db: AsyncSession, roles: List[Dict]):
        if roles:
            for role_data in roles:
                existing_role = await cls.find_by_authority(role_data["authority"], db)
                if not existing_role:
                    db.add(cls(**role_data))
            await db.commit()
