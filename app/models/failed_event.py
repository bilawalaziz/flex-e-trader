from sqlalchemy import Column, Integer, DateTime, JSON, String
from datetime import datetime

from app.models.base import Base


class FailedEvent(Base):
    __tablename__ = "failed_events"
    id = Column(Integer, primary_key=True)
    body = Column(JSON, nullable=False)
    headers = Column(JSON)
    fail_reason = Column(String)
    received_at = Column(DateTime(timezone=True), default=datetime.now)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
