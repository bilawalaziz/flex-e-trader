from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = (
        "postgresql+asyncpg://flexetrader:flexetrader@localhost:5432/flexetrader"
    )
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    redis_url: str = "redis://localhost:6379/0"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_title: str = "Flex-energy-Trader"
    app_version: str = "0.1.0"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
