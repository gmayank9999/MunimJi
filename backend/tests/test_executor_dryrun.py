"""Exercises the real `swy` binary against the live-registered tooling.json and
policies.json (dry-run only - reads local files, never calls the registry). Requires
the Swytchcode CLI on PATH and this project's .swytchcode/ state. As of this writing,
Stripe/Gmail/Jira/Slack/Notion/Twilio are connected via `swy auth connect`; Google
Sheets and Calendly are not, so Sheets is used below for the still-unauthenticated
"auth" category case. PayPal was replaced with Stripe - `swy auth connect PayPal` is
broken on Swytchcode's side (a plan limit per their own team). See
docs/swytchcode-notes.md for the full connection status and the Twilio AccountSid
quirk (not auto-injected, must be passed explicitly).
"""

import pytest

from app.swy.executor import CallCtx, call
from app.swy.registry import BlockedToolError, UnknownToolError, get_registry


def test_unknown_logical_raises_before_calling_swy():
    with pytest.raises(UnknownToolError):
        get_registry().resolve("not.a.real.tool")


async def test_blocked_tool_rejected_outside_governance_demo():
    with pytest.raises(BlockedToolError):
        await call(
            "stripe.invoices.void", {}, ctx=CallCtx(run_id="r_1", node="invoice_graph")
        )


async def test_governance_demo_can_reach_blocked_tool_and_gets_policy_blocked():
    result = await call(
        "stripe.invoices.void",
        {"params": {"invoice": "in_test123"}},
        ctx=CallCtx(run_id="r_1", node="governance_demo"),
        dry_run=True,
    )
    assert result.ok is False
    assert result.policy_blocked is True
    assert result.policy_id == "block-invoice-void"
    assert result.category == "policy_denied"


async def test_stripe_read_dry_run_succeeds():
    result = await call(
        "stripe.invoices.list", {"params": {"limit": 20}}, ctx=CallCtx(run_id="r_1"), dry_run=True
    )
    assert result.ok is True
    assert result.dry_run is True
    assert result.canonical_id == "stripe.invoice.list"


async def test_gmail_send_dry_run_succeeds_with_connected_credentials():
    result = await call(
        "gmail.send",
        {"params": {"userId": "me"}, "body": {"raw": "xxx"}},
        ctx=CallCtx(run_id="r_1"),
        dry_run=True,
    )
    assert result.ok is True
    assert result.policy_blocked is False


async def test_sheets_dry_run_fails_auth_without_connected_credentials():
    result = await call(
        "sheets.get",
        {"params": {"spreadsheetId": "dummy", "range": "A1"}},
        ctx=CallCtx(run_id="r_1"),
        dry_run=True,
    )
    assert result.ok is False
    assert result.category == "auth"


async def test_twilio_sms_dry_run_fails_validation_without_account_sid():
    result = await call(
        "twilio.sms.send", {}, ctx=CallCtx(run_id="r_1"), dry_run=True
    )
    assert result.ok is False
    assert result.category == "validation"


async def test_result_duration_is_recorded():
    result = await call(
        "stripe.invoices.list", {"params": {"limit": 20}}, ctx=CallCtx(run_id="r_1"), dry_run=True
    )
    assert result.duration_ms >= 0
