from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.broker import broker

router = APIRouter(tags=["monitor"])


@router.websocket("/ws/monitor")
async def monitor(websocket: WebSocket):
    await websocket.accept()
    try:
        async for event in broker.subscribe():
            await websocket.send_json(event)
    except WebSocketDisconnect:
        return
