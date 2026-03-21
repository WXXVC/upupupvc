import asyncio
import hashlib
import hmac
import mimetypes
from pathlib import Path
from urllib.parse import quote

import shutil

from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.models.db import init_db
from app.models.auth import load_auth_state
from app.models.config import load_config, save_config, is_configured, to_public_dict, verify_access_password
from app.models.download import (
    create_batch as create_download_batch,
    create_tasks,
    delete_batch as delete_download_batch,
    delete_task as delete_download_task,
    get_task as get_download_task,
    list_batch_children as list_download_batch_children,
    list_task_groups as list_download_task_groups,
    list_tasks,
)
from app.models.upload import (
    create_batch as create_upload_batch,
    create_task as create_upload_task,
    delete_batch as delete_upload_batch,
    delete_task as delete_upload_task,
    get_task as get_upload_task,
    list_batch_children,
    list_task_groups as list_upload_task_groups,
    list_tasks as list_upload_tasks,
    update_task as update_upload_task,
)
from app.models.logs import list_logs
from app.models.logs import add_log
from app.services.stream import EventBus
from app.services.scheduler import Scheduler
from app.services.uploader import UploadManager, enqueue_upload_for_file
from app.services.telegram.mtproto_client import TelegramClient
from app.services.download_prepare import router as download_prepare_router
from app.services.files import delete_with_artifacts, normalize_user_path
from app.services.media import generate_thumbnail

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Telegram Media Downloader")
app.include_router(download_prepare_router)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
bus = EventBus()
tdlib = TelegramClient(bus)
scheduler = Scheduler(bus)
uploader = UploadManager(bus, tdlib)
ACCESS_COOKIE = "upupup_access"


def _serialize_download_task(task) -> dict:
    data = task.__dict__.copy()
    data["preview_url"] = f"/api/tasks/file/{task.id}?variant=raw" if task.save_path else None
    data["thumb_url"] = f"/api/tasks/file/{task.id}?variant=thumb" if task.save_path and task.file_type in {"video", "image"} else None
    return data


def _guess_file_type_from_path(path: Path | None) -> str:
    suffix = (path.suffix or "").lower() if path else ""
    if suffix in {".mp4", ".mkv", ".mov", ".webm", ".m4v", ".avi", ".ts"}:
        return "video"
    if suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}:
        return "image"
    if suffix in {".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".opus"}:
        return "audio"
    return "file"


def _inline_file_headers(filename: str) -> dict[str, str]:
    encoded = quote(filename)
    return {
        "Accept-Ranges": "bytes",
        "Content-Disposition": f"inline; filename*=UTF-8''{encoded}",
    }


def _serialize_upload_task(task) -> dict:
    data = task.__dict__.copy()
    path = Path(task.source_path) if task.source_path else None
    file_type = _guess_file_type_from_path(path)
    data["title"] = path.name if path else f"任务 #{task.id}"
    data["file_type"] = file_type
    data["preview_url"] = f"/api/tasks/upload/file/{task.id}?variant=raw" if path and path.exists() and path.is_file() else None
    data["thumb_url"] = (
        f"/api/tasks/upload/file/{task.id}?variant=thumb"
        if path and path.exists() and path.is_file() and file_type in {"video", "image"}
        else None
    )
    return data


def _create_batch_upload_task_records(tasks: list, description: str) -> tuple[int, dict[int, int]]:
    batch_title = description or f"批量上传 {len(tasks)} 个文件"
    batch_id = create_upload_batch(batch_title, description or None, len(tasks))
    mapping: dict[int, int] = {}
    for task in tasks:
        upload_id = create_upload_task(
            task.save_path,
            load_config().target_channel,
            description or task.filename or Path(task.save_path).stem,
            batch_id=batch_id,
        )
        update_upload_task(upload_id, status="queued", error=None)
        mapping[task.id] = upload_id
    return batch_id, mapping


def _is_html_request(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "text/html" in accept.lower()


def _access_cookie_value(cfg) -> str:
    seed = f"{cfg.access_password_salt or ''}:{cfg.access_password_hash or ''}:ok"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _is_access_protected(cfg) -> bool:
    return bool(cfg.access_password_hash and cfg.access_password_salt)


def _is_access_verified(request: Request, cfg) -> bool:
    if not _is_access_protected(cfg):
        return True
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        return False
    return hmac.compare_digest(token, _access_cookie_value(cfg))


@app.on_event("startup")
async def on_startup() -> None:
    init_db()
    scheduler.set_concurrency(load_config().max_download_concurrency)
    uploader.set_concurrency(2)
    asyncio.create_task(scheduler.run())
    asyncio.create_task(uploader.run())


@app.middleware("http")
async def config_guard(request: Request, call_next):
    path = request.url.path
    cfg = load_config()
    public_allowlist = {
        "/unlock",
        "/api/access/status",
        "/api/access/login",
        "/api/access/logout",
        "/static",
        "/health",
    }
    setup_allowlist = {
        "/",
        "/config",
        "/api/config",
        "/api/auth/status",
        "/api/auth/submit",
        "/api/system",
        "/logs",
        "/api/logs",
    }
    if not cfg.configured:
        if any(path == p or path.startswith(p + "/") for p in public_allowlist | setup_allowlist):
            return await call_next(request)
        return RedirectResponse(url="/?tab=settings", status_code=302)
    if any(path == p or path.startswith(p + "/") for p in public_allowlist):
        return await call_next(request)
    if not _is_access_verified(request, cfg):
        if _is_html_request(request):
            return RedirectResponse(url="/unlock", status_code=302)
        return JSONResponse({"ok": False, "error": "access_denied"}, status_code=401)
    return await call_next(request)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/api/system")
async def api_system():
    cfg = load_config()
    path = cfg.download_path or "."
    try:
        usage = shutil.disk_usage(path)
        total = usage.total
        free = usage.free
    except Exception:
        total = 0
        free = 0
    return JSONResponse({"disk_total": total, "disk_free": free})


@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    return templates.TemplateResponse("logs.html", {"request": request})


@app.get("/api/logs")
async def api_logs(level: str | None = None, q: str | None = None, limit: int = 200):
    items = list_logs(limit=limit, level=level, q=q)
    return JSONResponse({"items": [item.__dict__ for item in items]})


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    cfg = to_public_dict(load_config())
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "config": cfg},
    )


@app.get("/config", response_class=HTMLResponse)
async def config_page():
    return RedirectResponse(url="/?tab=settings", status_code=302)


@app.get("/unlock", response_class=HTMLResponse)
async def unlock_page(request: Request):
    cfg = load_config()
    if not _is_access_protected(cfg):
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("unlock.html", {"request": request})


@app.get("/api/config")
async def api_get_config():
    cfg = load_config()
    return JSONResponse(to_public_dict(cfg))


@app.post("/api/config")
async def api_save_config(request: Request):
    data = await request.json()
    path = data.get("download_path")
    if path:
        try:
            p = Path(path)
            p.mkdir(parents=True, exist_ok=True)
            test_file = p / ".write_test"
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink(missing_ok=True)
        except Exception as exc:
            add_log("error", f"配置保存失败: 下载路径不可写 {path} ({exc})")
            return JSONResponse({"ok": False, "error": "download_path_not_writable"}, status_code=400)
    save_config(data)
    scheduler.set_concurrency(load_config().max_download_concurrency)
    return JSONResponse({"ok": True, "configured": is_configured()})


@app.get("/api/access/status")
async def api_access_status(request: Request):
    cfg = load_config()
    return JSONResponse({
        "enabled": _is_access_protected(cfg),
        "verified": _is_access_verified(request, cfg),
    })


@app.post("/api/access/login")
async def api_access_login(request: Request):
    cfg = load_config()
    if not _is_access_protected(cfg):
        return JSONResponse({"ok": True, "enabled": False})
    data = await request.json()
    password = (data.get("password") or "").strip()
    if not password or not verify_access_password(password, cfg):
        return JSONResponse({"ok": False, "error": "invalid_password"}, status_code=401)
    response = JSONResponse({"ok": True})
    response.set_cookie(
        ACCESS_COOKIE,
        _access_cookie_value(cfg),
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=60 * 60 * 24 * 30,
        path="/",
    )
    return response


@app.post("/api/access/logout")
async def api_access_logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(ACCESS_COOKIE, path="/")
    return response


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception):
    add_log("error", f"未处理异常 {request.url.path}: {exc}")
    return JSONResponse({"ok": False, "error": "internal_error"}, status_code=500)


@app.post("/api/tasks/download")
async def api_create_download(request: Request):
    data = await request.json()
    urls = data.get("urls")
    filename = data.get("filename")
    batch_description = (data.get("description") or "").strip()
    if isinstance(urls, str):
        urls = [{"url": urls, "filename": filename}]
    if not isinstance(urls, list) or not urls:
        return JSONResponse({"ok": False, "error": "urls required"}, status_code=400)
    if urls and isinstance(urls[0], str):
        urls = [{"url": u.strip()} for u in urls if u.strip()]
    urls = [u for u in urls if isinstance(u, dict) and u.get("url")]
    if not urls:
        return JSONResponse({"ok": False, "error": "urls required"}, status_code=400)
    batch_id = None
    if len(urls) > 1:
        batch_title = batch_description or f"批量下载 {len(urls)} 个链接"
        batch_id = create_download_batch(batch_title, batch_description or None, len(urls))
    ids = create_tasks(urls, batch_id=batch_id)
    return JSONResponse({"ok": True, "ids": ids})


@app.post("/api/tasks/download/auto-batch")
async def api_create_auto_batch_download(request: Request):
    data = await request.json()
    description = (data.get("description") or "").strip()
    raw_urls = data.get("urls")
    urls_text = data.get("urls_text")

    urls: list[dict] = []
    if isinstance(raw_urls, list):
        for item in raw_urls:
            if isinstance(item, str) and item.strip():
                urls.append({"url": item.strip()})
            elif isinstance(item, dict) and item.get("url"):
                urls.append({"url": str(item.get("url")).strip(), "filename": item.get("filename"), "format": item.get("format")})
    elif isinstance(raw_urls, str) and raw_urls.strip():
        urls.append({"url": raw_urls.strip()})

    if urls_text:
        urls.extend({"url": line.strip()} for line in str(urls_text).splitlines() if line.strip())

    deduped: list[dict] = []
    seen: set[str] = set()
    for item in urls:
        url = (item.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        deduped.append(item)
    urls = deduped

    if not description:
        return JSONResponse({"ok": False, "error": "description required"}, status_code=400)
    if not urls:
        return JSONResponse({"ok": False, "error": "urls required"}, status_code=400)
    if len(urls) < 2:
        return JSONResponse({"ok": False, "error": "batch requires at least 2 urls"}, status_code=400)

    batch_id = create_download_batch(
        description or f"自动批量下载 {len(urls)} 个链接",
        description,
        len(urls),
        auto_upload=True,
        transcode_video_codec="h264",
        transcode_video_format="mp4",
        transcode_image_format="jpg",
        upload_postprocess="delete",
        upload_postprocess_path=None,
    )
    ids = create_tasks(urls, batch_id=batch_id)
    add_log("info", f"创建自动批量下载上传批次 #{batch_id}: {len(urls)} 个链接")
    return JSONResponse({
        "ok": True,
        "batch_id": batch_id,
        "ids": ids,
        "policy": {
            "auto_upload": True,
            "transcode_video_codec": "h264",
            "transcode_video_format": "mp4",
            "transcode_image_format": "jpg",
            "upload_postprocess": "delete",
        },
    })


async def _run_download_batch_upload(task_ids: list[int], description: str) -> None:
    try:
        await tdlib.start()
        if not tdlib.is_ready():
            add_log("error", "批量上传失败: Telegram 未完成认证")
            return

        tasks = []
        for task_id in task_ids:
            task = get_download_task(task_id)
            if not task or task.status != "completed" or not task.save_path:
                continue
            path = Path(task.save_path)
            if path.exists() and path.is_file():
                tasks.append(task)

        if not tasks:
            add_log("warning", "批量上传跳过: 没有可上传的已完成下载任务")
            return

        batch_id, upload_map = _create_batch_upload_task_records(tasks, description)
        for upload_id in upload_map.values():
            update_upload_task(upload_id, status="uploading")
            await bus.publish({"event": "upload", "data": {"id": upload_id, "status": "uploading"}})

        media_tasks = [task for task in tasks if task.file_type in {"image", "video"}]
        other_tasks = [task for task in tasks if task.file_type in {"audio", "file"}]

        caption_used = False
        if media_tasks:
            for idx in range(0, len(media_tasks), 10):
                chunk = media_tasks[idx:idx + 10]
                sent_ids: list[int] = []
                fallback_tasks = []
                for task in chunk:
                    path = Path(task.save_path)
                    if tdlib.can_send_in_media_group(path):
                        sent_ids.append(task.id)
                    else:
                        fallback_tasks.append(task)
                        add_log("warning", f"媒体组跳过不兼容文件，改为单文件上传: {path.name}")
                if sent_ids:
                    paths = [Path(task.save_path) for task in chunk if task.id in sent_ids and task.save_path]
                    await tdlib.send_media_group(paths, caption=None if caption_used else (description or None))
                    caption_used = caption_used or bool(description)
                    for task_id in sent_ids:
                        upload_id = upload_map.get(task_id)
                        if upload_id:
                            update_upload_task(upload_id, status="completed", progress=100, speed=0)
                            await bus.publish({"event": "upload", "data": {"id": upload_id, "status": "completed"}})
                for task in fallback_tasks:
                    path = Path(task.save_path)
                    await tdlib.send_document(path, None if caption_used else (description or None))
                    caption_used = caption_used or bool(description)
                    upload_id = upload_map.get(task.id)
                    if upload_id:
                        update_upload_task(upload_id, status="completed", progress=100, speed=0)
                        await bus.publish({"event": "upload", "data": {"id": upload_id, "status": "completed"}})

        for task in other_tasks:
            path = Path(task.save_path)
            if not path.exists():
                continue
            caption = None if caption_used else description
            await tdlib.send_document(path, caption)
            caption_used = caption_used or bool(caption)
            upload_id = upload_map.get(task.id)
            if upload_id:
                update_upload_task(upload_id, status="completed", progress=100, speed=0)
                await bus.publish({"event": "upload", "data": {"id": upload_id, "status": "completed"}})

        add_log("info", f"批量上传完成: {len(tasks)} 个下载任务")
    except Exception as exc:
        for task_id, upload_id in locals().get("upload_map", {}).items():
            update_upload_task(upload_id, status="failed", error=str(exc))
            await bus.publish({"event": "upload", "data": {"id": upload_id, "status": "failed", "error": str(exc)}})
        add_log("error", f"批量上传失败: {exc}")


@app.get("/api/tasks/list")
async def api_list_tasks(
    status: str | None = None,
    q: str | None = None,
    file_type: str | None = None,
    completed_from: str | None = None,
    completed_to: str | None = None,
    page: int = 1,
    limit: int = 50,
):
    offset = max(page - 1, 0) * limit
    tasks = list_download_task_groups(
        status=status,
        search=q,
        file_type=file_type,
        completed_from=completed_from,
        completed_to=completed_to,
        limit=limit,
        offset=offset,
    )
    return JSONResponse({"items": [_serialize_download_task(task) for task in tasks]})


@app.get("/api/tasks/download/batch/{batch_id}")
async def api_download_batch_detail(batch_id: int):
    children = list_download_batch_children(batch_id)
    return JSONResponse({"items": [_serialize_download_task(child) for child in children]})


@app.get("/api/tasks/file/{task_id}")
async def api_task_file(task_id: int, variant: str = "raw"):
    task = get_download_task(task_id)
    if not task or not task.save_path:
        return JSONResponse({"ok": False, "error": "not_found"}, status_code=404)
    path = Path(task.save_path)
    if not path.exists() or not path.is_file():
        return JSONResponse({"ok": False, "error": "not_found"}, status_code=404)

    target = path
    if variant == "thumb":
        if task.file_type == "image":
            target = path
        elif task.file_type == "video":
            target = path.with_suffix(".jpg")
            if not target.exists():
                generated = generate_thumbnail(path)
                if generated:
                    target = generated
        else:
            return JSONResponse({"ok": False, "error": "unsupported"}, status_code=400)

    if not target.exists() or not target.is_file():
        return JSONResponse({"ok": False, "error": "not_found"}, status_code=404)
    media_type, _ = mimetypes.guess_type(str(target))
    headers = _inline_file_headers(target.name)
    return FileResponse(target, media_type=media_type or "application/octet-stream", filename=target.name, headers=headers)


@app.post("/api/tasks/download/batch-upload")
async def api_download_batch_upload(request: Request):
    data = await request.json()
    ids = data.get("ids") or []
    description = (data.get("description") or "").strip()
    if not isinstance(ids, list) or not ids:
        return JSONResponse({"ok": False, "error": "ids required"}, status_code=400)
    task_ids = [int(item) for item in ids]
    asyncio.create_task(_run_download_batch_upload(task_ids, description))
    return JSONResponse({"ok": True})


@app.get("/api/tasks/upload/file/{task_id}")
async def api_upload_task_file(task_id: int, variant: str = "raw"):
    task = get_upload_task(task_id)
    if not task or not task.source_path:
        return JSONResponse({"ok": False, "error": "not_found"}, status_code=404)
    path = Path(task.source_path)
    if not path.exists() or not path.is_file():
        return JSONResponse({"ok": False, "error": "not_found"}, status_code=404)

    file_type = _guess_file_type_from_path(path)
    target = path
    if variant == "thumb":
        if file_type == "image":
            target = path
        elif file_type == "video":
            target = path.with_suffix(".jpg")
            if not target.exists():
                generated = generate_thumbnail(path)
                if generated:
                    target = generated
        else:
            return JSONResponse({"ok": False, "error": "unsupported"}, status_code=400)

    if not target.exists() or not target.is_file():
        return JSONResponse({"ok": False, "error": "not_found"}, status_code=404)
    media_type, _ = mimetypes.guess_type(str(target))
    headers = _inline_file_headers(target.name)
    return FileResponse(target, media_type=media_type or "application/octet-stream", filename=target.name, headers=headers)


@app.get("/api/tasks/upload/list")
async def api_list_upload_tasks(status: str | None = None, q: str | None = None, page: int = 1, limit: int = 50):
    offset = max(page - 1, 0) * limit
    tasks = list_upload_task_groups(status=status, search=q, limit=limit, offset=offset)
    return JSONResponse({"items": [task.__dict__ for task in tasks]})


@app.get("/api/tasks/upload/batch/{batch_id}")
async def api_upload_batch_detail(batch_id: int):
    children = list_batch_children(batch_id)
    return JSONResponse({"items": [_serialize_upload_task(child) for child in children]})


@app.post("/api/tasks/upload")
async def api_create_upload(request: Request):
    data = await request.json()
    path = normalize_user_path(data.get("path") or "")
    description = (data.get("description") or "").strip()
    if not path:
        return JSONResponse({"ok": False, "error": "path required"}, status_code=400)
    try:
        file_path = Path(path)
        if not description:
            description = file_path.stem
        ids = enqueue_upload_for_file(file_path, description)
    except (ValueError, OSError) as exc:
        add_log("error", f"路径上传失败: {path} ({exc})")
        return JSONResponse({"ok": False, "error": "invalid_path", "detail": str(exc)}, status_code=400)
    return JSONResponse({"ok": True, "ids": ids})


@app.post("/api/tasks/upload/file")
async def api_create_upload_file(file: UploadFile = File(...), description: str | None = Form(None)):
    cfg = load_config()
    inbox = Path(cfg.download_path or "./downloads") / "_upload_inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    original = Path(file.filename or "upload.bin").name
    safe_name = "".join(ch for ch in original if ch not in '<>:"/\\|?*').strip() or "upload.bin"
    target = inbox / safe_name
    if target.exists():
        stem = target.stem
        suffix = target.suffix
        idx = 1
        while True:
            candidate = inbox / f"{stem}_{idx}{suffix}"
            if not candidate.exists():
                target = candidate
                break
            idx += 1
    try:
        with target.open("wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
    finally:
        await file.close()
    caption = (description or "").strip()
    if not caption:
        caption = target.stem
    ids = enqueue_upload_for_file(target, caption)
    return JSONResponse({"ok": True, "ids": ids, "path": str(target)})


@app.post("/api/tasks/action")
async def api_task_action(request: Request):
    data = await request.json()
    task_id = int(data.get("id"))
    action = data.get("action")
    kind = data.get("kind") or "task"
    target_ids = [task_id]
    if kind == "batch":
        target_ids = [item.id for item in list_download_batch_children(task_id)]
    if action == "pause":
        for target_id in target_ids:
            await scheduler.pause(target_id)
    elif action == "resume":
        for target_id in target_ids:
            await scheduler.resume(target_id)
    elif action == "cancel":
        for target_id in target_ids:
            await scheduler.cancel(target_id)
    elif action == "retry":
        for target_id in target_ids:
            await scheduler.retry(target_id)
    else:
        return JSONResponse({"ok": False, "error": "unknown action"}, status_code=400)
    return JSONResponse({"ok": True})


@app.post("/api/tasks/delete")
async def api_task_delete(request: Request):
    data = await request.json()
    task_id = int(data.get("id"))
    kind = data.get("kind") or "task"
    tasks = list_download_batch_children(task_id) if kind == "batch" else ([get_download_task(task_id)] if get_download_task(task_id) else [])
    for task in tasks:
        if task and task.save_path:
            try:
                deleted = delete_with_artifacts(Path(task.save_path))
                if deleted:
                    add_log("info", f"删除下载产物: {', '.join(str(item) for item in deleted)}")
            except Exception as exc:
                add_log("error", f"删除下载产物失败: {task.save_path} ({exc})")
    if kind == "batch":
        delete_download_batch(task_id)
    else:
        delete_download_task(task_id)
    return JSONResponse({"ok": True})


@app.post("/api/tasks/upload/action")
async def api_upload_action(request: Request):
    data = await request.json()
    task_id = int(data.get("id"))
    action = data.get("action")
    kind = data.get("kind") or "task"
    target_ids = [task_id]
    if kind == "batch":
        target_ids = [item.id for item in list_batch_children(task_id)]
    if action == "cancel":
        for target_id in target_ids:
            await uploader.cancel(target_id)
    elif action == "retry":
        for target_id in target_ids:
            await uploader.retry(target_id)
    else:
        return JSONResponse({"ok": False, "error": "unknown action"}, status_code=400)
    return JSONResponse({"ok": True})


@app.post("/api/tasks/upload/delete")
async def api_upload_delete(request: Request):
    data = await request.json()
    task_id = int(data.get("id"))
    kind = data.get("kind") or "task"
    if kind == "batch":
        delete_upload_batch(task_id)
    else:
        delete_upload_task(task_id)
    return JSONResponse({"ok": True})

@app.get("/api/auth/status")
async def api_auth_status():
    state = load_auth_state()
    return JSONResponse({"state": state.state, "detail": state.detail, "configured": is_configured()})


@app.post("/api/auth/submit")
async def api_auth_submit(request: Request):
    data = await request.json()
    kind = data.get("type")
    value = (data.get("value") or "").strip()
    if kind == "code":
        await tdlib.submit_code(value)
        return JSONResponse({"ok": True})
    if kind == "password":
        await tdlib.submit_password(value)
        return JSONResponse({"ok": True})
    return JSONResponse({"ok": False, "error": "unknown type"}, status_code=400)


@app.get("/sse")
async def sse():
    return StreamingResponse(bus.sse_stream(), media_type="text/event-stream")


