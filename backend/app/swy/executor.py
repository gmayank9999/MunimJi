import asyncio
import time
from typing import Any

import swytchcode_runtime as sr
from pydantic import BaseModel

from app.settings import get_settings
from app.swy.errors import classify
from app.swy.registry import ToolRegistry, get_registry

DEMO_PACE_SECONDS = 0.12

_GLOBAL_SEMAPHORE = asyncio.Semaphore(4)
_PER_INTEGRATION_LIMITS = {"notion": 3, "jira": 3}
_integration_semaphores: dict[str, asyncio.Semaphore] = {}


class CallCtx(BaseModel):
    run_id: str
    invoice_id: str | None = None
    node: str = ""


class ToolCallResult(BaseModel):
    logical: str
    canonical_id: str
    ok: bool
    data: Any | None = None
    error: str | None = None
    category: str | None = None
    duration_ms: int
    policy_blocked: bool = False
    policy_id: str | None = None
    dry_run: bool = False


def _semaphore_for(logical: str) -> asyncio.Semaphore:
    integration = logical.split(".", 1)[0]
    if integration not in _integration_semaphores:
        limit = _PER_INTEGRATION_LIMITS.get(integration, 4)
        _integration_semaphores[integration] = asyncio.Semaphore(limit)
    return _integration_semaphores[integration]


def _interpret_response(raw: Any, dry_run: bool) -> dict[str, Any]:
    """Classify a successful `sr.exec` return value.

    Real (non-dry-run) responses come back as an envelope: {data, request, status_code,
    [error_category, retryable, suggested_action]}. A 4xx/5xx here is a provider-level
    error that swytchcode_runtime does NOT raise for - only pre-flight failures (auth,
    policy, spawn) raise SwytchcodeError. Confirmed live: a Notion 400 validation error
    comes back with exit code 0 and this shape. Dry-run responses are a different,
    simpler preview shape ({headers, method, url}) and are always ok.
    """
    if dry_run or not isinstance(raw, dict) or "status_code" not in raw:
        return {"ok": True, "data": raw, "error": None, "category": None, "policy_blocked": False}

    status_code = raw["status_code"]
    if status_code < 400:
        return {
            "ok": True,
            "data": raw.get("data", raw),
            "error": None,
            "category": None,
            "policy_blocked": False,
        }

    inner = raw.get("data")
    message = inner.get("message") if isinstance(inner, dict) else str(inner)
    category = raw.get("error_category", "internal")
    return {
        "ok": False,
        "data": None,
        "error": message or f"HTTP {status_code}",
        "category": category,
        "policy_blocked": category == "policy_denied",
    }


async def call(
    logical: str,
    args: dict[str, Any],
    *,
    ctx: CallCtx,
    dry_run: bool = False,
    registry: ToolRegistry | None = None,
) -> ToolCallResult:
    """The only place in the codebase that calls swytchcode_runtime.exec.

    `args` must already be shaped for the runtime: {params, body, headers,
    Authorization} - see swytchcode_runtime.exec's docstring. Retries are
    Swytchcode's job, not ours.
    """
    registry = registry or get_registry()
    allow_blocked = ctx.node == "governance_demo"
    entry = registry.resolve(logical, allow_blocked=allow_blocked)

    start = time.monotonic()
    async with _GLOBAL_SEMAPHORE, _semaphore_for(logical):
        try:
            raw = await asyncio.to_thread(sr.exec, entry.id, args, dry_run=dry_run)
            interpreted = _interpret_response(raw, dry_run)
            result = ToolCallResult(
                logical=logical,
                canonical_id=entry.id,
                duration_ms=int((time.monotonic() - start) * 1000),
                dry_run=dry_run,
                **interpreted,
            )
        except sr.SwytchcodeError as exc:
            classified = classify(exc)
            result = ToolCallResult(
                logical=logical,
                canonical_id=entry.id,
                ok=False,
                error=classified.message,
                category=classified.category,
                duration_ms=int((time.monotonic() - start) * 1000),
                policy_blocked=classified.policy_blocked,
                policy_id=classified.policy_id,
                dry_run=dry_run,
            )

    if get_settings().demo_mode:
        await asyncio.sleep(DEMO_PACE_SECONDS)

    return result
