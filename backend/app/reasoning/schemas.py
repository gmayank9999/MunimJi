from typing import Literal

from pydantic import BaseModel

Channel = Literal["email", "jira", "slack", "sms"]
Tone = Literal["gentle", "firm", "serious-respectful", "apologetic", "thankful"]


class WriterBrief(BaseModel):
    channel: Channel
    decision: str
    tone: Tone
    client_name: str
    contact_name: str
    invoice_number: str
    amount_display: str
    due_date: str
    days_overdue: int
    key_quote: str = ""
    promise_date: str = ""
    meeting_link: str = ""
    pay_link_note: str = ""
    business_name: str
    tone_guide: str
    signature: str


class WriterOutput(BaseModel):
    subject: str = ""
    body: str


class IntentClassification(BaseModel):
    """Named to avoid a field named the same as the class - Groq's tool-calling for
    openai/gpt-oss-20b reliably 400s ("attempted to call tool 'intent' which was not in
    request.tools") when a structured-output schema class is itself called `Intent` and
    has an `intent` field; confirmed by renaming this one class and nothing else."""

    intent: Literal["sweep", "explain", "status", "override", "simulate", "smalltalk"]
    args: dict = {}
    reasoning: str
