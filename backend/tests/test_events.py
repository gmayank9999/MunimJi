import pytest

from app.db import Database
from app.events import EventBus


@pytest.fixture
async def bus(tmp_path):
    db = Database(str(tmp_path / "events.db"))
    await db.connect()
    event_bus = EventBus(db)
    yield event_bus
    await db.close()


async def test_emit_persists_and_increments_seq(bus):
    await bus.db.create_run("r_1", "check all payments", "ui", 0, "2026-09-25T10:00:00+05:30")
    e1 = await bus.emit("r_1", "run.started", "supervisor", {"a": 1})
    e2 = await bus.emit("r_1", "insight", "sense", {"scanned": 18})
    assert e1["seq"] == 1
    assert e2["seq"] == 2
    assert e1["run_id"] == "r_1"


async def test_seq_is_independent_per_run(bus):
    await bus.emit("r_a", "run.started", "supervisor", {})
    e = await bus.emit("r_b", "run.started", "supervisor", {})
    assert e["seq"] == 1


async def test_replay_returns_events_in_order(bus):
    await bus.db.create_run("r_2", "prompt", "ui", 0, "2026-09-25T10:00:00+05:30")
    await bus.emit("r_2", "run.started", "supervisor", {})
    await bus.emit("r_2", "rule_fired", "decide", {"decision": "ESCALATE"}, invoice_id="inv_1")
    replayed = await bus.replay("r_2")
    assert [e["type"] for e in replayed] == ["run.started", "rule_fired"]
    assert replayed[1]["invoice_id"] == "inv_1"
    assert replayed[1]["payload"]["decision"] == "ESCALATE"


async def test_subscriber_receives_live_events(bus):
    queue = bus.subscribe("r_3")
    await bus.emit("r_3", "run.started", "supervisor", {})
    event = queue.get_nowait()
    assert event["type"] == "run.started"


async def test_unsubscribe_stops_delivery(bus):
    queue = bus.subscribe("r_4")
    bus.unsubscribe("r_4", queue)
    await bus.emit("r_4", "run.started", "supervisor", {})
    assert queue.empty()


async def test_multiple_subscribers_all_receive(bus):
    q1 = bus.subscribe("r_5")
    q2 = bus.subscribe("r_5")
    await bus.emit("r_5", "run.started", "supervisor", {})
    assert q1.get_nowait()["type"] == "run.started"
    assert q2.get_nowait()["type"] == "run.started"
