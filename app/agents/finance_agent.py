from __future__ import annotations

import re
from typing import Any

from app.utils.helpers import parse_amount, parse_due_time, parse_period


class FinanceAgent:
    def plan(self, user_input: str) -> dict[str, Any]:
        text = user_input.lower()
        period = parse_period(user_input)

        if self._is_reminder_request(text):
            if any(word in text for word in ["done", "complete", "completed", "mark"]):
                return {"action": "mark_reminder_done", "data": self._extract_id_data(user_input, "reminder_id")}
            if any(word in text for word in ["create", "set", "add", "remind"]):
                return {"action": "create_reminder", "data": self._extract_reminder_data(user_input)}
            return {"action": "get_reminders", "data": {}}

        if self._is_invoice_request(text):
            if any(word in text for word in ["summary", "summarize", "total", "outstanding"]):
                return {"action": "invoice_summary", "data": period or {}}
            if any(word in text for word in ["paid", "mark"]):
                return {"action": "mark_invoice_paid", "data": self._extract_id_data(user_input, "invoice_id")}
            if any(word in text for word in ["create", "make", "raise", "generate", "new"]):
                return {"action": "create_invoice", "data": self._extract_invoice_data(user_input)}
            return {"action": "get_invoices", "data": period or {}}

        if self._is_transaction_request(text):
            if any(word in text for word in ["add", "record", "create", "log"]):
                return {"action": "add_transaction", "data": self._extract_transaction_data(user_input)}
            if any(word in text for word in ["how much", "summary", "summarize", "spend", "spent", "income"]):
                data = period or {}
                if any(word in text for word in ["spend", "spent", "expense", "expenses"]):
                    data["type"] = "expense"
                return {"action": "summarize_transactions", "data": data}
            return {"action": "get_transactions", "data": period or {}}

        if any(word in text for word in ["balance", "cash position", "net cash"]):
            return {"action": "get_balance", "data": {}}

        return {"action": "unknown", "data": {}}

    def run(self, user_input: str) -> dict[str, Any]:
        return self.plan(user_input)

    def _is_invoice_request(self, text: str) -> bool:
        return any(word in text for word in ["invoice", "invoices", "bill", "bills"])

    def _is_transaction_request(self, text: str) -> bool:
        return any(
            word in text
            for word in [
                "transaction",
                "transactions",
                "spending",
                "expense",
                "expenses",
                "spend",
                "spent",
                "income",
                "cash flow",
            ]
        )

    def _is_reminder_request(self, text: str) -> bool:
        return any(word in text for word in ["reminder", "remind", "task"])

    def _extract_invoice_data(self, user_input: str) -> dict[str, Any]:
        amount = self._extract_amount(user_input)
        client = self._extract_client(user_input)
        due_at = parse_due_time(user_input)
        return {
            "client_name": client,
            "amount": amount,
            "due_date": due_at,
        }

    def _extract_transaction_data(self, user_input: str) -> dict[str, Any]:
        text = user_input.lower()
        amount = self._extract_amount(user_input)
        transaction_type = "expense" if any(word in text for word in ["expense", "spent", "paid", "debit"]) else "income"
        category = self._extract_category(user_input)
        return {
            "type": transaction_type,
            "amount": amount,
            "category": category or "general",
            "description": user_input,
        }

    def _extract_reminder_data(self, user_input: str) -> dict[str, Any]:
        title = re.sub(r"(?i)\b(remind me to|set a reminder to|set reminder to|add reminder to|create reminder to)\b", "", user_input)
        title = re.sub(r"(?i)\b(today|tomorrow|next week)\b.*", "", title).strip(" .")
        return {
            "title": title or user_input,
            "due_at": parse_due_time(user_input),
        }

    def _extract_id_data(self, user_input: str, field_name: str) -> dict[str, Any]:
        match = re.search(r"\b(\d+)\b", user_input)
        return {field_name: int(match.group(1)) if match else None}

    def _extract_amount(self, user_input: str) -> float | None:
        match = re.search(
            r"(?:₹|rs\.?|inr|\$)?\s*\d+(?:,\d{3})*(?:\.\d+)?\s*(?:k|lakh|lakhs)?",
            user_input,
            re.IGNORECASE,
        )
        if not match:
            return None
        return parse_amount(match.group(0))

    def _extract_client(self, user_input: str) -> str | None:
        matches = re.findall(r"\b(?:for|to|client)\s+([A-Za-z][A-Za-z &.-]{1,60})", user_input, re.IGNORECASE)
        if matches:
            return matches[-1].strip(" .")
        return None

    def _extract_category(self, user_input: str) -> str | None:
        match = re.search(r"\b(?:for|on|category)\s+([A-Za-z][A-Za-z &.-]{1,40})", user_input, re.IGNORECASE)
        if match:
            return match.group(1).strip(" .")
        return None
