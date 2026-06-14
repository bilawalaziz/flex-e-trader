from sqlalchemy.ext.asyncio import AsyncSession
from app.models.failed_event import FailedEvent
from app.schemas.events import FailedEventCreate


async def add_failed_event(session: AsyncSession, event: FailedEventCreate) -> bool:
    db_event = FailedEvent(
        body=event.body,
        headers=event.headers,
        fail_reason=event.fail_reason,
    )
    session.add(db_event)
    return True
