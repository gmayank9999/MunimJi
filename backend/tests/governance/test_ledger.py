import pytest

from app.db import Database
from app.governance.ledger import InvalidTransition, Ledger

NOW = "2026-09-25T10:00:00+05:30"


@pytest.fixture
async def ledger(tmp_path):
    db = Database(str(tmp_path / "ledger.db"))
    await db.connect()
    yield Ledger(db)
    await db.close()


async def _planned(ledger: Ledger, key: str = "key1") -> None:
    await ledger.plan(
        idem_key=key, run_id="r_1", invoice_id="inv_1", action_type="gmail_reminder",
        tool="gmail.send", payload={"tone": "gentle"}, created_at=NOW,
    )


async def test_plan_creates_row_in_planned_status(ledger):
    await _planned(ledger)
    row = await ledger.get("key1")
    assert row["status"] == "planned"
    assert row["action_type"] == "gmail_reminder"


async def test_plan_is_idempotent_reentry(ledger):
    await _planned(ledger)
    await _planned(ledger)  # second call must not error or duplicate
    row = await ledger.get("key1")
    assert row["status"] == "planned"


async def test_get_unknown_key_returns_none(ledger):
    assert await ledger.get("nope") is None


async def test_transition_unknown_key_raises_keyerror(ledger):
    with pytest.raises(KeyError):
        await ledger.transition("nope", "executing", updated_at=NOW)


async def test_happy_path_planned_to_executing_to_done(ledger):
    await _planned(ledger)
    await ledger.executing("key1", updated_at=NOW)
    assert (await ledger.get("key1"))["status"] == "executing"
    await ledger.done("key1", {"ok": True}, updated_at=NOW)
    row = await ledger.get("key1")
    assert row["status"] == "done"
    assert '"ok": true' in row["result_json"]


async def test_approval_flow_pending_to_approved_to_executing(ledger):
    await _planned(ledger)
    await ledger.pending_approval("key1", updated_at=NOW)
    await ledger.approve("key1", updated_at=NOW, approval_channel="slack", approval_ts=NOW)
    row = await ledger.get("key1")
    assert row["status"] == "approved"
    assert row["approval_channel"] == "slack"
    await ledger.executing("key1", updated_at=NOW)
    assert (await ledger.get("key1"))["status"] == "executing"


async def test_approval_flow_can_reject(ledger):
    await _planned(ledger)
    await ledger.pending_approval("key1", updated_at=NOW)
    await ledger.reject("key1", updated_at=NOW, approval_channel="ui", approval_ts=NOW)
    assert (await ledger.get("key1"))["status"] == "rejected"


async def test_invalid_transition_raises(ledger):
    await _planned(ledger)
    with pytest.raises(InvalidTransition):
        await ledger.done("key1", {}, updated_at=NOW)  # planned -> done is not allowed directly


async def test_terminal_statuses_reject_further_transitions(ledger):
    await _planned(ledger)
    await ledger.executing("key1", updated_at=NOW)
    await ledger.done("key1", {}, updated_at=NOW)
    with pytest.raises(InvalidTransition):
        await ledger.executing("key1", updated_at=NOW)


async def test_skipped_is_not_terminal_a_real_run_can_still_execute_it(ledger):
    """"skipped" only ever comes from a dry run (see gate.py) - it never represents a
    real decision, so a later real sweep must still be able to move it forward."""
    await _planned(ledger)
    await ledger.skipped("key1", updated_at=NOW)
    await ledger.executing("key1", updated_at=NOW)
    assert (await ledger.get("key1"))["status"] == "executing"


async def test_failed_can_be_retried_to_executing(ledger):
    await _planned(ledger)
    await ledger.executing("key1", updated_at=NOW)
    await ledger.failed("key1", {"error": "timeout"}, updated_at=NOW)
    await ledger.executing("key1", updated_at=NOW)  # retry
    assert (await ledger.get("key1"))["status"] == "executing"


async def test_deferred_inserts_into_deferred_actions_table(ledger):
    await _planned(ledger)
    await ledger.deferred("key1", due_at="2026-09-26T09:00:00+05:30", reason="quiet hours", updated_at=NOW)
    row = await ledger.get("key1")
    assert row["status"] == "deferred"
    deferred_row = await ledger.db.fetchone("SELECT * FROM deferred_actions WHERE idem_key = ?", ("key1",))
    assert deferred_row["reason"] == "quiet hours"


@pytest.mark.parametrize("status", ["done", "rejected", "blocked"])
def test_is_terminal_skip_true_for_terminal_statuses(status):
    ledger = Ledger(db=None)
    assert ledger.is_terminal_skip(status) is True


def test_is_terminal_skip_false_for_a_dry_run_skip():
    """"skipped" is a dry-run marker, not a real decision - gate.py handles it
    specially (see test_gate.py) rather than treating it as permanently terminal."""
    ledger = Ledger(db=None)
    assert ledger.is_terminal_skip("skipped") is False


@pytest.mark.parametrize("status", ["planned", "pending_approval", "approved", "executing", "deferred", "failed"])
def test_is_terminal_skip_false_for_active_statuses(status):
    ledger = Ledger(db=None)
    assert ledger.is_terminal_skip(status) is False
