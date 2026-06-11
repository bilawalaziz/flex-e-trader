from contextlib import asynccontextmanager

from fastapi import FastAPI
from app.consumers.broker import broker
from app.core.config import settings
from app.consumers.price_consumer import router as price_router
from app.consumers.broker_queue import declare_delay_queue

broker.include_router(price_router)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await broker.start()
    await declare_delay_queue(broker)
    yield
    await broker.stop()


app = FastAPI(title=settings.app_title, version=settings.app_version, lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.app_title}
