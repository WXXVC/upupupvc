from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from .db import get_connection


@dataclass
class DownloadTask:
    id: int
    url: str
    file_type: str
    status: str
    progress: float
    speed: float
    downloaded: int
    total_size: int
    error: Optional[str]
    save_path: Optional[str]
    filename: Optional[str]
    retries: int


def create_tasks(urls: Iterable[str]) -> List[int]:
    ids: List[int] = []
    with get_connection() as conn:
        for url in urls:
            cur = conn.execute(
                """
                INSERT INTO download_tasks (url, file_type, status)
                VALUES (:url, :file_type, 'pending')
                """,
                {"url": url, "file_type": "unknown"},
            )
            ids.append(cur.lastrowid)
        conn.commit()
    return ids


def list_tasks(status: Optional[str] = None, search: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[DownloadTask]:
    where = []
    params = {}
    if status:
        where.append("status = :status")
        params["status"] = status
    if search:
        where.append("(url LIKE :q OR filename LIKE :q)")
        params["q"] = f"%{search}%"
    clause = " WHERE " + " AND ".join(where) if where else ""
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM download_tasks{clause} ORDER BY id DESC LIMIT :limit OFFSET :offset",
            {**params, "limit": limit, "offset": offset},
        ).fetchall()
    return [
        DownloadTask(
            id=row["id"],
            url=row["url"],
            file_type=row["file_type"],
            status=row["status"],
            progress=row["progress"],
            speed=row["speed"],
            downloaded=row["downloaded"],
            total_size=row["total_size"],
            error=row["error"],
            save_path=row["save_path"],
            filename=row["filename"],
            retries=row["retries"],
        )
        for row in rows
    ]


def get_task(task_id: int) -> Optional[DownloadTask]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM download_tasks WHERE id = :id",
            {"id": task_id},
        ).fetchone()
    if not row:
        return None
    return DownloadTask(
        id=row["id"],
        url=row["url"],
        file_type=row["file_type"],
        status=row["status"],
        progress=row["progress"],
        speed=row["speed"],
        downloaded=row["downloaded"],
        total_size=row["total_size"],
        error=row["error"],
        save_path=row["save_path"],
        filename=row["filename"],
        retries=row["retries"],
    )


def update_task(task_id: int, **fields) -> None:
    if not fields:
        return
    fields["id"] = task_id
    assignments = ", ".join([f"{k} = :{k}" for k in fields if k != "id"])
    with get_connection() as conn:
        conn.execute(
            f"""
            UPDATE download_tasks
            SET {assignments}, updated_at = CURRENT_TIMESTAMP
            WHERE id = :id
            """,
            fields,
        )
        conn.commit()
