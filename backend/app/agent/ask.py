"""Answers the owner's "explain"/"status" questions (why did you escalate Orion, what's
my exposure) by handing the LLM a snapshot of current invoice/client state plus each
invoice's latest decision trace - it only phrases an answer from those facts, it never
picks or invents one, same separation the writer/explainer already keep from the policy
layer.
"""

import json

from app.db import Database
from app.money import format_inr
from app.reasoning.ask import answer_question


async def _build_context(db: Database, *, today: str) -> str:
    invoices = await db.list_invoices()
    clients = await db.list_clients()
    decisions = await db.list_latest_decisions()
    kpis = await db.compute_kpis(today=today)

    client_names = {c["client_id"]: c["name"] for c in clients}
    decisions_by_invoice = {d["invoice_id"]: d for d in decisions}

    lines = ["Clients:"]
    for c in clients:
        paused = f", paused until {c['paused_until']}" if c["paused_until"] else ""
        lines.append(f"- {c['name']} ({c['client_id']}, tier {c['tier']}{paused})")

    lines.append("\nInvoices:")
    for inv in invoices:
        client_name = client_names.get(inv["client_id"], inv["client_id"])
        line = (
            f"- {inv['number']} | {client_name} | due {format_inr(inv['due_inr'])} | "
            f"status {inv['status']} | state {inv['state']} | due_date {inv['due_date']} | "
            f"reminders sent {inv['reminder_count']}"
        )
        decision = decisions_by_invoice.get(inv["invoice_id"])
        if decision is not None:
            reasons = ", ".join(json.loads(decision["reasons_json"]))
            line += (
                f" | last decision {decision['decision']} (rule {decision['rule_id']}, "
                f"severity {decision['severity']}): {reasons}. {decision['explanation']}"
            )
        lines.append(line)

    lines.append(
        f"\nKPIs: outstanding {format_inr(kpis['outstanding_inr'])}, "
        f"overdue {format_inr(kpis['overdue_inr'])}, "
        f"avg days overdue {kpis['avg_days_overdue']}, "
        f"decisions today {kpis['decisions_today']}"
    )
    return "\n".join(lines)


async def answer(question: str, *, db: Database, today: str) -> str:
    context = await _build_context(db, today=today)
    return await answer_question(question, context, db=db, cache=False)
