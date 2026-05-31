import asyncio
from collections.abc import AsyncGenerator


class Broker:
    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[dict]] = []

    async def publish(self, event: dict) -> None:
        for subscriber in list(self._subscribers):
            await subscriber.put(event)

    async def subscribe(self) -> AsyncGenerator[dict, None]:
        queue: asyncio.Queue[dict] = asyncio.Queue()
        self._subscribers.append(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            if queue in self._subscribers:
                self._subscribers.remove(queue)


broker = Broker()
