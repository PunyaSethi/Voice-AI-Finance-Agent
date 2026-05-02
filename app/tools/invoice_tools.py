from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from app.db import crud
from app.db.database import SessionLocal, init_db
from app.db.models import Invoice
from app.utils.helpers import compact_text, parse_amount, parse_iso_datetime


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


def _invoice_to_dict(invoice: Invoice) -> dict[str, Any]:
    return {
        "id": invoice.id,
        "client_name": invoice.client_name,
        "amount": float(invoice.amount),
        "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
        "status": invoice.status,
        "created_at": invoice.created_at.isoformat() if invoice.created_at else None,
        "updated_at": invoice.updated_at.isoformat() if getattr(invoice, "updated_at", None) else None,
        "deleted_at": invoice.deleted_at.isoformat() if getattr(invoice, "deleted_at", None) else None,
    }


def create_invoice(data: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = data or {}
    client_name = compact_text(
        payload.get("client_name") or payload.get("customer_name") or payload.get("client")
    )
    if not client_name:
        raise ValueError("client_name is required")

    amount = parse_amount(payload.get("amount"))
    due_date = parse_iso_datetime(payload.get("due_date"))

    with _session_scope() as db:
        invoice = crud.create_invoice(
            db=db,
            client_name=client_name,
            amount=amount,
            due_date=due_date,
        )
        return _invoice_to_dict(invoice)


def get_all_invoices(data: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    payload = data or {}
    start_date = parse_iso_datetime(payload.get("start_date"))
    end_date = parse_iso_datetime(payload.get("end_date"))
    with _session_scope() as db:
        return [
            _invoice_to_dict(invoice)
            for invoice in crud.get_all_invoices(db, start_date=start_date, end_date=end_date)
        ]


def get_invoice_summary(data: dict[str, Any] | None = None) -> dict[str, Any]:
    invoices = get_all_invoices(data)
    total = sum(invoice["amount"] for invoice in invoices)
    pending = [invoice for invoice in invoices if invoice["status"] == "pending"]
    paid = [invoice for invoice in invoices if invoice["status"] == "paid"]
    return {
        "count": len(invoices),
        "total_amount": round(total, 2),
        "pending_count": len(pending),
        "pending_amount": round(sum(invoice["amount"] for invoice in pending), 2),
        "paid_count": len(paid),
        "paid_amount": round(sum(invoice["amount"] for invoice in paid), 2),
        "items": invoices,
    }


def get_invoice_by_id(invoice_id: int | str) -> dict[str, Any] | None:
    with _session_scope() as db:
        invoice = crud.get_invoice_by_id(db, int(invoice_id))
        return _invoice_to_dict(invoice) if invoice else None


def mark_invoice_paid(invoice_id: int | str) -> dict[str, Any] | None:
    with _session_scope() as db:
        invoice = crud.mark_invoice_paid(db, int(invoice_id))
        return _invoice_to_dict(invoice) if invoice else None


def delete_invoice(invoice_id: int | str) -> dict[str, Any] | None:
    with _session_scope() as db:
        invoice = crud.delete_invoice(db, int(invoice_id))
        if invoice is None:
            raise ValueError("invoice not found")
        return _invoice_to_dict(invoice)


def update_invoice(data: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = data or {}
    invoice_id = payload.get("invoice_id") or payload.get("id")
    if not invoice_id:
        raise ValueError("invoice_id is required")

    client_name = compact_text(payload.get("client_name"))
    amount = parse_amount(payload.get("amount")) if payload.get("amount") is not None else None
    due_date = parse_iso_datetime(payload.get("due_date")) if payload.get("due_date") else None
    status = compact_text(payload.get("status")) or None
    if client_name is None and amount is None and due_date is None and status is None:
        raise ValueError("at least one field is required")

    with _session_scope() as db:
        invoice = crud.update_invoice(
            db=db,
            invoice_id=int(invoice_id),
            client_name=client_name or None,
            amount=amount,
            due_date=due_date,
            status=status,
        )
        if invoice is None:
            raise ValueError("invoice not found")
        return _invoice_to_dict(invoice)
