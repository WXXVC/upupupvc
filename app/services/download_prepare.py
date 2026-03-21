from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse, quote

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.models.config import load_config

router = APIRouter()
DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"


def _build_proxy_url() -> Optional[str]:
    cfg = load_config()
    if not cfg.proxy_enabled or not cfg.proxy_host or not cfg.proxy_port:
        return None
    scheme = "socks5" if cfg.proxy_type == "socks5" else "http"
    auth = ""
    if cfg.proxy_username:
        user = quote(cfg.proxy_username, safe="")
        pwd = quote(cfg.proxy_password or "", safe="")
        auth = f"{user}:{pwd}@"
    return f"{scheme}://{auth}{cfg.proxy_host}:{int(cfg.proxy_port)}"


def _guess_filename(url: str, content_disposition: Optional[str]) -> str:
    if content_disposition:
        match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', content_disposition)
        if match:
            return match.group(1)
    parsed = urlparse(url)
    name = parsed.path.rsplit("/", 1)[-1]
    return name or "download.bin"


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


def _parse_content_range(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    match = re.match(r"bytes\s+\d+-\d+/(\d+|\*)", value)
    if not match:
        return None
    total = match.group(1)
    if total == "*":
        return None
    return int(total)


def _probe_media(url: str) -> dict:
    try:
        import imageio_ffmpeg
        import subprocess

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        result = subprocess.run([ffmpeg, "-i", url], capture_output=True, text=True)
        output = result.stderr or ""
        duration_match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", output)
        resolution_match = re.search(r", (\d{2,5}x\d{2,5})[,\s]", output)
        duration_text = None
        duration_seconds = None
        if duration_match:
            h = int(duration_match.group(1))
            m = int(duration_match.group(2))
            s = float(duration_match.group(3))
            duration_seconds = int(h * 3600 + m * 60 + s)
            duration_text = f"{h:02d}:{m:02d}:{int(s):02d}"
        resolution = resolution_match.group(1) if resolution_match else None
        return {
            "duration_seconds": duration_seconds,
            "duration_text": duration_text,
            "resolution": resolution,
        }
    except Exception:
        return {"duration_seconds": None, "duration_text": None, "resolution": None}


def _probe_with_ytdlp(url: str, proxy_url: Optional[str]) -> Optional[dict]:
    try:
        import yt_dlp
    except Exception:
        return None
    try:
        base_opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "skip_download": True,
            "socket_timeout": 30,
            "http_headers": _build_web_headers(url),
        }
        if proxy_url:
            base_opts["proxy"] = proxy_url

        first_opts = {**base_opts, "impersonate": "chrome", "extractor_args": {"generic": {"impersonate": ["chrome"]}}}
        try:
            with yt_dlp.YoutubeDL(first_opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as exc:
            msg = str(exc)
            if "Impersonate target" not in msg:
                raise
            with yt_dlp.YoutubeDL(base_opts) as ydl:
                info = ydl.extract_info(url, download=False)
        if not isinstance(info, dict):
            return None
        ext = info.get("ext")
        title = (info.get("title") or "download").strip()
        filename = f"{title}.{ext}" if ext else title
        width = info.get("width")
        height = info.get("height")
        resolution = f"{width}x{height}" if width and height else None
        duration_seconds = info.get("duration")
        duration_text = None
        if isinstance(duration_seconds, (int, float)):
            total = int(duration_seconds)
            h = total // 3600
            m = (total % 3600) // 60
            s = total % 60
            duration_text = f"{h:02d}:{m:02d}:{s:02d}"
        size = info.get("filesize") or info.get("filesize_approx") or 0
        content_type = f"video/{ext}" if ext else None
        formats = info.get("formats") or []
        video_options = []
        audio_options = []
        seen_video = set()
        seen_audio = set()
        for f in formats:
            if not isinstance(f, dict):
                continue
            fid = f.get("format_id")
            if not fid:
                continue
            vcodec = f.get("vcodec")
            acodec = f.get("acodec")
            height = f.get("height") or 0
            tbr = f.get("tbr") or 0
            abr = f.get("abr") or 0
            ext_f = f.get("ext") or ""
            filesize = f.get("filesize") or f.get("filesize_approx") or 0
            if vcodec and vcodec != "none":
                key = (int(height), ext_f)
                if key in seen_video:
                    continue
                seen_video.add(key)
                label = f"{int(height) if height else 0}p {ext_f}".strip()
                if tbr:
                    label += f" ({int(tbr)}k)"
                video_options.append({
                    "id": str(fid),
                    "label": label,
                    "height": int(height) if height else 0,
                    "ext": ext_f,
                    "tbr": float(tbr) if tbr else 0,
                    "filesize": int(filesize) if isinstance(filesize, (int, float)) else 0,
                })
            if acodec and acodec != "none" and (not vcodec or vcodec == "none"):
                key = (int(abr) if abr else 0, ext_f)
                if key in seen_audio:
                    continue
                seen_audio.add(key)
                label = f"{int(abr) if abr else 0}k {ext_f}".strip()
                audio_options.append({
                    "id": str(fid),
                    "label": label,
                    "abr": int(abr) if abr else 0,
                    "ext": ext_f,
                    "filesize": int(filesize) if isinstance(filesize, (int, float)) else 0,
                })

        video_options.sort(key=lambda x: (x["height"], x["tbr"]), reverse=True)
        audio_options.sort(key=lambda x: x["abr"], reverse=True)

        return {
            "filename": filename,
            "content_type": content_type,
            "size": int(size) if isinstance(size, (int, float)) else 0,
            "duration_seconds": int(duration_seconds) if isinstance(duration_seconds, (int, float)) else None,
            "duration_text": duration_text,
            "resolution": resolution,
            "video_formats": video_options[:12],
            "audio_formats": audio_options[:12],
        }
    except Exception:
        return None


@router.post("/api/download/prepare")
async def prepare_download(request: Request):
    data = await request.json()
    url = (data.get("url") or "").strip()
    if not url:
        return JSONResponse({"ok": False, "error": "url required"}, status_code=400)

    proxy_url = _build_proxy_url()
    web_headers = _build_web_headers(url)
    ytdlp_meta = _probe_with_ytdlp(url, proxy_url)
    if ytdlp_meta:
        return JSONResponse({
            "ok": True,
            "url": url,
            **ytdlp_meta,
        })

    content_type = None
    total = 0
    content_disposition = None
    try:
        client_kwargs = {"follow_redirects": True, "timeout": 30.0}
        if proxy_url:
            client_kwargs["proxy"] = proxy_url
        async with httpx.AsyncClient(**client_kwargs) as client:
            head = await client.head(url, headers=web_headers)
            content_type = head.headers.get("Content-Type")
            content_length = head.headers.get("Content-Length")
            content_disposition = head.headers.get("Content-Disposition")
            total = int(content_length) if content_length and content_length.isdigit() else 0
            filename = _guess_filename(url, content_disposition)
            if not total:
                async with client.stream("GET", url, headers=web_headers) as resp:
                    resp.raise_for_status()
                    cr_total = _parse_content_range(resp.headers.get("Content-Range"))
                    if cr_total:
                        total = cr_total
                    else:
                        length = resp.headers.get("Content-Length")
                        total = int(length) if length and length.isdigit() else 0
                    content_type = content_type or resp.headers.get("Content-Type")
    except Exception as exc:
        filename = _guess_filename(url, None)
        return JSONResponse({
            "ok": True,
            "url": url,
            "filename": filename,
            "content_type": None,
            "size": 0,
            "duration_seconds": None,
            "duration_text": None,
            "resolution": None,
            "video_formats": [],
            "audio_formats": [],
            "warning": f"预解析失败，已降级为直接下载: {exc}",
        })

    media = _probe_media(url)

    return JSONResponse({
        "ok": True,
        "url": url,
        "filename": filename,
        "content_type": content_type,
        "size": total,
        "video_formats": [],
        "audio_formats": [],
        **media,
    })
