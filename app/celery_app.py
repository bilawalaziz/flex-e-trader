from celery import Celery
from app.core.config import settings


celery_app = Celery(
    "flexetrader",
    broker=settings.rabbitmq_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "run-optimisation-every-x-interval": {
            "task": "app.tasks.optimisation_task",
            "schedule": 60.0,
        },
        "publish-future-prices": {
            "task": "app.tasks.publish_test_prices",
            "schedule": 30.0,
        },
    },
)

import app.tasks  # noqa: F401, E402
