import logging
import os

from celery import Celery
from celery.signals import worker_init, worker_process_shutdown
from prometheus_client import multiprocess, start_http_server

from app.core.config import settings
from app.core.metrics import MULTIPROC_ENV, build_registry, reset_multiproc_dir

logger = logging.getLogger(__name__)


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


@worker_init.connect
def start_metrics_exporter(**_):
    """Serve /metrics from the worker's parent process.

    The optimisation task runs in a forked child, so its counters live in that
    child's memory and an HTTP server here would report zeros. Setting
    PROMETHEUS_MULTIPROC_DIR makes the children write to shared mmap files
    that this process sums on scrape — that is the whole reason the directory
    exists, and without it these metrics would look permanently idle.
    """
    if not settings.metrics_enabled:
        return
    if not os.environ.get(MULTIPROC_ENV):
        logger.warning(
            "%s is not set: worker metrics will be per-process and incomplete",
            MULTIPROC_ENV,
        )
    reset_multiproc_dir()
    start_http_server(settings.metrics_port, registry=build_registry())
    logger.info("metrics exporter listening | port=%s", settings.metrics_port)


@worker_process_shutdown.connect
def clean_up_worker_metrics(pid=None, **_):
    """Retire a dead child's gauges; its counters stay in the totals."""
    if os.environ.get(MULTIPROC_ENV) and pid is not None:
        multiprocess.mark_process_dead(pid)


import app.tasks  # noqa: F401, E402
