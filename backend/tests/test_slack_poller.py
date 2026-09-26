import pytest

from app.db import Database
from app.governance.ledger import Ledger
from app.swy.executor import ToolCallResult
from app.workers import slack_poller

NOW = "2026-09-26T10:00:00+05:30"


@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "poller.db"))
    await database.connect()
    yield database
    await database.close()


async def _pending_with_slack_ref(db, *, idem_key: str) -> None:
    ledger = Ledger(db)
    await ledger.plan(
        idem_key=idem_key, run_id="r1", invoice_id="inv1", action_type="gmail_reminder",
        tool="gmail.send", payload={"to": "kaarigar.clients.sim+orion@gmail.com", "body": "hi"},
        created_at=NOW,
    )
    await ledger.pending_approval(idem_key, updated_at=NOW)
    await db.set_slack_ref(idem_key, channel="C123", message_ts="1234.5678")


def _reactions_result(names: list[str]) -> ToolCallResult:
    return ToolCallResult(
        logical="slack.reactions.get", canonical_id="slack.reactions.get.list", ok=True,
        data={"message": {"reactions": [{"name": n, "count": 1} for n in names]}}, duration_ms=1,
    )


def _fake_get_reactions(result: ToolCallResult):
    async def _fake(*args, **kwargs):
        return result

    return _fake


async def test_checkmark_reaction_approves(db, monkeypatch):
    await _pending_with_slack_ref(db, idem_key="k1")
    monkeypatch.setattr(
        slack_poller.slack, "get_reactions", _fake_get_reactions(_reactions_result(["white_check_mark"]))
    )

    resolved = await slack_poller.poll_once(db)
    assert resolved == 1
    row = await Ledger(db).get("k1")
    assert row["status"] in ("done", "failed")  # resolved either way, never left pending


async def test_x_reaction_rejects(db, monkeypatch):
    await _pending_with_slack_ref(db, idem_key="k2")
    monkeypatch.setattr(slack_poller.slack, "get_reactions", _fake_get_reactions(_reactions_result(["x"])))

    resolved = await slack_poller.poll_once(db)
    assert resolved == 1
    row = await Ledger(db).get("k2")
    assert row["status"] == "rejected"


async def test_no_reaction_leaves_it_pending(db, monkeypatch):
    await _pending_with_slack_ref(db, idem_key="k3")
    monkeypatch.setattr(slack_poller.slack, "get_reactions", _fake_get_reactions(_reactions_result([])))

    resolved = await slack_poller.poll_once(db)
    assert resolved == 0
    row = await Ledger(db).get("k3")
    assert row["status"] == "pending_approval"


async def test_unrelated_reaction_leaves_it_pending(db, monkeypatch):
    await _pending_with_slack_ref(db, idem_key="k4")
    monkeypatch.setattr(slack_poller.slack, "get_reactions", _fake_get_reactions(_reactions_result(["eyes"])))

    resolved = await slack_poller.poll_once(db)
    assert resolved == 0


async def test_failed_slack_call_is_skipped_not_crashed(db, monkeypatch):
    await _pending_with_slack_ref(db, idem_key="k5")
    failed = ToolCallResult(logical="slack.reactions.get", canonical_id="x", ok=False, error="boom", duration_ms=1)
    monkeypatch.setattr(slack_poller.slack, "get_reactions", _fake_get_reactions(failed))

    resolved = await slack_poller.poll_once(db)
    assert resolved == 0


async def test_ignores_pending_approvals_without_a_slack_ref(db):
    ledger = Ledger(db)
    await ledger.plan(
        idem_key="no-slack", run_id="r1", invoice_id="inv1", action_type="gmail_reminder",
        tool="gmail.send", payload={}, created_at=NOW,
    )
    await ledger.pending_approval("no-slack", updated_at=NOW)

    resolved = await slack_poller.poll_once(db)
    assert resolved == 0
