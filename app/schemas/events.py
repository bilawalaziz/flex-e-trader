from pydantic import BaseModel, Field
from datetime import datetime


class PriceTick(BaseModel):
    product: str = Field(..., pattern=r"DE-AT-\d{4}")  # example: DE-AT-1700
    timestamp: datetime
    buy_price_eur_mwh: float
    sell_price_eur_mwh: float
    volume_mw: float
    message_id: str | None = None
