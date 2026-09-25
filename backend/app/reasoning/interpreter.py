from app.db import Database
from app.policy.facts import ResponseSignal
from app.reasoning.llm import get_fast_llm, structured
from app.reasoning.prompts import interpreter_system


async def interpret(
    unseen_client_messages: list[str],
    msg_date: str,
    *,
    llm=None,
    db: Database | None = None,
    cache: bool = False,
) -> ResponseSignal:
    if not unseen_client_messages:
        return ResponseSignal(category="NO_RESPONSE", sentiment="neutral", key_quote="", confidence=1.0)

    llm = llm or get_fast_llm()
    system = interpreter_system(msg_date)
    user = "\n\n---\n\n".join(unseen_client_messages)

    try:
        return await structured(llm, ResponseSignal, system, user, db=db, cache=cache)
    except Exception:  # noqa: BLE001 - low-confidence OTHER is the safe fallback, never crash the sweep
        return ResponseSignal(category="OTHER", sentiment="neutral", key_quote="", confidence=0.0)
