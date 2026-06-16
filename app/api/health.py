from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from app.core.config import settings
from app.core.database import get_session

router = APIRouter(prefix="/health")


class HealthResponse(BaseModel):
    status: str
    version: str
    service: str


@router.get("", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy", version=settings.app_version, service=settings.app_title
    )


@router.get("/ready")
async def readiness_check(response: Response, db: AsyncSession = Depends(get_session)):
    checks = {}

    # Database check
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"

    # Redis check
    try:
        redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        is_ok = await redis_client.ping()
        if is_ok:
            checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"

    all_ok = all(v == "ok" for v in checks.values())
    response.status_code = (
        status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    )

    return {"status": "ready" if all_ok else "not_ready", "checks": checks}
