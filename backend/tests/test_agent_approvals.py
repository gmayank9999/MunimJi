import pytest

from app.agent.approvals import execute_approved_action
from app.db import Database
from app.governance.ledger import Ledger

NOW = "2026-09-26T10:00:00+05:30"


@pytest.fixture
async def ledger(tmp_path):
    db = Database(str(tmp_path / "approvals.db"))
    await db.connect()
    yield Ledger(db)
    await db.close()


async def _planned_row(ledger, *, tool, payload, action_type="gmail_escalation"):
    idem_key = f"key-{tool}-{action_type}"
    await ledger.plan(
        idem_key=idem_key, run_id="r1", invoice_id="inv1", action_type=action_type,
        tool=tool, payload=payload, created_at=NOW,
    )
    await ledger.pending_approval(idem_key, updated_at=NOW)
    await ledger.approve(idem_key, updated_at=NOW, approval_channel="ui", approval_ts=NOW)
    await ledger.executing(idem_key, updated_at=NOW)
    return await ledger.get(idem_key)


async def test_gmail_send_dispatches_with_payload_recipient_and_body(ledger):
    row = await _planned_row(
        ledger,
        tool="gmail.send",
        payload={"to": "mayankguptawp+orion@gmail.com", "subject": "Re: invoice", "body": "hello"},
    )
    result = await execute_approved_action(row, dry_run=True)
    assert result.ok is True


async def test_gmail_send_skips_locally_when_payload_missing_body(ledger):
    row = await _planned_row(ledger, tool="gmail.send", payload={"to": "x@example.com"})
    result = await execute_approved_action(row, dry_run=True)
    assert result.ok is False
    assert "recipient/body" in result.error


async def test_twilio_sms_skips_locally_when_no_from_number(ledger, monkeypatch):
    from app import settings as settings_module

    monkeypatch.setattr(settings_module.get_settings(), "twilio_from_e164", "")
    row = await _planned_row(
        ledger, tool="twilio.sms.send", payload={"to": "+919999999999", "body": "hi"},
        action_type="twilio_sms_owner",
    )
    result = await execute_approved_action(row, dry_run=True)
    assert result.ok is False
    assert "TWILIO_FROM_E164" in result.error


async def test_unknown_tool_skips_locally_without_crashing(ledger):
    row = await _planned_row(ledger, tool="jira.issue.create", payload={}, action_type="jira_ticket")
    result = await execute_approved_action(row, dry_run=True)
    assert result.ok is False
    assert "no approval executor" in result.error
