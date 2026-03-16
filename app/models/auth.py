from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .db import get_connection


@dataclass
class AuthState:
    state: str
    detail: Optional[str] = None


def load_auth_state() -> AuthState:
    with get_connection() as conn:
        row = conn.execute("SELECT state, detail FROM auth_state WHERE id = 1").fetchone()
        if not row:
            return AuthState(state="idle", detail=None)
        return AuthState(state=row["state"], detail=row["detail"])


def save_auth_state(state: str, detail: Optional[str] = None) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE auth_state
            SET state = :state,
                detail = :detail,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = 1
            """,
            {"state": state, "detail": detail},
        )
        conn.commit()
