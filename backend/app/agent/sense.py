"""Reads live Stripe invoices and Notion client/invoice pages, merges them with each
invoice's persisted agent memory in SQLite, and assembles the InvoiceContext list the
per-invoice sub-graph runs against.

Stripe invoices are matched to Notion clients via the Stripe customer's own id (stamped
with our client_id in its metadata, see fetch_customer_client_ids) - not by email. Email
addresses get fixed after the fact when a demo domain turns out not to exist (see
docs/swytchcode-notes.md), and Stripe freezes customer_email onto each invoice at
creation time, so matching by email would silently break the moment any address changes.
Real Stripe disputes (list_disputes) are fetched for
completeness but left unmatched to a specific invoice: linking a dispute's charge back
to its invoice needs a stripe.charges.get call that isn't in tool_registry.yaml, and
this demo's one simulated-dispute scenario (INV-1070, see seed/invoices.yaml) is
delivered through a real Gmail/Slack message for the interpret node to read, not
through Stripe's dispute API - Stripe sandbox disputes can't be created programmatically.
"""

from datetime import UTC, datetime
from pathlib import Path

import yaml

from app.agent.schemas import Client, InvoiceContext, InvoiceMemory, StripeInvoice
from app.db import Database
from app.integrations import notion, stripe
from app.swy.executor import CallCtx

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def workspace_ids() -> dict:
    return yaml.safe_load((CONFIG_DIR / "workspace_ids.yaml").read_text(encoding="utf-8"))


async def fetch_clients(ctx: CallCtx) -> list[Client]:
    clients_db_id = workspace_ids()["notion"]["clients_db_id"]
    result = await notion.query_database(clients_db_id, page_size=100, ctx=ctx)
    if not result.ok:
        raise RuntimeError(f"failed to query Notion clients: {result.error}")
    return [notion.parse_client_page(page) for page in result.data["results"]]


async def fetch_customer_client_ids(ctx: CallCtx) -> dict[str, str]:
    """Maps Stripe customer id -> our client_id, read from each customer's
    munimji_client_id metadata (stamped on at seed time / by scripts/fix_client_emails.py)."""
    result = await stripe.list_customers(ctx=ctx)
    if not result.ok:
        raise RuntimeError(f"failed to list Stripe customers: {result.error}")
    mapping: dict[str, str] = {}
    for raw in result.data["data"]:
        client_id = (raw.get("metadata") or {}).get("munimji_client_id")
        if client_id:
            mapping[raw["id"]] = client_id
    return mapping


async def fetch_invoices(ctx: CallCtx) -> list[StripeInvoice]:
    """All invoices (open and closed) - a paid one can still need attention, e.g. a
    post-payment dispute."""
    result = await stripe.list_invoices(limit=100, ctx=ctx)
    if not result.ok:
        raise RuntimeError(f"failed to list Stripe invoices: {result.error}")
    return [stripe.parse_invoice(raw) for raw in result.data["data"]]


async def fetch_invoice_page_ids(ctx: CallCtx) -> dict[str, str]:
    """Maps Stripe invoice id -> its Notion Invoices Ledger page id, via the page's
    'Stripe ID' property (set at seed time)."""
    invoices_db_id = workspace_ids()["notion"]["invoices_db_id"]
    result = await notion.query_database(invoices_db_id, page_size=100, ctx=ctx)
    if not result.ok:
        raise RuntimeError(f"failed to query Notion invoices ledger: {result.error}")
    pages: dict[str, str] = {}
    for page in result.data["results"]:
        rich_text = page["properties"]["Stripe ID"]["rich_text"]
        stripe_id = "".join(fragment["plain_text"] for fragment in rich_text)
        if stripe_id:
            pages[stripe_id] = page["id"]
    return pages


def _load_memory(row) -> InvoiceMemory:
    if row is None:
        return InvoiceMemory()
    return InvoiceMemory(
        reminder_count=row["reminder_count"] or 0,
        last_reminder_at=row["last_reminder_at"],
        last_client_msg_at=row["last_client_msg_at"],
        promise_date=row["promise_date"],
        promise_source_msg=row["promise_source_msg"],
        dispute_open=bool(row["dispute_open"]),
        jira_key=row["jira_key"],
        notion_page_id=row["notion_page_id"],
        state=row["state"] or "Healthy",
        last_decision=row["last_decision"],
        last_severity=row["last_severity"],
    )


async def build_invoice_contexts(ctx: CallCtx, db: Database) -> list[InvoiceContext]:
    clients = await fetch_clients(ctx)
    clients_by_id = {client.client_id: client for client in clients}
    client_id_by_customer = await fetch_customer_client_ids(ctx)

    invoices = await fetch_invoices(ctx)
    invoice_page_ids = await fetch_invoice_page_ids(ctx)

    exposure_by_client: dict[str, int] = {}
    for invoice in invoices:
        client_id = client_id_by_customer.get(invoice.customer_id)
        client = clients_by_id.get(client_id) if client_id else None
        if client is None:
            continue
        exposure_by_client[client.client_id] = (
            exposure_by_client.get(client.client_id, 0) + invoice.due_amount.inr
        )

    now = datetime.now(UTC).isoformat()
    contexts: list[InvoiceContext] = []
    for invoice in invoices:
        client_id = client_id_by_customer.get(invoice.customer_id)
        client = clients_by_id.get(client_id) if client_id else None
        if client is None:
            continue  # stripe customer has no munimji_client_id metadata yet

        row = await db.get_invoice(invoice.id)
        memory = _load_memory(row)
        if memory.notion_page_id is None:
            memory.notion_page_id = invoice_page_ids.get(invoice.id)

        await db.upsert_invoice(
            invoice_id=invoice.id,
            number=invoice.number,
            client_id=client.client_id,
            status=invoice.status,
            amount_inr=invoice.amount.inr,
            due_inr=invoice.due_amount.inr,
            invoice_date=invoice.invoice_date.isoformat(),
            due_date=invoice.due_date.isoformat(),
            reminder_count=memory.reminder_count,
            last_reminder_at=memory.last_reminder_at.isoformat() if memory.last_reminder_at else None,
            last_client_msg_at=(
                memory.last_client_msg_at.isoformat() if memory.last_client_msg_at else None
            ),
            promise_date=memory.promise_date.isoformat() if memory.promise_date else None,
            promise_source_msg=memory.promise_source_msg,
            dispute_open=int(memory.dispute_open),
            jira_key=memory.jira_key,
            notion_page_id=memory.notion_page_id,
            state=memory.state,
            last_decision=memory.last_decision,
            last_severity=memory.last_severity,
            updated_at=now,
        )
        await db.upsert_client(
            client_id=client.client_id,
            name=client.name,
            email=client.email,
            tier=client.tier,
            contact_name=client.contact_name,
            relationship_notes=client.relationship_notes,
            notion_page_id=client.notion_page_id,
            paused_until=client.paused_until.isoformat() if client.paused_until else None,
        )

        contexts.append(
            InvoiceContext(
                invoice=invoice,
                client=client,
                memory=memory,
                dispute=None,
                client_open_exposure_inr=exposure_by_client.get(client.client_id, 0),
            )
        )
    return contexts


if __name__ == "__main__":
    import asyncio

    from app.settings import get_settings

    async def _manual_check() -> None:
        settings = get_settings()
        db = Database(settings.app_db_path)
        ctx = CallCtx(run_id="manual", node="sense")
        contexts = await build_invoice_contexts(ctx, db)
        print(f"built {len(contexts)} invoice contexts")
        for context in contexts:
            print(
                f"{context.invoice.number}  {context.client.name:<20} "
                f"{context.invoice.status:<6} due_inr={context.invoice.due_amount.inr}  "
                f"exposure_inr={context.client_open_exposure_inr}"
            )
        await db.close()

    asyncio.run(_manual_check())
