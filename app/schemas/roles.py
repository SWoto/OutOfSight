from pydantic import BaseModel, UUID4, field_validator

from app.core.configs import settings


class PlainRoleSchema(BaseModel):
    name: str

    @field_validator("name", mode='after')
    def transform_str_to_first_caps(cls, value):
        return value.title()


class ReturnRoleSchema(PlainRoleSchema):
    id: UUID4


class RoleWithAuthoritySchema(PlainRoleSchema):
    authority: int

    @field_validator("authority", mode='after')
    def check_between_range(cls, value):
        if not settings.MIN_ROLE <= value <= settings.MAX_ROLE:
            raise ValueError(
                f"Authority must be between min:{settings.MIN_ROLE} and max:{settings.MAX_ROLE}")

        return value


class ReturnRoleWithAuthoritySchema(RoleWithAuthoritySchema):
    id: UUID4
