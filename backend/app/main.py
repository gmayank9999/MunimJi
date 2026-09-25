import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from app.clock import Clock
from app.db import Database
from app.events import EventBus
from app.policy.config import load_policy_config
from app.policy.explain import generate_decision_table_markdown
from app.settings import get_settings
from app.swy import audit as swy_audit

HEARTBEAT_SECONDS = 15


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    db = Database(settings.app_db_path)
    await db.connect()
    app.state.db = db
    app.state.bus = EventBus(db)
    yield
    await db.close()


app = FastAPI(title="MunimJi", lifespan=lifespan)


@app.get("/api/health")
async def health():
    settings = get_settings()
    return {
        "status": "ok",
        "demo_mode": settings.demo_mode,
        "swytchcode_configured": bool(settings.swytchcode_bin or settings.swytchcode_token),
    }


@app.get("/api/runs/{run_id}/events")
async def run_events(run_id: str, request: Request):
    bus: EventBus = request.app.state.bus

    async def generator():
        for event in await bus.replay(run_id):
            if await request.is_disconnected():
                return
            yield {"event": event["type"], "data": json.dumps(event)}

        queue = bus.subscribe(run_id)
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
                    yield {"event": event["type"], "data": json.dumps(event)}
                except TimeoutError:
                    yield {"event": "heartbeat", "data": "{}"}
        finally:
            bus.unsubscribe(run_id, queue)

    return EventSourceResponse(generator())


@app.get("/api/runs")
async def list_runs(request: Request):
    db: Database = request.app.state.db
    return [dict(r) for r in await db.list_runs()]


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str, request: Request):
    db: Database = request.app.state.db
    row = await db.get_run(run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="run not found")
    return dict(row)


@app.get("/api/invoices")
async def list_invoices(request: Request):
    db: Database = request.app.state.db
    return [dict(r) for r in await db.list_invoices()]


@app.get("/api/invoices/{invoice_id}/trace")
async def invoice_trace(invoice_id: str, request: Request):
    db: Database = request.app.state.db
    return [dict(r) for r in await db.get_invoice_trace(invoice_id)]


@app.get("/api/clients")
async def list_clients(request: Request):
    db: Database = request.app.state.db
    return [dict(r) for r in await db.list_clients()]


@app.get("/api/kpis")
async def kpis(request: Request):
    db: Database = request.app.state.db
    today = Clock().today().isoformat()
    return await db.compute_kpis(today=today)


@app.get("/api/policy")
async def policy():
    config = load_policy_config()
    return {
        "config": config.model_dump(),
        "decision_table_markdown": generate_decision_table_markdown(config),
    }


@app.get("/api/audit")
async def audit(request: Request):
    db: Database = request.app.state.db
    tool_calls, integration_counts, policy_log, stats = await asyncio.gather(
        db.list_tool_calls(),
        db.tool_call_counts_by_integration(),
        swy_audit.policy_log(),
        swy_audit.stats(),
    )
    return {
        "tool_calls": [dict(r) for r in tool_calls],
        "calls_by_integration": [dict(r) for r in integration_counts],
        "swytchcode_policy_log": policy_log,
        "swytchcode_stats": stats,
    }
