"""Polls every pending_approval action that has a Slack notification (see
_notify_approval_needed in invoice_graph.py) for a :white_check_mark:/:x: reaction and
resolves it through the exact same resolve_approval() the /api/approvals endpoints use -
the Slack card is just another way to reach that one code path, not a parallel one.
"""

import asyncio
import logging

from app.agent.approvals import resolve_approval
from app.db import Database
from app.integrations import slack
from app.swy.executor import CallCtx

logger = logging.getLogger(__name__)

APPROVE_EMOJI = {"white_check_mark", "heavy_check_mark", "+1"}
REJECT_EMOJI = {"x", "no_entry", "-1"}


async def poll_once(db: Database) -> int:
    """Checks every pending approval with a known Slack message for a reaction.
    Returns how many it resolved."""
    rows = await db.list_pending_approvals_with_slack_ref()
    resolved = 0
    for row in rows:
        ctx = CallCtx(run_id=row["run_id"], invoice_id=row["invoice_id"], node="slack_poller")
        result = await slack.get_reactions(row["slack_channel"], row["slack_message_ts"], ctx=ctx)
        if not result.ok or not result.data:
            continue
        reactions = result.data.get("message", {}).get("reactions", [])
        names = {r["name"] for r in reactions}

        if names & APPROVE_EMOJI:
            await resolve_approval(db, row["idem_key"], approve=True, approval_channel="slack")
            resolved += 1
        elif names & REJECT_EMOJI:
            await resolve_approval(db, row["idem_key"], approve=False, approval_channel="slack")
            resolved += 1
    return resolved


async def run_forever(db: Database, *, interval_seconds: int = 10) -> None:
    while True:
        try:
            await poll_once(db)
        except Exception:  # noqa: BLE001 - one bad poll must never kill the worker loop
            logger.exception("slack_poller: poll_once failed")
        await asyncio.sleep(interval_seconds)
