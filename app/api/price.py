from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_session
from app.schemas import PriceOutputList
from app.repositories.price_repo import get_latest_prices_df

router = APIRouter(prefix="/prices")


@router.get("")
async def get_prices(session: AsyncSession = Depends(get_session)) -> PriceOutputList:
    """Return the latest price for each delivery slot"""
    df = await get_latest_prices_df(session)
    return df.to_dict(orient="records")
