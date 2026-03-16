from __future__ import annotations

from dataclasses import dataclass
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
    configured=False,
)


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
            configured=bool(row["configured"]),
        )


def save_config(data: dict) -> None:
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
    }
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
                configured = :configured,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
            """,
            {**fields, "configured": 1 if configured else 0},
        )
        conn.commit()


def is_configured() -> bool:
    return load_config().configured
