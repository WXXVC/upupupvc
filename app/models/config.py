from __future__ import annotations

from dataclasses import dataclass
import hashlib
import secrets
from typing import Optional

from .db import get_connection


@dataclass
class Config:
    api_id: Optional[str]
    api_hash: Optional[str]
    phone_number: Optional[str]
    target_channel: Optional[str]
    download_path: Optional[str]
    max_download_concurrency: int
    split_threshold_mb: int
    download_postprocess: str
    upload_postprocess: str
    upload_postprocess_path: Optional[str]
    auto_upload: bool
    proxy_enabled: bool
    proxy_type: str
    proxy_host: Optional[str]
    proxy_port: Optional[int]
    proxy_username: Optional[str]
    proxy_password: Optional[str]
    transcode_video_codec: str
    transcode_video_format: str
    transcode_image_format: str
    access_password_hash: Optional[str]
    access_password_salt: Optional[str]
    configured: bool


DEFAULTS = Config(
    api_id=None,
    api_hash=None,
    phone_number=None,
    target_channel=None,
    download_path="./downloads",
    max_download_concurrency=3,
    split_threshold_mb=2048,
    download_postprocess="keep",
    upload_postprocess="keep",
    upload_postprocess_path=None,
    auto_upload=True,
    proxy_enabled=False,
    proxy_type="http",
    proxy_host=None,
    proxy_port=None,
    proxy_username=None,
    proxy_password=None,
    transcode_video_codec="h264",
    transcode_video_format="mp4",
    transcode_image_format="jpg",
    access_password_hash=None,
    access_password_salt=None,
    configured=False,
)


def mask_sensitive(value: Optional[str]) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if len(raw) <= 4:
        return raw[:1] + ("*" * max(len(raw) - 2, 1)) + raw[-1:]
    return raw[:2] + "****" + raw[-2:]


def hash_access_password(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()


def verify_access_password(password: str, cfg: Config) -> bool:
    if not cfg.access_password_hash or not cfg.access_password_salt:
        return True
    return hash_access_password(password, cfg.access_password_salt) == cfg.access_password_hash


def is_masked_sensitive_input(value: Optional[str], original: Optional[str]) -> bool:
    incoming = (value or "").strip()
    if not incoming:
        return False
    return incoming == mask_sensitive(original)


def to_public_dict(cfg: Config) -> dict:
    data = cfg.__dict__.copy()
    data["api_id"] = mask_sensitive(cfg.api_id)
    data["api_hash"] = mask_sensitive(cfg.api_hash)
    data["phone_number"] = mask_sensitive(cfg.phone_number)
    data["access_password_enabled"] = bool(cfg.access_password_hash and cfg.access_password_salt)
    data.pop("access_password_hash", None)
    data.pop("access_password_salt", None)
    return data


def load_config() -> Config:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM config WHERE id = 1").fetchone()
        if not row:
            return DEFAULTS
        return Config(
            api_id=row["api_id"],
            api_hash=row["api_hash"],
            phone_number=row["phone_number"],
            target_channel=row["target_channel"],
            download_path=row["download_path"],
            max_download_concurrency=row["max_download_concurrency"] or DEFAULTS.max_download_concurrency,
            split_threshold_mb=row["split_threshold_mb"] or DEFAULTS.split_threshold_mb,
            download_postprocess=row["download_postprocess"] or DEFAULTS.download_postprocess,
            upload_postprocess=row["upload_postprocess"] or DEFAULTS.upload_postprocess,
            upload_postprocess_path=row["upload_postprocess_path"],
            auto_upload=bool(row["auto_upload"]) if row["auto_upload"] is not None else True,
            proxy_enabled=bool(row["proxy_enabled"]) if row["proxy_enabled"] is not None else False,
            proxy_type=row["proxy_type"] or DEFAULTS.proxy_type,
            proxy_host=row["proxy_host"],
            proxy_port=row["proxy_port"],
            proxy_username=row["proxy_username"],
            proxy_password=row["proxy_password"],
            transcode_video_codec=row["transcode_video_codec"] or DEFAULTS.transcode_video_codec,
            transcode_video_format=row["transcode_video_format"] or DEFAULTS.transcode_video_format,
            transcode_image_format=row["transcode_image_format"] or DEFAULTS.transcode_image_format,
            access_password_hash=row["access_password_hash"],
            access_password_salt=row["access_password_salt"],
            configured=bool(row["configured"]),
        )


def save_config(data: dict) -> None:
    current = load_config()
    fields = {
        "api_id": data.get("api_id"),
        "api_hash": data.get("api_hash"),
        "phone_number": data.get("phone_number"),
        "target_channel": data.get("target_channel"),
        "download_path": data.get("download_path") or DEFAULTS.download_path,
        "max_download_concurrency": int(data.get("max_download_concurrency") or DEFAULTS.max_download_concurrency),
        "split_threshold_mb": int(data.get("split_threshold_mb") or DEFAULTS.split_threshold_mb),
        "download_postprocess": data.get("download_postprocess") or DEFAULTS.download_postprocess,
        "upload_postprocess": data.get("upload_postprocess") or DEFAULTS.upload_postprocess,
        "upload_postprocess_path": data.get("upload_postprocess_path"),
        "auto_upload": 1 if str(data.get("auto_upload", "1")).lower() in {"1", "true", "yes", "on"} else 0,
        "proxy_enabled": 1 if str(data.get("proxy_enabled", "0")).lower() in {"1", "true", "yes", "on"} else 0,
        "proxy_type": (data.get("proxy_type") or DEFAULTS.proxy_type).strip().lower(),
        "proxy_host": (data.get("proxy_host") or "").strip() or None,
        "proxy_port": data.get("proxy_port"),
        "proxy_username": (data.get("proxy_username") or "").strip() or None,
        "proxy_password": (data.get("proxy_password") or "").strip() or None,
        "transcode_video_codec": (data.get("transcode_video_codec") or DEFAULTS.transcode_video_codec).strip().lower(),
        "transcode_video_format": (data.get("transcode_video_format") or DEFAULTS.transcode_video_format).strip().lower(),
        "transcode_image_format": (data.get("transcode_image_format") or DEFAULTS.transcode_image_format).strip().lower(),
        "access_password_hash": current.access_password_hash,
        "access_password_salt": current.access_password_salt,
    }

    if is_masked_sensitive_input(fields["api_id"], current.api_id):
        fields["api_id"] = current.api_id
    if is_masked_sensitive_input(fields["api_hash"], current.api_hash):
        fields["api_hash"] = current.api_hash
    if is_masked_sensitive_input(fields["phone_number"], current.phone_number):
        fields["phone_number"] = current.phone_number

    fields["api_id"] = (fields["api_id"] or "").strip() or None
    fields["api_hash"] = (fields["api_hash"] or "").strip() or None
    fields["phone_number"] = (fields["phone_number"] or "").strip() or None
    fields["target_channel"] = (fields["target_channel"] or "").strip() or None

    access_password = (data.get("access_password") or "").strip()
    clear_access_password = str(data.get("clear_access_password") or "0").lower() in {"1", "true", "yes", "on"}
    if clear_access_password:
        fields["access_password_hash"] = None
        fields["access_password_salt"] = None
    elif access_password:
        salt = secrets.token_hex(16)
        fields["access_password_salt"] = salt
        fields["access_password_hash"] = hash_access_password(access_password, salt)

    proxy_port_raw = fields["proxy_port"]
    if proxy_port_raw in (None, ""):
        fields["proxy_port"] = None
    else:
        try:
            fields["proxy_port"] = int(proxy_port_raw)
        except (TypeError, ValueError):
            fields["proxy_port"] = None
    if fields["proxy_port"] is not None and not (1 <= fields["proxy_port"] <= 65535):
        fields["proxy_port"] = None
    if fields["proxy_type"] not in {"http", "socks5"}:
        fields["proxy_type"] = DEFAULTS.proxy_type
    if fields["transcode_video_codec"] not in {"h264", "hevc"}:
        fields["transcode_video_codec"] = DEFAULTS.transcode_video_codec
    if fields["transcode_video_format"] not in {"mp4", "mkv"}:
        fields["transcode_video_format"] = DEFAULTS.transcode_video_format
    if fields["transcode_image_format"] not in {"jpg", "png", "webp"}:
        fields["transcode_image_format"] = DEFAULTS.transcode_image_format
    if not fields["proxy_enabled"]:
        fields["proxy_host"] = None
        fields["proxy_port"] = None
        fields["proxy_username"] = None
        fields["proxy_password"] = None
    elif not fields["proxy_host"] or not fields["proxy_port"]:
        fields["proxy_enabled"] = 0

    configured = all([
        fields["api_id"],
        fields["api_hash"],
        fields["phone_number"],
        fields["target_channel"],
        fields["download_path"],
    ])
    max_conc = max(1, min(10, fields["max_download_concurrency"]))
    fields["max_download_concurrency"] = max_conc
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE config
            SET api_id = :api_id,
                api_hash = :api_hash,
                phone_number = :phone_number,
                target_channel = :target_channel,
                download_path = :download_path,
                max_download_concurrency = :max_download_concurrency,
                split_threshold_mb = :split_threshold_mb,
                download_postprocess = :download_postprocess,
                upload_postprocess = :upload_postprocess,
                upload_postprocess_path = :upload_postprocess_path,
                auto_upload = :auto_upload,
                proxy_enabled = :proxy_enabled,
                proxy_type = :proxy_type,
                proxy_host = :proxy_host,
                proxy_port = :proxy_port,
                proxy_username = :proxy_username,
                proxy_password = :proxy_password,
                transcode_video_codec = :transcode_video_codec,
                transcode_video_format = :transcode_video_format,
                transcode_image_format = :transcode_image_format,
                access_password_hash = :access_password_hash,
                access_password_salt = :access_password_salt,
                configured = :configured,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
            """,
            {**fields, "configured": 1 if configured else 0},
        )
        conn.commit()


def is_configured() -> bool:
    return load_config().configured
