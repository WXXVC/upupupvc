import asyncio
from typing import AsyncGenerator, Dict, List


class EventBus:
    def __init__(self) -> None:
        self._queues: List[asyncio.Queue[Dict]] = []

    def subscribe(self) -> asyncio.Queue[Dict]:
        queue: asyncio.Queue[Dict] = asyncio.Queue()
        self._queues.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[Dict]) -> None:
        if queue in self._queues:
            self._queues.remove(queue)

    async def publish(self, event: Dict) -> None:
        for queue in list(self._queues):
            await queue.put(event)

    async def sse_stream(self) -> AsyncGenerator[bytes, None]:
        queue = self.subscribe()
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=5)
                    payload = _format_sse(event)
                    yield payload
                except asyncio.TimeoutError:
                    yield b"event: heartbeat\ndata: {}\n\n"
        finally:
            self.unsubscribe(queue)


def _format_sse(event: Dict) -> bytes:
    name = event.get("event", "message")
    data = event.get("data", {})
    import json

    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")
