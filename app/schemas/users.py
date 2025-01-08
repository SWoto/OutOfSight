import logging
from pydantic import BaseModel, EmailStr, field_validator, UUID4, model_validator, SecretStr, AfterValidator
from typing import Union, Optional, Annotated

logger = logging.getLogger(__name__)

class EmailNoneEmptyAllowedStr(EmailStr):
    @classmethod
    def _validate(cls, value: Union[str, None]) -> Union[str, None]:
        if not value or value == "":
            return value
        return super()._validate(value)
    

class ValidatedSecretStr(SecretStr):
    # Password policy constants
    SPECIAL_CHARS: set[str] = {"$", "@", "#", "%", "!", "^", "&", "*", "(", ")", "-", "_", "+", "=", "{", "}", "[", "]"}
    MIN_LENGTH: int = 8
    MAX_LENGTH: int = 99
    INCLUDES_SPECIAL_CHARS: bool = True
    INCLUDES_NUMBERS: bool = True
    INCLUDES_LOWERCASE: bool = True
    INCLUDES_UPPERCASE: bool = True

    @classmethod
    def validate(cls, value: SecretStr) -> SecretStr:
        if not isinstance(value.get_secret_value(), str):
            raise TypeError("A string is required")
        
        # Validate length
        if not cls.MIN_LENGTH <= len(value.get_secret_value()) <= cls.MAX_LENGTH:
            raise ValueError(f"Password length should be between {cls.MIN_LENGTH} and {cls.MAX_LENGTH} characters")

        # Validate inclusion of at least one number
        if cls.INCLUDES_NUMBERS and not any(char.isdigit() for char in value.get_secret_value()):
            raise ValueError("Password must include at least one number")

        # Validate inclusion of at least one uppercase letter
        if cls.INCLUDES_UPPERCASE and not any(char.isupper() for char in value.get_secret_value()):
            raise ValueError("Password must include at least one uppercase letter")

        # Validate inclusion of at least one lowercase letter
        if cls.INCLUDES_LOWERCASE and not any(char.islower() for char in value.get_secret_value()):
            raise ValueError("Password must include at least one lowercase letter")

        # Validate inclusion of at least one special character
        if cls.INCLUDES_SPECIAL_CHARS and not any(char in cls.SPECIAL_CHARS for char in value.get_secret_value()):
            raise ValueError(f"Password must include at least one special character from {cls.SPECIAL_CHARS}")

        return value

ValidatePassword = Annotated[SecretStr, AfterValidator(ValidatedSecretStr.validate)] 

class UserPassword(BaseModel):
    password: ValidatePassword

class PlainUserSchema(BaseModel):
    nickname: str
    email: EmailStr
    
    @field_validator("nickname", mode='after')
    def transform_str_to_first_caps(cls, value):
        return value.title()

class PostPutUserSchema(UserPassword, PlainUserSchema):
    password: ValidatePassword


class ReturnUserSchema(PlainUserSchema):
    id: UUID4
    confirmed: bool

class PatchUserSchema(BaseModel):
    nickname: str | None = None
    password: ValidatePassword | None = None
    email: EmailNoneEmptyAllowedStr = None

    @field_validator("nickname", mode='after')
    def transform_str_to_first_caps(cls, value):
        return value.title()

    @model_validator(mode='before')
    def check_at_least_one(cls, values): 
        if sum([bool(v) for v in values.values()]) == 0:
            raise ValueError('At least one field must be provided.')
        return values
    
class LoginUserSchema(BaseModel):
    email: EmailStr
    password: ValidatePassword