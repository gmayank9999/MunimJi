from datetime import UTC, datetime

from app.agent.schemas import Payment, StripeDispute, StripeInvoice
from app.money import Money
from app.swy.executor import CallCtx, ToolCallResult, call

OPEN_STATUSES = {"open"}
RECENTLY_CLOSED_STATUSES = {"paid", "uncollectible", "void"}


async def list_invoices(
    *,
    customer: str | None = None,
    status: str | None = None,
    limit: int = 20,
    ctx: CallCtx,
    dry_run: bool = False,
) -> ToolCallResult:
    params: dict = {"limit": limit}
    if customer is not None:
        params["customer"] = customer
    if status is not None:
        params["status"] = status
    return await call("stripe.invoices.list", {"params": params}, ctx=ctx, dry_run=dry_run)


async def get_invoice(invoice_id: str, *, ctx: CallCtx, dry_run: bool = False) -> ToolCallResult:
    return await call(
        "stripe.invoices.get", {"params": {"invoice": invoice_id}}, ctx=ctx, dry_run=dry_run
    )


async def send_invoice(invoice_id: str, *, ctx: CallCtx, dry_run: bool = False) -> ToolCallResult:
    """Also used to re-send/nudge an already-sent invoice (Stripe has no separate remind call)."""
    return await call(
        "stripe.invoices.send", {"params": {"invoice": invoice_id}}, ctx=ctx, dry_run=dry_run
    )


async def list_disputes(*, ctx: CallCtx, dry_run: bool = False) -> ToolCallResult:
    return await call("stripe.disputes.list", {"params": {}}, ctx=ctx, dry_run=dry_run)


async def refund_charge(
    charge_id: str,
    *,
    amount_cents: int | None = None,
    ctx: CallCtx,
    dry_run: bool = False,
) -> ToolCallResult:
    """Governed send - only ever called after MunimJi's own approval gate clears it."""
    body: dict = {}
    if amount_cents is not None:
        body["amount"] = amount_cents
    return await call(
        "stripe.charges.refund",
        {"params": {"charge": charge_id}, "body": body},
        ctx=ctx,
        dry_run=dry_run,
    )


async def create_customer(
    email: str, name: str, *, ctx: CallCtx, dry_run: bool = False
) -> ToolCallResult:
    """Setup-only: creates the demo clients."""
    body = {"email": email, "name": name}
    return await call("stripe.customers.create", {"body": body}, ctx=ctx, dry_run=dry_run)


async def create_draft_invoice(
    customer_id: str,
    *,
    due_date_unix: int,
    description: str | None = None,
    metadata: dict[str, str] | None = None,
    ctx: CallCtx,
    dry_run: bool = False,
) -> ToolCallResult:
    """Setup-only: creates a draft invoice (add items, then finalize, then send)."""
    body: dict = {
        "customer": customer_id,
        "collection_method": "send_invoice",
        "due_date": due_date_unix,
    }
    if description is not None:
        body["description"] = description
    if metadata is not None:
        body["metadata"] = metadata
    return await call("stripe.invoices.create", {"body": body}, ctx=ctx, dry_run=dry_run)


async def add_invoice_item(
    customer_id: str,
    invoice_id: str,
    amount_cents: int,
    currency: str,
    description: str,
    *,
    ctx: CallCtx,
    dry_run: bool = False,
) -> ToolCallResult:
    """Setup-only: attaches a line item to a draft invoice."""
    body = {
        "customer": customer_id,
        "invoice": invoice_id,
        "amount": amount_cents,
        "currency": currency.lower(),
        "description": description,
    }
    return await call("stripe.invoiceitems.create", {"body": body}, ctx=ctx, dry_run=dry_run)


async def finalize_invoice(invoice_id: str, *, ctx: CallCtx, dry_run: bool = False) -> ToolCallResult:
    """Setup-only: draft -> finalized, required before send/pay."""
    return await call(
        "stripe.invoices.finalize", {"params": {"invoice": invoice_id}}, ctx=ctx, dry_run=dry_run
    )


async def mark_paid_out_of_band(
    invoice_id: str, *, ctx: CallCtx, dry_run: bool = False
) -> ToolCallResult:
    """Setup-only: marks an invoice paid without a real charge (no card on the demo customers)."""
    body = {"paid_out_of_band": True}
    return await call(
        "stripe.invoices.pay", {"params": {"invoice": invoice_id}, "body": body}, ctx=ctx, dry_run=dry_run
    )


def _cents_to_money(cents: int, currency: str) -> Money:
    return Money.from_amount(str(cents / 100), currency.upper())


def parse_invoice(raw: dict) -> StripeInvoice:
    currency = raw["currency"]
    amount_due = _cents_to_money(raw.get("amount_due", 0), currency)
    amount_paid = _cents_to_money(raw.get("amount_paid", 0), currency)
    amount_remaining = _cents_to_money(raw.get("amount_remaining", 0), currency)

    created = datetime.fromtimestamp(raw["created"], tz=UTC)
    due_date_raw = raw.get("due_date")
    due_date = (
        datetime.fromtimestamp(due_date_raw, tz=UTC).date() if due_date_raw else created.date()
    )

    return StripeInvoice(
        id=raw["id"],
        number=raw.get("number") or raw["id"],
        status=raw["status"],
        client_email=raw.get("customer_email") or "",
        amount=amount_due,
        due_amount=amount_remaining,
        paid_amount=amount_paid,
        invoice_date=created.date(),
        due_date=due_date,
        hosted_invoice_url=raw.get("hosted_invoice_url"),
        last_payment_date=created if raw.get("amount_paid", 0) > 0 else None,
        payments=(
            [Payment(amount=amount_paid, date=created, method="stripe", transaction_id=raw["id"])]
            if raw.get("amount_paid", 0) > 0
            else []
        ),
    )


def parse_dispute(raw: dict) -> StripeDispute:
    amount = _cents_to_money(raw.get("amount", 0), raw.get("currency", "usd"))
    return StripeDispute(
        id=raw["id"],
        reason=raw.get("reason", "other"),
        status=raw.get("status", "warning_needs_response"),
        amount=amount,
        invoice_number=None,
        transaction_id=raw.get("charge"),
    )


if __name__ == "__main__":
    import asyncio

    async def _manual_check() -> None:
        ctx = CallCtx(run_id="manual", node="manual")
        result = await list_invoices(ctx=ctx, dry_run=True)
        print(result.model_dump_json(indent=2))

    asyncio.run(_manual_check())
