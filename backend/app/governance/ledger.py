import json

from app.db import Database

TERMINAL_SKIP_STATUSES = {"done", "rejected", "blocked", "skipped"}

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "planned": {"pending_approval", "approved", "executing", "blocked", "skipped", "deferred"},
    "pending_approval": {"approved", "rejected"},
    "approved": {"executing"},
    "executing": {"done", "failed"},
    "deferred": {"executing", "skipped"},
    "failed": {"executing"},
    "done": set(),
    "rejected": set(),
    "blocked": set(),
    "skipped": set(),
}


class InvalidTransition(Exception):
    pass


class Ledger:
    def __init__(self, db: Database):
        self.db = db

    async def get(self, idem_key: str):
        return await self.db.fetchone("SELECT * FROM action_ledger WHERE idem_key = ?", (idem_key,))

    def is_terminal_skip(self, status: str) -> bool:
        return status in TERMINAL_SKIP_STATUSES

    async def plan(
        self,
        *,
        idem_key: str,
        run_id: str,
        invoice_id: str,
        action_type: str,
        tool: str,
        payload: dict,
        created_at: str,
        thread_id: str | None = None,
    ) -> None:
        if await self.get(idem_key) is not None:
            return
        await self.db.execute(
            "INSERT INTO action_ledger "
            "(idem_key, run_id, thread_id, invoice_id, action_type, tool, payload_json, "
            "status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'planned', ?, ?)",
            (
                idem_key, run_id, thread_id, invoice_id, action_type, tool,
                json.dumps(payload), created_at, created_at,
            ),
        )

    async def transition(
        self,
        idem_key: str,
        new_status: str,
        *,
        updated_at: str,
        result: dict | None = None,
        approval_channel: str | None = None,
        approval_ts: str | None = None,
    ) -> None:
        row = await self.get(idem_key)
        if row is None:
            raise KeyError(idem_key)
        current = row["status"]
        if new_status not in ALLOWED_TRANSITIONS.get(current, set()):
            raise InvalidTransition(f"{idem_key}: cannot go from {current!r} to {new_status!r}")

        fields = ["status = ?", "updated_at = ?"]
        params: list = [new_status, updated_at]
        if result is not None:
            fields.append("result_json = ?")
            params.append(json.dumps(result))
        if approval_channel is not None:
            fields.append("approval_channel = ?")
            params.append(approval_channel)
        if approval_ts is not None:
            fields.append("approval_ts = ?")
            params.append(approval_ts)
        params.append(idem_key)
        await self.db.execute(f"UPDATE action_ledger SET {', '.join(fields)} WHERE idem_key = ?", tuple(params))

    async def pending_approval(self, idem_key: str, *, updated_at: str) -> None:
        await self.transition(idem_key, "pending_approval", updated_at=updated_at)

    async def approve(self, idem_key: str, *, updated_at: str, approval_channel: str, approval_ts: str) -> None:
        await self.transition(
            idem_key, "approved", updated_at=updated_at,
            approval_channel=approval_channel, approval_ts=approval_ts,
        )

    async def reject(self, idem_key: str, *, updated_at: str, approval_channel: str, approval_ts: str) -> None:
        await self.transition(
            idem_key, "rejected", updated_at=updated_at,
            approval_channel=approval_channel, approval_ts=approval_ts,
        )

    async def executing(self, idem_key: str, *, updated_at: str) -> None:
        await self.transition(idem_key, "executing", updated_at=updated_at)

    async def done(self, idem_key: str, result: dict, *, updated_at: str) -> None:
        await self.transition(idem_key, "done", updated_at=updated_at, result=result)

    async def failed(self, idem_key: str, result: dict, *, updated_at: str) -> None:
        await self.transition(idem_key, "failed", updated_at=updated_at, result=result)

    async def blocked(self, idem_key: str, result: dict, *, updated_at: str) -> None:
        await self.transition(idem_key, "blocked", updated_at=updated_at, result=result)

    async def skipped(self, idem_key: str, *, updated_at: str) -> None:
        await self.transition(idem_key, "skipped", updated_at=updated_at)

    async def deferred(self, idem_key: str, *, due_at: str, reason: str, updated_at: str) -> None:
        await self.transition(idem_key, "deferred", updated_at=updated_at)
        await self.db.execute(
            "INSERT INTO deferred_actions (idem_key, due_at, reason) VALUES (?, ?, ?) "
            "ON CONFLICT(idem_key) DO UPDATE SET due_at = excluded.due_at, reason = excluded.reason",
            (idem_key, due_at, reason),
        )
