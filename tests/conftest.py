import asyncio
from datetime import datetime, timedelta, timezone
import os
import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text

from app.schemas.events import PriceTick

os.environ["ENV"] = "dev"

from dotenv import load_dotenv

load_dotenv(".env.dev", override=True)

from app.core.database import get_session  # noqa: E402
from app.main import app  # noqa: E402

TEST_DATABASE_URL = os.getenv("DATABASE_URL")
if TEST_DATABASE_URL is None:
    raise RuntimeError("DATABASE_URL not set in .env.test")


def _run_alembic_migrations():
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")


async def _create_test_db():
    admin_url = TEST_DATABASE_URL.rsplit("/", 1)[0] + "/postgres"
    admin_engine = create_async_engine(
        admin_url, echo=False, isolation_level="AUTOCOMMIT"
    )
    async with admin_engine.connect() as conn:
        db_name = TEST_DATABASE_URL.rsplit("/", 1)[-1]
        result = await conn.execute(
            text(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'")
        )
        if not result.fetchone():
            await conn.execute(text(f"CREATE DATABASE {db_name}"))
    await admin_engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def test_db_setup():
    """Create the test database and run migrations once per session."""
    asyncio.run(_create_test_db())
    _run_alembic_migrations()
    yield


engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="function")
async def db_session(test_db_setup):
    async with TestSession() as session:
        async with session.begin() as trans:
            yield session
            await trans.rollback()


@pytest.fixture(scope="module")
async def async_client(test_db_setup):
    app.dependency_overrides[get_session] = lambda: TestSession()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def future_price_tick() -> PriceTick:
    now = datetime.now(timezone.utc)
    return PriceTick(
        product="DE-AT-2024",
        timestamp=now + timedelta(hours=1),
        buy_price_eur_mwh=100,
        sell_price_eur_mwh=110,
        volume_mw=200,
        event_time=now,
        message_id="msg-1",
    )
