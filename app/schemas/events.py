from pydantic import BaseModel, Field, RootModel
from typing import Any, List
from datetime import datetime


class PriceTick(BaseModel):
    product: str = Field(..., pattern=r"DE-AT-\d{4}")  # example: DE-AT-1700
    timestamp: datetime
    buy_price_eur_mwh: float
    sell_price_eur_mwh: float
    volume_mw: float
    message_id: str | None = None
    event_time: datetime


class FailedEventCreate(BaseModel):
    body: dict[str, Any] = Field(..., description="message body dict")
    headers: dict[str, Any] | None = Field(
        default=None, description="message headers dict"
    )
    fail_reason: str | None = Field(default=None, description="failure reason")


class PriceOutput(BaseModel):
    timestamp: datetime
    buy_price: float
    sell_price: float


class PriceOutputList(RootModel[List[PriceOutput]]):
    pass
