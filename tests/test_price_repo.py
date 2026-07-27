import pytest
from app.repositories.price_repo import upsert_price, get_latest_prices_df


@pytest.mark.asyncio
async def test_upsert_and_latest_price(db_session, future_price_tick):
    await upsert_price(db_session, future_price_tick)
    df = await get_latest_prices_df(db_session)
    assert len(df) == 1
    assert df.iloc[0]["buy_price"] == 100
