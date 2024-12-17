from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

from functools import lru_cache


class BaseConfig(BaseSettings):
    ENV_STATE: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file="app/core/.env", case_sensitive=True, extra="ignore")


class GlobalConfig(BaseConfig):
    API_V1_STR: str = "/api/v1"

    def __init__(self):
        super(GlobalConfig, self).__init__()


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
