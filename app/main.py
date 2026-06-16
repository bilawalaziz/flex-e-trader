import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.consumers.broker import broker
from app.core.config import settings
from app.consumers.price_consumer import router as comsuer_price_router
from app.consumers.broker_queue import declare_delay_queue
from app.api.price import router as price_router
from app.api.schedule import router as schedule_router
from app.api.tracker import router as ws_router
from app.api.health import router as health_router
from app.services.ws_manager import manager

broker.include_router(comsuer_price_router)


@asynccontextmanager
async def lifespan(app: FastAPI):

    cache_listener = asyncio.create_task(manager.start_redis_listener())
    await broker.start()
    await declare_delay_queue(broker)
    yield
    await broker.stop()
    await cache_listener.cancel()


def create_app(lifespan=lifespan) -> FastAPI:
    app = FastAPI(
        title=settings.app_title,
        description="Power Optimizer Service",
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        root_path="/api/v1",
    )
    app.include_router(price_router)
    app.include_router(schedule_router)
    app.include_router(ws_router)
    app.include_router(health_router)
    return app


app = create_app()
