import asyncio
import json
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.agent.context import GraphContext
from app.agent.graph import run_sweep
from app.agent.supervisor import classify_intent
from app.clock import Clock
from app.db import Database
from app.events import EventBus
from app.governance.allowlist import load_allowlist
from app.governance.ledger import Ledger
from app.policy.config import load_policy_config
from app.policy.explain import generate_decision_table_markdown
from app.policy.router import FeatureFlags
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
        # No "event" field: browser EventSource.onmessage only fires for the unnamed
        # default event type, so a named "event" here would silently never be received.
        # The event's own type is already inside the JSON payload.
        for event in await bus.replay(run_id):
            if await request.is_disconnected():
                return
            yield {"data": json.dumps(event)}

        queue = bus.subscribe(run_id)
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
                    yield {"data": json.dumps(event)}
                except TimeoutError:
                    yield {"data": "{}"}
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
    # Must match the Time-Machine offset every sweep runs with, or "today" here is the
    # real date while due_date/decision facts are all shifted - overdue_inr and
    # avg_days_overdue would silently read as 0 even for genuinely overdue invoices.
    today = Clock(offset_days=get_settings().clock_offset_days).today().isoformat()
    return await db.compute_kpis(today=today)


@app.get("/api/policy")
async def policy():
    config = load_policy_config()
    return {
        "config": config.model_dump(),
        "decision_table_markdown": generate_decision_table_markdown(config),
    }


class RunRequest(BaseModel):
    prompt: str = "check all payments"
    dry_run_sends: bool = True
    clock_offset_days: int | None = None


async def _run_sweep_background(run_id: str, context: GraphContext, intent_args: dict) -> None:
    settings = get_settings()
    try:
        await run_sweep(
            run_id=run_id, context=context, intent_args=intent_args,
            checkpoint_db_path=settings.checkpoint_db_path,
        )
    except Exception as exc:  # noqa: BLE001 - a crashed sweep must still close out the run record
        now = context.clock.now().isoformat()
        await context.db.finish_run(run_id, now, {"error": str(exc)})
        await context.bus.emit(run_id, "run.failed", "run", {"error": str(exc)})


@app.post("/api/run")
async def start_run(body: RunRequest, request: Request):
    settings = get_settings()
    db: Database = request.app.state.db
    bus: EventBus = request.app.state.bus

    clock_offset_days = (
        body.clock_offset_days if body.clock_offset_days is not None else settings.clock_offset_days
    )
    clock = Clock(offset_days=clock_offset_days)
    intent = await classify_intent(body.prompt, now_ist=clock.now().isoformat(), db=db, cache=False)

    run_id = f"run_{uuid.uuid4().hex[:12]}"
    await db.create_run(run_id, body.prompt, "ui", clock_offset_days, clock.now().isoformat())

    context = GraphContext(
        db=db, bus=bus, ledger=Ledger(db), allowlist=load_allowlist(),
        policy_config=load_policy_config(),
        flags=FeatureFlags(
            sheets=settings.feature_sheets, twilio=settings.feature_twilio,
            calendly=settings.feature_calendly, stripe_native_reminder=settings.feature_stripe_native_reminder,
        ),
        clock=clock, run_id=run_id, dry_run_sends=body.dry_run_sends,
        demo_epoch=settings.demo_epoch, llm_cache=False,
    )

    asyncio.create_task(_run_sweep_background(run_id, context, intent.args))
    return {"run_id": run_id, "intent": intent.model_dump()}


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
