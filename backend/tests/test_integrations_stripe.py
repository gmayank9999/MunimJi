from datetime import UTC, date, datetime

from app.integrations.stripe import parse_dispute, parse_invoice

CREATED_TS = int(datetime(2026, 9, 14, 10, 0, tzinfo=UTC).timestamp())
DUE_TS = int(datetime(2026, 9, 24, 0, 0, tzinfo=UTC).timestamp())

SAMPLE_INVOICE = {
    "id": "in_1ABC123",
    "number": "INV-1077",
    "status": "open",
    "currency": "usd",
    "customer_email": "kaarigar.clients.sim+orion@gmail.com",
    "amount_due": 102410,
    "amount_paid": 0,
    "amount_remaining": 102410,
    "created": CREATED_TS,
    "due_date": DUE_TS,
    "hosted_invoice_url": "https://invoice.stripe.com/i/acct_x/test",
}

SAMPLE_PAID_INVOICE = {
    **SAMPLE_INVOICE,
    "status": "paid",
    "amount_due": 100000,
    "amount_paid": 100000,
    "amount_remaining": 0,
}

SAMPLE_DISPUTE = {
    "id": "dp_1XYZ",
    "reason": "product_not_received",
    "status": "warning_needs_response",
    "currency": "usd",
    "amount": 6000000,
    "charge": "ch_1DEF456",
}


def test_parse_invoice_basic_fields():
    invoice = parse_invoice(SAMPLE_INVOICE)
    assert invoice.id == "in_1ABC123"
    assert invoice.number == "INV-1077"
    assert invoice.status == "open"
    assert invoice.client_email == "kaarigar.clients.sim+orion@gmail.com"
    assert invoice.invoice_date == date(2026, 9, 14)
    assert invoice.due_date == date(2026, 9, 24)
    assert invoice.amount.inr == round(1024.10 * 83.0)
    assert invoice.hosted_invoice_url == "https://invoice.stripe.com/i/acct_x/test"


def test_parse_invoice_open_has_no_payments():
    invoice = parse_invoice(SAMPLE_INVOICE)
    assert invoice.payments == []
    assert invoice.last_payment_date is None


def test_parse_invoice_paid_has_a_payment_entry():
    invoice = parse_invoice(SAMPLE_PAID_INVOICE)
    assert len(invoice.payments) == 1
    assert invoice.payments[0].method == "stripe"
    assert invoice.due_amount.inr == 0
    assert invoice.last_payment_date is not None


def test_parse_invoice_falls_back_to_created_when_no_due_date():
    raw = {**SAMPLE_INVOICE, "due_date": None}
    invoice = parse_invoice(raw)
    assert invoice.due_date == date(2026, 9, 14)


def test_parse_invoice_falls_back_to_id_when_no_number():
    raw = {**SAMPLE_INVOICE, "number": None}
    invoice = parse_invoice(raw)
    assert invoice.number == "in_1ABC123"


def test_parse_invoice_prefers_munimji_metadata_number_over_stripes_own():
    raw = {**SAMPLE_INVOICE, "number": "GA8HZ53N-0003", "metadata": {"munimji_number": "INV-1086"}}
    invoice = parse_invoice(raw)
    assert invoice.number == "INV-1086"


def test_parse_dispute_basic_fields():
    dispute = parse_dispute(SAMPLE_DISPUTE)
    assert dispute.id == "dp_1XYZ"
    assert dispute.reason == "product_not_received"
    assert dispute.transaction_id == "ch_1DEF456"
    assert dispute.amount.inr == round(60000.00 * 83.0)
