import asyncio
from app.celery_app import celery_app
from app.services.scheduler import run_optimisation


@celery_app.task(name="app.tasks.optimisation_task")
def run_optimisation_task():
    """Celery task wrapper that executes the async optimisation cycle"""
    return asyncio.run(run_optimisation())
