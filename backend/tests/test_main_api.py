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
