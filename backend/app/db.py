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
    decision TEXT, rule_id TEXT, reasons_json TEXT, counterfactuals_json TEXT,
    plan_json TEXT, results_json TEXT, explanation TEXT, created_at TEXT
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

    # -- clients --------------------------------------------------------------

    async def upsert_client(self, **fields: Any) -> None:
        columns = list(fields.keys())
        placeholders = ", ".join("?" for _ in columns)
        updates = ", ".join(f"{c} = excluded.{c}" for c in columns if c != "client_id")
        await self.execute(
            f"INSERT INTO clients ({', '.join(columns)}) VALUES ({placeholders}) "
            f"ON CONFLICT(client_id) DO UPDATE SET {updates}",
            tuple(fields.values()),
        )

    async def get_client(self, client_id: str) -> aiosqlite.Row | None:
        return await self.fetchone("SELECT * FROM clients WHERE client_id = ?", (client_id,))

    async def list_clients(self) -> list[aiosqlite.Row]:
        return await self.fetchall("SELECT * FROM clients ORDER BY name ASC")

    # -- invoices --------------------------------------------------------------

    async def upsert_invoice(self, **fields: Any) -> None:
        columns = list(fields.keys())
        placeholders = ", ".join("?" for _ in columns)
        updates = ", ".join(f"{c} = excluded.{c}" for c in columns if c != "invoice_id")
        await self.execute(
            f"INSERT INTO invoices ({', '.join(columns)}) VALUES ({placeholders}) "
            f"ON CONFLICT(invoice_id) DO UPDATE SET {updates}",
            tuple(fields.values()),
        )

    async def get_invoice(self, invoice_id: str) -> aiosqlite.Row | None:
        return await self.fetchone("SELECT * FROM invoices WHERE invoice_id = ?", (invoice_id,))

    async def list_invoices(self) -> list[aiosqlite.Row]:
        return await self.fetchall("SELECT * FROM invoices ORDER BY due_date ASC")

    # -- decisions / traces --------------------------------------------------------------

    async def insert_decision(self, **fields: Any) -> None:
        json_fields = {
            "facts_json", "signal_json", "severity_breakdown_json",
            "reasons_json", "counterfactuals_json", "plan_json", "results_json",
        }
        columns = list(fields.keys())
        values = [
            json.dumps(v) if c in json_fields and not isinstance(v, str) else v
            for c, v in fields.items()
        ]
        placeholders = ", ".join("?" for _ in columns)
        await self.execute(
            f"INSERT INTO decisions ({', '.join(columns)}) VALUES ({placeholders})", tuple(values)
        )

    async def get_invoice_trace(self, invoice_id: str) -> list[aiosqlite.Row]:
        return await self.fetchall(
            "SELECT * FROM decisions WHERE invoice_id = ? ORDER BY created_at ASC", (invoice_id,)
        )

    # -- tool calls --------------------------------------------------------------

    async def insert_tool_call(
        self,
        *,
        run_id: str,
        invoice_id: str | None,
        node: str,
        logical: str,
        canonical_id: str,
        ok: bool,
        policy_blocked: bool,
        duration_ms: int,
        ts: str,
    ) -> None:
        await self.execute(
            "INSERT INTO tool_calls (run_id, invoice_id, node, logical, canonical_id, ok, "
            "policy_blocked, duration_ms, ts) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (run_id, invoice_id, node, logical, canonical_id, int(ok), int(policy_blocked), duration_ms, ts),
        )

    async def list_tool_calls(self, limit: int = 100) -> list[aiosqlite.Row]:
        return await self.fetchall("SELECT * FROM tool_calls ORDER BY ts DESC LIMIT ?", (limit,))

    async def tool_call_counts_by_integration(self) -> list[aiosqlite.Row]:
        return await self.fetchall(
            "SELECT substr(logical, 1, instr(logical, '.') - 1) AS integration, COUNT(*) AS n "
            "FROM tool_calls GROUP BY integration ORDER BY n DESC"
        )

    # -- approvals --------------------------------------------------------------

    async def list_pending_approvals(self) -> list[aiosqlite.Row]:
        return await self.fetchall(
            "SELECT * FROM action_ledger WHERE status = 'pending_approval' ORDER BY created_at ASC"
        )

    # -- kpis --------------------------------------------------------------

    async def compute_kpis(self, *, today: str) -> dict[str, Any]:
        outstanding = await self.fetchone("SELECT COALESCE(SUM(due_inr), 0) AS total FROM invoices")
        overdue = await self.fetchone(
            "SELECT COALESCE(SUM(due_inr), 0) AS total FROM invoices WHERE due_date < ? AND due_inr > 0", (today,)
        )
        avg_days = await self.fetchone(
            "SELECT AVG(julianday(?) - julianday(due_date)) AS avg_days FROM invoices "
            "WHERE due_date < ? AND due_inr > 0",
            (today, today),
        )
        decisions_today = await self.fetchone(
            "SELECT COUNT(*) AS n FROM decisions WHERE created_at >= ?", (today,)
        )
        calls_today = await self.fetchone("SELECT COUNT(*) AS n FROM tool_calls WHERE ts >= ?", (today,))
        blocks_today = await self.fetchone(
            "SELECT COUNT(*) AS n FROM tool_calls WHERE ts >= ? AND policy_blocked = 1", (today,)
        )
        duplicates_prevented = await self.fetchone(
            "SELECT COUNT(*) AS n FROM trace_events WHERE type = 'idempotent.skip' AND ts >= ?", (today,)
        )
        return {
            "outstanding_inr": outstanding["total"],
            "overdue_inr": overdue["total"],
            "avg_days_overdue": round(avg_days["avg_days"] or 0, 1),
            "decisions_today": decisions_today["n"],
            "swytchcode_calls_today": calls_today["n"],
            "policy_blocks_today": blocks_today["n"],
            "duplicates_prevented_today": duplicates_prevented["n"],
        }
