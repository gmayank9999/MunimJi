from pydantic import BaseModel

from app.db import Database
from app.reasoning.llm import get_reasoning_llm, structured
from app.reasoning.prompts import EXPLAINER_SYSTEM


class Explanation(BaseModel):
    text: str


async def explain_decision(
    decision: str,
    rule_id: str,
    reasons: list[str],
    counterfactuals: list[str],
    *,
    llm=None,
    db: Database | None = None,
    cache: bool = False,
) -> str:
    user = (
        f"Decision: {decision} (rule {rule_id})\n"
        f"Reasons: {'; '.join(reasons)}\n"
        f"What would change this: {'; '.join(counterfactuals) if counterfactuals else 'nothing tracked'}"
    )
    try:
        llm = llm or get_reasoning_llm()
        result = await structured(llm, Explanation, EXPLAINER_SYSTEM, user, db=db, cache=cache)
        return result.text
    except Exception:  # noqa: BLE001 - fall back to a deterministic sentence built from the reasons
        base = f"{decision} because {'; '.join(reasons)}."
        if counterfactuals:
            base += f" {counterfactuals[0]}."
        return base
