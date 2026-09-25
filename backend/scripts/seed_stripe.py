"""Seeds 8 Stripe customers + 18 invoices (test mode) matching the demo scenarios in
seed/invoices.yaml (IMPLEMENTATION_PLAN.md Section 18.2, adapted from PayPal to Stripe -
see docs/swytchcode-notes.md). Idempotent: re-running skips customers/invoices already
recorded in seed/seeded_ids.yaml.

Run from backend/: python scripts/seed_stripe.py
"""

import asyncio
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402

from app.integrations import stripe  # noqa: E402
from app.money import usd_to_inr  # noqa: E402
from app.swy.executor import CallCtx  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]
CLIENTS_PATH = BACKEND_DIR / "seed" / "clients.yaml"
INVOICES_PATH = BACKEND_DIR / "seed" / "invoices.yaml"
SEEDED_IDS_PATH = BACKEND_DIR / "seed" / "seeded_ids.yaml"
BUSINESS_CONFIG_PATH = BACKEND_DIR / "config" / "business.yaml"

CURRENCY = "usd"


def _load_yaml(path: Path) -> list | dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_seeded_ids() -> dict:
    if SEEDED_IDS_PATH.exists():
        return yaml.safe_load(SEEDED_IDS_PATH.read_text(encoding="utf-8")) or {}
    return {}


def _save_seeded_ids(data: dict) -> None:
    SEEDED_IDS_PATH.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _inr_to_usd_cents(amount_inr: int, fx_inr_per_usd: float) -> int:
    usd = amount_inr / fx_inr_per_usd
    return round(usd * 100)


def _unix_days_from_now(offset_days: int) -> int:
    return int((datetime.now(UTC) + timedelta(days=offset_days)).timestamp())


def _compute_base_offset_days(invoices: list[dict]) -> int:
    """Stripe rejects a `due_date` that isn't strictly in the future at creation time,
    so a genuinely overdue demo invoice can't be seeded directly (same problem the plan
    anticipated for PayPal, Section 25: shift every due date into the future by a fixed
    amount, then run the agent with a matching positive clock offset so "today" lines
    back up with the intended overdue-ness). +1 extra day so the least-overdue invoice
    is still due tomorrow, not today, at seed time.
    """
    most_overdue = min((inv["due_offset_days"] for inv in invoices), default=0)
    return max(0, -most_overdue) + 1


async def _seed_customers(ctx: CallCtx, clients: list[dict], seeded: dict) -> dict[str, str]:
    customers = seeded.setdefault("customers", {})
    for client in clients:
        client_id = client["client_id"]
        if client_id in customers:
            print(f'customer {client_id} ({client["name"]}) already seeded: {customers[client_id]}')
            continue
        result = await stripe.create_customer(client["email"], client["name"], ctx=ctx)
        if not result.ok:
            raise RuntimeError(f'failed to create customer for {client["name"]}: {result.error}')
        customers[client_id] = result.data["id"]
        print(f'created customer {client_id} ({client["name"]}): {customers[client_id]}')
    return customers


async def _seed_invoice(
    ctx: CallCtx, invoice: dict, customer_id: str, fx_inr_per_usd: float, base_offset_days: int
) -> dict:
    amount_cents = _inr_to_usd_cents(invoice["amount_inr"], fx_inr_per_usd)
    due_unix = _unix_days_from_now(base_offset_days + invoice["due_offset_days"])

    create_result = await stripe.create_draft_invoice(
        customer_id,
        due_date_unix=due_unix,
        description=f"MunimJi demo invoice {invoice['number']}",
        metadata={"munimji_number": invoice["number"]},
        ctx=ctx,
    )
    if not create_result.ok:
        raise RuntimeError(f'failed to create invoice {invoice["number"]}: {create_result.error}')
    stripe_invoice_id = create_result.data["id"]

    item_result = await stripe.add_invoice_item(
        customer_id,
        stripe_invoice_id,
        amount_cents,
        CURRENCY,
        f"Services - {invoice['number']}",
        ctx=ctx,
    )
    if not item_result.ok:
        raise RuntimeError(f'failed to add line item to {invoice["number"]}: {item_result.error}')

    finalize_result = await stripe.finalize_invoice(stripe_invoice_id, ctx=ctx)
    if not finalize_result.ok:
        raise RuntimeError(f'failed to finalize {invoice["number"]}: {finalize_result.error}')

    send_result = await stripe.send_invoice(stripe_invoice_id, ctx=ctx)
    if not send_result.ok:
        raise RuntimeError(f'failed to send {invoice["number"]}: {send_result.error}')

    if invoice.get("status") == "paid":
        pay_result = await stripe.mark_paid_out_of_band(stripe_invoice_id, ctx=ctx)
        if not pay_result.ok:
            raise RuntimeError(f'failed to mark {invoice["number"]} paid: {pay_result.error}')

    return {"stripe_invoice_id": stripe_invoice_id, "customer_id": customer_id}


async def _seed_invoices(
    ctx: CallCtx,
    invoices: list[dict],
    customers: dict[str, str],
    seeded: dict,
    fx_inr_per_usd: float,
    base_offset_days: int,
) -> None:
    seeded_invoices = seeded.setdefault("invoices", {})
    for invoice in invoices:
        number = invoice["number"]
        if number in seeded_invoices:
            print(f'{number} already seeded: {seeded_invoices[number]["stripe_invoice_id"]}')
            continue
        customer_id = customers[invoice["client_id"]]
        seeded_invoices[number] = await _seed_invoice(
            ctx, invoice, customer_id, fx_inr_per_usd, base_offset_days
        )
        print(f'seeded {number}: {seeded_invoices[number]["stripe_invoice_id"]} ({invoice.get("status", "open")})')


async def main() -> None:
    ctx = CallCtx(run_id="seed", node="seed_stripe")
    business = _load_yaml(BUSINESS_CONFIG_PATH)
    fx_inr_per_usd = float(business["fx_inr_per_usd"])

    clients = _load_yaml(CLIENTS_PATH)
    invoices = _load_yaml(INVOICES_PATH)
    seeded = _load_seeded_ids()

    base_offset_days = seeded.get("demo_base_offset_days")
    if base_offset_days is None:
        base_offset_days = _compute_base_offset_days(invoices)
        seeded["demo_base_offset_days"] = base_offset_days
    print(f"demo_base_offset_days: {base_offset_days}")

    customers = await _seed_customers(ctx, clients, seeded)
    _save_seeded_ids(seeded)

    await _seed_invoices(ctx, invoices, customers, seeded, fx_inr_per_usd, base_offset_days)
    _save_seeded_ids(seeded)

    print(f"wrote {SEEDED_IDS_PATH}")
    print(
        f"\nSet CLOCK_OFFSET_DAYS={base_offset_days} in .env (Time-Machine) so the agent's "
        "'today' lines up with these due dates and every invoice is exactly as overdue as intended."
    )
    # sanity check: money.py's converter should round-trip close to our own cents math
    sample_cents = _inr_to_usd_cents(85000, fx_inr_per_usd)
    assert abs(usd_to_inr(sample_cents / 100, fx_inr_per_usd) - 85000) < 100


if __name__ == "__main__":
    asyncio.run(main())
