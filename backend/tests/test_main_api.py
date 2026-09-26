import asyncio

import pytest
from fastapi.testclient import TestClient

from app.settings import get_settings


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("EXTENSION_KEY", "test-ext-key")
    # The lifespan's background pollers make real Slack calls on a timer - TestClient
    # runs the full lifespan per test, so leaving this on made unrelated tests flaky/hang
    # on live network calls that cancel() can't reliably interrupt mid-flight.
    monkeypatch.setenv("ENABLE_BACKGROUND_POLLERS", "false")
    get_settings.cache_clear()
    from app.main import app

    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_invoices_empty_by_default(client):
    r = client.get("/api/invoices")
    assert r.status_code == 200
    assert r.json() == []


def test_clients_empty_by_default(client):
    r = client.get("/api/clients")
    assert r.status_code == 200
    assert r.json() == []


def test_invoice_trace_empty_for_unknown_invoice(client):
    r = client.get("/api/invoices/does-not-exist/trace")
    assert r.status_code == 200
    assert r.json() == []


def test_kpis_zero_by_default(client):
    r = client.get("/api/kpis")
    assert r.status_code == 200
    data = r.json()
    assert data["outstanding_inr"] == 0
    assert data["overdue_inr"] == 0
    assert data["decisions_today"] == 0


def test_policy_returns_config_and_decision_table(client):
    r = client.get("/api/policy")
    assert r.status_code == 200
    data = r.json()
    assert data["config"]["grace_days"] == 2
    assert data["config"]["escalate_amount_inr"] == 50000
    assert "R01" in data["decision_table_markdown"]


def test_invoices_report_xlsx_downloads_with_the_right_headers(client):
    r = client.get("/api/reports/invoices.xlsx")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert "attachment" in r.headers["content-disposition"]
    assert r.content[:2] == b"PK"  # xlsx is a zip archive


def test_invoices_report_pdf_downloads_with_the_right_headers(client):
    r = client.get("/api/reports/invoices.pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert "attachment" in r.headers["content-disposition"]
    assert r.content[:5] == b"%PDF-"


def test_runs_list_empty_by_default(client):
    r = client.get("/api/runs")
    assert r.status_code == 200
    assert r.json() == []


def test_run_not_found_returns_404(client):
    r = client.get("/api/runs/does-not-exist")
    assert r.status_code == 404


def test_audit_returns_tool_calls_and_swytchcode_data(client):
    r = client.get("/api/audit")
    assert r.status_code == 200
    data = r.json()
    assert data["tool_calls"] == []
    assert isinstance(data["swytchcode_policy_log"], list)
    assert isinstance(data["swytchcode_stats"], dict)


def test_approvals_list_empty_by_default(client):
    r = client.get("/api/approvals")
    assert r.status_code == 200
    assert r.json() == []


def test_approve_unknown_idem_key_returns_404(client):
    r = client.post("/api/approvals/does-not-exist/approve")
    assert r.status_code == 404


def test_reject_unknown_idem_key_returns_404(client):
    r = client.post("/api/approvals/does-not-exist/reject")
    assert r.status_code == 404


async def _plan_pending_approval(app, *, idem_key: str, tool: str) -> None:
    from app.governance.ledger import Ledger

    ledger = Ledger(app.state.db)
    await ledger.plan(
        idem_key=idem_key, run_id="r1", invoice_id="inv1", action_type="gmail_escalation",
        tool=tool, payload={}, created_at="2026-09-26T10:00:00+05:30",
    )
    await ledger.pending_approval(idem_key, updated_at="2026-09-26T10:00:00+05:30")


def test_approve_appears_in_pending_list_then_clears_after_resolving(client):
    asyncio.run(_plan_pending_approval(client.app, idem_key="k1", tool="jira.issue.create"))

    r = client.get("/api/approvals")
    assert r.status_code == 200
    assert [row["idem_key"] for row in r.json()] == ["k1"]

    r = client.post("/api/approvals/k1/approve")
    assert r.status_code == 200
    assert r.json()["ok"] is False  # no approval executor wired for jira - fails locally, doesn't crash

    r = client.get("/api/approvals")
    assert r.json() == []  # resolved, no longer pending


def test_reject_clears_pending_approval(client):
    asyncio.run(_plan_pending_approval(client.app, idem_key="k2", tool="jira.issue.create"))

    r = client.post("/api/approvals/k2/reject")
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"

    r = client.get("/api/approvals")
    assert r.json() == []


EXT_HEADERS = {"X-MunimJi-Ext-Key": "test-ext-key"}


def test_ext_routes_reject_missing_key(client):
    assert client.get("/api/ext/lookup", params={"email": "x@example.com"}).status_code == 401
    assert client.get("/api/ext/approvals").status_code == 401
    assert client.post("/api/ext/approvals/k1/approve").status_code == 401
    assert client.post("/api/ext/approvals/k1/reject").status_code == 401


def test_ext_routes_reject_wrong_key(client):
    r = client.get(
        "/api/ext/lookup", params={"email": "x@example.com"}, headers={"X-MunimJi-Ext-Key": "wrong"}
    )
    assert r.status_code == 401


def test_ext_lookup_unknown_email_returns_404(client):
    r = client.get("/api/ext/lookup", params={"email": "nobody@example.com"}, headers=EXT_HEADERS)
    assert r.status_code == 404


async def _upsert_client(app, *, client_id: str, email: str) -> None:
    await app.state.db.upsert_client(
        client_id=client_id, name="Orion Retail", email=email, tier="Regular",
        contact_name="Rohit Malhotra", relationship_notes="", notion_page_id="page1", paused_until=None,
    )


def test_ext_lookup_returns_client_and_their_invoices(client):
    asyncio.run(_upsert_client(client.app, client_id="C01", email="mayankguptawp+orion@gmail.com"))

    r = client.get(
        "/api/ext/lookup", params={"email": "MayankGuptaWp+Orion@Gmail.com"}, headers=EXT_HEADERS
    )
    assert r.status_code == 200
    data = r.json()
    assert data["client"]["client_id"] == "C01"
    assert data["invoices"] == []


async def _upsert_invoice(app, *, invoice_id: str, client_id: str, due_date: str) -> None:
    await app.state.db.upsert_invoice(
        invoice_id=invoice_id, number="INV-TEST", client_id=client_id, status="open",
        amount_inr=10000, due_inr=10000, invoice_date="2026-01-01", due_date=due_date,
        reminder_count=0, last_reminder_at=None, last_client_msg_at=None, promise_date=None,
        promise_source_msg=None, dispute_open=0, jira_key=None, notion_page_id=None,
        state="Watching", last_decision=None, last_severity=None, updated_at="2026-01-01T00:00:00+05:30",
    )


def test_ext_lookup_computes_days_overdue_from_the_simulated_clock_not_real_time(client, monkeypatch):
    """The extension's badge showed '0 days overdue' for a genuinely ~12-day-overdue
    invoice - it was computing against the browser's real date instead of the demo's
    CLOCK_OFFSET_DAYS-shifted 'today', which every due_date is itself seeded relative to."""
    from datetime import date

    from app.clock import Clock

    monkeypatch.setenv("CLOCK_OFFSET_DAYS", "10")
    get_settings.cache_clear()
    asyncio.run(_upsert_client(client.app, client_id="C01", email="mayankguptawp+orion@gmail.com"))
    asyncio.run(_upsert_invoice(client.app, invoice_id="in_1", client_id="C01", due_date="2026-01-01"))

    expected_overdue = (Clock(offset_days=10).today() - date(2026, 1, 1)).days

    r = client.get(
        "/api/ext/lookup", params={"email": "mayankguptawp+orion@gmail.com"}, headers=EXT_HEADERS
    )
    assert r.status_code == 200
    assert r.json()["invoices"][0]["days_overdue"] == expected_overdue


def test_ext_approvals_list_and_resolve_with_key(client):
    asyncio.run(_plan_pending_approval(client.app, idem_key="k3", tool="jira.issue.create"))

    r = client.get("/api/ext/approvals", headers=EXT_HEADERS)
    assert r.status_code == 200
    assert [row["idem_key"] for row in r.json()] == ["k3"]

    r = client.post("/api/ext/approvals/k3/reject", headers=EXT_HEADERS)
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"
