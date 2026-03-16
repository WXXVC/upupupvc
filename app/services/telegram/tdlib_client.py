import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable, Dict

from app.models.auth import load_auth_state, save_auth_state
from app.models.config import is_configured, load_config
from app.services.stream import EventBus
from app.services.telegram.tdlib_json import TelegramService, TDLibError


@dataclass
class AuthPrompt:
    kind: str
    message: str


class TDLibStub:
    """Fallback stub when TDLib binary is unavailable."""

    def __init__(self, bus: EventBus) -> None:
        self.bus = bus
        self._lock = asyncio.Lock()

    def is_ready(self) -> bool:
        state = load_auth_state()
        return state.state == "ready"

    async def start(self) -> None:
        if not is_configured():
            return
        state = load_auth_state()
        if state.state in {"ready", "wait_password"}:
            await self._emit_state(state.state, state.detail)
            return
        await self._require_code()

    async def submit_code(self, code: str) -> None:
        async with self._lock:
            if code.strip().lower() == "2fa":
                await self._require_password("需要两步验证密码")
                return
            await self._set_ready("验证码已确认")

    async def submit_password(self, password: str) -> None:
        async with self._lock:
            if not password.strip():
                await self._require_password("密码不能为空")
                return
            await self._set_ready("两步验证完成")

    async def send_document(self, path: Path, caption: Optional[str]) -> Optional[int]:
        return None

    def register_file_handler(self, file_id: int, handler: Callable[[Dict], None]) -> None:
        return None

    async def _require_code(self) -> None:
        save_auth_state("wait_code", "需要短信验证码")
        await self._emit_state("wait_code", "需要短信验证码")

    async def _require_password(self, detail: str) -> None:
        save_auth_state("wait_password", detail)
        await self._emit_state("wait_password", detail)

    async def _set_ready(self, detail: str) -> None:
        save_auth_state("ready", detail)
        await self._emit_state("ready", detail)

    async def _emit_state(self, state: str, detail: Optional[str]) -> None:
        await self.bus.publish({
            "event": "auth",
            "data": {"state": state, "detail": detail},
        })


class TelegramClient:
    def __init__(self, bus: EventBus) -> None:
        self.bus = bus
        self._real: Optional[TelegramService] = None
        self._stub = TDLibStub(bus)

    def is_ready(self) -> bool:
        if self._real:
            return self._real.is_ready()
        return self._stub.is_ready()

    async def start(self) -> None:
        cfg = load_config()
        if cfg.tdlib_lib_path:
            self._real = TelegramService(self.bus)
            await self._real.start()
            if self._real.is_active():
                return
        await self._stub.start()

    async def submit_code(self, code: str) -> None:
        if self._real:
            await self._real.submit_code(code)
            return
        await self._stub.submit_code(code)

    async def submit_password(self, password: str) -> None:
        if self._real:
            await self._real.submit_password(password)
            return
        await self._stub.submit_password(password)

    async def send_document(self, path: Path, caption: Optional[str]) -> Optional[int]:
        if self._real:
            try:
                return await self._real.send_document(path, caption)
            except TDLibError:
                return None
        return await self._stub.send_document(path, caption)

    def register_file_handler(self, file_id: int, handler: Callable[[Dict], None]) -> None:
        if self._real:
            self._real.register_file_handler(file_id, handler)

    async def cancel_upload(self, file_id: int) -> None:
        if self._real:
            await self._real.cancel_upload(file_id)
