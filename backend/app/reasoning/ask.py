import hashlib
import json

from app.db import Database
from app.reasoning.llm import get_reasoning_llm
from app.reasoning.prompts import ASK_SYSTEM


def _cache_key(model: str, system: str, user: str) -> str:
    raw = f"ask|{model}|{system}|{user}"
    return hashlib.sha256(raw.encode()).hexdigest()


async def answer_question(
    question: str,
    context: str,
    *,
    llm=None,
    db: Database | None = None,
    cache: bool = False,
) -> str:
    """Answer an owner question. `context` is pre-fetched SQL results and decision traces.

    Plain chat completion, not structured/tool-call output: AskAnswer used to be a
    single-field {text: str} wrapper, and Groq's forced tool-calling for
    openai/gpt-oss-120b reliably 400'd with "Tool choice is required, but model did not
    call a tool" on this kind of open-ended prose question - confirmed live, and the
    model's own (rejected) answer in the error body was correct every time. There's no
    real structure to validate for a single string field, so there's nothing lost by not
    forcing tool-call mode here.
    """
    user = f"Context:\n{context}\n\nQuestion: {question}"

    try:
        llm = llm or get_reasoning_llm()
        model_name = getattr(llm, "model_name", getattr(llm, "model", ""))
        key = _cache_key(model_name, ASK_SYSTEM, user) if cache else None

        if cache and db is not None:
            row = await db.fetchone("SELECT output_json FROM llm_cache WHERE key = ?", (key,))
            if row:
                return json.loads(row["output_json"])["text"]

        response = await llm.ainvoke([("system", ASK_SYSTEM), ("human", user)])
        text = response.content

        if cache and db is not None and key is not None:
            await db.execute(
                "INSERT INTO llm_cache (key, output_json, created_at) VALUES (?, ?, datetime('now')) "
                "ON CONFLICT(key) DO NOTHING",
                (key, json.dumps({"text": text})),
            )
        return text
    except Exception:  # noqa: BLE001
        return "I couldn't reach the reasoning model just now - please try again in a moment."
