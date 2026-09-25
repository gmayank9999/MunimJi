"""Populates the Notion Clients and Invoices Ledger databases (created by
setup_notion.py) with the same 8 clients / 18 invoices seeded into Stripe by
seed_stripe.py. MunimJi State / Last Decision / Severity are left blank - those are
the agent's job to compute live, not something seed data should pre-fill.

Idempotent: re-running skips clients/invoices whose Notion page ids are already
recorded in seed/seeded_ids.yaml.

Run from backend/: python scripts/seed_notion.py (after seed_stripe.py)
"""

import asyncio
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402

from app.integrations import notion  # noqa: E402
from app.swy.executor import CallCtx  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]
CLIENTS_PATH = BACKEND_DIR / "seed" / "clients.yaml"
INVOICES_PATH = BACKEND_DIR / "seed" / "invoices.yaml"
SEEDED_IDS_PATH = BACKEND_DIR / "seed" / "seeded_ids.yaml"
WORKSPACE_IDS_PATH = BACKEND_DIR / "config" / "workspace_ids.yaml"


def _load_yaml(path: Path) -> list | dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _save_seeded_ids(data: dict) -> None:
    SEEDED_IDS_PATH.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _rich_text(text: str) -> dict:
    return {"rich_text": [{"text": {"content": text}}]}


def _title(text: str) -> dict:
    return {"title": [{"text": {"content": text}}]}


def _due_date_iso(base_offset_days: int, due_offset_days: int) -> str:
    return (datetime.now(UTC) + timedelta(days=base_offset_days + due_offset_days)).date().isoformat()


async def _seed_client_pages(
    ctx: CallCtx, clients: list[dict], clients_db_id: str, seeded: dict
) -> dict[str, str]:
    pages = seeded.setdefault("notion_client_pages", {})
    for client in clients:
        client_id = client["client_id"]
        if client_id in pages:
            print(f'client page {client_id} already seeded: {pages[client_id]}')
            continue
        properties = {
            "Name": _title(client["name"]),
            "Client ID": _rich_text(client_id),
            "Email": {"email": client["email"]},
            "Tier": {"select": {"name": client["tier"]}},
            "Contact Person": _rich_text(client["contact_name"]),
            "Payment Behaviour": {"select": {"name": client["behaviour"]}},
        }
        result = await notion.create_page(clients_db_id, properties, ctx=ctx)
        if not result.ok:
            raise RuntimeError(f'failed to create client page for {client["name"]}: {result.error}')
        pages[client_id] = result.data["id"]
        print(f'created client page {client_id} ({client["name"]}): {pages[client_id]}')
    return pages


async def _seed_invoice_pages(
    ctx: CallCtx,
    invoices: list[dict],
    client_pages: dict[str, str],
    invoices_db_id: str,
    seeded: dict,
    base_offset_days: int,
) -> None:
    pages = seeded.setdefault("notion_invoice_pages", {})
    seeded_stripe_invoices = seeded.get("invoices", {})
    for invoice in invoices:
        number = invoice["number"]
        if number in pages:
            print(f'invoice page {number} already seeded: {pages[number]}')
            continue
        stripe_id = seeded_stripe_invoices.get(number, {}).get("stripe_invoice_id", "")
        due_date = _due_date_iso(base_offset_days, invoice["due_offset_days"])
        status = invoice.get("status", "open")
        properties = {
            "Name": _title(number),
            "Stripe ID": _rich_text(stripe_id),
            "Client": {"relation": [{"id": client_pages[invoice["client_id"]]}]},
            "Amount": {"number": invoice["amount_inr"]},
            "Due Amount": {"number": 0 if status == "paid" else invoice["amount_inr"]},
            "Due Date": {"date": {"start": due_date}},
            "Status": {"select": {"name": status}},
            "Reminder Count": {"number": invoice.get("reminder_count", 0)},
        }
        result = await notion.create_page(invoices_db_id, properties, ctx=ctx)
        if not result.ok:
            raise RuntimeError(f'failed to create invoice page for {number}: {result.error}')
        pages[number] = result.data["id"]
        print(f'created invoice page {number}: {pages[number]}')


async def main() -> None:
    ctx = CallCtx(run_id="seed", node="seed_notion")
    clients = _load_yaml(CLIENTS_PATH)
    invoices = _load_yaml(INVOICES_PATH)
    seeded = yaml.safe_load(SEEDED_IDS_PATH.read_text(encoding="utf-8")) or {}
    workspace_ids = yaml.safe_load(WORKSPACE_IDS_PATH.read_text(encoding="utf-8")) or {}

    base_offset_days = seeded["demo_base_offset_days"]
    clients_db_id = workspace_ids["notion"]["clients_db_id"]
    invoices_db_id = workspace_ids["notion"]["invoices_db_id"]

    client_pages = await _seed_client_pages(ctx, clients, clients_db_id, seeded)
    _save_seeded_ids(seeded)

    await _seed_invoice_pages(ctx, invoices, client_pages, invoices_db_id, seeded, base_offset_days)
    _save_seeded_ids(seeded)

    print(f"wrote {SEEDED_IDS_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
