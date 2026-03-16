from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from .db import get_connection


@dataclass
class UploadTask:
    id: int
    source_path: str
    target_channel: Optional[str]
    status: str
    progress: float
    speed: float
    uploaded: int
    total_size: int
    error: Optional[str]
    description: Optional[str]
    file_id: Optional[int]
    part_index: Optional[int]
    part_total: Optional[int]


def create_task(
    source_path: str,
    target_channel: Optional[str],
    description: Optional[str] = None,
    part_index: Optional[int] = None,
    part_total: Optional[int] = None,
) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO upload_tasks (source_path, target_channel, status, description, part_index, part_total)
            VALUES (:source_path, :target_channel, 'pending', :description, :part_index, :part_total)
            """,
            {
                "source_path": source_path,
                "target_channel": target_channel,
                "description": description,
                "part_index": part_index,
                "part_total": part_total,
            },
        )
        conn.commit()
        return cur.lastrowid


def list_tasks(status: Optional[str] = None, search: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[UploadTask]:
    where = []
    params = {}
    if status:
        where.append("status = :status")
        params["status"] = status
    if search:
        where.append("(source_path LIKE :q OR description LIKE :q)")
        params["q"] = f"%{search}%"
    clause = " WHERE " + " AND ".join(where) if where else ""
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM upload_tasks{clause} ORDER BY id DESC LIMIT :limit OFFSET :offset",
            {**params, "limit": limit, "offset": offset},
        ).fetchall()
    return [
        UploadTask(
            id=row["id"],
            source_path=row["source_path"],
            target_channel=row["target_channel"],
            status=row["status"],
            progress=row["progress"],
            speed=row["speed"],
            uploaded=row["uploaded"],
            total_size=row["total_size"],
            error=row["error"],
            description=row["description"],
            file_id=row["file_id"],
            part_index=row["part_index"],
            part_total=row["part_total"],
        )
        for row in rows
    ]


def get_task(task_id: int) -> Optional[UploadTask]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM upload_tasks WHERE id = :id",
            {"id": task_id},
        ).fetchone()
    if not row:
        return None
    return UploadTask(
        id=row["id"],
        source_path=row["source_path"],
        target_channel=row["target_channel"],
        status=row["status"],
        progress=row["progress"],
        speed=row["speed"],
        uploaded=row["uploaded"],
        total_size=row["total_size"],
        error=row["error"],
        description=row["description"],
        file_id=row["file_id"],
        part_index=row["part_index"],
        part_total=row["part_total"],
    )


def update_task(task_id: int, **fields) -> None:
    if not fields:
        return
    fields["id"] = task_id
    assignments = ", ".join([f"{k} = :{k}" for k in fields if k != "id"])
    with get_connection() as conn:
        conn.execute(
            f"""
            UPDATE upload_tasks
            SET {assignments}, updated_at = CURRENT_TIMESTAMP
            WHERE id = :id
            """,
            fields,
        )
        conn.commit()
