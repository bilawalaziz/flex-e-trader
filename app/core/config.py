from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    database_url: str = (
        "postgresql+asyncpg://flexetrader:flexetrader@localhost:5432/flexetrader"
    )
    rabbitmq_url: str = Field("amqp://guest:guest@localhost:5672/", env="RABBITMQ_URL")
    redis_url: str = Field("redis://localhost:6379/0", env="REDIS_URL")
    app_host: str = Field("0.0.0.0", env="APP_HOST")
    app_port: int = Field(8000, env="APP_PORT")
    app_title: str = Field("Flex-energy-Trader", env="APP_TITLE")
    app_version: str = Field("0.1.0", env="APP_VERSION")

    prefetch_count: int = Field(10, env="PREFETCH_COUNT")
    max_retries: int = Field(3, env="MAX_RETRIES")

    # Dead Letter configuration
    dlx_exchange: str = Field("prices.dlx", env="DLX_EXCHANGE")
    delay_exchange: str = Field("prices.delay", env="DELAY_EXCHANGE")
    main_exchange: str = Field("prices", env="MAIN_EXCHANGE")
    main_queue: str = Field("price-queue", env="MAIN_QUEUE")
    delay_queue: str = Field("price-delay-queue", env="DELAY_QUEUE")
    queue_msg_ttl: int = Field(604800000, env="QUEUE_MSG_TTL")  # 7 days
    upsert_batch_size: int = Field(100, env="UPSERT_BATCH_SIZE")
    interval_mins: int = Field(1, env="INTERVAL_MINS")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
