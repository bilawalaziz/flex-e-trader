import pandas as pd
from app.services.optimisation import compute_battery_schedule


def test_schedule_shape(battery_spec):
    prices = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=4, freq="15min"),
            "buy_price": [50, 60, 40, 70],
            "sell_price": [55, 65, 45, 75],
        }
    )
    result = compute_battery_schedule(prices, battery_spec, delta_t=0.25)
    assert len(result) == 4
    assert list(result.columns) == ["timestamp", "power_mw", "soc_kwh"]
    assert result["soc_kwh"].between(0.5, 4.5).all()


def test_schedule_no_prices(battery_spec):
    empty = pd.DataFrame(columns=["timestamp", "buy_price", "sell_price"])
    result = compute_battery_schedule(empty, battery_spec)
    assert result.empty
