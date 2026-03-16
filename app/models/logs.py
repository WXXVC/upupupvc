from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .db import get_connection


@dataclass
class LogItem:
    id: int
    level: str
    message: str
    created_at: str


def add_log(level: str, message: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO logs (level, message) VALUES (:level, :message)",
            {"level": level, "message": message},
        )
        conn.commit()


def list_logs(limit: int = 200, level: Optional[str] = None, q: Optional[str] = None) -> List[LogItem]:
    where = []
    params = {"limit": limit}
    if level:
        where.append("level = :level")
        params["level"] = level
    if q:
        where.append("message LIKE :q")
        params["q"] = f"%{q}%"
    clause = " WHERE " + " AND ".join(where) if where else ""
    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM logs{clause} ORDER BY id DESC LIMIT :limit",
            params,
        ).fetchall()
    return [
        LogItem(id=row["id"], level=row["level"], message=row["message"], created_at=row["created_at"])
        for row in rows
    ]
