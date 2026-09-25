from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="MunimJi", lifespan=lifespan)


@app.get("/api/health")
async def health():
    settings = get_settings()
    return {
        "status": "ok",
        "demo_mode": settings.demo_mode,
        "swytchcode_configured": bool(settings.swytchcode_bin or settings.swytchcode_token),
    }
