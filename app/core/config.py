from functools import lru_cache
import os

from pydantic_settings import BaseSettings
from pydantic import ConfigDict, Field


class Settings(BaseSettings):
    database_url: str = Field(
        "postgresql+asyncpg://flexetrader:flexetrader@localhost:5432/flexetrader",
        alias="DATABASE_URL",
    )
    rabbitmq_url: str = Field(
        "amqp://guest:guest@localhost:5672/", alias="RABBITMQ_URL"
    )
    redis_url: str = Field("redis://localhost:6379/0", alias="REDIS_URL")
    app_host: str = Field("0.0.0.0", alias="APP_HOST")
    app_port: int = Field(8000, alias="APP_PORT")
    app_title: str = Field("Flex-energy-Trader", alias="APP_TITLE")
    app_version: str = Field("0.1.0", alias="APP_VERSION")

    prefetch_count: int = Field(10, alias="PREFETCH_COUNT")
    max_retries: int = Field(3, alias="MAX_RETRIES")

    # Dead Letter configuration
    dlx_exchange: str = Field("prices.dlx", alias="DLX_EXCHANGE")
    delay_exchange: str = Field("prices.delay", alias="DELAY_EXCHANGE")
    main_exchange: str = Field("prices", alias="MAIN_EXCHANGE")
    main_queue: str = Field("price-queue", alias="MAIN_QUEUE")
    delay_queue: str = Field("price-delay-queue", alias="DELAY_QUEUE")
    queue_msg_ttl: int = Field(604800000, alias="QUEUE_MSG_TTL")  # 7 days
    upsert_batch_size: int = Field(100, alias="UPSERT_BATCH_SIZE")
    interval_mins: int = Field(1, alias="INTERVAL_MINS")

    model_config = ConfigDict(
        env_file=os.getenv("ENV_FILE", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
