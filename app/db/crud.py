from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.db import models


def create_invoice(db: Session, client_name: str, amount: float, due_date: datetime | None = None):
    invoice = models.Invoice(
        client_name=client_name,
        amount=amount,
        due_date=due_date,
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def get_all_invoices(db: Session, start_date: datetime | None = None, end_date: datetime | None = None):
    query = db.query(models.Invoice)
    query = query.filter(models.Invoice.deleted_at.is_(None))
    if start_date:
        query = query.filter(models.Invoice.created_at >= start_date)
    if end_date:
        query = query.filter(models.Invoice.created_at < end_date)
    return query.order_by(models.Invoice.created_at.desc()).all()


def get_invoice_by_id(db: Session, invoice_id: int):
    return (
        db.query(models.Invoice)
        .filter(models.Invoice.id == invoice_id, models.Invoice.deleted_at.is_(None))
        .first()
    )


def mark_invoice_paid(db: Session, invoice_id: int):
    invoice = get_invoice_by_id(db, invoice_id)
    if invoice is None:
        return None
    invoice.status = "paid"
    db.commit()
    db.refresh(invoice)
    return invoice


def update_invoice(
    db: Session,
    invoice_id: int,
    client_name: str | None = None,
    amount: float | None = None,
    due_date: datetime | None = None,
    status: str | None = None,
):
    invoice = get_invoice_by_id(db, invoice_id)
    if invoice is None:
        return None
    if client_name is not None:
        invoice.client_name = client_name
    if amount is not None:
        invoice.amount = amount
    if due_date is not None:
        invoice.due_date = due_date
    if status is not None:
        invoice.status = status
    db.commit()
    db.refresh(invoice)
    return invoice


def delete_invoice(db: Session, invoice_id: int):
    invoice = get_invoice_by_id(db, invoice_id)
    if invoice is None:
        return None
    invoice.status = "deleted"
    invoice.deleted_at = datetime.now(UTC)
    db.commit()
    db.refresh(invoice)
    return invoice



def create_transaction(
    db: Session,
    type: str,
    amount: float,
    category: str = None,
    description: str = None
):
    transaction = models.Transaction(
        type=type,
        amount=amount,
        category=category,
        description=description
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


def get_all_transactions(db: Session):
    return get_transactions(db)


def get_transactions(
    db: Session,
    type: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
):
    query = db.query(models.Transaction)
    query = query.filter(models.Transaction.deleted_at.is_(None))
    if type:
        query = query.filter(models.Transaction.type == type)
    if start_date:
        query = query.filter(models.Transaction.created_at >= start_date)
    if end_date:
        query = query.filter(models.Transaction.created_at < end_date)
    return query.order_by(models.Transaction.created_at.desc()).all()


def get_transactions_by_type(db: Session, type: str):
    return get_transactions(db, type=type)


def update_transaction(
    db: Session,
    transaction_id: int,
    type: str | None = None,
    amount: float | None = None,
    category: str | None = None,
    description: str | None = None,
):
    transaction = (
        db.query(models.Transaction)
        .filter(models.Transaction.id == transaction_id, models.Transaction.deleted_at.is_(None))
        .first()
    )
    if transaction is None:
        return None
    if type is not None:
        transaction.type = type
    if amount is not None:
        transaction.amount = amount
    if category is not None:
        transaction.category = category
    if description is not None:
        transaction.description = description
    db.commit()
    db.refresh(transaction)
    return transaction


def delete_transaction(db: Session, transaction_id: int):
    transaction = (
        db.query(models.Transaction)
        .filter(models.Transaction.id == transaction_id, models.Transaction.deleted_at.is_(None))
        .first()
    )
    if transaction is None:
        return None
    transaction.deleted_at = datetime.now(UTC)
    db.commit()
    db.refresh(transaction)
    return transaction



def create_reminder(db: Session, title: str, due_at: datetime | None = None):
    reminder = models.Reminder(title=title, due_at=due_at)
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder


def get_all_reminders(db: Session, status: str | None = None):
    query = db.query(models.Reminder)
    query = query.filter(models.Reminder.deleted_at.is_(None))
    if status:
        query = query.filter(models.Reminder.status == status)
    return query.order_by(models.Reminder.created_at.desc()).all()


def get_reminder_by_id(db: Session, reminder_id: int):
    return (
        db.query(models.Reminder)
        .filter(models.Reminder.id == reminder_id, models.Reminder.deleted_at.is_(None))
        .first()
    )


def mark_reminder_done(db: Session, reminder_id: int):
    reminder = get_reminder_by_id(db, reminder_id)
    if reminder is None:
        return None
    reminder.status = "done"
    reminder.completed_at = datetime.now(UTC)
    db.commit()
    db.refresh(reminder)
    return reminder


def update_reminder(
    db: Session,
    reminder_id: int,
    title: str | None = None,
    due_at: datetime | None = None,
    status: str | None = None,
):
    reminder = get_reminder_by_id(db, reminder_id)
    if reminder is None:
        return None
    if title is not None:
        reminder.title = title
    if due_at is not None:
        reminder.due_at = due_at
    if status is not None:
        reminder.status = status
    db.commit()
    db.refresh(reminder)
    return reminder


def delete_reminder(db: Session, reminder_id: int):
    reminder = get_reminder_by_id(db, reminder_id)
    if reminder is None:
        return None
    reminder.status = "deleted"
    reminder.deleted_at = datetime.now(UTC)
    db.commit()
    db.refresh(reminder)
    return reminder



def create_interaction(
    db: Session,
    role: str,
    content: str,
    route: str | None = None,
    action: str | None = None,
):
    interaction = models.Interaction(role=role, content=content, route=route, action=action)
    db.add(interaction)
    db.commit()
    db.refresh(interaction)
    return interaction


def get_recent_interactions(db: Session, limit: int = 10):
    return db.query(models.Interaction).order_by(models.Interaction.created_at.desc()).limit(limit).all()
