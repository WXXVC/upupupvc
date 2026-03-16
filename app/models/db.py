import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / "data.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
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
                tdlib_lib_path TEXT,
                tdlib_database_dir TEXT,
                tdlib_files_dir TEXT,
                tdlib_encryption_key TEXT,
                max_download_concurrency INTEGER DEFAULT 3,
                split_threshold_mb INTEGER DEFAULT 2048,
                download_postprocess TEXT DEFAULT 'keep',
                upload_postprocess TEXT DEFAULT 'keep',
                upload_postprocess_path TEXT,
                auto_upload INTEGER DEFAULT 1,
                configured INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        _ensure_config_column(conn, "phone_number", "TEXT")
        _ensure_config_column(conn, "tdlib_lib_path", "TEXT")
        _ensure_config_column(conn, "tdlib_database_dir", "TEXT")
        _ensure_config_column(conn, "tdlib_files_dir", "TEXT")
        _ensure_config_column(conn, "tdlib_encryption_key", "TEXT")
        _ensure_config_column(conn, "upload_postprocess_path", "TEXT")
        _ensure_config_column(conn, "auto_upload", "INTEGER")
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
                url TEXT NOT NULL,
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS upload_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_path TEXT NOT NULL,
                target_channel TEXT,
                status TEXT,
                progress REAL DEFAULT 0,
                speed REAL DEFAULT 0,
                uploaded INTEGER DEFAULT 0,
                total_size INTEGER DEFAULT 0,
                error TEXT,
                description TEXT,
                file_id INTEGER,
                part_index INTEGER,
                part_total INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        _ensure_upload_column(conn, "file_id", "INTEGER")
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
