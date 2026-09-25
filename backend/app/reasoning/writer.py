from app.db import Database
from app.reasoning.llm import get_reasoning_llm, structured
from app.reasoning.prompts import writer_system
from app.reasoning.schemas import WriterBrief, WriterOutput
from app.reasoning.writer_templates import render_template


def passes_number_guard(brief: WriterBrief, output: WriterOutput) -> bool:
    """The writer must never change amounts or dates - reject if the LLM did."""
    text = f"{output.subject}\n{output.body}"
    if brief.amount_display and brief.amount_display not in text:
        return False
    if brief.promise_date and brief.promise_date not in text:
        return False
    return True


async def write_message(
    brief: WriterBrief,
    *,
    llm=None,
    db: Database | None = None,
    cache: bool = False,
) -> WriterOutput:
    system = writer_system(brief.business_name, brief.tone_guide)
    user = brief.model_dump_json()

    try:
        llm = llm or get_reasoning_llm()
        result = await structured(llm, WriterOutput, system, user, db=db, cache=cache)
        if passes_number_guard(brief, result):
            return result
    except Exception:  # noqa: BLE001 - any LLM failure falls back to the deterministic template
        pass

    return render_template(brief)
