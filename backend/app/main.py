import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from sse_starlette.sse import EventSourceResponse

from app.db import Database
from app.events import EventBus
from app.settings import get_settings

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
