from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Cloud SQL connection and pool settings."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_host: str
    database_name: str
    database_username: str
    database_password: SecretStr
    database_port: int = 5432

    # Pool settings for Cloud SQL Postgres
    database_pool_size: int = 5
    database_max_overflow: int = 5
    database_pool_recycle_seconds: int = 1800


@lru_cache
def get_settings() -> Settings:
    return Settings()
