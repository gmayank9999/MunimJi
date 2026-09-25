from app.reasoning.schemas import WriterBrief, WriterOutput


def render_template(brief: WriterBrief) -> WriterOutput:
    if brief.channel == "email":
        return _email(brief)
    if brief.channel == "jira":
        return _jira(brief)
    if brief.channel == "slack":
        return _slack(brief)
    if brief.channel == "sms":
        return _sms(brief)
    raise ValueError(f"unknown channel: {brief.channel}")


def _email(b: WriterBrief) -> WriterOutput:
    greeting = f"Dear {b.contact_name}," if b.tone in ("gentle", "thankful") else f"Hi {b.contact_name},"
    lines = [greeting, ""]

    if b.tone == "thankful":
        lines.append(f"Thank you for your payment of {b.amount_display} against invoice {b.invoice_number}.")
    else:
        lines.append(
            f"This is a reminder that invoice {b.invoice_number} for {b.amount_display} was due on "
            f"{b.due_date} and is currently {b.days_overdue} day(s) overdue."
        )
        if b.promise_date:
            lines.append(f"You had kindly mentioned payment by {b.promise_date}.")
        if b.pay_link_note:
            lines.append(b.pay_link_note)
        if b.meeting_link:
            lines.append(f"If it's easier, here is a 20-minute slot to discuss: {b.meeting_link}")

    lines.append("")
    lines.append(b.signature)

    subject_action = "Payment received" if b.tone == "thankful" else "Payment reminder"
    subject = f"{b.invoice_number} - {b.amount_display} - {subject_action}"
    return WriterOutput(subject=subject, body="\n".join(lines))


def _jira(b: WriterBrief) -> WriterOutput:
    summary = f"{b.invoice_number} - {b.client_name} - {b.decision} ({b.amount_display})"[:90]
    body_lines = [
        f"* Invoice {b.invoice_number} for {b.client_name}: {b.amount_display}, {b.days_overdue} day(s) overdue",
        f"* Decision: {b.decision}",
    ]
    if b.key_quote:
        body_lines.append(f'* Client said: "{b.key_quote}"')
    body_lines.append(f"* Requested action: {b.decision}")
    return WriterOutput(subject=summary, body="\n".join(body_lines))


def _slack(b: WriterBrief) -> WriterOutput:
    return WriterOutput(
        body=f":rotating_light: {b.client_name} - {b.invoice_number} - {b.amount_display} - {b.decision}"
    )


def _sms(b: WriterBrief) -> WriterOutput:
    text = f"MunimJi: {b.client_name} {b.invoice_number} {b.amount_display} {b.decision}"
    return WriterOutput(body=text[:280])
