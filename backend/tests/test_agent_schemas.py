from datetime import date

from app.agent.schemas import Client, InvoiceContext, InvoiceMemory, StripeInvoice
from app.money import Money


def _invoice() -> StripeInvoice:
    return StripeInvoice(
        id="in_1ABC123",
        number="INV-1077",
        status="open",
        client_email="mayankguptawp+orion@gmail.com",
        customer_id="cus_TEST123",
        amount=Money.from_amount("85000", "INR"),
        due_amount=Money.from_amount("85000", "INR"),
        paid_amount=Money.from_amount("0", "INR"),
        invoice_date=date(2026, 9, 14),
        due_date=date(2026, 9, 24),
    )


def _client() -> Client:
    return Client(
        client_id="C01",
        name="Orion Retail",
        email="mayankguptawp+orion@gmail.com",
        tier="Regular",
        contact_name="Rohit Malhotra",
    )


def test_invoice_context_builds_with_nested_money():
    ctx = InvoiceContext(invoice=_invoice(), client=_client(), memory=InvoiceMemory(reminder_count=2))
    assert ctx.invoice.amount.inr == 85000
    assert ctx.client.tier == "Regular"
    assert ctx.memory.reminder_count == 2
    assert ctx.dispute is None


def test_invoice_memory_defaults():
    memory = InvoiceMemory()
    assert memory.reminder_count == 0
    assert memory.state == "Healthy"
    assert memory.dispute_open is False
