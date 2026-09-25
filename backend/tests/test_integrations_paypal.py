from datetime import date

from app.integrations.paypal import parse_dispute, parse_invoice

FX = 83.0

SAMPLE_INVOICE = {
    "id": "INV2-XXXX-YYYY-ZZZZ",
    "status": "SENT",
    "detail": {
        "invoice_number": "INV-1077",
        "invoice_date": "2026-09-14",
        "payment_term": {"due_date": "2026-09-24"},
    },
    "amount": {"currency_code": "USD", "value": "1024.10"},
    "due_amount": {"currency_code": "USD", "value": "1024.10"},
    "primary_recipients": [
        {"billing_info": {"email_address": "kaarigar.clients.sim+orion@gmail.com"}}
    ],
    "payments": {"transactions": []},
}

SAMPLE_PARTIALLY_PAID_INVOICE = {
    **SAMPLE_INVOICE,
    "status": "PARTIALLY_PAID",
    "amount": {"currency_code": "USD", "value": "1000.00"},
    "due_amount": {"currency_code": "USD", "value": "400.00"},
    "payments": {
        "transactions": [
            {
                "amount": {"currency_code": "USD", "value": "600.00"},
                "payment_date": "2026-09-20T10:00:00Z",
                "method": "PAYPAL",
                "transaction_id": "TXN123",
            }
        ]
    },
}

SAMPLE_DISPUTE = {
    "dispute_id": "PP-D-12345",
    "reason": "MERCHANDISE_OR_SERVICE_NOT_AS_DESCRIBED",
    "status": "OPEN_INQUIRIES",
    "dispute_amount": {"currency_code": "USD", "value": "60000.00"},
    "disputed_transactions": [
        {"invoice_number": "INV-1070", "seller_transaction_id": "TXN999"}
    ],
}


def test_parse_invoice_basic_fields():
    invoice = parse_invoice(SAMPLE_INVOICE, FX)
    assert invoice.id == "INV2-XXXX-YYYY-ZZZZ"
    assert invoice.number == "INV-1077"
    assert invoice.status == "SENT"
    assert invoice.client_email == "kaarigar.clients.sim+orion@gmail.com"
    assert invoice.invoice_date == date(2026, 9, 14)
    assert invoice.due_date == date(2026, 9, 24)
    assert invoice.amount.inr == round(1024.10 * FX)


def test_parse_invoice_no_payments_means_no_last_payment_date():
    invoice = parse_invoice(SAMPLE_INVOICE, FX)
    assert invoice.payments == []
    assert invoice.last_payment_date is None


def test_parse_invoice_with_partial_payment():
    invoice = parse_invoice(SAMPLE_PARTIALLY_PAID_INVOICE, FX)
    assert len(invoice.payments) == 1
    assert invoice.payments[0].transaction_id == "TXN123"
    assert invoice.due_amount.inr == round(400.00 * FX)
    assert invoice.last_payment_date is not None


def test_parse_invoice_falls_back_to_invoice_date_when_no_due_date():
    raw = {**SAMPLE_INVOICE, "detail": {**SAMPLE_INVOICE["detail"], "payment_term": {}}}
    invoice = parse_invoice(raw, FX)
    assert invoice.due_date == date(2026, 9, 14)


def test_parse_dispute_basic_fields():
    dispute = parse_dispute(SAMPLE_DISPUTE, FX)
    assert dispute.id == "PP-D-12345"
    assert dispute.reason == "MERCHANDISE_OR_SERVICE_NOT_AS_DESCRIBED"
    assert dispute.invoice_number == "INV-1070"
    assert dispute.transaction_id == "TXN999"
    assert dispute.amount.inr == round(60000.00 * FX)


def test_parse_dispute_with_no_transactions():
    raw = {**SAMPLE_DISPUTE, "disputed_transactions": []}
    dispute = parse_dispute(raw, FX)
    assert dispute.invoice_number is None
    assert dispute.transaction_id is None
