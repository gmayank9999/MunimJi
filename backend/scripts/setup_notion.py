"""Discovers the 4 MunimJi Notion databases (data sources) that were created by hand
under "MunimJi HQ" (Swytchcode's Notion bundle has no database-creation endpoint - see
docs/swytchcode-notes.md), adds their property schemas via the data source update
endpoint, and writes their ids to config/workspace_ids.yaml.

Idempotent: re-running skips property updates already recorded as done.

Run from backend/: python scripts/setup_notion.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402

from app.integrations.notion import search, update_database_schema  # noqa: E402
from app.swy.executor import CallCtx  # noqa: E402

WORKSPACE_IDS_PATH = Path(__file__).resolve().parents[1] / "config" / "workspace_ids.yaml"

TIER_OPTIONS = ["VIP", "Regular", "New", "Watchlist"]
BEHAVIOUR_OPTIONS = ["Prompt", "Usually Late", "Chronic"]
STRIPE_STATUS_OPTIONS = ["draft", "open", "paid", "uncollectible", "void"]
MUNIMJI_STATE_OPTIONS = [
    "Healthy", "Watching", "Reminded", "High Priority", "Escalated",
    "Disputed", "Reconciling", "Promise Pending", "Promise Broken", "Closed",
]
DECISION_OPTIONS = [
    "CLOSE", "WAIT", "FOLLOWUP", "HIGH_PRIORITY", "ESCALATE",
    "DISPUTE_ROUTE", "RECONCILE", "CRITICAL", "HANDOVER",
]


def _select(options: list[str]) -> dict:
    return {"select": {"options": [{"name": o} for o in options]}}


def _relation(data_source_id: str) -> dict:
    return {"relation": {"data_source_id": data_source_id, "type": "single_property", "single_property": {}}}


CLIENTS_PROPERTIES = {
    "Client ID": {"rich_text": {}},
    "Email": {"email": {}},
    "Tier": _select(TIER_OPTIONS),
    "Contact Person": {"rich_text": {}},
    "Relationship Notes": {"rich_text": {}},
    "Paused Until": {"date": {}},
    "Payment Behaviour": _select(BEHAVIOUR_OPTIONS),
    "Lifetime Billed": {"number": {"format": "rupee"}},
    "Open Exposure": {"number": {"format": "rupee"}},
}


def invoices_ledger_properties(clients_db_id: str) -> dict:
    return {
        "Stripe ID": {"rich_text": {}},
        "Client": _relation(clients_db_id),
        "Amount": {"number": {"format": "rupee"}},
        "Due Amount": {"number": {"format": "rupee"}},
        "Due Date": {"date": {}},
        "Status": _select(STRIPE_STATUS_OPTIONS),
        "MunimJi State": _select(MUNIMJI_STATE_OPTIONS),
        "Days Overdue": {"number": {}},
        "Reminder Count": {"number": {}},
        "Last Reminder": {"date": {}},
        "Promise Date": {"date": {}},
        "Jira": {"url": {}},
        "Last Decision": _select(DECISION_OPTIONS),
        "Severity": {"number": {}},
        "Last Reasoning": {"rich_text": {}},
    }


def decision_traces_properties(invoices_db_id: str) -> dict:
    return {
        "Invoice": _relation(invoices_db_id),
        "Run ID": {"rich_text": {}},
        "As Of": {"date": {}},
        "Decision": _select(DECISION_OPTIONS),
        "Rule ID": {"rich_text": {}},
        "Severity": {"number": {}},
        "Facts": {"rich_text": {}},
        "Client Signal": {"rich_text": {}},
        "Reasons": {"rich_text": {}},
        "Actions Taken": {"rich_text": {}},
        "Result": {"rich_text": {}},
        "Explanation": {"rich_text": {}},
    }


RUN_REPORTS_PROPERTIES = {
    "Run ID": {"rich_text": {}},
    "Prompt": {"rich_text": {}},
    "Started": {"date": {}},
    "Invoices Scanned": {"number": {}},
    "Counts Per Decision": {"rich_text": {}},
    "Exposure": {"number": {"format": "rupee"}},
    "Swytchcode Calls": {"number": {}},
    "Policy Blocks": {"number": {}},
    "Approvals": {"number": {}},
}

DB_KEYS = {
    "Clients": "clients_db_id",
    "Invoices Ledger": "invoices_db_id",
    "Decision Traces": "decisions_db_id",
    "Run Reports": "runs_db_id",
}


def _title_text(obj: dict) -> str:
    return "".join(t.get("plain_text", "") for t in obj.get("title", [])).strip()


async def _find_data_source_id(ctx: CallCtx, name: str) -> str:
    result = await search(name, ctx=ctx)
    if not result.ok:
        raise RuntimeError(f'notion search for "{name}" failed: {result.error}')
    for item in result.data["results"]:
        if item.get("object") == "data_source" and _title_text(item) == name:
            return item["id"]
    raise RuntimeError(
        f'data source "{name}" not found - create an inline database with this exact name under "MunimJi HQ"'
    )


def _load_workspace_ids() -> dict:
    if WORKSPACE_IDS_PATH.exists():
        return yaml.safe_load(WORKSPACE_IDS_PATH.read_text(encoding="utf-8")) or {}
    return {}


def _save_workspace_ids(data: dict) -> None:
    WORKSPACE_IDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    WORKSPACE_IDS_PATH.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


async def main() -> None:
    ctx = CallCtx(run_id="setup", node="setup_notion")
    ids = _load_workspace_ids()
    notion_ids = ids.setdefault("notion", {})

    for name, key in DB_KEYS.items():
        if key not in notion_ids:
            notion_ids[key] = await _find_data_source_id(ctx, name)
            print(f'found "{name}": {notion_ids[key]}')
        else:
            print(f'"{name}" already recorded: {notion_ids[key]}')

    schema_steps = [
        ("clients_properties_added", "clients_db_id", CLIENTS_PROPERTIES),
        (
            "invoices_properties_added",
            "invoices_db_id",
            invoices_ledger_properties(notion_ids["clients_db_id"]),
        ),
        (
            "decisions_properties_added",
            "decisions_db_id",
            decision_traces_properties(notion_ids["invoices_db_id"]),
        ),
        ("runs_properties_added", "runs_db_id", RUN_REPORTS_PROPERTIES),
    ]
    for done_flag, db_key, properties in schema_steps:
        if notion_ids.get(done_flag):
            print(f"{db_key} properties already added")
            continue
        result = await update_database_schema(notion_ids[db_key], properties, ctx=ctx)
        if not result.ok:
            raise RuntimeError(f"failed to update {db_key} schema: {result.error}")
        notion_ids[done_flag] = True
        print(f"added properties to {db_key}")

    _save_workspace_ids(ids)
    print(f"wrote {WORKSPACE_IDS_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
