import asyncio
import os
import time
from pathlib import Path
from typing import Optional, Any
from urllib.parse import urlparse, urljoin, quote
import re

import httpx

from app.models.config import load_config
from app.models.logs import add_log
from app.models.download import get_batch, get_task, update_task
from app.services.media import (
    convert_image_to_jpg,
    current_video_format,
    generate_thumbnail,
    is_transcoded_video,
    reencode_to_mp4,
)
from app.services.stream import EventBus
from app.services.uploader import enqueue_upload_for_file

CHUNK_SIZE = 1024 * 256
RANGE_THRESHOLD = 5 * 1024 * 1024
DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
DEFAULT_YTDLP_FORMAT = (
    "bv*[vcodec~='^(avc1|h264)'][ext=mp4]+ba[ext=m4a]"
    "/bv*[vcodec~='^(avc1|h264)']+ba"
    "/b[ext=mp4]"
    "/bv*[ext=mp4]+ba[ext=m4a]"
    "/bv*+ba/b"
)


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
    if ext in {"mp4", "mkv", "mov", "webm", "m4v", "avi", "ts"}:
        return "video"
    if ext in {"m4a", "mp3", "wav", "flac", "aac", "ogg", "opus"}:
        return "audio"
    return "file"


def _parse_content_range(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    match = re.match(r"bytes\\s+\\d+-\\d+/(\\d+|\\*)", value)
    if not match:
        return None
    total = match.group(1)
    if total == "*":
        return None
    return int(total)


def _build_proxy_url(cfg) -> Optional[str]:
    if not cfg.proxy_enabled or not cfg.proxy_host or not cfg.proxy_port:
        return None
    scheme = "socks5" if cfg.proxy_type == "socks5" else "http"
    auth = ""
    if cfg.proxy_username:
        user = quote(cfg.proxy_username, safe="")
        pwd = quote(cfg.proxy_password or "", safe="")
        auth = f"{user}:{pwd}@"
    return f"{scheme}://{auth}{cfg.proxy_host}:{int(cfg.proxy_port)}"


def _effective_batch_policy(task) -> dict:
    cfg = load_config()
    batch = get_batch(task.batch_id) if task and task.batch_id else None
    return {
        "description": batch.description if batch else None,
        "auto_upload": (bool(batch.auto_upload) if batch and batch.auto_upload is not None else bool(cfg.auto_upload)),
        "video_codec": (batch.transcode_video_codec if batch and batch.transcode_video_codec else cfg.transcode_video_codec),
        "video_format": (batch.transcode_video_format if batch and batch.transcode_video_format else cfg.transcode_video_format),
        "image_format": (batch.transcode_image_format if batch and batch.transcode_image_format else cfg.transcode_image_format),
        "upload_postprocess": (batch.upload_postprocess if batch and batch.upload_postprocess else cfg.upload_postprocess),
        "upload_postprocess_path": (batch.upload_postprocess_path if batch and batch.upload_postprocess_path is not None else cfg.upload_postprocess_path),
    }


def _httpx_client_kwargs(timeout: float, proxy_url: Optional[str]) -> dict:
    kwargs = {"follow_redirects": True, "timeout": timeout}
    if proxy_url:
        kwargs["proxy"] = proxy_url
    return kwargs


def _looks_like_webpage(url: str) -> bool:
    parsed = urlparse(url)
    name = Path(parsed.path).name.lower()
    if not name or "." not in name:
        return True
    ext = name.rsplit(".", 1)[-1]
    direct_ext = {"m3u8", "mp4", "mkv", "mov", "webm", "mp3", "m4a", "aac", "wav", "flac", "jpg", "jpeg", "png", "gif", "webp"}
    if ext in direct_ext:
        return False
    web_ext = {"html", "htm", "php", "asp", "aspx", "jsp"}
    return ext in web_ext


def _build_web_headers(url: str) -> dict:
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""
    return {
        "User-Agent": DEFAULT_UA,
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": origin + "/" if origin else "",
        "Origin": origin,
    }


def _clean_error_text(value: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", value or "").strip()


def _build_ytdlp_options(
    outtmpl: str,
    web_headers: dict,
    progress_hook,
    proxy_url: Optional[str],
    requested_format: Optional[str],
    fragment_concurrency: int,
) -> dict:
    opts = {
        "outtmpl": outtmpl,
        "format": requested_format or DEFAULT_YTDLP_FORMAT,
        "format_sort": [
            "vcodec:h264",
            "acodec:aac",
            "ext:mp4:m4a",
            "res",
            "fps",
            "br",
            "size",
        ],
        "noplaylist": True,
        "concurrent_fragment_downloads": fragment_concurrency,
        "retries": 5,
        "fragment_retries": 5,
        "merge_output_format": current_video_format(),
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 40,
        "http_headers": web_headers,
        "progress_hooks": [progress_hook],
    }
    if proxy_url:
        opts["proxy"] = proxy_url
    return opts


def _finalize_video_file(path: Path, policy: dict) -> Path:
    final_path = path
    if final_path.suffix.lower() in {".mp4", ".mkv", ".mov", ".avi", ".ts", ".webm", ".m4v"} and not is_transcoded_video(final_path):
        converted = reencode_to_mp4(
            final_path,
            video_codec=policy.get("video_codec"),
            video_format=policy.get("video_format"),
        )
        if converted.exists() and converted != final_path:
            try:
                final_path.unlink(missing_ok=True)
            except OSError:
                pass
            final_path = converted
    if final_path.exists():
        generate_thumbnail(final_path)
    return final_path


def _finalize_image_file(path: Path, policy: dict) -> Path:
    final_path = path
    converted = convert_image_to_jpg(final_path, image_format=policy.get("image_format"))
    if converted.exists() and converted != final_path:
        try:
            final_path.unlink(missing_ok=True)
        except OSError:
            pass
        final_path = converted
    return final_path


def _finalize_download_result(task_id: int, final_path: Path, bus: EventBus) -> None:
    task = get_task(task_id)
    policy = _effective_batch_policy(task)
    resolved = final_path
    guessed_type = _guess_type(resolved.name)
    if guessed_type == "video":
        resolved = _finalize_video_file(resolved, policy)
        guessed_type = "video"
    elif guessed_type == "image":
        resolved = _finalize_image_file(resolved, policy)
        guessed_type = "image"
    downloaded = resolved.stat().st_size if resolved.exists() else 0
    update_task(
        task_id,
        status="completed",
        progress=100,
        speed=0,
        downloaded=downloaded,
        total_size=downloaded,
        filename=resolved.name,
        save_path=str(resolved),
        file_type=guessed_type,
        error=None,
    )
    asyncio.create_task(bus.publish({"event": "download", "data": {"id": task_id, "status": "completed"}}))
    if policy["auto_upload"]:
        upload_description = policy["description"]
        if not upload_description:
            if resolved.exists():
                upload_description = resolved.stem or resolved.name
            elif task:
                upload_description = task.filename or None
        enqueue_upload_for_file(
            resolved,
            upload_description,
            postprocess=policy.get("upload_postprocess"),
            postprocess_path=policy.get("upload_postprocess_path"),
        )


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
    proxy_url = _build_proxy_url(cfg)
    web_headers = _build_web_headers(task.url)
    file_type = _guess_type(filename)
    if file_type == "m3u8" and filename.lower().endswith(".m3u8"):
        filename = filename[:-5] + (".mp4" if _has_ffmpeg() else ".ts")
    base_dir = Path(cfg.download_path)
    base_dir.mkdir(parents=True, exist_ok=True)
    final_path = base_dir / filename
    tmp_path = base_dir / (filename + ".part")

    update_task(task_id, status="downloading", file_type=file_type, save_path=str(final_path), filename=filename, error=None)
    await bus.publish({"event": "download", "data": {"id": task_id, "status": "downloading"}})

    ytdlp_error: dict[str, Optional[str]] = {"message": None}
    ytdlp_ok = await _download_with_ytdlp(
        task_id,
        task.url,
        base_dir,
        task.filename,
        bus,
        ytdlp_error,
        proxy_url,
        task.download_format,
    )
    if ytdlp_ok:
        return
    if _looks_like_webpage(task.url) and ytdlp_error["message"]:
        err = ytdlp_error["message"]
        update_task(task_id, status="failed", error=err)
        add_log("error", f"下载失败 {task.url}: {err}")
        await bus.publish({"event": "download", "data": {"id": task_id, "status": "failed", "error": err}})
        return

    if file_type == "m3u8":
        await _download_m3u8(task_id, task.url, final_path, bus, proxy_url)
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
        async with httpx.AsyncClient(**_httpx_client_kwargs(60.0, proxy_url)) as client:
            head = await client.head(task.url, headers=web_headers)
            total = int(head.headers.get("Content-Length", "0"))
            accept_ranges = head.headers.get("Accept-Ranges", "").lower()
    except Exception:
        total = 0
        accept_ranges = ""

    if total >= RANGE_THRESHOLD and "bytes" in accept_ranges:
        ok = await _download_range(task_id, task.url, tmp_path, total, bus, start_time, downloaded, proxy_url, web_headers)
        if not ok:
            return
        downloaded = total
    else:
        async with httpx.AsyncClient(**_httpx_client_kwargs(60.0, proxy_url)) as client:
            try:
                merged_headers = {**web_headers, **headers}
                async with client.stream("GET", task.url, headers=merged_headers) as resp:
                    resp.raise_for_status()
                    cr_total = _parse_content_range(resp.headers.get("Content-Range"))
                    total = cr_total or int(resp.headers.get("Content-Length", "0"))
                    if downloaded > 0 and total > 0 and not cr_total:
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
                            progress = min(progress, 100.0)
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
    _finalize_download_result(task_id, final_path, bus)


async def _download_with_ytdlp(
    task_id: int,
    url: str,
    base_dir: Path,
    requested_filename: Optional[str],
    bus: EventBus,
    error_out: Optional[dict[str, Optional[str]]] = None,
    proxy_url: Optional[str] = None,
    requested_format: Optional[str] = None,
) -> bool:
    try:
        import yt_dlp
    except Exception:
        return False

    loop = asyncio.get_running_loop()
    last_emit = 0.0
    final_path_holder: dict[str, Any] = {"path": None}
    web_headers = _build_web_headers(url)

    class _Abort(Exception):
        pass

    def _publish(payload: dict) -> None:
        try:
            asyncio.run_coroutine_threadsafe(bus.publish(payload), loop)
        except Exception:
            pass

    def _hook(d: dict) -> None:
        nonlocal last_emit
        task = get_task(task_id)
        if not task:
            raise _Abort("task not found")
        if task.status in {"paused", "canceled"}:
            raise _Abort(task.status)
        status = d.get("status")
        if status == "finished":
            final_path_holder["path"] = d.get("filename")
            return
        if status != "downloading":
            return
        now = time.time()
        if now - last_emit < 0.5:
            return
        downloaded = int(d.get("downloaded_bytes") or 0)
        total = int(d.get("total_bytes") or d.get("total_bytes_estimate") or 0)
        speed = float(d.get("speed") or 0)
        progress = (downloaded / total) * 100 if total > 0 else 0
        progress = min(progress, 100.0)
        update_task(task_id, downloaded=downloaded, total_size=total, speed=speed, progress=progress, status="downloading")
        _publish({
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
        last_emit = now

    def _run() -> dict:
        if requested_filename:
            stem = Path(requested_filename).stem
            outtmpl = str(base_dir / f"{stem}.%(ext)s")
        else:
            outtmpl = str(base_dir / "%(title).180B.%(ext)s")
        policy = _effective_batch_policy(get_task(task_id))
        cfg = load_config()
        base_opts = _build_ytdlp_options(
            outtmpl,
            web_headers,
            _hook,
            proxy_url,
            requested_format,
            cfg.ytdlp_fragment_concurrency,
        )
        base_opts["merge_output_format"] = policy.get("video_format") or current_video_format()

        # Try impersonation first; fallback when runtime lacks this feature/deps.
        first_opts = {**base_opts, "impersonate": "chrome", "extractor_args": {"generic": {"impersonate": ["chrome"]}}}
        try:
            with yt_dlp.YoutubeDL(first_opts) as ydl:
                return ydl.extract_info(url, download=True)
        except Exception as exc:
            msg = _clean_error_text(str(exc))
            if "Impersonate target" not in msg:
                raise
        with yt_dlp.YoutubeDL(base_opts) as ydl:
            return ydl.extract_info(url, download=True)

    try:
        info = await asyncio.to_thread(_run)
    except _Abort:
        return True
    except Exception as exc:
        err_text = _clean_error_text(str(exc))
        if error_out is not None:
            error_out["message"] = err_text
        add_log("warning", f"yt-dlp 下载失败，回退直链下载: {url} ({err_text})")
        return False

    final_path: Optional[Path] = None
    path_from_hook = final_path_holder.get("path")
    if path_from_hook:
        candidate = Path(path_from_hook)
        if candidate.exists():
            final_path = candidate

    if final_path is None and isinstance(info, dict):
        requested = info.get("requested_downloads") or []
        for item in requested:
            fp = item.get("filepath")
            if fp and Path(fp).exists():
                final_path = Path(fp)
                break
        if final_path is None:
            fp = info.get("_filename")
            if fp and Path(fp).exists():
                final_path = Path(fp)

    if final_path is None:
        update_task(task_id, status="failed", error="yt-dlp completed but output file not found")
        await bus.publish({"event": "download", "data": {"id": task_id, "status": "failed", "error": "output file not found"}})
        return True

    _finalize_download_result(task_id, final_path, bus)
    return True


async def _download_range(
    task_id: int,
    url: str,
    tmp_path: Path,
    total: int,
    bus: EventBus,
    start_time: float,
    downloaded: int,
    proxy_url: Optional[str],
    web_headers: dict,
) -> bool:
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp_path, "wb") as f:
        f.truncate(total)

    cfg = load_config()
    parts = max(1, min(cfg.range_download_concurrency, max(2, total // RANGE_THRESHOLD)))
    chunk_size = total // parts
    lock = asyncio.Lock()

    async def fetch_part(index: int) -> None:
        nonlocal downloaded
        start = index * chunk_size
        end = total - 1 if index == parts - 1 else (start + chunk_size - 1)
        headers = {**web_headers, "Range": f"bytes={start}-{end}"}
        async with httpx.AsyncClient(**_httpx_client_kwargs(60.0, proxy_url)) as client:
            async with client.stream("GET", url, headers=headers) as resp:
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
                            progress = min(progress, 100.0)
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


async def _download_m3u8(task_id: int, url: str, final_path: Path, bus: EventBus, proxy_url: Optional[str]) -> None:
    base = url
    web_headers = _build_web_headers(url)
    if _has_ffmpeg():
        ok = _download_m3u8_with_ffmpeg(task_id, url, final_path, bus)
        if ok:
            return
    tmp_dir = final_path.parent / (final_path.stem + "_parts")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    segments = []

    try:
        async with httpx.AsyncClient(**_httpx_client_kwargs(60.0, proxy_url)) as client:
            resp = await client.get(url, headers=web_headers)
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
        async with httpx.AsyncClient(**_httpx_client_kwargs(60.0, proxy_url)) as client:
            resp = await client.get(base, headers=web_headers)
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
            async with httpx.AsyncClient(**_httpx_client_kwargs(60.0, proxy_url)) as client:
                async with client.stream("GET", seg_url, headers=web_headers) as resp:
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

    _finalize_download_result(task_id, final_path, bus)


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
        _finalize_download_result(task_id, final_path, bus)
        return True
    except Exception as exc:
        add_log("error", f"m3u8 ffmpeg 失败 {url}: {exc}")
        return False
