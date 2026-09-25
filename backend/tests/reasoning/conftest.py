from app.reasoning.schemas import WriterBrief


def make_brief(**overrides) -> WriterBrief:
    base = dict(
        channel="email",
        decision="FOLLOWUP",
        tone="gentle",
        client_name="Bluepeak Media",
        contact_name="Neha",
        invoice_number="INV-1063",
        amount_display="₹22,000",
        due_date="20 Sep 2026",
        days_overdue=5,
        key_quote="",
        promise_date="",
        meeting_link="",
        pay_link_note="",
        business_name="Kaarigar Studio",
        tone_guide="Warm, respectful, Indian business English.",
        signature="Accounts Team · Kaarigar Studio",
    )
    base.update(overrides)
    return WriterBrief.model_validate(base)
