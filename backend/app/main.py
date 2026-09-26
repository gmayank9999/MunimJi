import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from datetime import date

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.agent import ask, override
from app.agent.approvals import resolve_approval
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
from app.swy.executor import CallCtx
from app.workers import slack_poller

HEARTBEAT_SECONDS = 15


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    db = Database(settings.app_db_path)
    await db.connect()
    app.state.db = db
    app.state.bus = EventBus(db)
    poller_task = asyncio.create_task(slack_poller.run_forever(db))
    yield
    poller_task.cancel()
    await db.close()


app = FastAPI(title="MunimJi", lifespan=lifespan)

# The frontend fetches (and opens an EventSource) directly from the browser, not
# server-side - localhost:3000 -> localhost:8000 is cross-origin, and without this every
# one of those calls fails silently in the browser with no server-side trace of why.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    # False by default: this demo's every recipient (client emails, owner phone) is
    # allowlisted to safe sandboxed addresses (see config/allowlist.yaml), so a real
    # sweep is safe and is what makes the approval queue and actual reminders show up.
    # True is for a "simulate" run that must not touch anything client-facing.
    dry_run_sends: bool = False
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

    # explain/status/override/smalltalk answer synchronously, right here - no run record,
    # no sweep, no sse stream. Only sweep/simulate are long-running graph runs.
    if intent.intent in ("explain", "status"):
        question = intent.args.get("question") or body.prompt
        answer = await ask.answer(question, db=db, today=clock.now().isoformat())
        return {"run_id": None, "intent": intent.model_dump(), "answer": answer}

    if intent.intent == "override":
        ctx = CallCtx(run_id="override", node="override")
        answer = await override.apply_override(intent.args, ctx=ctx, db=db)
        return {"run_id": None, "intent": intent.model_dump(), "answer": answer}

    if intent.intent == "smalltalk":
        return {"run_id": None, "intent": intent.model_dump(), "answer": intent.reasoning}

    # "simulate" is a sweep that must never touch anything client-facing and shifts the
    # clock forward by the requested number of days, on top of the demo's own offset.
    dry_run_sends = body.dry_run_sends
    if intent.intent == "simulate":
        dry_run_sends = True
        days_ahead = intent.args.get("days")
        if isinstance(days_ahead, int):
            clock_offset_days += days_ahead
            clock = Clock(offset_days=clock_offset_days)

    run_id = f"run_{uuid.uuid4().hex[:12]}"
    await db.create_run(run_id, body.prompt, "ui", clock_offset_days, clock.now().isoformat())

    context = GraphContext(
        db=db, bus=bus, ledger=Ledger(db), allowlist=load_allowlist(),
        policy_config=load_policy_config(),
        flags=FeatureFlags(
            sheets=settings.feature_sheets, twilio=settings.feature_twilio,
            calendly=settings.feature_calendly, stripe_native_reminder=settings.feature_stripe_native_reminder,
        ),
        clock=clock, run_id=run_id, dry_run_sends=dry_run_sends,
        demo_epoch=settings.demo_epoch, llm_cache=False,
    )

    asyncio.create_task(_run_sweep_background(run_id, context, intent.args))
    return {"run_id": run_id, "intent": intent.model_dump()}


@app.get("/api/approvals")
async def list_approvals(request: Request):
    db: Database = request.app.state.db
    return [dict(r) for r in await db.list_pending_approvals()]


@app.post("/api/approvals/{idem_key}/approve")
async def approve_action(idem_key: str, request: Request):
    db: Database = request.app.state.db
    result = await resolve_approval(db, idem_key, approve=True, approval_channel="ui")
    if result is None:
        raise HTTPException(status_code=404, detail="no pending approval with that key")
    return result


@app.post("/api/approvals/{idem_key}/reject")
async def reject_action(idem_key: str, request: Request):
    db: Database = request.app.state.db
    result = await resolve_approval(db, idem_key, approve=False, approval_channel="ui")
    if result is None:
        raise HTTPException(status_code=404, detail="no pending approval with that key")
    return result


def _require_ext_key(x_munimji_ext_key: str | None = Header(default=None)) -> None:
    """MunimJi Lens (the browser extension) never stores credentials or calls
    providers directly - its service worker calls these routes with a shared key
    instead, so a leaked/forged request from a random page can't reach the backend."""
    if x_munimji_ext_key != get_settings().extension_key:
        raise HTTPException(status_code=401, detail="missing or invalid extension key")


@app.get("/api/ext/lookup")
async def ext_lookup(email: str, request: Request, _: None = Depends(_require_ext_key)):
    db: Database = request.app.state.db
    email_lower = email.strip().lower()
    clients = await db.list_clients()
    client = next((c for c in clients if c["email"].lower() == email_lower), None)
    if client is None:
        raise HTTPException(status_code=404, detail="no client with that email")

    # days_overdue must come from the demo's simulated clock, not the extension's real
    # wall-clock date - due dates were themselves shifted into the future by
    # CLOCK_OFFSET_DAYS at seed time (Stripe rejects a past due_date), so computing this
    # client-side against a real "now" undercounts every invoice, sometimes to zero.
    today = Clock(offset_days=get_settings().clock_offset_days).today()
    invoices = []
    for row in await db.list_invoices():
        if row["client_id"] != client["client_id"]:
            continue
        invoice = dict(row)
        invoice["days_overdue"] = max(0, (today - date.fromisoformat(invoice["due_date"])).days)
        invoices.append(invoice)

    return {"client": dict(client), "invoices": invoices}


@app.get("/api/ext/approvals")
async def ext_list_approvals(request: Request, _: None = Depends(_require_ext_key)):
    db: Database = request.app.state.db
    return [dict(r) for r in await db.list_pending_approvals()]


@app.post("/api/ext/approvals/{idem_key}/approve")
async def ext_approve(idem_key: str, request: Request, _: None = Depends(_require_ext_key)):
    db: Database = request.app.state.db
    result = await resolve_approval(db, idem_key, approve=True, approval_channel="extension")
    if result is None:
        raise HTTPException(status_code=404, detail="no pending approval with that key")
    return result


@app.post("/api/ext/approvals/{idem_key}/reject")
async def ext_reject(idem_key: str, request: Request, _: None = Depends(_require_ext_key)):
    db: Database = request.app.state.db
    result = await resolve_approval(db, idem_key, approve=False, approval_channel="extension")
    if result is None:
        raise HTTPException(status_code=404, detail="no pending approval with that key")
    return result


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
