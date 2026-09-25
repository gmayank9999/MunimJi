from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from app.money import Money

ClientTier = Literal["VIP", "Regular", "New", "Watchlist"]


class Payment(BaseModel):
    amount: Money
    date: datetime
    method: str | None = None
    transaction_id: str | None = None


class PaypalInvoice(BaseModel):
    id: str
    number: str
    status: str
    client_email: str
    amount: Money
    due_amount: Money
    paid_amount: Money
    invoice_date: date
    due_date: date
    last_payment_date: datetime | None = None
    payments: list[Payment] = []


class PaypalDispute(BaseModel):
    id: str
    reason: str
    status: str
    amount: Money
    invoice_number: str | None = None
    transaction_id: str | None = None


class Client(BaseModel):
    client_id: str
    name: str
    email: str
    tier: ClientTier
    contact_name: str
    relationship_notes: str = ""
    notion_page_id: str | None = None
    paused_until: date | None = None


class GmailMessage(BaseModel):
    message_id: str
    thread_id: str
    from_email: str
    to_email: str
    date: datetime
    subject: str
    body: str
    is_from_client: bool


class InvoiceMemory(BaseModel):
    """Persisted, agent-owned state for an invoice (SQLite `invoices` table)."""

    reminder_count: int = 0
    last_reminder_at: datetime | None = None
    last_client_msg_at: datetime | None = None
    promise_date: date | None = None
    promise_source_msg: str | None = None
    dispute_open: bool = False
    jira_key: str | None = None
    notion_page_id: str | None = None
    state: str = "Healthy"
    last_decision: str | None = None
    last_severity: int | None = None


class InvoiceContext(BaseModel):
    """Everything the per-invoice sub-graph needs: PayPal truth + client + agent memory."""

    invoice: PaypalInvoice
    client: Client
    memory: InvoiceMemory
    dispute: PaypalDispute | None = None
    client_open_exposure_inr: int = 0
