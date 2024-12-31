import logging
from pydantic import BaseModel, EmailStr, field_validator, UUID4, model_validator
from typing import Union

logger = logging.getLogger(__name__)

class EmailNoneEmptyAllowedStr(EmailStr):
    @classmethod
    def _validate(cls, value: Union[str, None]) -> Union[str, None]:
        if not value or value == "":
            return value
        return super()._validate(value)

class PlainUserSchema(BaseModel):
    nickname: str
    email: EmailStr
    
    @field_validator("nickname", mode='after')
    def transform_str_to_first_caps(cls, value):
        return value.title()

class PostPutUserSchema(PlainUserSchema):
    password: str


class ReturnUserSchema(PlainUserSchema):
    id: UUID4
    confirmed: bool

class PatchUserSchema(BaseModel):
    nickname: str | None = None
    password: str | None = None
    email: EmailNoneEmptyAllowedStr = None

    @field_validator("nickname", mode='after')
    def transform_str_to_first_caps(cls, value):
        return value.title()

    @model_validator(mode='before')
    def check_at_least_one(cls, values): 
        if sum([bool(v) for v in values.values()]) == 0:
            raise ValueError('At least one field must be provided.')
        return values
    