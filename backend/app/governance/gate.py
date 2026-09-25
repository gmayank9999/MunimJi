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
) -> GateResult:
    """Decide what happens to one planned action, park-and-continue style.

    Approvals and deferrals never block the caller - they record ledger state and
    return an outcome; the sweep moves on to the next action. Approval resolution
    (Slack reaction / UI click) and deferred execution are handled elsewhere.
    """
    # Idempotency first: a terminal status (including a prior "blocked") must short-circuit
    # before anything re-evaluates and tries to re-apply a transition - "blocked" has no
    # allowed outgoing transitions, not even to itself, so re-blocking it would raise.
    existing = await ledger.get(action.idem_key)
    if existing is not None and ledger.is_terminal_skip(existing["status"]):
        return GateResult(action, "idempotent_skip")

    kind = RECIPIENT_TOOLS.get(action.tool_logical)
    if kind is not None and recipient is not None:
        allowed = allowlist.is_email_allowed(recipient) if kind == "email" else allowlist.is_sms_allowed(recipient)
        if not allowed:
            await ledger.plan(
                idem_key=action.idem_key, run_id=run_id, invoice_id=invoice_id,
                action_type=action.action_type, tool=action.tool_logical,
                payload=action.args_template, created_at=now,
            )
            await ledger.blocked(action.idem_key, {"reason": "recipient not in allowlist"}, updated_at=now)
            return GateResult(action, "blocked_allowlist")

    await ledger.plan(
        idem_key=action.idem_key, run_id=run_id, invoice_id=invoice_id,
        action_type=action.action_type, tool=action.tool_logical,
        payload=action.args_template, created_at=now,
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
