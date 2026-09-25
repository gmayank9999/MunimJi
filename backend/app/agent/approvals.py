"""Resolves an action parked in `pending_approval` by governance_gate - the owner's
Slack ✅/❌ (or a UI click) either sends it for real or rejects it, hours or days after
the sweep that planned it finished. Everything needed to send is read back off the
ledger row's payload_json (see governance_gate_node in invoice_graph.py), not
recomputed - the original graph run is long gone by the time this executes.
"""

import json

import aiosqlite

from app.integrations import gmail, twilio
from app.settings import get_settings
from app.swy.executor import CallCtx, ToolCallResult


def _skip(error: str) -> ToolCallResult:
    return ToolCallResult(
        logical="none", canonical_id="none", ok=False, error=error, category="internal", duration_ms=0
    )


async def execute_approved_action(row: aiosqlite.Row, *, dry_run: bool = False) -> ToolCallResult:
    payload = json.loads(row["payload_json"]) if row["payload_json"] else {}
    ctx = CallCtx(run_id=row["run_id"], invoice_id=row["invoice_id"], node="approval")

    if row["tool"] == "gmail.send":
        if not payload.get("to") or not payload.get("body"):
            return _skip("approved gmail action has no recipient/body on its ledger row")
        raw = gmail.build_raw(
            to=payload["to"],
            from_=get_settings().business_email,
            subject=payload.get("subject", ""),
            body=payload["body"],
            idem_key=row["idem_key"],
            decision=row["action_type"],
        )
        return await gmail.send(raw, ctx=ctx, dry_run=dry_run)

    if row["tool"] == "twilio.sms.send":
        settings = get_settings()
        if not settings.twilio_from_e164:
            return _skip("TWILIO_FROM_E164 is not configured")
        if not payload.get("to") or not payload.get("body"):
            return _skip("approved sms action has no recipient/body on its ledger row")
        return await twilio.sms_owner(
            payload["to"], settings.twilio_from_e164, payload["body"], ctx=ctx, dry_run=dry_run
        )

    return _skip(f"no approval executor for {row['tool']}")
