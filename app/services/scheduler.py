import asyncio
from typing import Optional

from app.models.download import get_task, list_tasks, update_task
from app.services.downloader import download_task, cleanup_download
from app.services.stream import EventBus


class Scheduler:
    def __init__(self, bus: EventBus, concurrency: int = 3) -> None:
        self.bus = bus
        self._sem = asyncio.Semaphore(concurrency)
        self._running = False
        self._concurrency = concurrency

    def set_concurrency(self, value: int) -> None:
        if value <= 0 or value == self._concurrency:
            return
        self._concurrency = value
        self._sem = asyncio.Semaphore(value)

    async def run(self) -> None:
        if self._running:
            return
        self._running = True
        while True:
            await self._dispatch_pending()
            await asyncio.sleep(1)

    async def _dispatch_pending(self) -> None:
        tasks = list_tasks(status="pending")
        for task in tasks:
            if self._sem._value == 0:
                return
            update_task(task.id, status="queued")
            await self.bus.publish({"event": "download", "data": {"id": task.id, "status": "queued"}})
            asyncio.create_task(self._run_task(task.id))

    async def _run_task(self, task_id: int) -> None:
        async with self._sem:
            task = get_task(task_id)
            if not task or task.status not in {"queued", "pending"}:
                return
            await download_task(task_id, self.bus)

    async def pause(self, task_id: int) -> None:
        update_task(task_id, status="paused")
        await self.bus.publish({"event": "download", "data": {"id": task_id, "status": "paused"}})

    async def resume(self, task_id: int) -> None:
        update_task(task_id, status="pending")
        await self.bus.publish({"event": "download", "data": {"id": task_id, "status": "pending"}})

    async def cancel(self, task_id: int) -> None:
        update_task(task_id, status="canceled")
        cleanup_download(task_id)
        await self.bus.publish({"event": "download", "data": {"id": task_id, "status": "canceled"}})

    async def retry(self, task_id: int) -> None:
        update_task(task_id, status="pending", error=None)
        await self.bus.publish({"event": "download", "data": {"id": task_id, "status": "pending"}})
