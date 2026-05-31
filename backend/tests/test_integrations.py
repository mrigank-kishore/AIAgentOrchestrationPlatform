import pytest


@pytest.mark.asyncio
async def test_integration_status_hides_telegram_token(async_client):
    response = await async_client.get("/api/integrations/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["telegram"]["channel"] == "telegram"
    assert "token" not in payload["telegram"]
