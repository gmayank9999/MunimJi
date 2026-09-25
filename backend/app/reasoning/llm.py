import hashlib
import json
from functools import lru_cache
from typing import TypeVar

from langchain_groq import ChatGroq
from pydantic import BaseModel

from app.db import Database
from app.settings import get_settings

T = TypeVar("T", bound=BaseModel)


@lru_cache
def _client(model: str) -> ChatGroq:
    settings = get_settings()
    return ChatGroq(model=model, api_key=settings.groq_api_key, temperature=0)


def get_reasoning_llm() -> ChatGroq:
    return _client(get_settings().model_reasoning)


def get_fast_llm() -> ChatGroq:
    return _client(get_settings().model_fast)


def _cache_key(model: str, system: str, user: str) -> str:
    raw = f"{model}|{system}|{user}"
    return hashlib.sha256(raw.encode()).hexdigest()


async def structured(
    llm: ChatGroq,
    schema: type[T],
    system: str,
    user: str,
    *,
    db: Database | None = None,
    cache: bool = False,
) -> T:
    """Call the LLM for a structured Pydantic output, retrying once on failure.

    Raises if both attempts fail - callers own the ultimate fallback (interpreter
    falls back to OTHER/confidence 0, writer falls back to a deterministic template).
    """
    model_name = getattr(llm, "model_name", getattr(llm, "model", ""))
    key = _cache_key(model_name, system, user) if cache else None

    if cache and db is not None:
        row = await db.fetchone("SELECT output_json FROM llm_cache WHERE key = ?", (key,))
        if row:
            return schema.model_validate(json.loads(row["output_json"]))

    structured_llm = llm.with_structured_output(schema)
    messages = [("system", system), ("human", user)]

    try:
        result = await structured_llm.ainvoke(messages)
    except Exception as first_error:  # noqa: BLE001 - retry once, then let the caller fall back
        retry_messages = [
            *messages,
            (
                "human",
                f"Your previous output was invalid: {first_error}. Return valid output matching the schema.",
            ),
        ]
        result = await structured_llm.ainvoke(retry_messages)

    if cache and db is not None and key is not None:
        await db.execute(
            "INSERT INTO llm_cache (key, output_json, created_at) VALUES (?, ?, datetime('now')) "
            "ON CONFLICT(key) DO NOTHING",
            (key, result.model_dump_json()),
        )

    return result
