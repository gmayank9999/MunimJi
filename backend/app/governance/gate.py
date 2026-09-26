from dataclasses import dataclass
from typing import Literal

from app.governance.allowlist import Allowlist
from app.governance.ledger import Ledger
from app.policy.router import PlannedAction

GateOutcome = Literal[
    "blocked_allowlist", "idempotent_skip", "dry_run_skip", "deferred", "approval_requested", "ready"
]

# tool_logical -> recipient kind, for actions that reach a human and must be allowlist-checked.
# stripe.invoices.send emails the client (Stripe's own hosted-invoice reminder), so it's a
# send just like gmail.send - both the allowlist and dry_run_sends must gate it too.
RECIPIENT_TOOLS = {"gmail.send": "email", "twilio.sms.send": "sms", "stripe.invoices.send": "email"}


@dataclass
class GateResult:
    action: PlannedAction
    outcome: GateOutcome


async def gate_action(
    action: PlannedAction,
    *,
    ledger: Ledger,
    allowlist: Allowlist,
    run_id: str,
    invoice_id: str,
    dry_run_sends: bool,
    now: str,
    recipient: str | None = None,
    payload: dict | None = None,
) -> GateResult:
    """Decide what happens to one planned action, park-and-continue style.

    Approvals and deferrals never block the caller - they record ledger state and
    return an outcome; the sweep moves on to the next action. Approval resolution
    (Slack reaction / UI click) and deferred execution are handled elsewhere, reading
    `payload` back off the ledger row - it must carry everything needed to actually send
    later (recipient, written subject/body), not just the router's args_template.
    """
    ledger_payload = payload if payload is not None else action.args_template

    # Idempotency first: re-evaluating the same idem_key (a sweep re-run same day, still
    # the same invoice/decision) must short-circuit before anything below tries to
    # re-apply a transition - none of these statuses can transition to themselves
    # (confirmed live: 'blocked'->'blocked' and 'pending_approval'->'pending_approval'
    # both raised InvalidTransition and crashed the whole invoice mid-sweep).
    existing = await ledger.get(action.idem_key)
    if existing is not None:
        status = existing["status"]
        # "skipped" only ever means a *previous dry run* short-circuited here (see
        # below) - it was never actually decided. If this call is dry-run too, there's
        # still nothing to redo; if it's a real call now, fall through and gate it for
        # real instead of skipping it forever.
        if status == "skipped" and not dry_run_sends:
            pass
        elif ledger.is_terminal_skip(status):
            return GateResult(action, "idempotent_skip")
        elif status == "pending_approval":
            return GateResult(action, "approval_requested")
        elif status == "deferred":
            return GateResult(action, "deferred")
        elif status == "executing":
            return GateResult(action, "idempotent_skip")
        elif status == "skipped":
            return GateResult(action, "idempotent_skip")

    kind = RECIPIENT_TOOLS.get(action.tool_logical)
    if kind is not None and recipient is not None:
        allowed = allowlist.is_email_allowed(recipient) if kind == "email" else allowlist.is_sms_allowed(recipient)
        if not allowed:
            await ledger.plan(
                idem_key=action.idem_key, run_id=run_id, invoice_id=invoice_id,
                action_type=action.action_type, tool=action.tool_logical,
                payload=ledger_payload, created_at=now,
            )
            await ledger.blocked(action.idem_key, {"reason": "recipient not in allowlist"}, updated_at=now)
            return GateResult(action, "blocked_allowlist")

    await ledger.plan(
        idem_key=action.idem_key, run_id=run_id, invoice_id=invoice_id,
        action_type=action.action_type, tool=action.tool_logical,
        payload=ledger_payload, created_at=now,
    )

    if dry_run_sends and kind is not None:
        await ledger.skipped(action.idem_key, updated_at=now)
        return GateResult(action, "dry_run_skip")

    if action.defer_until is not None:
        await ledger.deferred(
            action.idem_key, due_at=action.defer_until.isoformat(), reason="quiet hours", updated_at=now
        )
        return GateResult(action, "deferred")

    if action.needs_approval:
        await ledger.pending_approval(action.idem_key, updated_at=now)
        return GateResult(action, "approval_requested")

    return GateResult(action, "ready")
