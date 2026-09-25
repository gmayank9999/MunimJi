"""One read (+ Twilio dry-run send) per integration through Swytchcode, plus a check
that the cancel-invoice policy block still fires. Prints a status table with latency.

Run from backend/: python scripts/smoke_swytchcode.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

from app.integrations import gmail, jira, notion, paypal, sheets, slack, twilio  # noqa: E402
from app.swy.executor import CallCtx, ToolCallResult, call  # noqa: E402

console = Console()


async def _check_cancel_is_policy_blocked() -> ToolCallResult:
    ctx = CallCtx(run_id="smoke", node="governance_demo")
    return await call(
        "paypal.invoices.cancel",
        {"params": {"invoice_id": "INV2-SMOKE-TEST"}},
        ctx=ctx,
        dry_run=True,
    )


async def main() -> None:
    ctx = CallCtx(run_id="smoke", node="smoke")

    checks = [
        ("PayPal", "invoices list", paypal.list_invoices_page(ctx=ctx, dry_run=True)),
        ("Gmail", "labels list", gmail.list_labels(ctx=ctx, dry_run=True)),
        ("Jira", "search project = FIN", jira.search("project = FIN", ctx=ctx, dry_run=True)),
        ("Slack", "channels list", slack.list_channels(ctx=ctx, dry_run=True)),
        ("Notion", "search", notion.search("MunimJi HQ", ctx=ctx, dry_run=True)),
        ("Google Sheets", "values get A1", sheets.get_values("dummy-sheet-id", "A1", ctx=ctx, dry_run=True)),
        (
            "Twilio",
            "sms dry-run",
            twilio.sms_owner("+910000000000", "+10000000000", "MunimJi: smoke test", ctx=ctx, dry_run=True),
        ),
    ]

    table = Table(title="MunimJi <-> Swytchcode smoke test")
    table.add_column("Integration")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Latency (ms)", justify="right")
    table.add_column("Detail")

    all_green = True
    for name, check_name, coro in checks:
        result = await coro
        if result.ok:
            status, ok_for_ci = "[green]OK[/green]", True
        elif result.category == "auth":
            status, ok_for_ci = "[yellow]NEEDS AUTH[/yellow]", True
        else:
            status, ok_for_ci = "[red]FAIL[/red]", False
        all_green = all_green and ok_for_ci
        detail = "" if result.ok else (result.error or "")[:70]
        table.add_row(name, check_name, status, str(result.duration_ms), detail)

    table.add_row(
        "Calendly", "(skipped)", "[yellow]SKIPPED[/yellow]", "-",
        "registry bundle is broken, see docs/swytchcode-notes.md",
    )

    cancel_result = await _check_cancel_is_policy_blocked()
    if cancel_result.policy_blocked and cancel_result.policy_id == "block-invoice-cancel":
        table.add_row("Governance", "cancel invoice blocked", "[green]OK[/green]", str(cancel_result.duration_ms), "")
    else:
        table.add_row("Governance", "cancel invoice blocked", "[red]FAIL[/red]", str(cancel_result.duration_ms), "policy did not fire")
        all_green = False

    console.print(table)
    if not all_green:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
