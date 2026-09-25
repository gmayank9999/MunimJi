import asyncio
import json
from collections import defaultdict
from datetime import datetime
from typing import Any

from app.clock import IST
from app.db import Database


class EventBus:
    """Per-run event stream: persists every TraceEvent and fans it out to live SSE subscribers."""

    def __init__(self, db: Database):
        self.db = db
        self._seq: dict[str, int] = defaultdict(int)
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)

    def _next_seq(self, run_id: str) -> int:
        self._seq[run_id] += 1
        return self._seq[run_id]

    async def emit(
        self,
        run_id: str,
        type_: str,
        node: str,
        payload: dict[str, Any],
        invoice_id: str | None = None,
    ) -> dict[str, Any]:
        seq = self._next_seq(run_id)
        ts = datetime.now(IST).isoformat()
        event = {
            "run_id": run_id,
            "seq": seq,
            "ts": ts,
            "type": type_,
            "node": node,
            "invoice_id": invoice_id,
            "payload": payload,
        }
        await self.db.insert_trace_event(run_id, seq, ts, type_, node, invoice_id, payload)
        for queue in list(self._subscribers.get(run_id, [])):
            queue.put_nowait(event)
        return event

    def subscribe(self, run_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[run_id].append(queue)
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue) -> None:
        subs = self._subscribers.get(run_id)
        if subs and queue in subs:
            subs.remove(queue)

    async def replay(self, run_id: str) -> list[dict[str, Any]]:
        rows = await self.db.get_trace_events(run_id)
        return [
            {
                "run_id": r["run_id"],
                "seq": r["seq"],
                "ts": r["ts"],
                "type": r["type"],
                "node": r["node"],
                "invoice_id": r["invoice_id"],
                "payload": json.loads(r["payload_json"]),
            }
            for r in rows
        ]
