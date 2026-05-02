from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from app.db import crud
from app.db.database import SessionLocal, init_db
from app.db.models import Transaction
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


def _transaction_to_dict(transaction: Transaction) -> dict[str, Any]:
    return {
        "id": transaction.id,
        "type": transaction.type,
        "amount": float(transaction.amount),
        "category": transaction.category,
        "description": transaction.description,
        "created_at": transaction.created_at.isoformat() if transaction.created_at else None,
        "updated_at": transaction.updated_at.isoformat() if getattr(transaction, "updated_at", None) else None,
        "deleted_at": transaction.deleted_at.isoformat() if getattr(transaction, "deleted_at", None) else None,
    }


def add_transaction(data: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = data or {}
    transaction_type = compact_text(payload.get("type") or payload.get("transaction_type")).lower()
    if transaction_type in {"credit", "income", "inflow"}:
        transaction_type = "income"
    elif transaction_type in {"debit", "expense", "spend", "outflow"}:
        transaction_type = "expense"
    else:
        raise ValueError("type must be one of: income, expense")

    amount = parse_amount(payload.get("amount"))
    category = compact_text(payload.get("category")) or None
    description = compact_text(payload.get("description") or payload.get("note")) or None

    with _session_scope() as db:
        transaction = crud.create_transaction(
            db=db,
            type=transaction_type,
            amount=amount,
            category=category,
            description=description,
        )
        return _transaction_to_dict(transaction)


def get_all_transactions(data: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    payload = data or {}
    start_date = parse_iso_datetime(payload.get("start_date"))
    end_date = parse_iso_datetime(payload.get("end_date"))
    transaction_type = compact_text(payload.get("type") or payload.get("transaction_type")).lower() or None
    with _session_scope() as db:
        return [
            _transaction_to_dict(transaction)
            for transaction in crud.get_transactions(
                db,
                type=transaction_type,
                start_date=start_date,
                end_date=end_date,
            )
        ]


def get_transactions_by_type(type: str) -> list[dict[str, Any]]:
    transaction_type = compact_text(type).lower()
    with _session_scope() as db:
        return [
            _transaction_to_dict(transaction)
            for transaction in crud.get_transactions_by_type(db, transaction_type)
        ]


def delete_transaction(transaction_id: int | str) -> dict[str, Any] | None:
    with _session_scope() as db:
        transaction = crud.delete_transaction(db, int(transaction_id))
        if transaction is None:
            raise ValueError("transaction not found")
        return _transaction_to_dict(transaction)


def update_transaction(data: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = data or {}
    transaction_id = payload.get("transaction_id") or payload.get("id")
    if not transaction_id:
        raise ValueError("transaction_id is required")

    transaction_type = compact_text(payload.get("type") or payload.get("transaction_type")).lower() or None
    if transaction_type in {"credit", "income", "inflow"}:
        transaction_type = "income"
    elif transaction_type in {"debit", "expense", "spend", "outflow"}:
        transaction_type = "expense"
    elif transaction_type:
        raise ValueError("type must be one of: income, expense")

    amount = parse_amount(payload.get("amount")) if payload.get("amount") is not None else None
    category = compact_text(payload.get("category")) or None
    description = compact_text(payload.get("description") or payload.get("note")) or None
    if transaction_type is None and amount is None and category is None and description is None:
        raise ValueError("at least one field is required")

    with _session_scope() as db:
        transaction = crud.update_transaction(
            db=db,
            transaction_id=int(transaction_id),
            type=transaction_type,
            amount=amount,
            category=category,
            description=description,
        )
        if transaction is None:
            raise ValueError("transaction not found")
        return _transaction_to_dict(transaction)


def get_balance() -> dict[str, float]:
    transactions = get_all_transactions()
    balance = 0.0
    for transaction in transactions:
        if transaction["type"] == "income":
            balance += transaction["amount"]
        else:
            balance -= transaction["amount"]
    return {"balance": round(balance, 2)}


def summarize_transactions(data: dict[str, Any] | None = None) -> dict[str, Any]:
    transactions = get_all_transactions(data)
    income = sum(item["amount"] for item in transactions if item["type"] == "income")
    expenses = sum(item["amount"] for item in transactions if item["type"] == "expense")
    by_category: dict[str, float] = {}

    for item in transactions:
        if item["type"] != "expense":
            continue
        category = item.get("category") or "uncategorized"
        by_category[category] = round(by_category.get(category, 0.0) + item["amount"], 2)

    return {
        "transaction_count": len(transactions),
        "income_total": round(income, 2),
        "expense_total": round(expenses, 2),
        "net_total": round(income - expenses, 2),
        "expense_by_category": by_category,
        "items": transactions,
    }
