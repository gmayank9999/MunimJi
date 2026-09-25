import asyncio

import pytest
from fastapi.testclient import TestClient

from app.settings import get_settings


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "test.db"))
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
