import asyncio
import os
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, urljoin

import httpx

from app.models.config import load_config
from app.models.logs import add_log
from app.models.download import get_task, update_task
from app.services.stream import EventBus
from app.services.uploader import enqueue_upload_for_file

CHUNK_SIZE = 1024 * 256
RANGE_THRESHOLD = 5 * 1024 * 1024


def _guess_filename(url: str) -> str:
    parsed = urlparse(url)
    name = Path(parsed.path).name
    return name or "download.bin"


def _guess_type(filename: str) -> str:
    ext = filename.lower().rsplit(".", 1)
    if len(ext) == 2:
        ext = ext[1]
    else:
        ext = ""
    if ext in {"m3u8"}:
        return "m3u8"
    if ext in {"jpg", "jpeg", "png", "gif", "webp"}:
        return "image"
    if ext in {"mp4", "mkv", "mov", "mp3", "wav", "flac"}:
        return "media"
    return "file"


async def download_task(task_id: int, bus: EventBus) -> None:
    task = get_task(task_id)
    if not task:
        return
    cfg = load_config()
    if not cfg.download_path:
        update_task(task_id, status="failed", error="下载路径未配置")
        add_log("error", f"下载失败 {task.url}: 下载路径未配置")
        return

    filename = task.filename or _guess_filename(task.url)
    file_type = _guess_type(filename)
    if file_type == "m3u8" and filename.lower().endswith(".m3u8"):
        filename = filename[:-5] + (".mp4" if _has_ffmpeg() else ".ts")
    base_dir = Path(cfg.download_path)
    base_dir.mkdir(parents=True, exist_ok=True)
    final_path = base_dir / filename
    tmp_path = base_dir / (filename + ".part")

    update_task(task_id, status="downloading", file_type=file_type, save_path=str(final_path), filename=filename, error=None)
    await bus.publish({"event": "download", "data": {"id": task_id, "status": "downloading"}})

    if file_type == "m3u8":
        await _download_m3u8(task_id, task.url, final_path, bus)
        return

    start_time = time.time()
    last_update = start_time
    downloaded = 0

    if tmp_path.exists():
        downloaded = tmp_path.stat().st_size

    headers = {}
    if downloaded > 0:
        headers["Range"] = f"bytes={downloaded}-"

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
            head = await client.head(task.url)
            total = int(head.headers.get("Content-Length", "0"))
            accept_ranges = head.headers.get("Accept-Ranges", "").lower()
    except Exception:
        total = 0
        accept_ranges = ""

    if total >= RANGE_THRESHOLD and "bytes" in accept_ranges:
        ok = await _download_range(task_id, task.url, tmp_path, total, bus, start_time, downloaded)
        if not ok:
            return
        downloaded = total
    else:
        async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
            try:
                resp = await client.get(task.url, headers=headers, stream=True)
                resp.raise_for_status()
                total = int(resp.headers.get("Content-Length", "0"))
                if downloaded > 0 and total > 0:
                    total += downloaded
                update_task(task_id, total_size=total)
                async for chunk in resp.aiter_bytes(CHUNK_SIZE):
                    if not chunk:
                        continue
                    if get_task(task_id).status in {"paused", "canceled"}:
                        return
                    tmp_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(tmp_path, "ab") as f:
                        f.write(chunk)
                    downloaded += len(chunk)
                    now = time.time()
                    if now - last_update >= 1:
                        speed = (downloaded / max(now - start_time, 0.001))
                        progress = (downloaded / total) * 100 if total > 0 else 0
                        update_task(task_id, downloaded=downloaded, speed=speed, progress=progress)
                        await bus.publish({
                            "event": "download",
                            "data": {
                                "id": task_id,
                                "status": "downloading",
                                "downloaded": downloaded,
                                "total": total,
                                "speed": speed,
                                "progress": progress,
                            },
                        })
                        last_update = now
            except Exception as exc:
                update_task(task_id, status="failed", error=str(exc))
                add_log("error", f"下载失败 {task.url}: {exc}")
                await bus.publish({"event": "download", "data": {"id": task_id, "status": "failed", "error": str(exc)}})
                return

    os.replace(tmp_path, final_path)
    update_task(task_id, status="completed", progress=100, speed=0, downloaded=downloaded)
    await bus.publish({"event": "download", "data": {"id": task_id, "status": "completed"}})
    if load_config().auto_upload:
        enqueue_upload_for_file(final_path)


async def _download_range(task_id: int, url: str, tmp_path: Path, total: int, bus: EventBus, start_time: float, downloaded: int) -> bool:
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp_path, "wb") as f:
        f.truncate(total)

    parts = min(8, max(2, total // RANGE_THRESHOLD))
    chunk_size = total // parts
    lock = asyncio.Lock()

    async def fetch_part(index: int) -> None:
        nonlocal downloaded
        start = index * chunk_size
        end = total - 1 if index == parts - 1 else (start + chunk_size - 1)
        headers = {"Range": f"bytes={start}-{end}"}
        async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
            resp = await client.get(url, headers=headers, stream=True)
            resp.raise_for_status()
            with open(tmp_path, "r+b") as f:
                f.seek(start)
                async for chunk in resp.aiter_bytes(CHUNK_SIZE):
                    if not chunk:
                        continue
                    if get_task(task_id).status in {"paused", "canceled"}:
                        return
                    f.write(chunk)
                    async with lock:
                        downloaded += len(chunk)
                        now = time.time()
                        speed = (downloaded / max(now - start_time, 0.001))
                        progress = (downloaded / total) * 100 if total > 0 else 0
                        update_task(task_id, downloaded=downloaded, speed=speed, progress=progress, total_size=total)
                        await bus.publish({
                            "event": "download",
                            "data": {
                                "id": task_id,
                                "status": "downloading",
                                "downloaded": downloaded,
                                "total": total,
                                "speed": speed,
                                "progress": progress,
                            },
                        })

    try:
        await asyncio.gather(*(fetch_part(i) for i in range(parts)))
    except Exception as exc:
        update_task(task_id, status="failed", error=str(exc))
        add_log("error", f"下载失败 {url}: {exc}")
        await bus.publish({"event": "download", "data": {"id": task_id, "status": "failed", "error": str(exc)}})
        return False
    return True


async def _download_m3u8(task_id: int, url: str, final_path: Path, bus: EventBus) -> None:
    base = url
    if _has_ffmpeg():
        ok = _download_m3u8_with_ffmpeg(task_id, url, final_path, bus)
        if ok:
            return
    tmp_dir = final_path.parent / (final_path.stem + "_parts")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    segments = []

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            text = resp.text
    except Exception as exc:
        update_task(task_id, status="failed", error=str(exc))
        add_log("error", f"m3u8 解析失败 {url}: {exc}")
        await bus.publish({"event": "download", "data": {"id": task_id, "status": "failed", "error": str(exc)}})
        return

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for i, line in enumerate(lines):
        if line.startswith("#EXT-X-STREAM-INF"):
            if i + 1 < len(lines):
                base = urljoin(url, lines[i + 1])
            break

    if base != url:
        async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
            resp = await client.get(base)
            resp.raise_for_status()
            lines = [line.strip() for line in resp.text.splitlines() if line.strip()]

    for line in lines:
        if line.startswith("#"):
            continue
        segments.append(urljoin(base, line))

    if not segments:
        update_task(task_id, status="failed", error="未找到分片")
        add_log("error", f"m3u8 未找到分片 {url}")
        await bus.publish({"event": "download", "data": {"id": task_id, "status": "failed", "error": "未找到分片"}})
        return

    total_segments = len(segments)
    update_task(task_id, total_size=total_segments)

    sem = asyncio.Semaphore(8)
    completed = 0
    lock = asyncio.Lock()

    async def fetch_segment(idx: int, seg_url: str) -> None:
        nonlocal completed
        name = tmp_dir / f"{idx:06d}.ts"
        async with sem:
            async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
                resp = await client.get(seg_url, stream=True)
                resp.raise_for_status()
                with open(name, "wb") as f:
                    async for chunk in resp.aiter_bytes(CHUNK_SIZE):
                        if not chunk:
                            continue
                        if get_task(task_id).status in {"paused", "canceled"}:
                            return
                        f.write(chunk)
        async with lock:
            completed += 1
            progress = (completed / total_segments) * 100
            update_task(task_id, progress=progress, downloaded=completed)
            await bus.publish({"event": "download", "data": {"id": task_id, "status": "downloading", "progress": progress}})

    try:
        await asyncio.gather(*(fetch_segment(i, seg) for i, seg in enumerate(segments)))
    except Exception as exc:
        update_task(task_id, status="failed", error=str(exc))
        add_log("error", f"m3u8 下载失败 {url}: {exc}")
        await bus.publish({"event": "download", "data": {"id": task_id, "status": "failed", "error": str(exc)}})
        return

    with open(final_path, "wb") as out:
        for i in range(total_segments):
            part = tmp_dir / f"{i:06d}.ts"
            with open(part, "rb") as f:
                out.write(f.read())
            try:
                os.remove(part)
            except OSError:
                pass

    try:
        tmp_dir.rmdir()
    except OSError:
        pass

    update_task(task_id, status="completed", progress=100, speed=0, downloaded=total_segments)
    await bus.publish({"event": "download", "data": {"id": task_id, "status": "completed"}})


def cleanup_download(task_id: int) -> None:
    task = get_task(task_id)
    if not task or not task.save_path:
        return
    path = Path(task.save_path)
    tmp_path = Path(str(path) + ".part")
    if tmp_path.exists():
        try:
            tmp_path.unlink()
        except OSError:
            pass
    tmp_dir = path.parent / (path.stem + "_parts")
    if tmp_dir.exists():
        for item in tmp_dir.glob("*"):
            try:
                item.unlink()
            except OSError:
                pass
        try:
            tmp_dir.rmdir()
        except OSError:
            pass


def _has_ffmpeg() -> bool:
    try:
        import imageio_ffmpeg
        return bool(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:
        return False


def _download_m3u8_with_ffmpeg(task_id: int, url: str, final_path: Path, bus: EventBus) -> bool:
    import subprocess
    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            url,
            "-c",
            "copy",
            str(final_path),
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        update_task(task_id, status="completed", progress=100, speed=0)
        asyncio.create_task(bus.publish({"event": "download", "data": {"id": task_id, "status": "completed"}}))
        return True
    except Exception as exc:
        add_log("error", f"m3u8 ffmpeg 失败 {url}: {exc}")
        return False
