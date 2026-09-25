"""Maps a governed PlannedAction to the actual Swytchcode call that carries it out.

Dispatches on `tool_logical` (not `action_type`) since that's what determines the
call shape; several action_types share a tool (e.g. every "notion_state_*" action is
a notion.page.update with different property values).

Every call here executes for real (no dry_run threading): governance_gate already
decided this action is "ready" before execute_node ever calls execute_action -
dry_run_sends only ever turns a send-risk action into a "dry_run_skip" outcome at the
gate, it never reaches here. See app/governance/gate.py.
"""

from app.agent.context import GraphContext
from app.agent.state import InvoiceState
from app.business import get_business_config
from app.integrations import gmail, jira, notion, slack, stripe, twilio
from app.policy.router import PlannedAction
from app.settings import get_settings
from app.swy.executor import CallCtx, ToolCallResult

DECISION_TO_STATE = {
    "CLOSE": "Closed",
    "WAIT": "Watching",
    "FOLLOWUP": "Reminded",
    "HIGH_PRIORITY": "High Priority",
    "ESCALATE": "Escalated",
    "DISPUTE_ROUTE": "Disputed",
    "RECONCILE": "Reconciling",
    "CRITICAL": "Escalated",  # no dedicated "Critical" state option in Notion's schema
    "HANDOVER": "Escalated",
}


def state_for_decision(decision: str, promise_status: str) -> str:
    if decision == "WAIT" and promise_status == "pending":
        return "Promise Pending"
    if decision == "WAIT" and promise_status == "broken":
        return "Promise Broken"
    return DECISION_TO_STATE.get(decision, "Watching")


def _skip(error: str) -> ToolCallResult:
    """A locally-synthesized failure for actions this demo can't actually carry out
    (missing data Swytchcode has no endpoint to supply) - never calls swytchcode_runtime."""
    return ToolCallResult(
        logical="none", canonical_id="none", ok=False, error=error,
        category="internal", duration_ms=0,
    )


async def _notion_state_update(state: InvoiceState, ctx: CallCtx) -> ToolCallResult:
    page_id = state["memory"].get("notion_page_id")
    if not page_id:
        return _skip("no Notion Invoices Ledger page id on this invoice")
    facts = state["facts"]
    severity = state["severity"]
    properties = {
        "MunimJi State": {"select": {"name": state_for_decision(state["decision"], facts["promise_status"])}},
        "Last Decision": {"select": {"name": state["decision"]}},
        "Severity": {"number": severity["score"]},
        "Days Overdue": {"number": facts["days_overdue"]},
        "Due Amount": {"number": facts["due_inr"]},
        "Last Reasoning": {"rich_text": [{"text": {"content": state["reasons"][0][:2000]}}]},
    }
    if facts.get("promise_date"):
        properties["Promise Date"] = {"date": {"start": facts["promise_date"]}}
    return await notion.update_page(page_id, properties, ctx=ctx)


async def _gmail_send(state: InvoiceState, action: PlannedAction, ctx: CallCtx) -> ToolCallResult:
    output = state["messages"].get(action.action_type)
    if output is None:
        return _skip(f"no written message for {action.action_type}")
    settings = get_settings()
    raw = gmail.build_raw(
        to=state["client"]["email"],
        from_=settings.business_email,
        subject=output["subject"],
        body=output["body"],
        idem_key=action.idem_key,
        decision=state["decision"],
    )
    return await gmail.send(raw, ctx=ctx)


async def _slack_post(state: InvoiceState, action: PlannedAction, ctx: CallCtx) -> ToolCallResult:
    output = state["messages"].get(action.action_type)
    text = output["body"] if output else f"{state['invoice']['number']} - {state['decision']}"
    channel_key = "audit_channel_id" if action.action_type == "slack_payment_received" else "finance_ops_channel_id"
    channel = _workspace_ids()["slack"][channel_key]
    return await slack.post(channel, text, ctx=ctx)


def _workspace_ids() -> dict:
    import yaml

    from app.agent.sense import CONFIG_DIR

    return yaml.safe_load((CONFIG_DIR / "workspace_ids.yaml").read_text(encoding="utf-8"))


JIRA_PROJECT_KEY = "MUNIMJI"


async def _jira_create(state: InvoiceState, action: PlannedAction, ctx: CallCtx) -> ToolCallResult:
    output = state["messages"].get(action.action_type)
    summary = output["subject"] if output else f"{state['invoice']['number']} - {state['decision']}"
    description = output["body"] if output else ""
    return await jira.create_issue(
        JIRA_PROJECT_KEY,
        summary,
        description_adf=jira.to_adf(description),
        priority=action.args_template.get("priority"),
        ctx=ctx,
    )


async def _jira_update_priority(
    state: InvoiceState, action: PlannedAction, ctx: CallCtx
) -> ToolCallResult:
    jira_key = state["memory"].get("jira_key")
    if not jira_key:
        return _skip("no Jira issue linked to this invoice yet")
    return await jira.update_issue(jira_key, priority=action.args_template.get("priority"), ctx=ctx)


async def _jira_close(state: InvoiceState, ctx: CallCtx) -> ToolCallResult:
    """Closing needs the target transition's id, which only jira.list_transitions can
    give us per-issue - not implemented; the ticket is left open for the owner to close."""
    jira_key = state["memory"].get("jira_key")
    if not jira_key:
        return _skip("no Jira issue linked to this invoice")
    return _skip(f"transition lookup not implemented; close {jira_key} manually")


async def _stripe_reminder(state: InvoiceState, ctx: CallCtx) -> ToolCallResult:
    return await stripe.send_invoice(state["invoice"]["id"], ctx=ctx)


async def _stripe_refund() -> ToolCallResult:
    """Refunds need a Stripe charge id; our invoices (collection_method=send_invoice,
    marked paid out-of-band) never have one - there's no real card charge behind them."""
    return _skip("invoice has no Stripe charge id (paid out-of-band, not by card)")


async def _twilio_sms(state: InvoiceState, ctx: CallCtx) -> ToolCallResult:
    output = state["messages"].get("twilio_sms_owner")
    settings = get_settings()
    if not settings.twilio_from_e164:
        return _skip("TWILIO_FROM_E164 is not configured")
    body = output["body"] if output else f"MunimJi: {state['invoice']['number']} {state['decision']}"
    return await twilio.sms_owner(settings.owner_phone_e164, settings.twilio_from_e164, body, ctx=ctx)


async def execute_action(
    action: PlannedAction, state: InvoiceState, *, ctx: CallCtx, context: GraphContext
) -> ToolCallResult:
    get_business_config()  # validates config/business.yaml is present before any send

    if action.tool_logical == "notion.page.update":
        return await _notion_state_update(state, ctx)
    if action.tool_logical == "gmail.send":
        return await _gmail_send(state, action, ctx)
    if action.tool_logical == "slack.post":
        return await _slack_post(state, action, ctx)
    if action.tool_logical == "jira.issue.create":
        return await _jira_create(state, action, ctx)
    if action.tool_logical == "jira.issue.update":
        return await _jira_update_priority(state, action, ctx)
    if action.tool_logical == "jira.issue.transition":
        return await _jira_close(state, ctx)
    if action.tool_logical == "stripe.invoices.send":
        return await _stripe_reminder(state, ctx)
    if action.tool_logical == "stripe.charges.refund":
        return await _stripe_refund()
    if action.tool_logical == "twilio.sms.send":
        return await _twilio_sms(state, ctx)
    if action.tool_logical in ("sheets.append", "calendly.scheduling_link"):
        return _skip(f"{action.tool_logical} not wired up (feature-flagged off in this demo)")
    return _skip(f"no executor mapping for {action.tool_logical}")
