"""Lets the owner ask MunimJi questions from Slack (#munimji-ask) the same way the web
dashboard's ask box does - by polling slack.history for new human messages, classifying
each with the same classify_intent() the dashboard uses, and posting the answer back in
a thread.

Scoped to read-only intents only (explain/status/smalltalk): a chat message someone
drops in a channel is not an approval, so it must never trigger a real sweep, override,
or send. classify_intent() also silently falls back to "sweep" if the LLM call itself
fails - that fallback must be caught here too, not just intents the model chose on
purpose.
"""

import asyncio
import logging

from app.agent import ask
from app.agent.sense import workspace_ids
from app.agent.supervisor import classify_intent
from app.clock import Clock
from app.db import Database
from app.integrations import slack
from app.settings import get_settings
from app.swy.executor import CallCtx

logger = logging.getLogger(__name__)

CURSOR_NAME = "slack_ask_last_ts"
DECLINE_MESSAGE = (
    "I can answer status/explain questions here (e.g. \"how many payments are pending?\", "
    "\"why did you escalate Orion Retail?\"), but I don't run sweeps, overrides, or sends "
    "from chat - use the MunimJi dashboard for that."
)


async def _handle_message(text: str, *, db: Database) -> str:
    clock = Clock(offset_days=get_settings().clock_offset_days)
    intent = await classify_intent(text, now_ist=clock.now().isoformat(), db=db, cache=False)
    if intent.intent in ("explain", "status"):
        question = intent.args.get("question") or text
        return await ask.answer(question, db=db, today=clock.now().isoformat())
    if intent.intent == "smalltalk":
        return intent.reasoning
    return DECLINE_MESSAGE


async def poll_once(db: Database) -> int:
    """Answers every new human message in the ask channel since the last poll.
    Returns how many it answered."""
    channel_id = workspace_ids()["slack"]["ask_channel_id"]
    ctx = CallCtx(run_id="slack_ask", node="slack_ask_poller")
    last_ts = await db.get_cursor(CURSOR_NAME)

    result = await slack.history(channel_id, oldest=last_ts, ctx=ctx)
    if not result.ok or not result.data:
        return 0

    # Slack returns newest-first and `oldest` is inclusive - sort ascending and drop the
    # boundary message so each one is answered exactly once.
    messages = sorted(result.data.get("messages", []), key=lambda m: float(m["ts"]))

    if last_ts is None:
        # Cold start: seed the cursor to the latest message instead of answering the
        # channel's whole history (old setup/welcome messages included).
        if messages:
            await db.set_cursor(CURSOR_NAME, messages[-1]["ts"])
        return 0

    answered = 0
    newest_ts = last_ts
    for msg in messages:
        newest_ts = msg["ts"]
        if last_ts is not None and msg["ts"] == last_ts:
            continue
        if msg.get("bot_id") or not msg.get("text"):
            continue
        answer_text = await _handle_message(msg["text"], db=db)
        await slack.post(channel_id, answer_text, thread_ts=msg["ts"], ctx=ctx)
        answered += 1

    if newest_ts is not None:
        await db.set_cursor(CURSOR_NAME, newest_ts)
    return answered


async def run_forever(db: Database, *, interval_seconds: int = 10) -> None:
    while True:
        try:
            await poll_once(db)
        except Exception:  # noqa: BLE001 - one bad poll must never kill the worker loop
            logger.exception("slack_ask_poller: poll_once failed")
        await asyncio.sleep(interval_seconds)
