from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.agents.orchestrator import Orchestrator
from app.config import get_settings
from app.db.database import engine
from app.llm.memory import ConversationMemory
from app.observability.metrics import metrics_store
from app.security.auth import require_api_key
from app.security.rate_limit import rate_limit_request
from app.tools.invoice_tools import (
    create_invoice,
    delete_invoice,
    get_all_invoices,
    get_invoice_summary,
    mark_invoice_paid,
    update_invoice,
)
from app.tools.reminder_tools import (
    create_reminder,
    delete_reminder,
    get_all_reminders,
    mark_reminder_done,
    update_reminder,
)
from app.tools.transaction_tools import (
    add_transaction,
    delete_transaction,
    get_all_transactions,
    summarize_transactions,
    update_transaction,
)
from app.utils.logger import get_logger
from app.voice.tts import TextToSpeech


public_router = APIRouter()
router = APIRouter(dependencies=[Depends(require_api_key), Depends(rate_limit_request)])

logger = get_logger(__name__)
orchestrator = Orchestrator()
memory = ConversationMemory()
tts = TextToSpeech()


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    response: str
    route: str | None = None
    action: str | None = None
    data: Any = None
    plan: list[str] = Field(default_factory=list)
    error: str | None = None
    audio_url: str | None = None


class InvoiceCreateRequest(BaseModel):
    client_name: str = Field(..., min_length=1, max_length=200)
    amount: float | str = Field(..., examples=[5000])
    due_date: str | None = Field(default=None, max_length=80)


class InvoiceUpdateRequest(BaseModel):
    client_name: str | None = Field(default=None, max_length=200)
    amount: float | str | None = Field(default=None, examples=[5000])
    due_date: str | None = Field(default=None, max_length=80)
    status: str | None = Field(default=None, max_length=40)


class TransactionCreateRequest(BaseModel):
    type: str = Field(..., pattern="^(income|expense|credit|debit|inflow|outflow|spend)$")
    amount: float | str = Field(..., examples=[250])
    category: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class TransactionUpdateRequest(BaseModel):
    type: str | None = Field(default=None, pattern="^(income|expense|credit|debit|inflow|outflow|spend)$")
    amount: float | str | None = Field(default=None, examples=[250])
    category: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class ReminderCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    due_at: str | None = None


class ReminderUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    due_at: str | None = None
    status: str | None = Field(default=None, max_length=40)


@public_router.get("/health")
def health_check():
    return {"status": "ok"}


@public_router.get("/ready")
def readiness_check():
    settings = get_settings()
    checks: dict[str, Any] = {
        "database": False,
        "data_dir": settings.data_dir.exists(),
        "audio_output_dir": settings.audio_output_dir.exists(),
        "faiss_index_dir": settings.faiss_index_dir.exists(),
        "ffmpeg": shutil.which("ffmpeg") is not None,
    }

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception as exc:
        logger.warning("Readiness database check failed: %s", exc)

    return {
        "status": "ready" if checks["database"] else "degraded",
        "checks": checks,
    }


@public_router.get("/capabilities")
def capabilities():
    return {
        "text_chat": True,
        "browser_voice_stt": False,
        "backend_whisper_stt": shutil.which("ffmpeg") is not None,
        "backend_tts": True,
        "rag": True,
        "memory": True,
        "database": get_settings().database_url,
    }


@public_router.get("/metrics")
def metrics():
    if not get_settings().enable_metrics:
        raise HTTPException(status_code=404, detail="Metrics disabled")
    return metrics_store.snapshot()


@router.post("/chat", response_model=ChatResponse)
def chat_endpoint(payload: ChatRequest):
    try:
        result = orchestrator.run(payload.message)
        audio_path = tts.synthesize(result["response"])
        if audio_path:
            result["audio_url"] = f"/audio/{Path(audio_path).name}"
        return ChatResponse(**result)
    except Exception as exc:
        logger.exception("Chat request failed")
        raise HTTPException(status_code=500, detail="Chat request failed") from exc


@router.get("/invoices")
def list_invoices():
    return {"items": get_all_invoices({})}


@router.post("/invoices", status_code=201)
def create_invoice_endpoint(payload: InvoiceCreateRequest):
    try:
        return create_invoice(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/invoices/{invoice_id}")
def update_invoice_endpoint(invoice_id: int, payload: InvoiceUpdateRequest):
    try:
        data = payload.model_dump(exclude_unset=True)
        data["invoice_id"] = invoice_id
        return update_invoice(data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/invoices/summary")
def invoice_summary():
    return get_invoice_summary({})


@router.patch("/invoices/{invoice_id}/paid")
def mark_invoice_paid_endpoint(invoice_id: int):
    invoice = mark_invoice_paid(invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.delete("/invoices/{invoice_id}")
def delete_invoice_endpoint(invoice_id: int):
    try:
        return delete_invoice(invoice_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/transactions")
def list_transactions():
    return {"items": get_all_transactions({})}


@router.post("/transactions", status_code=201)
def create_transaction_endpoint(payload: TransactionCreateRequest):
    try:
        return add_transaction(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/transactions/{transaction_id}")
def update_transaction_endpoint(transaction_id: int, payload: TransactionUpdateRequest):
    try:
        data = payload.model_dump(exclude_unset=True)
        data["transaction_id"] = transaction_id
        return update_transaction(data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/transactions/summary")
def transaction_summary():
    return summarize_transactions({})


@router.delete("/transactions/{transaction_id}")
def delete_transaction_endpoint(transaction_id: int):
    try:
        return delete_transaction(transaction_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/reminders")
def list_reminders():
    return {"items": get_all_reminders({})}


@router.post("/reminders", status_code=201)
def create_reminder_endpoint(payload: ReminderCreateRequest):
    try:
        return create_reminder(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/reminders/{reminder_id}")
def update_reminder_endpoint(reminder_id: int, payload: ReminderUpdateRequest):
    try:
        data = payload.model_dump(exclude_unset=True)
        data["reminder_id"] = reminder_id
        return update_reminder(data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/reminders/{reminder_id}/done")
def mark_reminder_done_endpoint(reminder_id: int):
    reminder = mark_reminder_done(reminder_id)
    if reminder is None:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return reminder


@router.delete("/reminders/{reminder_id}")
def delete_reminder_endpoint(reminder_id: int):
    try:
        return delete_reminder(reminder_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/memory")
def recent_memory():
    return {"items": memory.recent(limit=20)}
