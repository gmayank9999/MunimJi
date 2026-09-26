import json
from datetime import datetime

import pytest

from app.db import Database
from app.governance.allowlist import Allowlist
from app.governance.gate import gate_action
from app.governance.ledger import Ledger
from app.policy.router import PlannedAction

NOW = "2026-09-25T10:00:00+05:30"
ALLOWLIST = Allowlist(email_recipients_patterns=["mayankguptawp+*@gmail.com"], sms_recipients=["+910000000000"])


@pytest.fixture
async def ledger(tmp_path):
    db = Database(str(tmp_path / "gate.db"))
    await db.connect()
    yield Ledger(db)
    await db.close()


def _action(**overrides) -> PlannedAction:
    base = dict(
        action_type="gmail_reminder", tool_logical="gmail.send", args_template={}, needs_approval=False,
        idem_key="key1", defer_until=None,
    )
    base.update(overrides)
    return PlannedAction.model_validate(base)


async def test_disallowed_recipient_is_blocked(ledger):
    action = _action()
    result = await gate_action(
        action, ledger=ledger, allowlist=ALLOWLIST, run_id="r1", invoice_id="inv1",
        dry_run_sends=False, now=NOW, recipient="someone.else@gmail.com",
    )
    assert result.outcome == "blocked_allowlist"
    assert (await ledger.get("key1"))["status"] == "blocked"


async def test_allowed_recipient_with_no_flags_is_ready(ledger):
    action = _action()
    result = await gate_action(
        action, ledger=ledger, allowlist=ALLOWLIST, run_id="r1", invoice_id="inv1",
        dry_run_sends=False, now=NOW, recipient="mayankguptawp+orion@gmail.com",
    )
    assert result.outcome == "ready"
    assert (await ledger.get("key1"))["status"] == "planned"


async def test_non_recipient_action_skips_allowlist_check(ledger):
    action = _action(action_type="notion_state_watching", tool_logical="notion.page.update")
    result = await gate_action(
        action, ledger=ledger, allowlist=ALLOWLIST, run_id="r1", invoice_id="inv1",
        dry_run_sends=False, now=NOW,
    )
    assert result.outcome == "ready"


async def test_already_done_action_is_idempotent_skip(ledger):
    action = _action()
    await ledger.plan(
        idem_key="key1", run_id="r0", invoice_id="inv1", action_type="gmail_reminder",
        tool="gmail.send", payload={}, created_at=NOW,
    )
    await ledger.executing("key1", updated_at=NOW)
    await ledger.done("key1", {"ok": True}, updated_at=NOW)

    result = await gate_action(
        action, ledger=ledger, allowlist=ALLOWLIST, run_id="r1", invoice_id="inv1",
        dry_run_sends=False, now=NOW, recipient="mayankguptawp+orion@gmail.com",
    )
    assert result.outcome == "idempotent_skip"
    assert (await ledger.get("key1"))["status"] == "done"  # untouched


async def test_dry_run_sends_skips_send_type_actions(ledger):
    action = _action()
    result = await gate_action(
        action, ledger=ledger, allowlist=ALLOWLIST, run_id="r1", invoice_id="inv1",
        dry_run_sends=True, now=NOW, recipient="mayankguptawp+orion@gmail.com",
    )
    assert result.outcome == "dry_run_skip"
    assert (await ledger.get("key1"))["status"] == "skipped"


async def test_dry_run_sends_does_not_affect_non_send_actions(ledger):
    action = _action(action_type="notion_state_watching", tool_logical="notion.page.update")
    result = await gate_action(
        action, ledger=ledger, allowlist=ALLOWLIST, run_id="r1", invoice_id="inv1",
        dry_run_sends=True, now=NOW,
    )
    assert result.outcome == "ready"


async def test_deferred_action_records_reason_and_due_date(ledger):
    action = _action(defer_until=datetime(2026, 9, 26, 9, 0))
    result = await gate_action(
        action, ledger=ledger, allowlist=ALLOWLIST, run_id="r1", invoice_id="inv1",
        dry_run_sends=False, now=NOW,
    )
    assert result.outcome == "deferred"
    row = await ledger.db.fetchone("SELECT * FROM deferred_actions WHERE idem_key = ?", ("key1",))
    assert row["reason"] == "quiet hours"


async def test_needs_approval_parks_the_action(ledger):
    action = _action(needs_approval=True)
    result = await gate_action(
        action, ledger=ledger, allowlist=ALLOWLIST, run_id="r1", invoice_id="inv1",
        dry_run_sends=False, now=NOW, recipient="mayankguptawp+orion@gmail.com",
    )
    assert result.outcome == "approval_requested"
    assert (await ledger.get("key1"))["status"] == "pending_approval"


async def test_needs_approval_stores_the_written_message_not_just_args_template():
    """A pending action must carry enough to send it later - the router's args_template
    alone (e.g. {'tone': 'gentle'}) isn't a recipient or a written subject/body."""
    ledger = Ledger(Database(":memory:"))
    await ledger.db.connect()
    action = _action(needs_approval=True)
    payload = {"to": "mayankguptawp+orion@gmail.com", "subject": "Re: invoice", "body": "hello there"}
    await gate_action(
        action, ledger=ledger, allowlist=ALLOWLIST, run_id="r1", invoice_id="inv1",
        dry_run_sends=False, now=NOW, recipient="mayankguptawp+orion@gmail.com", payload=payload,
    )
    row = await ledger.get("key1")
    assert json.loads(row["payload_json"]) == payload
    await ledger.db.close()


async def test_sms_recipient_checked_against_sms_allowlist(ledger):
    action = _action(action_type="twilio_sms_owner", tool_logical="twilio.sms.send")
    blocked = await gate_action(
        action, ledger=ledger, allowlist=ALLOWLIST, run_id="r1", invoice_id="inv1",
        dry_run_sends=False, now=NOW, recipient="+911111111111",
    )
    assert blocked.outcome == "blocked_allowlist"


async def test_reblocking_the_same_action_is_an_idempotent_skip_not_a_crash(ledger):
    """A blocked action re-evaluated on a later sweep (same idem_key) must not try to
    transition 'blocked' -> 'blocked' again - that transition doesn't exist and used to
    raise InvalidTransition, crashing the whole invoice."""
    action = _action()
    first = await gate_action(
        action, ledger=ledger, allowlist=ALLOWLIST, run_id="r1", invoice_id="inv1",
        dry_run_sends=False, now=NOW, recipient="someone.else@gmail.com",
    )
    assert first.outcome == "blocked_allowlist"

    second = await gate_action(
        action, ledger=ledger, allowlist=ALLOWLIST, run_id="r2", invoice_id="inv1",
        dry_run_sends=False, now=NOW, recipient="someone.else@gmail.com",
    )
    assert second.outcome == "idempotent_skip"
