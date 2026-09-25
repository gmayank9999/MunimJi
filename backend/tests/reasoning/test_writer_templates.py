from app.reasoning.writer_templates import render_template
from tests.reasoning.conftest import make_brief


def test_email_template_includes_amount_and_due_date():
    output = render_template(make_brief(channel="email", tone="gentle"))
    assert "₹22,000" in output.body
    assert "20 Sep 2026" in output.body
    assert "INV-1063" in output.body
    assert output.subject


def test_thankful_email_does_not_repeat_overdue_language():
    output = render_template(make_brief(channel="email", tone="thankful"))
    assert "Thank you" in output.body
    assert "overdue" not in output.body


def test_email_mentions_promise_date_when_present():
    output = render_template(make_brief(channel="email", tone="firm", promise_date="17 Oct 2026"))
    assert "17 Oct 2026" in output.body


def test_email_includes_meeting_link_when_present():
    output = render_template(
        make_brief(channel="email", tone="serious-respectful", meeting_link="https://calendly.com/x/y")
    )
    assert "https://calendly.com/x/y" in output.body


def test_jira_summary_capped_at_90_chars():
    output = render_template(make_brief(channel="jira"))
    assert len(output.subject) <= 90


def test_jira_body_includes_key_quote():
    output = render_template(make_brief(channel="jira", key_quote="will pay Friday"))
    assert "will pay Friday" in output.body


def test_slack_body_is_short_and_includes_decision():
    output = render_template(make_brief(channel="slack", decision="ESCALATE"))
    assert "ESCALATE" in output.body
    assert len(output.body) < 200


def test_sms_starts_with_munimji_and_is_capped():
    output = render_template(make_brief(channel="sms"))
    assert output.body.startswith("MunimJi:")
    assert len(output.body) <= 280


def test_unknown_channel_raises():
    brief = make_brief().model_copy()
    data = brief.model_dump()
    data["channel"] = "carrier-pigeon"
    unvalidated = type(brief).model_construct(**data)
    try:
        render_template(unvalidated)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for unknown channel")
