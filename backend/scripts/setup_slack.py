"""Resolves the 4 MunimJi Slack channel ids and posts a welcome message to each.
Channels are created by hand and the bot invited manually (`/invite @swytchcode`) -
the shared Swytchcode Slack app has neither channels:manage nor channels:join scope,
so neither channel creation nor joining can be done via API. See docs/swytchcode-notes.md.

Idempotent: re-running skips channels whose ids are already recorded and skips the
welcome message for channels already marked as welcomed.

Run from backend/: python scripts/setup_slack.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402

from app.integrations import slack  # noqa: E402
from app.swy.executor import CallCtx  # noqa: E402

WORKSPACE_IDS_PATH = Path(__file__).resolve().parents[1] / "config" / "workspace_ids.yaml"

CHANNEL_KEYS = {
    "finance-ops": "finance_ops_channel_id",
    "munimji-approvals": "approvals_channel_id",
    "munimji-audit": "audit_channel_id",
    "munimji": "ask_channel_id",
}

WELCOME_MESSAGES = {
    "finance-ops": "🪔 MunimJi is online. Team alerts for overdue invoices land here.",
    "munimji-approvals": "🪔 MunimJi is online. React ✅ to approve or ❌ to reject a parked action.",
    "munimji-audit": "🪔 MunimJi is online. Every write/send action gets mirrored here for audit.",
    "munimji": "🪔 MunimJi is online. Ask me things like \"what's my exposure?\" in this channel.",
}


def _load_workspace_ids() -> dict:
    if WORKSPACE_IDS_PATH.exists():
        return yaml.safe_load(WORKSPACE_IDS_PATH.read_text(encoding="utf-8")) or {}
    return {}


def _save_workspace_ids(data: dict) -> None:
    WORKSPACE_IDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    WORKSPACE_IDS_PATH.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


async def main() -> None:
    ctx = CallCtx(run_id="setup", node="setup_slack")
    ids = _load_workspace_ids()
    slack_ids = ids.setdefault("slack", {})

    result = await slack.list_channels(exclude_archived=True, ctx=ctx)
    if not result.ok:
        raise RuntimeError(f"failed to list channels: {result.error}")
    by_name = {c["name"]: c["id"] for c in result.data["channels"]}

    for name, key in CHANNEL_KEYS.items():
        if name not in by_name:
            raise RuntimeError(f'channel "#{name}" not found - create it in Slack first')
        slack_ids[key] = by_name[name]
        print(f'"#{name}": {slack_ids[key]}')

    for name, key in CHANNEL_KEYS.items():
        welcomed_flag = f"{key}_welcomed"
        if slack_ids.get(welcomed_flag):
            print(f'"#{name}" already welcomed')
            continue
        post_result = await slack.post(slack_ids[key], WELCOME_MESSAGES[name], ctx=ctx)
        if not post_result.ok:
            raise RuntimeError(
                f'failed to post to "#{name}": {post_result.error} '
                f"(is the bot invited? `/invite @swytchcode`)"
            )
        slack_ids[welcomed_flag] = True
        print(f'posted welcome message to "#{name}"')

    _save_workspace_ids(ids)
    print(f"wrote {WORKSPACE_IDS_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
