import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
from fastapi.middleware.cors import CORSMiddleware

from apps.api.db import engine
from apps.api.routers import auth, datasets


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title="CortexBI",
    version="0.1.0",
    description="AI-powered CSV analytics platform",
    lifespan=lifespan,
)

allowed_origins = os.getenv(
    "CORS_ORIGINS", "http://localhost:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(datasets.router)
app.include_router(datasets.shared_router)


@app.get("/health")
async def health():
    from apps.api.db import async_session
    try:
        async with async_session() as session:
            await session.execute(__import__("sqlalchemy").text("SELECT 1"))
        return {"status": "ok"}
    except Exception:
        return {"status": "degraded", "db": "unreachable"}
