from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Postgres
    database_url: str = "postgresql+asyncpg://sidebet:sidebet@localhost:5432/sidebet"

    # Kafka
    kafka_bootstrap_servers: str = "localhost:29092"
    kafka_bets_topic: str = "bets"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # App
    app_name: str = "SideBet"
    debug: bool = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()
