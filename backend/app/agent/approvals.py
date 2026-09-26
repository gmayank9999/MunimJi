"""Resolves an action parked in `pending_approval` by governance_gate - the owner's
Slack ✅/❌ (or a UI click) either sends it for real or rejects it, hours or days after
the sweep that planned it finished. Everything needed to send is read back off the
ledger row's payload_json (see governance_gate_node in invoice_graph.py), not
recomputed - the original graph run is long gone by the time this executes.
"""

import json

import aiosqlite

from app.clock import Clock
from app.db import Database
from app.governance.ledger import Ledger
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


async def resolve_approval(
    db: Database, idem_key: str, *, approve: bool, approval_channel: str
) -> dict | None:
    """Shared by the /api/approvals endpoints and the Slack reaction poller, so a ✅ in
    Slack and a click in the UI go through the exact same transitions and side effects.
    Returns None if there's no matching pending_approval row (caller decides what that means)."""
    ledger = Ledger(db)
    row = await ledger.get(idem_key)
    if row is None or row["status"] != "pending_approval":
        return None

    now = Clock(offset_days=get_settings().clock_offset_days).now().isoformat()

    if not approve:
        await ledger.reject(idem_key, updated_at=now, approval_channel=approval_channel, approval_ts=now)
        return {"idem_key": idem_key, "status": "rejected"}

    await ledger.approve(idem_key, updated_at=now, approval_channel=approval_channel, approval_ts=now)
    await ledger.executing(idem_key, updated_at=now)
    result = await execute_approved_action(row)
    if result.ok:
        await ledger.done(idem_key, result.data or {}, updated_at=now)
    else:
        await ledger.failed(idem_key, {"error": result.error}, updated_at=now)
    await db.insert_tool_call(
        run_id=row["run_id"], invoice_id=row["invoice_id"], node="approval",
        logical=row["tool"], canonical_id=result.canonical_id, ok=result.ok,
        policy_blocked=result.policy_blocked, duration_ms=result.duration_ms, ts=now,
    )
    return {"idem_key": idem_key, "ok": result.ok, "error": result.error}
