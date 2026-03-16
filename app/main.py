import asyncio
from pathlib import Path

import shutil

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.models.db import init_db
from app.models.auth import load_auth_state
from app.models.config import load_config, save_config, is_configured
from app.models.download import create_tasks, list_tasks
from app.models.upload import list_tasks as list_upload_tasks
from app.models.logs import list_logs
from app.models.logs import add_log
from app.services.stream import EventBus
from app.services.scheduler import Scheduler
from app.services.uploader import UploadManager, enqueue_upload_for_file
from app.services.telegram.tdlib_client import TelegramClient

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Telegram Media Downloader")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
bus = EventBus()
tdlib = TelegramClient(bus)
scheduler = Scheduler(bus)
uploader = UploadManager(bus, tdlib)


@app.on_event("startup")
async def on_startup() -> None:
    init_db()
    scheduler.set_concurrency(load_config().max_download_concurrency)
    uploader.set_concurrency(2)
    await tdlib.start()
    asyncio.create_task(scheduler.run())
    asyncio.create_task(uploader.run())


@app.middleware("http")
async def config_guard(request: Request, call_next):
    path = request.url.path
    allowlist = {
        "/config",
        "/api/config",
        "/api/auth/status",
        "/api/auth/submit",
        "/api/system",
        "/logs",
        "/api/logs",
        "/static",
        "/health",
    }
    if path == "/":
        if not is_configured():
            return RedirectResponse(url="/config", status_code=302)
    elif not any(path == p or path.startswith(p + "/") for p in allowlist):
        if not is_configured():
            return RedirectResponse(url="/config", status_code=302)
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
    cfg = load_config()
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "config": cfg},
    )


@app.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    cfg = load_config()
    return templates.TemplateResponse(
        "config.html",
        {"request": request, "config": cfg},
    )


@app.get("/api/config")
async def api_get_config():
    cfg = load_config()
    return JSONResponse(cfg.__dict__)


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
    await tdlib.start()
    return JSONResponse({"ok": True, "configured": is_configured()})


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception):
    add_log("error", f"未处理异常 {request.url.path}: {exc}")
    return JSONResponse({"ok": False, "error": "internal_error"}, status_code=500)


@app.post("/api/tasks/download")
async def api_create_download(request: Request):
    data = await request.json()
    urls = data.get("urls")
    if isinstance(urls, str):
        urls = [urls]
    if not isinstance(urls, list) or not urls:
        return JSONResponse({"ok": False, "error": "urls required"}, status_code=400)
    ids = create_tasks([u.strip() for u in urls if u.strip()])
    return JSONResponse({"ok": True, "ids": ids})


@app.get("/api/tasks/list")
async def api_list_tasks(status: str | None = None, q: str | None = None, page: int = 1, limit: int = 50):
    offset = max(page - 1, 0) * limit
    tasks = list_tasks(status=status, search=q, limit=limit, offset=offset)
    return JSONResponse({"items": [task.__dict__ for task in tasks]})


@app.get("/api/tasks/upload/list")
async def api_list_upload_tasks(status: str | None = None, q: str | None = None, page: int = 1, limit: int = 50):
    offset = max(page - 1, 0) * limit
    tasks = list_upload_tasks(status=status, search=q, limit=limit, offset=offset)
    return JSONResponse({"items": [task.__dict__ for task in tasks]})


@app.post("/api/tasks/upload")
async def api_create_upload(request: Request):
    data = await request.json()
    path = data.get("path")
    description = data.get("description")
    if not path:
        return JSONResponse({"ok": False, "error": "path required"}, status_code=400)
    ids = enqueue_upload_for_file(Path(path), description)
    return JSONResponse({"ok": True, "ids": ids})


@app.post("/api/tasks/action")
async def api_task_action(request: Request):
    data = await request.json()
    task_id = int(data.get("id"))
    action = data.get("action")
    if action == "pause":
        await scheduler.pause(task_id)
    elif action == "resume":
        await scheduler.resume(task_id)
    elif action == "cancel":
        await scheduler.cancel(task_id)
    elif action == "retry":
        await scheduler.retry(task_id)
    else:
        return JSONResponse({"ok": False, "error": "unknown action"}, status_code=400)
    return JSONResponse({"ok": True})


@app.post("/api/tasks/upload/action")
async def api_upload_action(request: Request):
    data = await request.json()
    task_id = int(data.get("id"))
    action = data.get("action")
    if action == "cancel":
        await uploader.cancel(task_id)
    elif action == "retry":
        await uploader.retry(task_id)
    else:
        return JSONResponse({"ok": False, "error": "unknown action"}, status_code=400)
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


