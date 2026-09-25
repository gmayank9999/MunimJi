import pytest

from app.db import Database


@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.connect()
    yield database
    await database.close()


async def test_schema_creates_all_tables(db):
    rows = await db.fetchall("SELECT name FROM sqlite_master WHERE type='table'")
    names = {r["name"] for r in rows}
    expected = {
        "runs", "trace_events", "tool_calls", "invoices", "clients",
        "interpretations", "decisions", "action_ledger", "deferred_actions",
        "cursors", "llm_cache",
    }
    assert expected.issubset(names)


async def test_create_and_get_run(db):
    await db.create_run("r_1", "check all payments", "ui", 0, "2026-09-25T10:00:00+05:30")
    row = await db.get_run("r_1")
    assert row["run_id"] == "r_1"
    assert row["status"] == "running"


async def test_finish_run_stores_summary(db):
    await db.create_run("r_2", "prompt", "ui", 0, "2026-09-25T10:00:00+05:30")
    await db.finish_run("r_2", "2026-09-25T10:05:00+05:30", {"scanned": 18})
    row = await db.get_run("r_2")
    assert row["status"] == "finished"
    assert '"scanned": 18' in row["summary_json"]


async def test_trace_events_ordered_by_seq(db):
    await db.create_run("r_3", "prompt", "ui", 0, "2026-09-25T10:00:00+05:30")
    await db.insert_trace_event("r_3", 2, "t2", "rule_fired", "decide", "inv_1", {"b": 2})
    await db.insert_trace_event("r_3", 1, "t1", "run.started", "supervisor", None, {"a": 1})
    events = await db.get_trace_events("r_3")
    assert [e["seq"] for e in events] == [1, 2]
    assert events[0]["invoice_id"] is None


async def test_cursor_upsert(db):
    await db.set_cursor("paypal_watcher", "2026-09-25T00:00:00Z")
    assert await db.get_cursor("paypal_watcher") == "2026-09-25T00:00:00Z"
    await db.set_cursor("paypal_watcher", "2026-09-26T00:00:00Z")
    assert await db.get_cursor("paypal_watcher") == "2026-09-26T00:00:00Z"


async def test_missing_cursor_returns_none(db):
    assert await db.get_cursor("nope") is None
