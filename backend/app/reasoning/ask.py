from pydantic import BaseModel

from app.db import Database
from app.reasoning.llm import get_reasoning_llm, structured
from app.reasoning.prompts import ASK_SYSTEM


class AskAnswer(BaseModel):
    text: str


async def answer_question(
    question: str,
    context: str,
    *,
    llm=None,
    db: Database | None = None,
    cache: bool = False,
) -> str:
    """Answer an owner question. `context` is pre-fetched SQL results and decision traces."""
    user = f"Context:\n{context}\n\nQuestion: {question}"
    try:
        llm = llm or get_reasoning_llm()
        result = await structured(llm, AskAnswer, ASK_SYSTEM, user, db=db, cache=cache)
        return result.text
    except Exception:  # noqa: BLE001
        return "I couldn't reach the reasoning model just now - please try again in a moment."
