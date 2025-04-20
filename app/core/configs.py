import secrets
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, Any
from sqlalchemy.orm import declarative_base
from functools import lru_cache


class BaseConfig(BaseSettings):
    ENV_STATE: Optional[str] = None
    ALGORITHM: str = "HS256"
    TIMEZONE_OFFSET: int = -3
    VERSION: str = "unknown"

    MIN_ROLE: int = 0
    MAX_ROLE: int = 99

    S3_BUCKET_NAME: Optional[str] = None

    """Loads the dotenv file. Including this is necessary to get
    pydantic to load a .env file."""
    model_config = SettingsConfigDict(
        env_file="app/core/.env", case_sensitive=True, extra="ignore")


class GlobalConfig(BaseConfig):
    API_V1_STR: str = "/api/v1"

    JWT_SECRET: str = secrets.token_hex(64)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60*24*1  # 1 day
    CONFIRMATION_TOKEN_EXPIRE_MINUTES: int = 30  # 30 minutes

    ADMIN_DEFAULT_PASSWORD: Optional[str] = None
    ADMIN_DEFAULT_EMAIL: Optional[str] = None

    SQLALCHEMY_ECHO: Optional[bool] = False

    DATABASE_URL: Optional[str] = None
    POSTGRES_USER: Optional[str] = None
    POSTGRES_PASSWORD: Optional[str] = None
    POSTGRES_DB: Optional[str] = None
    POSTGRES_PORT: Optional[int] = None
    POSTGRES_HOST: Optional[str] = None

    REDIS_HOST: Optional[str] = None
    REDIS_PORT: Optional[str] = None

    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: Optional[str] = None
    AWS_SQS_CONFIRMATION_EMAIL_URL: Optional[str] = None

    DBBaseModel: Any = declarative_base()

    def __init__(self):
        super(GlobalConfig, self).__init__()
        self.DATABASE_URL = f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"


class DevConfig(GlobalConfig):
    model_config = SettingsConfigDict(env_prefix="DEV_")


class ProdConfig(GlobalConfig):
    model_config = SettingsConfigDict(env_prefix="PROD_")


class TestConfig(GlobalConfig):
    model_config = SettingsConfigDict(env_prefix="TEST_")


@lru_cache
def get_config(env_state: str):
    configs = {"dev": DevConfig, "prod": ProdConfig, "test": TestConfig}
    return configs[env_state]()


settings = get_config(BaseConfig().ENV_STATE)
