import asyncio

import pytest
from fastapi.testclient import TestClient

from app.core.broker import broker
from app.main import app


def test_websocket_receives_broker_event():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/monitor") as websocket:
            asyncio.run(broker.publish({"type": "test", "value": 1}))
            assert websocket.receive_json() == {"type": "test", "value": 1}
