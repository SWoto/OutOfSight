from sqlalchemy import Column, String, Numeric, ForeignKey
from sqlalchemy.orm import relationship, mapped_column

from app.models.base import BaseModel


class FileModel(BaseModel):
    __tablenames__ = "files"

    filename = Column(String(256), nullable=False)
    path = Column(String(256), nullable=False)
    filetype = Column(String(15), nullable=False)
    size = Column(Numeric(precision=10, scale=2))

    user_id = mapped_column(ForeignKey("users.id"),
                            unique=False, nullable=False)
    user = relationship("UserModel", back_populates="files", lazy='selectin')

    def __init__(self, *args, **kwargs):
        super(FileModel, self).__init__(*args, **kwargs)
