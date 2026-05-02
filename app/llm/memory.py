from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from app.db import crud
from app.db.database import SessionLocal, init_db


@contextmanager
def _session_scope():
    init_db()
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


class ConversationMemory:
    def add(self, role: str, content: str, route: str | None = None, action: str | None = None) -> None:
        with _session_scope() as db:
            crud.create_interaction(db, role=role, content=content, route=route, action=action)

    def recent(self, limit: int = 10) -> list[dict[str, Any]]:
        with _session_scope() as db:
            interactions = crud.get_recent_interactions(db, limit=limit)
            return [
                {
                    "role": item.role,
                    "content": item.content,
                    "route": item.route,
                    "action": item.action,
                    "created_at": item.created_at.isoformat() if item.created_at else None,
                }
                for item in reversed(interactions)
            ]
