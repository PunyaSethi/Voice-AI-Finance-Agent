from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from app.llm.llm_provider import LLMProvider


Route = Literal["finance", "research", "clarify"]


class CommandPlan(BaseModel):
    route: Route
    action: str = "answer_question"
    arguments: dict[str, Any] = Field(default_factory=dict)
    needs_clarification: bool = False
    clarification_question: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reasoning: str | None = None


class StructuredPlanner:
    def __init__(self, llm_provider: LLMProvider | None = None):
        self.llm_provider = llm_provider or LLMProvider()

    def plan(self, user_input: str, recent_messages: list[dict[str, Any]] | None = None) -> CommandPlan:
        prompt = self._build_prompt(user_input, recent_messages or [])
        raw = self.llm_provider.generate_structured(prompt, temperature=0.0)

        if raw:
            try:
                return CommandPlan.model_validate(raw)
            except ValidationError:
                pass

        return self._fallback_plan(user_input)

    def _build_prompt(self, user_input: str, recent_messages: list[dict[str, Any]]) -> str:
        conversation = "\n".join(
            f"- {message.get('role', 'unknown')}: {message.get('content', '')}"
            for message in recent_messages[-6:]
        )

        return (
            "You are a strict command planner for a finance automation assistant.\n"
            "Return only valid JSON matching this schema:\n"
            "{"
            '"route":"finance|research|clarify",'
            '"action":"string",'
            '"arguments":{},'
            '"needs_clarification":true|false,'
            '"clarification_question":"string or null",'
            '"confidence":0.0,'
            '"reasoning":"short string or null"'
            "}\n"
            "Rules:\n"
            "- Choose finance for invoices, transactions, reminders, balances, and any database-changing command.\n"
            "- Choose research for questions that need explanation, analysis, or knowledge lookup.\n"
            "- Choose clarify when the command is ambiguous or missing critical identifiers.\n"
            "- Prefer executable actions such as create_invoice, delete_invoice, mark_invoice_paid, add_transaction, "
            "delete_transaction, create_reminder, mark_reminder_done, delete_reminder, get_invoices, get_transactions, "
            "get_reminders, invoice_summary, summarize_transactions, get_balance, answer_question.\n"
            "- For destructive actions, set route to finance and action to the concrete delete_* action.\n"
            "- Populate arguments with only the fields needed to execute the action.\n"
            "- If an identifier or required field is missing, ask a direct clarification question.\n"
            f"Recent conversation:\n{conversation or '- none'}\n"
            f"User request:\n{user_input}\n"
        )

    def _fallback_plan(self, user_input: str) -> CommandPlan:
        text = user_input.lower()

        finance_keywords = [
            "invoice",
            "payment",
            "expense",
            "transaction",
            "balance",
            "spending",
            "spend",
            "spent",
            "income",
            "reminder",
            "remind",
            "delete",
            "remove",
            "mark",
            "update",
            "edit",
            "change",
            "modify",
        ]
        research_keywords = ["market", "trend", "analysis", "research", "compare", "explain", "why", "how"]

        if any(word in text for word in finance_keywords):
            if "invoice" in text:
                if any(word in text for word in ["delete", "remove"]):
                    return CommandPlan(
                        route="finance",
                        action="delete_invoice",
                        arguments={"invoice_id": self._extract_id(text)},
                        confidence=0.45,
                    )
                if any(word in text for word in ["update", "edit", "change", "modify"]):
                    return CommandPlan(
                        route="finance",
                        action="update_invoice",
                        arguments={"invoice_id": self._extract_id(text)},
                        confidence=0.45,
                    )
                if any(word in text for word in ["paid", "mark"]):
                    return CommandPlan(
                        route="finance",
                        action="mark_invoice_paid",
                        arguments={"invoice_id": self._extract_id(text)},
                        confidence=0.45,
                    )
                if any(word in text for word in ["create", "make", "raise", "generate", "new"]):
                    return CommandPlan(route="finance", action="create_invoice", arguments={}, confidence=0.45)
                return CommandPlan(route="finance", action="get_invoices", arguments={}, confidence=0.4)

            if "transaction" in text or any(term in text for term in ["expense", "income", "spend", "spent"]):
                if any(word in text for word in ["delete", "remove"]):
                    return CommandPlan(
                        route="finance",
                        action="delete_transaction",
                        arguments={"transaction_id": self._extract_id(text)},
                        confidence=0.45,
                    )
                if any(word in text for word in ["update", "edit", "change", "modify"]):
                    return CommandPlan(
                        route="finance",
                        action="update_transaction",
                        arguments={"transaction_id": self._extract_id(text)},
                        confidence=0.45,
                    )
                if any(word in text for word in ["add", "record", "create", "log"]):
                    return CommandPlan(route="finance", action="add_transaction", arguments={}, confidence=0.45)
                if any(word in text for word in ["balance"]):
                    return CommandPlan(route="finance", action="get_balance", arguments={}, confidence=0.45)
                return CommandPlan(route="finance", action="summarize_transactions", arguments={}, confidence=0.4)

            if any(term in text for term in ["reminder", "remind", "task"]):
                if any(word in text for word in ["delete", "remove"]):
                    return CommandPlan(
                        route="finance",
                        action="delete_reminder",
                        arguments={"reminder_id": self._extract_id(text)},
                        confidence=0.45,
                    )
                if any(word in text for word in ["update", "edit", "change", "modify"]):
                    return CommandPlan(
                        route="finance",
                        action="update_reminder",
                        arguments={"reminder_id": self._extract_id(text)},
                        confidence=0.45,
                    )
                if any(word in text for word in ["done", "complete", "completed", "mark"]):
                    return CommandPlan(
                        route="finance",
                        action="mark_reminder_done",
                        arguments={"reminder_id": self._extract_id(text)},
                        confidence=0.45,
                    )
                if any(word in text for word in ["create", "set", "add", "remind"]):
                    return CommandPlan(route="finance", action="create_reminder", arguments={}, confidence=0.45)
                return CommandPlan(route="finance", action="get_reminders", arguments={}, confidence=0.4)

            return CommandPlan(route="finance", action="answer_question", arguments={"query": user_input}, confidence=0.3)
        if any(word in text for word in research_keywords):
            return CommandPlan(route="research", action="answer_question", arguments={"query": user_input}, confidence=0.35)

        return CommandPlan(route="research", action="answer_question", arguments={"query": user_input}, confidence=0.2)

    def _extract_id(self, text: str) -> int | None:
        import re

        match = re.search(r"\b(\d+)\b", text)
        return int(match.group(1)) if match else None
