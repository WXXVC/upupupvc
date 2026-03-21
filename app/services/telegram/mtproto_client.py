import asyncio
from pathlib import Path
from typing import Callable, Optional

from telethon import TelegramClient as MTProtoClient
from telethon.errors import SessionPasswordNeededError

from app.models.auth import save_auth_state
from app.models.config import load_config
from app.models.logs import add_log
from app.services.media import ensure_faststart, ffmpeg_exe, generate_thumbnail, is_transcoded_video, needs_reencode_for_streaming, reencode_to_mp4
from app.services.stream import EventBus


class TelegramClient:
    def __init__(self, bus: EventBus) -> None:
        self.bus = bus
        self.client: Optional[MTProtoClient] = None
        self._connected = False
        self._authorized = False
        self._client_signature: Optional[tuple] = None

    @staticmethod
    def _build_proxy(cfg):
        if not cfg.proxy_enabled or not cfg.proxy_host or not cfg.proxy_port:
            return None
        try:
            import socks
        except ImportError:
            return None
        proxy_kind = socks.HTTP if cfg.proxy_type == "http" else socks.SOCKS5
        return (
            proxy_kind,
            cfg.proxy_host,
            int(cfg.proxy_port),
            True,
            cfg.proxy_username or None,
            cfg.proxy_password or None,
        )

    @staticmethod
    def _signature(cfg) -> tuple:
        return (
            cfg.api_id,
            cfg.api_hash,
            cfg.proxy_enabled,
            cfg.proxy_type,
            cfg.proxy_host,
            cfg.proxy_port,
            cfg.proxy_username,
            cfg.proxy_password,
        )

    async def _ensure_client(self, cfg) -> bool:
        if not (cfg.api_id and cfg.api_hash and cfg.phone_number):
            return False
        signature = self._signature(cfg)
        if self.client is not None and self._client_signature == signature:
            return True
        if self.client is not None:
            await self.client.disconnect()
            self._connected = False
            self._authorized = False
        session_dir = Path("./telethon")
        session_dir.mkdir(parents=True, exist_ok=True)
        session_path = session_dir / "session"
        proxy = self._build_proxy(cfg)
        self.client = MTProtoClient(str(session_path), int(cfg.api_id), cfg.api_hash, proxy=proxy)
        self._client_signature = signature
        return True

    async def start(self) -> bool:
        cfg = load_config()
        if not await self._ensure_client(cfg):
            return False
        if not self._connected:
            await self.client.connect()
            self._connected = True
        if not await self.client.is_user_authorized():
            await self.client.send_code_request(cfg.phone_number)
            save_auth_state("wait_code", "请输入短信验证码")
            await self.bus.publish({"event": "auth", "data": {"state": "wait_code", "detail": "请输入短信验证码"}})
            self._authorized = False
            return False
        save_auth_state("ready", "已连接")
        await self.bus.publish({"event": "auth", "data": {"state": "ready", "detail": "已连接"}})
        self._authorized = True
        return True

    def is_ready(self) -> bool:
        return self._connected and self._authorized

    async def submit_code(self, code: str) -> None:
        cfg = load_config()
        if not self.client:
            await self.start()
        if not self.client:
            return
        try:
            await self.client.sign_in(cfg.phone_number, code)
            save_auth_state("ready", "已连接")
            await self.bus.publish({"event": "auth", "data": {"state": "ready", "detail": "已连接"}})
            self._authorized = True
        except SessionPasswordNeededError:
            save_auth_state("wait_password", "需要两步验证密码")
            await self.bus.publish({"event": "auth", "data": {"state": "wait_password", "detail": "需要两步验证密码"}})
            self._authorized = False

    async def submit_password(self, password: str) -> None:
        if not self.client:
            await self.start()
        if not self.client:
            return
        await self.client.sign_in(password=password)
        save_auth_state("ready", "已连接")
        await self.bus.publish({"event": "auth", "data": {"state": "ready", "detail": "已连接"}})
        self._authorized = True

    async def send_document(
        self,
        path: Path,
        caption: Optional[str],
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> Path:
        if not self.client:
            return path
        cfg = load_config()
        target = cfg.target_channel
        add_log("info", f"上传 ffmpeg 检测: {'ok' if ffmpeg_exe() else 'missing'}")
        send_path, is_video, is_image, is_audio, thumb = self._prepare_send_path(path)
        force_document = not (is_video or is_image or is_audio)
        add_log("info", f"开始上传文件: source={path}, send={send_path}, supports_streaming={is_video}, as_image={is_image}, as_audio={is_audio}, force_document={force_document}")
        await self.client.send_file(
            target,
            str(send_path),
            caption=caption,
            progress_callback=progress_cb,
            supports_streaming=is_video,
            force_document=force_document,
            thumb=str(thumb) if (thumb and not is_video) else None,
        )
        return send_path

    def _prepare_send_path(self, path: Path) -> tuple[Path, bool, bool, bool, Optional[Path]]:
        suffix = path.suffix.lower()
        is_video = suffix in {".mp4", ".mkv", ".mov", ".m4v", ".ts", ".avi", ".webm"}
        is_image = suffix in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
        is_audio = suffix in {".mp3", ".m4a", ".aac", ".wav", ".flac", ".ogg", ".opus"}
        send_path = path
        thumb = None
        if is_video:
            if is_transcoded_video(path):
                send_path = path
            elif needs_reencode_for_streaming(path):
                send_path = reencode_to_mp4(path)
                if send_path != path:
                    add_log("info", f"上传前转码: {path} -> {send_path}")
                else:
                    add_log("warning", f"上传前转码未生效，继续使用原文件: {path}")
            else:
                send_path = ensure_faststart(path)
                if send_path != path:
                    add_log("info", f"上传前 faststart: {path} -> {send_path}")
            thumb = generate_thumbnail(send_path)
            if thumb:
                add_log("info", f"上传缩略图已生成: {thumb}")
            else:
                add_log("warning", f"上传缩略图生成失败: {send_path}")
        return send_path, is_video, is_image, is_audio, thumb

    async def send_media_group(self, paths: list[Path], caption: Optional[str] = None) -> list[Path]:
        if not self.client or not paths:
            return paths
        cfg = load_config()
        target = cfg.target_channel
        prepared_paths: list[str] = []
        final_paths: list[Path] = []
        for idx, path in enumerate(paths):
            send_path, is_video, is_image, _, _ = self._prepare_send_path(path)
            if not (is_video or is_image):
                continue
            prepared_paths.append(str(send_path))
            final_paths.append(send_path)
        if not prepared_paths:
            return []
        add_log("info", f"开始批量媒体上传: {len(prepared_paths)} 个文件")
        await self.client.send_file(target, prepared_paths, caption=caption, force_document=False)
        return final_paths

    @staticmethod
    def can_send_in_media_group(path: Path) -> bool:
        suffix = path.suffix.lower()
        if suffix == ".mp4":
            return True
        return suffix in {".jpg", ".jpeg", ".png"}
