from app.reasoning.interpreter import interpret


class _RaisingStructuredLLM:
    def with_structured_output(self, schema):
        return self

    async def ainvoke(self, messages):
        raise RuntimeError("simulated LLM outage")


async def test_no_unseen_messages_returns_no_response_without_llm_call():
    signal = await interpret([], "2026-09-25", llm=_RaisingStructuredLLM())
    assert signal.category == "NO_RESPONSE"
    assert signal.confidence == 1.0


async def test_llm_failure_falls_back_to_other_with_zero_confidence():
    signal = await interpret(["Sir payment kal tak ho jayega"], "2026-09-25", llm=_RaisingStructuredLLM())
    assert signal.category == "OTHER"
    assert signal.confidence == 0.0
