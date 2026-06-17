import pytest


@pytest.mark.asyncio
async def test_get_schedule_nonexistent(async_client):
    response = await async_client.get("/api/v1/schedules/999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_override_schedule_slot(async_client, db_session):
    payload = {
        "start_time": "2026-06-16T12:00:00Z",
        "power_mw": 2.0,
        "state_of_charge_kwh": 2000,
    }
    response = await async_client.post("/api/v1/schedules/1", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["power_mw"] == 2.0
    assert data["is_manual_override"] is True
