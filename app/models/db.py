import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
LEGACY_DB_PATH = BASE_DIR / "data.db"
DATA_DIR = Path(os.getenv("APP_DATA_DIR", str(BASE_DIR / "data")))
PRIMARY_DB_PATH = Path(os.getenv("APP_DB_PATH", str(DATA_DIR / "data.db")))


def _resolve_db_path() -> Path:
    search_dir = PRIMARY_DB_PATH.parent
    migrated = [path for path in search_dir.glob("data.migrated*.db") if path.exists() and path.stat().st_size > 0]
    if not migrated:
        if PRIMARY_DB_PATH.exists():
            return PRIMARY_DB_PATH
        if LEGACY_DB_PATH.exists():
            return LEGACY_DB_PATH
        return PRIMARY_DB_PATH
    migrated.sort(key=lambda path: path.stat().st_mtime)
    return migrated[-1]


DB_PATH = _resolve_db_path()


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=MEMORY")
    conn.execute("PRAGMA synchronous=OFF")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS config (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                api_id TEXT,
                api_hash TEXT,
                phone_number TEXT,
                target_channel TEXT,
                download_path TEXT,
                max_download_concurrency INTEGER DEFAULT 1,
                range_download_concurrency INTEGER DEFAULT 2,
                ytdlp_fragment_concurrency INTEGER DEFAULT 1,
                split_threshold_mb INTEGER DEFAULT 2048,
                download_postprocess TEXT DEFAULT 'keep',
                upload_postprocess TEXT DEFAULT 'keep',
                upload_postprocess_path TEXT,
                auto_upload INTEGER DEFAULT 1,
                proxy_enabled INTEGER DEFAULT 0,
                proxy_type TEXT DEFAULT 'http',
                proxy_host TEXT,
                proxy_port INTEGER,
                proxy_username TEXT,
                proxy_password TEXT,
                transcode_video_codec TEXT DEFAULT 'h264',
                transcode_video_format TEXT DEFAULT 'mp4',
                transcode_image_format TEXT DEFAULT 'jpg',
                access_password_hash TEXT,
                access_password_salt TEXT,
                configured INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        _ensure_config_column(conn, "phone_number", "TEXT")
        _ensure_config_column(conn, "upload_postprocess_path", "TEXT")
        _ensure_config_column(conn, "auto_upload", "INTEGER")
        _ensure_config_column(conn, "range_download_concurrency", "INTEGER")
        _ensure_config_column(conn, "ytdlp_fragment_concurrency", "INTEGER")
        _ensure_config_column(conn, "proxy_enabled", "INTEGER")
        _ensure_config_column(conn, "proxy_type", "TEXT")
        _ensure_config_column(conn, "proxy_host", "TEXT")
        _ensure_config_column(conn, "proxy_port", "INTEGER")
        _ensure_config_column(conn, "proxy_username", "TEXT")
        _ensure_config_column(conn, "proxy_password", "TEXT")
        _ensure_config_column(conn, "transcode_video_codec", "TEXT")
        _ensure_config_column(conn, "transcode_video_format", "TEXT")
        _ensure_config_column(conn, "transcode_image_format", "TEXT")
        _ensure_config_column(conn, "access_password_hash", "TEXT")
        _ensure_config_column(conn, "access_password_salt", "TEXT")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT,
                message TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS download_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id INTEGER,
                url TEXT NOT NULL,
                download_format TEXT,
                file_type TEXT,
                status TEXT,
                progress REAL DEFAULT 0,
                speed REAL DEFAULT 0,
                downloaded INTEGER DEFAULT 0,
                total_size INTEGER DEFAULT 0,
                error TEXT,
                save_path TEXT,
                filename TEXT,
                retries INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        _ensure_download_column(conn, "batch_id", "INTEGER")
        _ensure_download_column(conn, "download_format", "TEXT")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS download_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                description TEXT,
                status TEXT DEFAULT 'pending',
                auto_upload INTEGER,
                transcode_video_codec TEXT,
                transcode_video_format TEXT,
                transcode_image_format TEXT,
                upload_postprocess TEXT,
                upload_postprocess_path TEXT,
                total_count INTEGER DEFAULT 0,
                completed_count INTEGER DEFAULT 0,
                failed_count INTEGER DEFAULT 0,
                progress REAL DEFAULT 0,
                error TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        _ensure_download_batch_column(conn, "auto_upload", "INTEGER")
        _ensure_download_batch_column(conn, "transcode_video_codec", "TEXT")
        _ensure_download_batch_column(conn, "transcode_video_format", "TEXT")
        _ensure_download_batch_column(conn, "transcode_image_format", "TEXT")
        _ensure_download_batch_column(conn, "upload_postprocess", "TEXT")
        _ensure_download_batch_column(conn, "upload_postprocess_path", "TEXT")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS upload_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id INTEGER,
                source_path TEXT NOT NULL,
                target_channel TEXT,
                status TEXT,
                progress REAL DEFAULT 0,
                speed REAL DEFAULT 0,
                uploaded INTEGER DEFAULT 0,
                total_size INTEGER DEFAULT 0,
                error TEXT,
                description TEXT,
                postprocess TEXT,
                postprocess_path TEXT,
                file_id INTEGER,
                part_index INTEGER,
                part_total INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        _ensure_upload_column(conn, "batch_id", "INTEGER")
        _ensure_upload_column(conn, "file_id", "INTEGER")
        _ensure_upload_column(conn, "postprocess", "TEXT")
        _ensure_upload_column(conn, "postprocess_path", "TEXT")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS upload_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                description TEXT,
                status TEXT DEFAULT 'pending',
                total_count INTEGER DEFAULT 0,
                completed_count INTEGER DEFAULT 0,
                failed_count INTEGER DEFAULT 0,
                progress REAL DEFAULT 0,
                error TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                state TEXT,
                detail TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            "INSERT OR IGNORE INTO config (id) VALUES (1)"
        )
        conn.execute(
            "INSERT OR IGNORE INTO auth_state (id, state) VALUES (1, 'idle')"
        )
        conn.commit()


def _ensure_config_column(conn: sqlite3.Connection, name: str, col_type: str) -> None:
    columns = [row[1] for row in conn.execute("PRAGMA table_info(config)").fetchall()]
    if name not in columns:
        conn.execute(f"ALTER TABLE config ADD COLUMN {name} {col_type}")


def _ensure_upload_column(conn: sqlite3.Connection, name: str, col_type: str) -> None:
    columns = [row[1] for row in conn.execute("PRAGMA table_info(upload_tasks)").fetchall()]
    if name not in columns:
        conn.execute(f"ALTER TABLE upload_tasks ADD COLUMN {name} {col_type}")


def _ensure_download_column(conn: sqlite3.Connection, name: str, col_type: str) -> None:
    columns = [row[1] for row in conn.execute("PRAGMA table_info(download_tasks)").fetchall()]
    if name not in columns:
        conn.execute(f"ALTER TABLE download_tasks ADD COLUMN {name} {col_type}")


def _ensure_download_batch_column(conn: sqlite3.Connection, name: str, col_type: str) -> None:
    columns = [row[1] for row in conn.execute("PRAGMA table_info(download_batches)").fetchall()]
    if name not in columns:
        conn.execute(f"ALTER TABLE download_batches ADD COLUMN {name} {col_type}")
