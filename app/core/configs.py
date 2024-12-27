from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, Any

from sqlalchemy.orm import declarative_base

from functools import lru_cache


class BaseConfig(BaseSettings):
    ENV_STATE: Optional[str] = None

    """Loads the dotenv file. Including this is necessary to get
    pydantic to load a .env file."""
    model_config = SettingsConfigDict(
        env_file="app/core/.env", case_sensitive=True, extra="ignore")


class GlobalConfig(BaseConfig):
    API_V1_STR: str = "/api/v1"

    DATABASE_URL: Optional[str] = None
    POSTGRES_USER: Optional[str] = None
    POSTGRES_PASSWORD: Optional[str] = None
    POSTGRES_DB: Optional[str] = None
    POSTGRES_PORT: Optional[int] = None
    POSTGRES_HOST: Optional[str] = None

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
    configs = {"def": DevConfig, "prod": ProdConfig, "test": TestConfig}
    return configs[env_state]()


settings = get_config(BaseConfig().ENV_STATE)
