from app.agents.action_agent import ActionAgent
from app.agents.finance_agent import FinanceAgent
from app.agents.orchestrator import Orchestrator
from app.agents.planner import CommandPlan, StructuredPlanner


class FakePlanner:
    def __init__(self, plan: CommandPlan):
        self.plan_result = plan

    def plan(self, user_input, recent_messages=None):
        return self.plan_result


class FakeActionAgent:
    def __init__(self, result):
        self.result = result

    def run(self, task):
        return self.result


def test_finance_agent_routes_invoice_listing():
    task = FinanceAgent().run("show all invoices")

    assert task["action"] == "get_invoices"
    assert task["data"] == {}


def test_finance_agent_extracts_invoice_amount_and_client():
    task = FinanceAgent().run("create invoice for 10k for Aman")

    assert task["action"] == "create_invoice"
    assert task["data"]["client_name"] == "Aman"
    assert task["data"]["amount"] == 10000.0


def test_finance_agent_extracts_rupee_amounts():
    task = FinanceAgent().run("create invoice for ₹5,000 for Rahul")

    assert task["action"] == "create_invoice"
    assert task["data"]["client_name"] == "Rahul"
    assert task["data"]["amount"] == 5000.0


def test_finance_agent_summarizes_spending_periods():
    task = FinanceAgent().run("how much did I spend last week")

    assert task["action"] == "summarize_transactions"
    assert task["data"]["type"] == "expense"
    assert "start_date" in task["data"]


def test_finance_agent_extracts_reminder_request():
    task = FinanceAgent().run("remind me to send invoice tomorrow at 10am")

    assert task["action"] == "create_reminder"
    assert "send invoice" in task["data"]["title"].lower()
    assert task["data"]["due_at"] is not None


def test_action_agent_returns_structured_error_for_unknown_action():
    result = ActionAgent().execute("missing_tool", {})

    assert result["ok"] is False
    assert "Unknown action" in result["error"]


def test_orchestrator_routes_finance_requests():
    orchestrator = Orchestrator(
        planner=FakePlanner(
            CommandPlan(
                route="finance",
                action="get_transactions",
                arguments={},
                confidence=1.0,
            )
        ),
        research_agent=None,
    )

    assert orchestrator.route_agent("show my transactions") == "finance"


def test_orchestrator_uses_structured_planner_for_delete():
    orchestrator = Orchestrator(
        planner=FakePlanner(
            CommandPlan(
                route="finance",
                action="delete_reminder",
                arguments={"reminder_id": 1},
                confidence=1.0,
            )
        ),
        action_agent=FakeActionAgent({"ok": True, "error": None, "data": {"id": 1, "title": "Call Rahul"}}),
        research_agent=None,
    )

    result = orchestrator.run("delete reminder 1")
    assert result["route"] == "finance"
    assert result["action"] == "delete_reminder"
    assert result["response"].lower().startswith("deleted reminder")
