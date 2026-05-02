from __future__ import annotations

from typing import Any, Callable

from app.tools.invoice_tools import (
    create_invoice,
    delete_invoice,
    get_all_invoices,
    get_invoice_summary,
    mark_invoice_paid,
    update_invoice,
)
from app.tools.reminder_tools import create_reminder, delete_reminder, get_all_reminders, mark_reminder_done, update_reminder
from app.tools.transaction_tools import (
    add_transaction,
    delete_transaction,
    get_all_transactions,
    get_balance,
    summarize_transactions,
    update_transaction,
)


class ActionAgent:
    def __init__(self):
        self._tools: dict[str, Callable[[dict[str, Any]], Any]] = {
            "create_invoice": create_invoice,
            "get_invoices": get_all_invoices,
            "invoice_summary": get_invoice_summary,
            "mark_invoice_paid": lambda data: mark_invoice_paid(data.get("invoice_id")),
            "delete_invoice": lambda data: delete_invoice(data.get("invoice_id")),
            "update_invoice": update_invoice,
            "add_transaction": add_transaction,
            "get_transactions": get_all_transactions,
            "summarize_transactions": summarize_transactions,
            "get_balance": lambda _data: get_balance(),
            "delete_transaction": lambda data: delete_transaction(data.get("transaction_id")),
            "update_transaction": update_transaction,
            "create_reminder": create_reminder,
            "get_reminders": get_all_reminders,
            "mark_reminder_done": lambda data: mark_reminder_done(data.get("reminder_id")),
            "delete_reminder": lambda data: delete_reminder(data.get("reminder_id")),
            "update_reminder": update_reminder,
        }

    def execute(self, action: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        tool = self._tools.get(action)
        if tool is None:
            return {"ok": False, "error": f"Unknown action: {action}", "data": None}

        try:
            result = tool(data or {})
            return {"ok": True, "error": None, "data": result}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "data": None}

    def run(self, task: dict[str, Any]) -> dict[str, Any]:
        return self.execute(task.get("action", "unknown"), task.get("data", {}))
