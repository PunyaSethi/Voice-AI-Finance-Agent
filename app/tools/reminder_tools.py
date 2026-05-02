from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from app.db import crud
from app.db.database import SessionLocal, init_db
from app.db.models import Reminder
from app.utils.helpers import compact_text, parse_iso_datetime


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


def _reminder_to_dict(reminder: Reminder) -> dict[str, Any]:
    return {
        "id": reminder.id,
        "title": reminder.title,
        "due_at": reminder.due_at.isoformat() if reminder.due_at else None,
        "status": reminder.status,
        "created_at": reminder.created_at.isoformat() if reminder.created_at else None,
        "updated_at": reminder.updated_at.isoformat() if getattr(reminder, "updated_at", None) else None,
        "deleted_at": reminder.deleted_at.isoformat() if getattr(reminder, "deleted_at", None) else None,
        "completed_at": reminder.completed_at.isoformat() if reminder.completed_at else None,
    }


def create_reminder(data: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = data or {}
    title = compact_text(payload.get("title") or payload.get("description"))
    due_at = parse_iso_datetime(payload.get("due_at") or payload.get("due_time") or payload.get("due_date"))

    if not title:
        raise ValueError("title is required")

    with _session_scope() as db:
        reminder = crud.create_reminder(db=db, title=title, due_at=due_at)
        return _reminder_to_dict(reminder)


def get_all_reminders(data: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    payload = data or {}
    status = compact_text(payload.get("status")).lower() or None
    with _session_scope() as db:
        return [_reminder_to_dict(reminder) for reminder in crud.get_all_reminders(db, status=status)]


def get_pending_reminders() -> list[dict[str, Any]]:
    return get_all_reminders({"status": "pending"})


def mark_reminder_done(reminder_id: int | str) -> dict[str, Any] | None:
    with _session_scope() as db:
        reminder = crud.mark_reminder_done(db, int(reminder_id))
        return _reminder_to_dict(reminder) if reminder else None


def delete_reminder(reminder_id: int | str) -> dict[str, Any] | None:
    with _session_scope() as db:
        reminder = crud.delete_reminder(db, int(reminder_id))
        if reminder is None:
            raise ValueError("reminder not found")
        return _reminder_to_dict(reminder)


def update_reminder(data: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = data or {}
    reminder_id = payload.get("reminder_id") or payload.get("id")
    if not reminder_id:
        raise ValueError("reminder_id is required")

    title = compact_text(payload.get("title") or payload.get("description")) or None
    due_at = parse_iso_datetime(payload.get("due_at") or payload.get("due_time") or payload.get("due_date"))
    status = compact_text(payload.get("status")).lower() or None
    if title is None and due_at is None and status is None:
        raise ValueError("at least one field is required")

    with _session_scope() as db:
        reminder = crud.update_reminder(
            db=db,
            reminder_id=int(reminder_id),
            title=title,
            due_at=due_at,
            status=status,
        )
        if reminder is None:
            raise ValueError("reminder not found")
        return _reminder_to_dict(reminder)
