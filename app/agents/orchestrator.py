from __future__ import annotations

from typing import Any

from app.agents.action_agent import ActionAgent
from app.agents.finance_agent import FinanceAgent
from app.agents.planner import CommandPlan, StructuredPlanner
from app.agents.research_agent import ResearchAgent
from app.llm.memory import ConversationMemory


class Orchestrator:
    def __init__(
        self,
        finance_agent: FinanceAgent | None = None,
        research_agent: ResearchAgent | None = None,
        action_agent: ActionAgent | None = None,
        planner: StructuredPlanner | None = None,
        memory: ConversationMemory | None = None,
    ):
        self.finance_agent = finance_agent or FinanceAgent()
        self.research_agent = research_agent or ResearchAgent()
        self.action_agent = action_agent or ActionAgent()
        self.planner = planner or StructuredPlanner()
        self.memory = memory or ConversationMemory()

    def route_agent(self, user_input: str) -> str:
        return self.plan(user_input).route

    def plan(self, user_input: str) -> CommandPlan:
        recent = self.memory.recent(limit=6)
        return self.planner.plan(user_input, recent_messages=recent)

    def run(self, user_input: str) -> dict[str, Any]:
        self.memory.add(role="user", content=user_input)
        plan = self._normalize_plan(user_input, self.plan(user_input))
        route = plan.route
        action = plan.action

        if plan.needs_clarification or route == "clarify":
            response_text = plan.clarification_question or "I need a little more detail before I can act on that."
            result = self._response(
                text=response_text,
                route=route,
                action=action,
                data={"arguments": plan.arguments},
                plan=self._build_plan(route, action, plan),
                error="clarification_required",
            )
            self.memory.add("assistant", result["response"], route=route, action=action)
            return result

        if route == "finance":
            task = {"action": action, "data": plan.arguments}
            if action in {"unknown", "answer_question"}:
                task = self.finance_agent.run(user_input)
                task["data"] = {**task.get("data", {}), **plan.arguments}

            validation_error = self._validate_task(action, task.get("data", {}))
            if validation_error:
                result = self._response(
                    text=validation_error,
                    route=route,
                    action=action,
                    data={"required": True},
                    plan=self._build_plan(route, action, plan),
                    error="clarification_required",
                )
                self.memory.add("assistant", result["response"], route=route, action=action)
                return result

            execution = self.action_agent.run(task)
            if not execution["ok"]:
                result = self._response(
                    text=f"I couldn't complete that action: {execution['error']}",
                    route=route,
                    action=action,
                    data=None,
                    plan=self._build_plan(route, action, plan),
                    error=execution["error"],
                )
                self.memory.add("assistant", result["response"], route=route, action=action)
                return result

            result = self._response(
                text=self._summarize_action(action, execution["data"]),
                route=route,
                action=action,
                data=execution["data"],
                plan=self._build_plan(route, action, plan),
            )
            self.memory.add("assistant", result["response"], route=route, action=action)
            return result

        task = self.research_agent.run(user_input)
        result = self._response(
            text=task.get("result", "I don't have enough information to answer that yet."),
            route=route,
            action=task.get("action"),
            data=task.get("data"),
            plan=self._build_plan(route, task.get("action"), plan),
        )
        self.memory.add("assistant", result["response"], route=route, action=task.get("action"))
        return result

    def _response(
        self,
        text: str,
        route: str,
        action: str | None,
        data: Any,
        plan: list[str] | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        return {
            "response": text,
            "route": route,
            "action": action,
            "data": data,
            "plan": plan or [],
            "error": error,
        }

    def _validate_task(self, action: str, data: dict[str, Any]) -> str | None:
        if action == "create_invoice":
            missing = []
            if not data.get("client_name"):
                missing.append("client name")
            if not data.get("amount"):
                missing.append("amount")
            if missing:
                return f"I can create that invoice, but I need the {' and '.join(missing)}."

        if action == "add_transaction":
            if not data.get("amount"):
                return "I can record that transaction, but I need the amount."

        if action in {"update_invoice", "update_transaction", "update_reminder"}:
            update_fields = {
                "update_invoice": ["client_name", "amount", "due_date", "status"],
                "update_transaction": ["type", "amount", "category", "description"],
                "update_reminder": ["title", "due_at", "status"],
            }[action]
            if not any(data.get(field) is not None for field in update_fields):
                return "I need at least one field to update."
            id_field = {
                "update_invoice": "invoice_id",
                "update_transaction": "transaction_id",
                "update_reminder": "reminder_id",
            }[action]
            if not data.get(id_field):
                return f"Which {id_field.replace('_', ' ')} should I update?"

        if action == "mark_invoice_paid" and not data.get("invoice_id"):
            return "Which invoice ID should I mark as paid?"

        if action == "mark_reminder_done" and not data.get("reminder_id"):
            return "Which reminder ID should I mark as done?"

        if action in {"delete_invoice", "delete_transaction", "delete_reminder"}:
            id_field = {
                "delete_invoice": "invoice_id",
                "delete_transaction": "transaction_id",
                "delete_reminder": "reminder_id",
            }[action]
            if not data.get(id_field):
                return f"Which {id_field.replace('_', ' ')} should I delete?"

        return None

    def _normalize_plan(self, user_input: str, plan: CommandPlan) -> CommandPlan:
        text = user_input.lower()
        show_verbs = ["show", "list", "view", "display", "see", "what are", "what is", "give me", "all my"]
        create_verbs = ["create", "add", "make", "generate", "new", "record", "log", "set up"]

        if plan.route != "finance":
            return plan

        if plan.action == "create_invoice" and "invoice" in text:
            if any(verb in text for verb in show_verbs) and not any(verb in text for verb in create_verbs):
                return plan.model_copy(update={"action": "get_invoices", "arguments": {}})

        if plan.action == "add_transaction" and any(term in text for term in ["transaction", "expense", "income", "spend", "spent"]):
            if any(verb in text for verb in show_verbs) and not any(verb in text for verb in create_verbs):
                return plan.model_copy(update={"action": "get_transactions", "arguments": {}})

        if plan.action == "create_reminder" and any(term in text for term in ["reminder", "remind", "task"]):
            if any(verb in text for verb in show_verbs) and not any(verb in text for verb in create_verbs):
                return plan.model_copy(update={"action": "get_reminders", "arguments": {}})

        return plan

    def _build_plan(self, route: str, action: str | None, plan: CommandPlan | None = None) -> list[str]:
        steps = []
        if plan and plan.reasoning:
            steps.append(f"Planner reasoning: {plan.reasoning}")
        if plan and plan.needs_clarification:
            steps.append("Pause for clarification")
            return steps
        return [
            f"Route request to {route} agent",
            f"Execute action: {action or 'answer_question'}",
            "Respond with text, structured data, and voice output",
        ]

    def _summarize_action(self, action: str, data: Any) -> str:
        if action == "get_invoices":
            count = len(data or [])
            if count == 0:
                return "I couldn't find any invoices yet."
            preview = self._summarize_invoice_list(data)
            return f"I found {count} invoice{'s' if count != 1 else ''}. {preview}"
        if action == "invoice_summary":
            return (
                f"Invoice summary: {data['count']} invoices totaling {self._format_amount(data['total_amount'])}. "
                f"Pending amount is {self._format_amount(data['pending_amount'])} across {data['pending_count']} invoices."
            )
        if action == "create_invoice":
            return (
                f"Created invoice {data['id']} for {data['client_name']} "
                f"worth {self._format_amount(data['amount'])}."
            )
        if action == "mark_invoice_paid":
            return f"Marked invoice {data['id']} as paid."
        if action == "delete_invoice":
            if not data:
                return "I couldn't find that invoice to delete."
            return f"Deleted invoice {data['id']}."
        if action == "get_transactions":
            count = len(data or [])
            if count == 0:
                return "I couldn't find any transactions yet."
            preview = self._summarize_transaction_list(data)
            return f"I found {count} transaction{'s' if count != 1 else ''}. {preview}"
        if action == "summarize_transactions":
            return (
                f"Financial summary: income {self._format_amount(data['income_total'])}, "
                f"expenses {self._format_amount(data['expense_total'])}, "
                f"net {self._format_amount(data['net_total'])}."
            )
        if action == "add_transaction":
            return f"Recorded a {data['type']} transaction of {self._format_amount(data['amount'])}."
        if action == "get_balance":
            return f"Current balance is {self._format_amount(data['balance'])}."
        if action == "delete_transaction":
            if not data:
                return "I couldn't find that transaction to delete."
            return f"Deleted transaction {data['id']}."
        if action == "create_reminder":
            return f"Created reminder: {data['title']}."
        if action == "get_reminders":
            count = len(data or [])
            if count == 0:
                return "I couldn't find any reminders yet."
            reminder = data[0]
            return f"I found {count} reminder{'s' if count != 1 else ''}. Latest reminder: {reminder['title']}."
        if action == "mark_reminder_done":
            return f"Marked reminder {data['id']} as done."
        if action == "delete_reminder":
            if not data:
                return "I couldn't find that reminder to delete."
            return f"Deleted reminder {data['id']}."
        if action == "update_invoice":
            return f"Updated invoice {data['id']}."
        if action == "update_transaction":
            return f"Updated transaction {data['id']}."
        if action == "update_reminder":
            return f"Updated reminder {data['id']}."
        return "Action completed."

    def _summarize_invoice_list(self, invoices: list[dict[str, Any]]) -> str:
        invoice = invoices[0]
        return (
            f"Latest invoice {invoice['id']} is for {invoice['client_name']}, "
            f"amount {self._format_amount(invoice['amount'])}, status {invoice['status']}."
        )

    def _summarize_transaction_list(self, transactions: list[dict[str, Any]]) -> str:
        transaction = transactions[0]
        category = transaction.get("category") or "uncategorized"
        return (
            f"Latest transaction is a {transaction['type']} of "
            f"{self._format_amount(transaction['amount'])} for {category}."
        )

    def _format_amount(self, amount: float | int) -> str:
        return f"{float(amount):,.2f}"
