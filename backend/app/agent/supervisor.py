from app.db import Database
from app.reasoning.llm import get_fast_llm, structured
from app.reasoning.prompts import supervisor_system
from app.reasoning.schemas import Intent


async def classify_intent(
    prompt: str,
    *,
    now_ist: str,
    llm=None,
    db: Database | None = None,
    cache: bool = False,
) -> Intent:
    llm = llm or get_fast_llm()
    system = supervisor_system(now_ist)
    try:
        return await structured(llm, Intent, system, prompt, db=db, cache=cache)
    except Exception:  # noqa: BLE001 - a full sweep is always a safe fallback; policy still governs every action
        return Intent(
            intent="sweep",
            args={"scope": "all_open"},
            reasoning="Could not classify the request; defaulting to a full sweep of open invoices.",
        )
