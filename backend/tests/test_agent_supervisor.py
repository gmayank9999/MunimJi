from app.agent.supervisor import classify_intent


class _RaisingStructuredLLM:
    def with_structured_output(self, schema):
        return self

    async def ainvoke(self, messages):
        raise RuntimeError("simulated LLM outage")


async def test_llm_failure_falls_back_to_safe_sweep():
    intent = await classify_intent(
        "check all pending PayPal transactions", now_ist="2026-09-25T10:00:00+05:30", llm=_RaisingStructuredLLM()
    )
    assert intent.intent == "sweep"
    assert intent.args == {"scope": "all_open"}
