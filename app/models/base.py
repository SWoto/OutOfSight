from sqlalchemy import Column, Sequence, Integer, DateTime, func, select, inspect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from app.core.configs import settings


class BaseModel(settings.DBBaseModel):
    __abstract__ = True

    id = Column(Integer, Sequence('user_id_seq',
                start=1, increment=1), primary_key=True)
    created_on = Column(DateTime, default=func.now(), nullable=False)
    modified_on = Column(DateTime, default=func.now(),
                         onupdate=func.now(), nullable=False)

    def __init__(self, *args, **kwargs):
        super(BaseModel, self).__init__(*args, **kwargs)

    def __repr__(self):
        attrs = ", ".join(
            f"{key}={getattr(self, key)!r}" for key in self.__table__.columns.keys())
        return f"<{self.__class__.__name__}({attrs})>"

    async def save_to_db(self, db: AsyncSession):
        db.add(self)
        try:
            await db.commit()
        except SQLAlchemyError as e:
            await db.rollback()
            raise RuntimeError(
                f"Failed to save {self.__class__.__name__} to the database.") from e

    async def delete_from_db(self, db: AsyncSession):
        try:
            await db.delete(self)
            await db.commit()
        except SQLAlchemyError as e:
            await db.rollback()
            raise RuntimeError(
                f"Failed to delete {self.__class__.__name__} to the database.") from e

    @classmethod
    async def find_by_id(cls, id: int, db: AsyncSession):
        query = select(cls).filter_by(id=id)
        result = await db.execute(query)
        return result.scalars().unique().one_or_none()