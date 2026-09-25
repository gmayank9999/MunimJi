from datetime import date, datetime

from app.agent.schemas import Payment, PaypalDispute, PaypalInvoice
from app.money import Money
from app.swy.executor import CallCtx, ToolCallResult, call

OPEN_STATUSES = {"SENT", "UNPAID", "PARTIALLY_PAID", "PAYMENT_PENDING", "SCHEDULED"}
RECENTLY_CLOSED_STATUSES = {"PAID", "MARKED_AS_PAID", "REFUNDED", "PARTIALLY_REFUNDED"}


async def list_invoices_page(
    *, page: int = 1, page_size: int = 20, ctx: CallCtx, dry_run: bool = False
) -> ToolCallResult:
    params = {"page": page, "page_size": page_size, "total_required": True}
    return await call("paypal.invoices.list", {"params": params}, ctx=ctx, dry_run=dry_run)


async def search_invoices(
    *,
    statuses: list[str] | None = None,
    page: int = 1,
    page_size: int = 20,
    ctx: CallCtx,
    dry_run: bool = False,
) -> ToolCallResult:
    body: dict = {}
    if statuses is not None:
        body["status"] = statuses
    params = {"page": page, "page_size": page_size, "total_required": True}
    return await call("paypal.invoices.search", {"params": params, "body": body}, ctx=ctx, dry_run=dry_run)


async def get_invoice(invoice_id: str, *, ctx: CallCtx, dry_run: bool = False) -> ToolCallResult:
    return await call(
        "paypal.invoices.get", {"params": {"invoice_id": invoice_id}}, ctx=ctx, dry_run=dry_run
    )


async def send_native_reminder(
    invoice_id: str,
    *,
    subject: str | None = None,
    note: str | None = None,
    ctx: CallCtx,
    dry_run: bool = False,
) -> ToolCallResult:
    body: dict = {}
    if subject is not None:
        body["subject"] = subject
    if note is not None:
        body["note"] = note
    return await call(
        "paypal.invoices.remind",
        {"params": {"invoice_id": invoice_id}, "body": body},
        ctx=ctx,
        dry_run=dry_run,
    )


async def list_disputes(
    *, start_time: str | None = None, ctx: CallCtx, dry_run: bool = False
) -> ToolCallResult:
    params: dict = {}
    if start_time is not None:
        params["start_time"] = start_time
    return await call("paypal.disputes.list", {"params": params}, ctx=ctx, dry_run=dry_run)


async def refund_capture(
    capture_id: str,
    *,
    amount: Money | None = None,
    note_to_payer: str | None = None,
    ctx: CallCtx,
    dry_run: bool = False,
) -> ToolCallResult:
    """Governed send - only ever called after MunimJi's own approval gate clears it."""
    body: dict = {}
    if amount is not None:
        body["amount"] = {"value": str(amount.value), "currency_code": amount.currency}
    if note_to_payer is not None:
        body["note_to_payer"] = note_to_payer
    return await call(
        "paypal.captures.refund",
        {"params": {"capture_id": capture_id}, "body": body},
        ctx=ctx,
        dry_run=dry_run,
    )


def parse_invoice(raw: dict, fx_inr_per_usd: float) -> PaypalInvoice:
    detail = raw["detail"]
    amount_raw = raw["amount"]
    currency = amount_raw["currency_code"]
    amount = Money.from_amount(amount_raw["value"], currency, fx_inr_per_usd)

    due_raw = raw.get("due_amount", amount_raw)
    due_amount = Money.from_amount(
        due_raw.get("value", "0"), due_raw.get("currency_code", currency), fx_inr_per_usd
    )

    payments_raw = raw.get("payments", {}).get("transactions", []) or []
    payments = [
        Payment(
            amount=Money.from_amount(
                p["amount"]["value"], p["amount"]["currency_code"], fx_inr_per_usd
            ),
            date=datetime.fromisoformat(p["payment_date"]) if p.get("payment_date") else datetime.now(),
            method=p.get("method"),
            transaction_id=p.get("transaction_id"),
        )
        for p in payments_raw
    ]
    paid_inr = sum(p.amount.inr for p in payments)
    paid_amount = Money(value=amount.value - due_amount.value, currency=currency, inr=paid_inr)

    due_date_raw = detail.get("payment_term", {}).get("due_date")
    due_date = date.fromisoformat(due_date_raw) if due_date_raw else date.fromisoformat(detail["invoice_date"])

    return PaypalInvoice(
        id=raw["id"],
        number=detail["invoice_number"],
        status=raw["status"],
        client_email=raw["primary_recipients"][0]["billing_info"]["email_address"],
        amount=amount,
        due_amount=due_amount,
        paid_amount=paid_amount,
        invoice_date=date.fromisoformat(detail["invoice_date"]),
        due_date=due_date,
        last_payment_date=payments[-1].date if payments else None,
        payments=payments,
    )


def parse_dispute(raw: dict, fx_inr_per_usd: float) -> PaypalDispute:
    amount_raw = raw.get("dispute_amount", {"currency_code": "USD", "value": "0"})
    transactions = raw.get("disputed_transactions", [])
    return PaypalDispute(
        id=raw["dispute_id"],
        reason=raw.get("reason", "OTHER"),
        status=raw.get("status", "OPEN_INQUIRIES"),
        amount=Money.from_amount(amount_raw["value"], amount_raw["currency_code"], fx_inr_per_usd),
        invoice_number=transactions[0].get("invoice_number") if transactions else None,
        transaction_id=transactions[0].get("seller_transaction_id") if transactions else None,
    )


if __name__ == "__main__":
    import asyncio

    async def _manual_check() -> None:
        ctx = CallCtx(run_id="manual", node="manual")
        result = await list_invoices_page(ctx=ctx, dry_run=True)
        print(result.model_dump_json(indent=2))

    asyncio.run(_manual_check())
