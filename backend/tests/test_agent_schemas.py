from datetime import date

from app.agent.schemas import Client, InvoiceContext, InvoiceMemory, PaypalInvoice
from app.money import Money


def _invoice() -> PaypalInvoice:
    return PaypalInvoice(
        id="INV2-ABC",
        number="INV-1077",
        status="SENT",
        client_email="kaarigar.clients.sim+orion@gmail.com",
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
        email="kaarigar.clients.sim+orion@gmail.com",
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
