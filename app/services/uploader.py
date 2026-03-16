import asyncio
import time
from pathlib import Path

from app.models.config import load_config
from app.models.logs import add_log
from app.models.upload import create_task, get_task, update_task
from app.services.files import split_by_size
from app.services.stream import EventBus
from app.services.telegram.mtproto_client import TelegramClient


class UploadManager:
    def __init__(self, bus: EventBus, tg: TelegramClient, concurrency: int = 2) -> None:
        self.bus = bus
        self.tg = tg
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
        from app.models.upload import list_tasks

        tasks = list_tasks(status=None)
        for task in tasks:
            if task.status not in {"pending", "auth_required"}:
                continue
            if self._sem._value == 0:
                return
            if task.status == "auth_required" and not self.tg.is_ready():
                continue
            update_task(task.id, status="queued")
            await self.bus.publish({"event": "upload", "data": {"id": task.id, "status": "queued"}})
            asyncio.create_task(self._run_task(task.id))

    async def _run_task(self, task_id: int) -> None:
        async with self._sem:
            task = get_task(task_id)
            if not task or task.status not in {"queued", "pending", "auth_required"}:
                return
            await self.tg.start()
            if not self.tg.is_ready():
                update_task(task_id, status="auth_required", error="需要认证")
                await self.bus.publish({"event": "upload", "data": {"id": task_id, "status": "auth_required", "error": "需要认证"}})
                return
            if self.tg.is_ready():
                ok = await self._upload_mtproto(task_id)
                if ok:
                    return
            await self._upload_stub(task_id)

    async def _upload_mtproto(self, task_id: int) -> bool:
        task = get_task(task_id)
        if not task:
            return False
        path = Path(task.source_path)
        if not path.exists():
            update_task(task_id, status="failed", error="源文件不存在")
            add_log("error", f"上传失败: 源文件不存在 {task.source_path}")
            await self.bus.publish({"event": "upload", "data": {"id": task_id, "status": "failed", "error": "源文件不存在"}})
            return True
        total = path.stat().st_size
        update_task(task_id, status="uploading", total_size=total)
        await self.bus.publish({"event": "upload", "data": {"id": task_id, "status": "uploading"}})
        def progress_cb(current: int, total_size: int) -> None:
            progress = (current / total_size) * 100 if total_size else 0
            update_task(task_id, uploaded=current, total_size=total_size, progress=progress, status="uploading")
            asyncio.create_task(self.bus.publish({
                "event": "upload",
                "data": {
                    "id": task_id,
                    "status": "uploading",
                    "uploaded": current,
                    "total": total_size,
                    "progress": progress,
                },
            }))

        try:
            await self.tg.send_document(path, task.description, progress_cb=progress_cb)
        except Exception as exc:
            update_task(task_id, status="failed", error=str(exc))
            add_log("error", f"上传失败 MTProto: {task.source_path} ({exc})")
            await self.bus.publish({"event": "upload", "data": {"id": task_id, "status": "failed", "error": str(exc)}})
            return True

        update_task(task_id, status="completed", progress=100, speed=0)
        await self.bus.publish({"event": "upload", "data": {"id": task_id, "status": "completed"}})
        self._after_upload(task_id)
        return True

    async def _upload_stub(self, task_id: int) -> None:
        task = get_task(task_id)
        if not task:
            return
        path = Path(task.source_path)
        if not path.exists():
            update_task(task_id, status="failed", error="源文件不存在")
            await self.bus.publish({"event": "upload", "data": {"id": task_id, "status": "failed", "error": "源文件不存在"}})
            return

        total = path.stat().st_size
        update_task(task_id, status="uploading", total_size=total)
        await self.bus.publish({"event": "upload", "data": {"id": task_id, "status": "uploading"}})

        uploaded = 0
        start = time.time()
        while uploaded < total:
            await asyncio.sleep(0.3)
            step = min(512 * 1024, total - uploaded)
            uploaded += step
            speed = uploaded / max(time.time() - start, 0.001)
            progress = (uploaded / total) * 100
            update_task(task_id, uploaded=uploaded, speed=speed, progress=progress)
            await self.bus.publish({
                "event": "upload",
                "data": {
                    "id": task_id,
                    "status": "uploading",
                    "uploaded": uploaded,
                    "total": total,
                    "speed": speed,
                    "progress": progress,
                },
            })

        update_task(task_id, status="completed", progress=100, speed=0)
        await self.bus.publish({"event": "upload", "data": {"id": task_id, "status": "completed"}})
        self._after_upload(task_id)

    async def cancel(self, task_id: int) -> None:
        update_task(task_id, status="canceled")
        await self.bus.publish({"event": "upload", "data": {"id": task_id, "status": "canceled"}})

    async def retry(self, task_id: int) -> None:
        update_task(task_id, status="pending", error=None)
        await self.bus.publish({"event": "upload", "data": {"id": task_id, "status": "pending"}})

    def _after_upload(self, task_id: int) -> None:
        cfg = load_config()
        task = get_task(task_id)
        if not task:
            return
        if cfg.upload_postprocess == "delete":
            from app.services.files import safe_delete
            safe_delete(Path(task.source_path))
            return
        if cfg.upload_postprocess == "move":
            from app.services.files import move_with_template
            move_with_template(Path(task.source_path), cfg.upload_postprocess_path or "")


def enqueue_upload_for_file(path: Path, description: str | None = None) -> list[int]:
    cfg = load_config()
    threshold = (cfg.split_threshold_mb or 2048) * 1024 * 1024
    parts = split_by_size(path, threshold)
    total_parts = len(parts)
    ids = []
    for idx, part in enumerate(parts, start=1):
        desc = description
        if total_parts > 1:
            suffix = f" (part {idx}/{total_parts})"
            desc = (description or part.stem) + suffix
        ids.append(create_task(str(part), cfg.target_channel, desc, idx if total_parts > 1 else None, total_parts if total_parts > 1 else None))
    return ids
