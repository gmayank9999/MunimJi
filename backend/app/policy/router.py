import hashlib
from datetime import datetime, time, timedelta
from typing import Any

from pydantic import BaseModel

from app.policy.config import PolicyConfig
from app.policy.facts import InvoiceFacts, ResponseSignal
from app.policy.rules import Decision


class FeatureFlags(BaseModel):
    sheets: bool = True
    twilio: bool = True
    calendly: bool = True
    paypal_native_reminder: bool = True


class PlannedAction(BaseModel):
    action_type: str
    tool_logical: str
    args_template: dict[str, Any] = {}
    needs_approval: bool = False
    idem_key: str
    defer_until: datetime | None = None


def _idem_key(demo_epoch: int, invoice_id: str, action_type: str, decision: str, as_of: datetime) -> str:
    raw = f"{demo_epoch}|{invoice_id}|{action_type}|{decision}|{as_of.date()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def _next_quiet_hours_end(as_of: datetime, quiet_end: str) -> datetime:
    end_t = time.fromisoformat(quiet_end)
    candidate = as_of.replace(hour=end_t.hour, minute=end_t.minute, second=0, microsecond=0)
    if candidate <= as_of:
        candidate += timedelta(days=1)
    return candidate


def route(
    facts: InvoiceFacts,
    signal: ResponseSignal,
    decision: Decision,
    config: PolicyConfig,
    *,
    flags: FeatureFlags | None = None,
    demo_epoch: int = 1,
) -> list[PlannedAction]:
    flags = flags or FeatureFlags()
    actions: list[PlannedAction] = []

    def add(
        action_type: str,
        tool_logical: str,
        args: dict[str, Any] | None = None,
        *,
        needs_approval: bool = False,
        defer: bool = False,
    ) -> None:
        defer_until = _next_quiet_hours_end(facts.as_of, config.quiet_hours.end) if defer else None
        actions.append(
            PlannedAction(
                action_type=action_type,
                tool_logical=tool_logical,
                args_template=args or {},
                needs_approval=needs_approval,
                idem_key=_idem_key(demo_epoch, facts.invoice_id, action_type, decision, facts.as_of),
                defer_until=defer_until,
            )
        )

    is_vip = facts.client_tier == "VIP"

    if decision == "CLOSE":
        add("notion_state_closed", "notion.page.update")
        if facts.open_jira_key:
            add("jira_close", "jira.issue.transition")
        add("slack_payment_received", "slack.post")
        if flags.sheets:
            add("sheets_payment_row", "sheets.append")
            add("sheets_decision_row", "sheets.append")
        if signal.category == "CLAIMS_PAID":
            add("gmail_thank_you", "gmail.send")

    elif decision == "WAIT":
        add("notion_state_watching", "notion.page.update")
        if flags.sheets:
            add("sheets_decision_row", "sheets.append")

    elif decision == "FOLLOWUP":
        add("gmail_reminder", "gmail.send", {"tone": "gentle"}, needs_approval=is_vip)
        if flags.paypal_native_reminder:
            add("paypal_reminder", "paypal.invoices.remind")
        add("jira_ticket", "jira.issue.create", {"priority": "Low"})
        add("notion_state_reminded", "notion.page.update")
        if flags.sheets:
            add("sheets_decision_row", "sheets.append")

    elif decision == "HIGH_PRIORITY":
        add("gmail_reminder", "gmail.send", {"tone": "firm"}, needs_approval=is_vip)
        add("jira_priority_high", "jira.issue.update", {"priority": "High"})
        add("slack_alert", "slack.post")
        add("notion_state_high_priority", "notion.page.update")
        if flags.sheets:
            add("sheets_decision_row", "sheets.append")

    elif decision == "ESCALATE":
        if flags.calendly:
            add("calendly_link", "calendly.scheduling_link")
        add("gmail_escalation", "gmail.send", {"tone": "serious-respectful"}, needs_approval=True)
        add("jira_priority_highest", "jira.issue.update", {"priority": "Highest"})
        add("slack_alert_here", "slack.post")
        if flags.twilio:
            add("twilio_sms_owner", "twilio.sms.send", defer=facts.in_quiet_hours)
        add("notion_state_escalated", "notion.page.update")
        if flags.sheets:
            add("sheets_decision_row", "sheets.append")

    elif decision == "DISPUTE_ROUTE":
        add("gmail_acknowledgment", "gmail.send", needs_approval=True)
        add("jira_delivery_ticket", "jira.issue.create", {"priority": "High", "label": "delivery-issue"})
        add("slack_alert", "slack.post")
        add("notion_state_disputed", "notion.page.update")
        if flags.sheets:
            add("sheets_decision_row", "sheets.append")

    elif decision == "RECONCILE":
        add("jira_reconcile_ticket", "jira.issue.create")
        add("gmail_reconcile_request", "gmail.send", needs_approval=True)
        add("notion_state_reconciling", "notion.page.update")
        add("slack_alert", "slack.post")
        if flags.sheets:
            add("sheets_decision_row", "sheets.append")

    elif decision == "CRITICAL":
        add("jira_priority_highest", "jira.issue.update", {"priority": "Highest"})
        add("slack_alert_here", "slack.post")
        if flags.twilio:
            add("twilio_sms_owner", "twilio.sms.send", defer=facts.in_quiet_hours)
        add("gmail_acknowledgment", "gmail.send", needs_approval=True)
        if (
            signal.category == "REFUND_REQUEST"
            and signal.refund_amount_inr is not None
            and signal.refund_amount_inr <= config.refund_auto_propose_max_inr
        ):
            add(
                "paypal_refund",
                "paypal.captures.refund",
                {"amount_inr": signal.refund_amount_inr},
                needs_approval=True,
            )
        if flags.sheets:
            add("sheets_decision_row", "sheets.append")

    elif decision == "HANDOVER":
        add("slack_handover", "slack.post")
        add("notion_state_handover", "notion.page.update")
        if flags.twilio:
            add("twilio_sms_owner", "twilio.sms.send", defer=facts.in_quiet_hours)

    return actions
