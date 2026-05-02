from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_capabilities_endpoint():
    response = client.get("/api/capabilities")

    assert response.status_code == 200
    assert response.json()["database"].startswith("sqlite")


def test_readiness_endpoint_checks_runtime_dependencies():
    response = client.get("/api/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"ready", "degraded"}
    assert payload["checks"]["database"] is True


def test_chat_endpoint_returns_orchestrated_response():
    response = client.post("/api/chat", json={"message": "show invoices"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["route"] == "finance"
    assert payload["action"] == "get_invoices"
    assert "invoice" in payload["response"].lower()
    assert payload["plan"]
    assert "audio_url" in payload


def test_transaction_summary_endpoint():
    response = client.get("/api/transactions/summary")

    assert response.status_code == 200
    assert "expense_total" in response.json()


def test_direct_invoice_transaction_and_reminder_endpoints():
    invoice_response = client.post(
        "/api/invoices",
        json={"client_name": "Endpoint Client", "amount": "₹1,250"},
    )
    assert invoice_response.status_code == 201
    invoice = invoice_response.json()
    assert invoice["client_name"] == "Endpoint Client"
    assert invoice["amount"] == 1250.0

    update_response = client.patch(
        f"/api/invoices/{invoice['id']}",
        json={"client_name": "Updated Client", "amount": 1400},
    )
    assert update_response.status_code == 200
    assert update_response.json()["client_name"] == "Updated Client"

    paid_response = client.patch(f"/api/invoices/{invoice['id']}/paid")
    assert paid_response.status_code == 200
    assert paid_response.json()["status"] == "paid"

    transaction_response = client.post(
        "/api/transactions",
        json={"type": "expense", "amount": 250, "category": "food"},
    )
    assert transaction_response.status_code == 201
    assert transaction_response.json()["type"] == "expense"

    reminder_response = client.post(
        "/api/reminders",
        json={"title": "Pay rent"},
    )
    assert reminder_response.status_code == 201
    reminder = reminder_response.json()
    assert reminder["title"] == "Pay rent"

    reminder_update_response = client.patch(
        f"/api/reminders/{reminder['id']}",
        json={"title": "Pay rent updated"},
    )
    assert reminder_update_response.status_code == 200
    assert reminder_update_response.json()["title"] == "Pay rent updated"

    done_response = client.patch(f"/api/reminders/{reminder['id']}/done")
    assert done_response.status_code == 200
    assert done_response.json()["status"] == "done"

    delete_invoice_response = client.delete(f"/api/invoices/{invoice['id']}")
    assert delete_invoice_response.status_code == 200
    assert delete_invoice_response.json()["status"] == "deleted"

    delete_transaction_response = client.delete(f"/api/transactions/{transaction_response.json()['id']}")
    assert delete_transaction_response.status_code == 200
    assert delete_transaction_response.json()["deleted_at"] is not None

    delete_reminder_response = client.delete(f"/api/reminders/{reminder['id']}")
    assert delete_reminder_response.status_code == 200
    assert delete_reminder_response.json()["status"] == "deleted"


def test_memory_endpoint():
    response = client.get("/api/memory")

    assert response.status_code == 200
    assert "items" in response.json()


def test_chat_endpoint_allows_local_file_frontend_cors_preflight():
    response = client.options(
        "/api/chat",
        headers={
            "Origin": "null",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "null"


def test_chat_endpoint_allows_vscode_live_server_cors_preflight():
    response = client.options(
        "/api/chat",
        headers={
            "Origin": "http://127.0.0.1:5500",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5500"
