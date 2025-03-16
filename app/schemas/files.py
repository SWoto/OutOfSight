from pydantic import BaseModel, UUID4, PositiveFloat
from typing import List

# Removed path. Used only internally and should not be returned to end-user


class PlainFileSchema(BaseModel):
    filename: str
    filetype: str
    size_kB: PositiveFloat


class ReturnFileSchema(PlainFileSchema):
    id: UUID4

# ---- File Status


class PlainFileStatusSchema(BaseModel):
    name: str
    description: str


class ReturnFileStatusSchema(PlainFileStatusSchema):
    id: UUID4


# ---- File Status History
class ReturnFileStatusHistorySchema(BaseModel):
    id: UUID4
    status: ReturnFileStatusSchema


# ---- Nested File Schema
class ReturnNestedFileSchema(ReturnFileSchema):
    status_history: ReturnFileStatusHistorySchema


class ReturnNestedHistoricalFileSchema(ReturnFileSchema):
    status_history: List[ReturnFileStatusHistorySchema]
