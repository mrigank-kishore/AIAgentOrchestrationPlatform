import pytest


@pytest.mark.asyncio
async def test_create_and_list_agents(async_client):
    payload = {
        "name": "Billing Agent",
        "role": "Handles invoices",
        "system_prompt": "Be precise about billing.",
        "model": "mock",
        "tools": ["search_kb"],
    }
    create_response = await async_client.post("/api/agents/", json=payload)
    assert create_response.status_code == 201
    agent = create_response.json()
    assert agent["name"] == payload["name"]

    list_response = await async_client.get("/api/agents/")
    assert list_response.status_code == 200
    assert [item["name"] for item in list_response.json()] == ["Billing Agent"]
