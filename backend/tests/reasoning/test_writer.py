from app.reasoning.schemas import WriterOutput
from app.reasoning.writer import passes_number_guard, write_message
from tests.reasoning.conftest import make_brief


class _RaisingStructuredLLM:
    """Stands in for a ChatGroq instance whose structured call always fails."""

    def with_structured_output(self, schema):
        return self

    async def ainvoke(self, messages):
        raise RuntimeError("simulated LLM outage")


class _HallucinatingStructuredLLM:
    """Returns output that changed the amount - the guard must reject this."""

    def with_structured_output(self, schema):
        return self

    async def ainvoke(self, messages):
        return WriterOutput(subject="wrong", body="We now owe you ₹1 - please pay by tomorrow")


def test_guard_passes_when_amount_and_promise_date_present():
    brief = make_brief(promise_date="17 Oct 2026")
    output = WriterOutput(subject="s", body=f"blah {brief.amount_display} blah 17 Oct 2026")
    assert passes_number_guard(brief, output) is True


def test_guard_fails_when_amount_missing():
    brief = make_brief()
    output = WriterOutput(subject="s", body="a message with no amount in it")
    assert passes_number_guard(brief, output) is False


def test_guard_fails_when_promise_date_missing():
    brief = make_brief(promise_date="17 Oct 2026")
    output = WriterOutput(subject="s", body=f"has the amount {brief.amount_display} but not the date")
    assert passes_number_guard(brief, output) is False


async def test_write_message_falls_back_to_template_on_llm_failure():
    brief = make_brief()
    output = await write_message(brief, llm=_RaisingStructuredLLM())
    assert brief.amount_display in output.body
    assert brief.invoice_number in output.body


async def test_write_message_falls_back_when_llm_hallucinates_amount():
    brief = make_brief()
    output = await write_message(brief, llm=_HallucinatingStructuredLLM())
    assert brief.amount_display in output.body
    assert "We now owe you" not in output.body
