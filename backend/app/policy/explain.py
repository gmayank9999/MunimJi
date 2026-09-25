import argparse
from pathlib import Path

from app.money import format_inr
from app.policy.config import PolicyConfig, load_policy_config
from app.policy.facts import InvoiceFacts, ResponseSignal
from app.policy.rules import RULES, DecisionResult

DOCS_PATH = Path(__file__).resolve().parents[3] / "docs" / "decision-table.md"


def _r01(f: InvoiceFacts, s: ResponseSignal, c: PolicyConfig) -> list[str]:
    return ["Open PayPal dispute on this invoice's payment", f"{format_inr(f.due_inr)} due"]


def _r02(f: InvoiceFacts, s: ResponseSignal, c: PolicyConfig) -> list[str]:
    bullets = ["Client requested a refund"]
    if s.refund_amount_inr is not None:
        bullets.append(f"Requested amount: {format_inr(s.refund_amount_inr)}")
    if s.key_quote:
        bullets.append(f'"{s.key_quote}"')
    return bullets


def _r03(f: InvoiceFacts, s: ResponseSignal, c: PolicyConfig) -> list[str]:
    return [f"Invoice fully paid ({format_inr(f.paid_inr)} of {format_inr(f.amount_inr)})"]


def _r04(f: InvoiceFacts, s: ResponseSignal, c: PolicyConfig) -> list[str]:
    return ["Invoice was refunded"]


def _r05(f: InvoiceFacts, s: ResponseSignal, c: PolicyConfig) -> list[str]:
    return [f"Paused by owner until {f.paused_until}"]


def _r06(f: InvoiceFacts, s: ResponseSignal, c: PolicyConfig) -> list[str]:
    bullets = [s.dispute_reason or "Client disputes the deliverable/service"]
    bullets.append("Reminders paused until the delivery ticket is resolved")
    return bullets


def _r07(f: InvoiceFacts, s: ResponseSignal, c: PolicyConfig) -> list[str]:
    bullets = []
    if s.claimed_payment_date:
        bullets.append(f"Client claims payment on {s.claimed_payment_date}")
    else:
        bullets.append("Client claims payment was already made")
    if s.claimed_reference:
        bullets.append(f"Reference given: {s.claimed_reference}")
    bullets.append("PayPal shows no matching transaction")
    return bullets


def _r08(f: InvoiceFacts, s: ResponseSignal, c: PolicyConfig) -> list[str]:
    return ["Client claims payment", "PayPal confirms a matching transaction"]


def _r09(f: InvoiceFacts, s: ResponseSignal, c: PolicyConfig) -> list[str]:
    return [f"Client promised payment by {f.promise_date}", "Still within the grace period"]


def _r10(f: InvoiceFacts, s: ResponseSignal, c: PolicyConfig) -> list[str]:
    return [
        f"Promised payment by {f.promise_date} was not kept",
        f"{format_inr(f.due_inr)} due (>= {format_inr(c.escalate_amount_inr)})",
    ]


def _r11(f: InvoiceFacts, s: ResponseSignal, c: PolicyConfig) -> list[str]:
    return [f"Promised payment by {f.promise_date} was not kept"]


def _r12(f: InvoiceFacts, s: ResponseSignal, c: PolicyConfig) -> list[str]:
    return [f"Client asked for more time, until {s.requested_extension_until}", "Extension acknowledged"]


def _r13(f: InvoiceFacts, s: ResponseSignal, c: PolicyConfig) -> list[str]:
    return [
        f"{f.reminder_count} reminders sent (>= {c.max_reminders_before_human})",
        "Handing over to the owner",
    ]


def _r14(f: InvoiceFacts, s: ResponseSignal, c: PolicyConfig) -> list[str]:
    return ["Invoice is not yet due"]


def _r15(f: InvoiceFacts, s: ResponseSignal, c: PolicyConfig) -> list[str]:
    return [f"{f.days_overdue} day(s) overdue, within the {c.grace_days}-day grace period"]


def _r16(f: InvoiceFacts, s: ResponseSignal, c: PolicyConfig) -> list[str]:
    return [
        f"Reminded {f.hours_since_last_reminder:.0f}h ago",
        f"Cooldown is {c.reminder_cooldown_hours}h",
    ]


def _r17(f: InvoiceFacts, s: ResponseSignal, c: PolicyConfig) -> list[str]:
    return [
        f"{f.days_overdue} days overdue",
        f"{format_inr(f.due_inr)} due (>= {format_inr(c.critical_amount_inr)})",
        "No engagement from client",
    ]


def _r18(f: InvoiceFacts, s: ResponseSignal, c: PolicyConfig) -> list[str]:
    return [
        f"{f.days_overdue} days overdue",
        f"{format_inr(f.due_inr)} due (>= {format_inr(c.escalate_amount_inr)})",
        f"{f.unanswered_reminders} reminders unanswered",
    ]


def _r19(f: InvoiceFacts, s: ResponseSignal, c: PolicyConfig) -> list[str]:
    return [f"{f.days_overdue} days overdue (>= {c.high_priority_after_days})"]


def _r20(f: InvoiceFacts, s: ResponseSignal, c: PolicyConfig) -> list[str]:
    return [f"{f.days_overdue} days overdue (>= {c.followup_after_days})"]


def _r21(f: InvoiceFacts, s: ResponseSignal, c: PolicyConfig) -> list[str]:
    return ["No rule condition matched; defaulting to wait"]


_BUILDERS = {
    "R01": _r01, "R02": _r02, "R03": _r03, "R04": _r04, "R05": _r05,
    "R06": _r06, "R07": _r07, "R08": _r08, "R09": _r09, "R10": _r10,
    "R11": _r11, "R12": _r12, "R13": _r13, "R14": _r14, "R15": _r15,
    "R16": _r16, "R17": _r17, "R18": _r18, "R19": _r19, "R20": _r20,
    "R21": _r21,
}


def deterministic_reasons(
    facts: InvoiceFacts, signal: ResponseSignal, result: DecisionResult, config: PolicyConfig
) -> list[str]:
    builder = _BUILDERS.get(result.rule_id)
    if builder is None:
        return [result.reason]
    return builder(facts, signal, config)


def generate_decision_table_markdown(config: PolicyConfig) -> str:
    lines = [
        "# MunimJi decision table",
        "",
        "Generated from `backend/app/policy/rules.py` and `backend/config/policy.yaml`. First match wins.",
        "",
        "| # | Rule id | Condition | Decision |",
        "|---|---|---|---|",
    ]
    for i, rule in enumerate(RULES, start=1):
        lines.append(f"| {i:02d} | `{rule.id}` ({rule.label}) | {rule.condition} | {rule.decision} |")
    lines.append("")
    lines.append("## Thresholds")
    lines.append("")
    lines.append(f"- Grace period: {config.grace_days} day(s)")
    lines.append(f"- Follow-up after: {config.followup_after_days} day(s) overdue")
    lines.append(f"- High priority after: {config.high_priority_after_days} day(s) overdue")
    lines.append(f"- Escalate threshold: {format_inr(config.escalate_amount_inr)}")
    lines.append(f"- Critical threshold: {format_inr(config.critical_amount_inr)}")
    lines.append(f"- Reminder cooldown: {config.reminder_cooldown_hours}h")
    lines.append(f"- Max reminders before handover: {config.max_reminders_before_human}")
    lines.append(f"- Refund auto-propose max: {format_inr(config.refund_auto_propose_max_inr)}")
    lines.append("")
    return "\n".join(lines)


def write_decision_table_doc(config: PolicyConfig | None = None, path: Path = DOCS_PATH) -> Path:
    config = config or load_policy_config()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(generate_decision_table_markdown(config), encoding="utf-8")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-docs", action="store_true")
    args = parser.parse_args()
    if args.write_docs:
        out = write_decision_table_doc()
        print(f"wrote {out}")
