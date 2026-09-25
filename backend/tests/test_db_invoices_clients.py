import pytest

from app.db import Database


@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.connect()
    yield database
    await database.close()


async def test_upsert_and_get_client(db):
    await db.upsert_client(
        client_id="C01", name="Orion Retail", email="orion@x.com", tier="Regular", contact_name="Rohit"
    )
    row = await db.get_client("C01")
    assert row["name"] == "Orion Retail"
    assert row["tier"] == "Regular"


async def test_upsert_client_is_idempotent_update(db):
    await db.upsert_client(
        client_id="C01", name="Orion Retail", email="orion@x.com", tier="Regular", contact_name="Rohit"
    )
    await db.upsert_client(
        client_id="C01", name="Orion Retail Pvt Ltd", email="orion@x.com", tier="VIP", contact_name="Rohit"
    )
    row = await db.get_client("C01")
    assert row["name"] == "Orion Retail Pvt Ltd"
    assert row["tier"] == "VIP"


async def test_list_clients_sorted_by_name(db):
    await db.upsert_client(client_id="C02", name="Zephyr Hotels", email="z@x.com", tier="VIP", contact_name="Ananya")
    await db.upsert_client(client_id="C01", name="Bluepeak Media", email="b@x.com", tier="Regular", contact_name="Neha")
    rows = await db.list_clients()
    assert [r["name"] for r in rows] == ["Bluepeak Media", "Zephyr Hotels"]


async def test_upsert_and_get_invoice(db):
    await db.upsert_invoice(
        invoice_id="INV2-1", number="INV-1077", client_id="C01", status="SENT",
        amount_inr=85000, due_inr=85000, invoice_date="2026-09-14", due_date="2026-09-24",
    )
    row = await db.get_invoice("INV2-1")
    assert row["number"] == "INV-1077"
    assert row["due_inr"] == 85000


async def test_upsert_invoice_updates_existing_row(db):
    await db.upsert_invoice(
        invoice_id="INV2-1", number="INV-1077", client_id="C01", status="SENT",
        amount_inr=85000, due_inr=85000, invoice_date="2026-09-14", due_date="2026-09-24",
    )
    await db.upsert_invoice(
        invoice_id="INV2-1", number="INV-1077", client_id="C01", status="PAID",
        amount_inr=85000, due_inr=0, invoice_date="2026-09-14", due_date="2026-09-24",
    )
    row = await db.get_invoice("INV2-1")
    assert row["status"] == "PAID"
    assert row["due_inr"] == 0


async def test_list_invoices_sorted_by_due_date(db):
    await db.upsert_invoice(
        invoice_id="a", number="INV-2", client_id="C01", status="SENT",
        amount_inr=1000, due_inr=1000, invoice_date="2026-09-01", due_date="2026-09-20",
    )
    await db.upsert_invoice(
        invoice_id="b", number="INV-1", client_id="C01", status="SENT",
        amount_inr=1000, due_inr=1000, invoice_date="2026-09-01", due_date="2026-09-10",
    )
    rows = await db.list_invoices()
    assert [r["invoice_id"] for r in rows] == ["b", "a"]


async def test_insert_decision_and_get_trace(db):
    await db.insert_decision(
        run_id="r1", invoice_id="inv1", as_of="2026-09-25T10:00:00+05:30",
        facts_json={"days_overdue": 11}, signal_json={"category": "NO_RESPONSE"},
        severity=78, severity_breakdown_json={"aging": 18.3}, decision="ESCALATE", rule_id="R18",
        reasons_json=["11 days overdue"], plan_json=[], results_json=[],
        explanation="escalated", created_at="2026-09-25T10:00:00+05:30",
    )
    trace = await db.get_invoice_trace("inv1")
    assert len(trace) == 1
    assert trace[0]["decision"] == "ESCALATE"
    assert trace[0]["severity"] == 78


async def test_compute_kpis_reflects_overdue_invoices(db):
    await db.upsert_invoice(
        invoice_id="a", number="INV-1", client_id="C01", status="SENT",
        amount_inr=85000, due_inr=85000, invoice_date="2026-09-01", due_date="2026-09-14",
    )
    await db.upsert_invoice(
        invoice_id="b", number="INV-2", client_id="C01", status="SENT",
        amount_inr=8000, due_inr=8000, invoice_date="2026-09-20", due_date="2026-09-30",
    )
    kpis = await db.compute_kpis(today="2026-09-25")
    assert kpis["outstanding_inr"] == 93000
    assert kpis["overdue_inr"] == 85000
