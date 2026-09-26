"""Posts a run's results to the humans watching: a Slack digest in #finance-ops and a
Notion Run Report row, both best-effort - a run is already finished and recorded in
SQLite by the time this runs, so a Slack/Notion hiccup here must never look like the
sweep itself failed.
"""

import json

from app.agent.sense import workspace_ids
from app.integrations import notion, slack
from app.money import format_inr
from app.swy.executor import CallCtx, ToolCallResult


async def post_slack_digest(
    summary: dict, *, run_id: str, prompt: str, ctx: CallCtx
) -> ToolCallResult:
    channel = workspace_ids()["slack"]["finance_ops_channel_id"]
    counts = summary["counts_per_decision"]
    lines = [f":bar_chart: *Sweep complete* — _{prompt}_"]
    lines.append(
        f"{summary['invoices_scanned']} invoice(s) scanned · "
        f"exposure {format_inr(summary['exposure_inr'])}"
    )
    if counts:
        lines.append(" · ".join(f"{decision}: {count}" for decision, count in counts.items()))
    lines.append(
        f"Swytchcode calls: {summary['swytchcode_calls']} · "
        f"Policy blocks: {summary['policy_blocks']} · "
        f"Approvals pending: {summary['approvals_pending']}"
    )
    return await slack.post(channel, "\n".join(lines), ctx=ctx)


async def write_run_report(
    summary: dict, *, run_id: str, prompt: str, started_at: str, ctx: CallCtx
) -> ToolCallResult:
    runs_db_id = workspace_ids()["notion"]["runs_db_id"]
    properties = {
        "Name": {"title": [{"text": {"content": run_id}}]},
        "Run ID": {"rich_text": [{"text": {"content": run_id}}]},
        "Prompt": {"rich_text": [{"text": {"content": prompt[:2000]}}]},
        "Started": {"date": {"start": started_at}},
        "Invoices Scanned": {"number": summary["invoices_scanned"]},
        "Counts Per Decision": {"rich_text": [{"text": {"content": json.dumps(summary["counts_per_decision"])}}]},
        "Exposure": {"number": summary["exposure_inr"]},
        "Swytchcode Calls": {"number": summary["swytchcode_calls"]},
        "Policy Blocks": {"number": summary["policy_blocks"]},
        "Approvals": {"number": summary["approvals_pending"]},
    }
    return await notion.create_page(runs_db_id, properties, ctx=ctx)
