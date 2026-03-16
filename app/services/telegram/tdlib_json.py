import asyncio
import ctypes
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from app.models.auth import save_auth_state
from app.models.config import load_config
from app.services.stream import EventBus


class TDLibError(RuntimeError):
    pass


@dataclass
class AuthUpdate:
    state: str
    detail: Optional[str]


class TDLibJsonClient:
    def __init__(self, bus: EventBus, library_path: Path) -> None:
        self.bus = bus
        self.library_path = library_path
        self._lib = ctypes.CDLL(str(library_path))
        self._lib.td_json_client_create.restype = ctypes.c_void_p
        self._lib.td_json_client_send.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        self._lib.td_json_client_receive.argtypes = [ctypes.c_void_p, ctypes.c_double]
        self._lib.td_json_client_receive.restype = ctypes.c_char_p
        self._lib.td_json_client_execute.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        self._lib.td_json_client_execute.restype = ctypes.c_char_p
        self._lib.td_json_client_destroy.argtypes = [ctypes.c_void_p]
        self._client = self._lib.td_json_client_create()
        self._pending: Dict[str, asyncio.Future] = {}
        self._on_update: Optional[Callable[[Dict[str, Any]], None]] = None

    def set_update_handler(self, handler: Callable[[Dict[str, Any]], None]) -> None:
        self._on_update = handler

    def send(self, query: Dict[str, Any], extra: Optional[str] = None) -> asyncio.Future:
        if extra:
            query["@extra"] = extra
        payload = json.dumps(query).encode("utf-8")
        self._lib.td_json_client_send(self._client, ctypes.c_char_p(payload))
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        if extra:
            self._pending[extra] = fut
        else:
            fut.set_result({})
        return fut

    def execute(self, query: Dict[str, Any]) -> Dict[str, Any]:
        payload = json.dumps(query).encode("utf-8")
        result = self._lib.td_json_client_execute(self._client, ctypes.c_char_p(payload))
        if not result:
            return {}
        return json.loads(ctypes.cast(result, ctypes.c_char_p).value.decode("utf-8"))

    async def receive_loop(self) -> None:
        while True:
            result = self._lib.td_json_client_receive(self._client, ctypes.c_double(1.0))
            if not result:
                await asyncio.sleep(0.05)
                continue
            data = json.loads(ctypes.cast(result, ctypes.c_char_p).value.decode("utf-8"))
            extra = data.get("@extra")
            if extra and extra in self._pending:
                fut = self._pending.pop(extra)
                if not fut.done():
                    fut.set_result(data)
                continue
            if self._on_update:
                self._on_update(data)

    def close(self) -> None:
        self._lib.td_json_client_destroy(self._client)


class TelegramService:
    def __init__(self, bus: EventBus) -> None:
        self.bus = bus
        self._client: Optional[TDLibJsonClient] = None
        self._ready = False
        self._file_handlers: Dict[int, Callable[[Dict[str, Any]], None]] = {}

    def is_active(self) -> bool:
        return self._client is not None

    def is_ready(self) -> bool:
        return self._ready

    async def start(self) -> None:
        cfg = load_config()
        if not cfg.tdlib_lib_path:
            return
        lib_path = Path(cfg.tdlib_lib_path)
        if not lib_path.exists():
            return
        if self._client:
            return
        self._client = TDLibJsonClient(self.bus, lib_path)
        self._client.set_update_handler(self._handle_update)
        asyncio.create_task(self._client.receive_loop())
        await self._send_tdlib_parameters()

    async def _send_tdlib_parameters(self) -> None:
        cfg = load_config()
        db_dir = cfg.tdlib_database_dir or "./tdlib"
        files_dir = cfg.tdlib_files_dir or "./tdlib/files"
        params = {
            "@type": "setTdlibParameters",
            "parameters": {
                "database_directory": db_dir,
                "files_directory": files_dir,
                "use_message_database": True,
                "use_secret_chats": False,
                "api_id": int(cfg.api_id),
                "api_hash": cfg.api_hash,
                "system_language_code": "en",
                "device_model": "server",
                "system_version": "1.0",
                "application_version": "1.0",
                "enable_storage_optimizer": True,
            },
        }
        await self._client.send(params, extra="setTdlibParameters")

    async def submit_code(self, code: str) -> None:
        if not self._client:
            return
        await self._client.send({"@type": "checkAuthenticationCode", "code": code}, extra=f"code:{time.time()}")

    async def submit_password(self, password: str) -> None:
        if not self._client:
            return
        await self._client.send({"@type": "checkAuthenticationPassword", "password": password}, extra=f"pwd:{time.time()}")

    async def send_document(self, path: Path, caption: Optional[str]) -> Optional[int]:
        if not self._client:
            return None
        cfg = load_config()
        extra = f"send:{time.time()}"
        chat_id = await self._resolve_chat_id(cfg.target_channel)
        if chat_id is None:
            raise TDLibError("无法解析频道")
        query = {
            "@type": "sendMessage",
            "chat_id": chat_id,
            "input_message_content": {
                "@type": "inputMessageDocument",
                "document": {"@type": "inputFileLocal", "path": str(path)},
                "caption": {"@type": "formattedText", "text": caption or ""},
            },
        }
        response = await self._client.send(query, extra=extra)
        if response.get("@type") == "error":
            raise TDLibError(response.get("message", "sendMessage failed"))
        file_id = _find_file_id(response)
        return file_id

    async def cancel_upload(self, file_id: int) -> None:
        if not self._client:
            return
        await self._client.send({"@type": "cancelUploadFile", "file_id": file_id}, extra=f"cancel:{time.time()}")

    async def _resolve_chat_id(self, value: Optional[str]) -> Optional[int]:
        if not value:
            return None
        if value.startswith("@"):
            response = await self._client.send(
                {"@type": "searchPublicChat", "username": value[1:]},
                extra=f"chat:{time.time()}",
            )
            if response.get("@type") == "chat":
                return int(response.get("id"))
            return None
        return int(value)

    def register_file_handler(self, file_id: int, handler: Callable[[Dict[str, Any]], None]) -> None:
        self._file_handlers[file_id] = handler

    def _handle_update(self, data: Dict[str, Any]) -> None:
        if data.get("@type") == "updateAuthorizationState":
            self._handle_auth_state(data.get("authorization_state"))
            return
        if data.get("@type") == "updateFile":
            file = data.get("file") or {}
            file_id = file.get("id")
            handler = self._file_handlers.get(file_id)
            if handler:
                handler(file)
            return

    def _handle_auth_state(self, state: Dict[str, Any]) -> None:
        if not state:
            return
        kind = state.get("@type")
        if kind == "authorizationStateWaitTdlibParameters":
            return
        if kind == "authorizationStateWaitEncryptionKey":
            cfg = load_config()
            key = cfg.tdlib_encryption_key or ""
            self._client.send({"@type": "checkDatabaseEncryptionKey", "encryption_key": key}, extra=f"key:{time.time()}")
            return
        if kind == "authorizationStateWaitTdlibParameters":
            asyncio.create_task(self._send_tdlib_parameters())
            return
        if kind == "authorizationStateWaitPhoneNumber":
            cfg = load_config()
            save_auth_state("wait_code", "请输入短信验证码")
            asyncio.create_task(self.bus.publish({"event": "auth", "data": {"state": "wait_code", "detail": "请输入短信验证码"}}))
            self._client.send({"@type": "setAuthenticationPhoneNumber", "phone_number": cfg.phone_number}, extra=f"phone:{time.time()}")
            return
        if kind == "authorizationStateWaitCode":
            save_auth_state("wait_code", "请输入短信验证码")
            asyncio.create_task(self.bus.publish({"event": "auth", "data": {"state": "wait_code", "detail": "请输入短信验证码"}}))
            return
        if kind == "authorizationStateWaitPassword":
            save_auth_state("wait_password", "需要两步验证密码")
            asyncio.create_task(self.bus.publish({"event": "auth", "data": {"state": "wait_password", "detail": "需要两步验证密码"}}))
            return
        if kind == "authorizationStateReady":
            self._ready = True
            save_auth_state("ready", "已连接")
            asyncio.create_task(self.bus.publish({"event": "auth", "data": {"state": "ready", "detail": "已连接"}}))


def _find_file_id(payload: Dict[str, Any]) -> Optional[int]:
    if not isinstance(payload, dict):
        return None
    if "file" in payload and isinstance(payload["file"], dict):
        fid = payload["file"].get("id")
        if isinstance(fid, int):
            return fid
    for value in payload.values():
        if isinstance(value, dict):
            fid = _find_file_id(value)
            if fid is not None:
                return fid
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    fid = _find_file_id(item)
                    if fid is not None:
                        return fid
    return None
