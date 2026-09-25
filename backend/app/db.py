import json
from pathlib import Path
from typing import Any

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY, prompt TEXT, source TEXT, intent TEXT, clock_offset_days INTEGER,
    status TEXT, started_at TEXT, finished_at TEXT, summary_json TEXT
);
CREATE TABLE IF NOT EXISTS trace_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, seq INTEGER, ts TEXT,
    type TEXT, node TEXT, invoice_id TEXT, payload_json TEXT
);
CREATE TABLE IF NOT EXISTS tool_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, invoice_id TEXT, node TEXT,
    logical TEXT, canonical_id TEXT, ok INTEGER, policy_blocked INTEGER, duration_ms INTEGER, ts TEXT
);
CREATE TABLE IF NOT EXISTS invoices (
    invoice_id TEXT PRIMARY KEY, number TEXT, client_id TEXT, status TEXT,
    amount_inr INTEGER, due_inr INTEGER, invoice_date TEXT, due_date TEXT,
    reminder_count INTEGER DEFAULT 0, last_reminder_at TEXT, last_client_msg_at TEXT,
    promise_date TEXT, promise_source_msg TEXT, dispute_open INTEGER DEFAULT 0,
    jira_key TEXT, notion_page_id TEXT, state TEXT, last_decision TEXT, last_severity INTEGER,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS clients (
    client_id TEXT PRIMARY KEY, name TEXT, email TEXT, tier TEXT, contact_name TEXT,
    relationship_notes TEXT, notion_page_id TEXT, paused_until TEXT
);
CREATE TABLE IF NOT EXISTS interpretations (
    message_id TEXT PRIMARY KEY, invoice_id TEXT, signal_json TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, invoice_id TEXT, as_of TEXT,
    facts_json TEXT, signal_json TEXT, severity INTEGER, severity_breakdown_json TEXT,
    decision TEXT, rule_id TEXT, reasons_json TEXT, plan_json TEXT, results_json TEXT,
    explanation TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS action_ledger (
    idem_key TEXT PRIMARY KEY, run_id TEXT, thread_id TEXT, invoice_id TEXT,
    action_type TEXT, tool TEXT, payload_json TEXT,
    status TEXT CHECK(status IN ('planned','pending_approval','approved','executing','done',
                                 'rejected','failed','blocked','skipped','deferred')),
    approval_channel TEXT, approval_ts TEXT, result_json TEXT, created_at TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS deferred_actions (
    idem_key TEXT PRIMARY KEY, due_at TEXT, reason TEXT
);
CREATE TABLE IF NOT EXISTS cursors (
    name TEXT PRIMARY KEY, value TEXT
);
CREATE TABLE IF NOT EXISTS llm_cache (
    key TEXT PRIMARY KEY, output_json TEXT, created_at TEXT
);
"""


class Database:
    def __init__(self, path: str):
        self.path = path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> aiosqlite.Connection:
        if self._conn is not None:
            return self._conn
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        conn = await aiosqlite.connect(self.path)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        await conn.executescript(SCHEMA)
        await conn.commit()
        self._conn = conn
        return conn

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def execute(self, sql: str, params: tuple = ()) -> None:
        conn = await self.connect()
        await conn.execute(sql, params)
        await conn.commit()

    async def fetchone(self, sql: str, params: tuple = ()) -> aiosqlite.Row | None:
        conn = await self.connect()
        async with conn.execute(sql, params) as cursor:
            return await cursor.fetchone()

    async def fetchall(self, sql: str, params: tuple = ()) -> list[aiosqlite.Row]:
        conn = await self.connect()
        async with conn.execute(sql, params) as cursor:
            return await cursor.fetchall()

    # -- runs --------------------------------------------------------------

    async def create_run(
        self, run_id: str, prompt: str, source: str, clock_offset_days: int, started_at: str
    ) -> None:
        await self.execute(
            "INSERT INTO runs (run_id, prompt, source, clock_offset_days, status, started_at) "
            "VALUES (?, ?, ?, ?, 'running', ?)",
            (run_id, prompt, source, clock_offset_days, started_at),
        )

    async def finish_run(self, run_id: str, finished_at: str, summary: dict[str, Any]) -> None:
        await self.execute(
            "UPDATE runs SET status = 'finished', finished_at = ?, summary_json = ? WHERE run_id = ?",
            (finished_at, json.dumps(summary), run_id),
        )

    async def get_run(self, run_id: str) -> aiosqlite.Row | None:
        return await self.fetchone("SELECT * FROM runs WHERE run_id = ?", (run_id,))

    async def list_runs(self, limit: int = 50) -> list[aiosqlite.Row]:
        return await self.fetchall(
            "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,)
        )

    # -- trace events --------------------------------------------------------

    async def insert_trace_event(
        self, run_id: str, seq: int, ts: str, type_: str, node: str, invoice_id: str | None, payload: dict[str, Any]
    ) -> None:
        await self.execute(
            "INSERT INTO trace_events (run_id, seq, ts, type, node, invoice_id, payload_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (run_id, seq, ts, type_, node, invoice_id, json.dumps(payload)),
        )

    async def get_trace_events(self, run_id: str) -> list[aiosqlite.Row]:
        return await self.fetchall(
            "SELECT * FROM trace_events WHERE run_id = ? ORDER BY seq ASC", (run_id,)
        )

    # -- cursors --------------------------------------------------------------

    async def get_cursor(self, name: str) -> str | None:
        row = await self.fetchone("SELECT value FROM cursors WHERE name = ?", (name,))
        return row["value"] if row else None

    async def set_cursor(self, name: str, value: str) -> None:
        await self.execute(
            "INSERT INTO cursors (name, value) VALUES (?, ?) "
            "ON CONFLICT(name) DO UPDATE SET value = excluded.value",
            (name, value),
        )
