from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.routers import activity, agent, auth, boards, comments, skills, users, ws
from app.services import agent_runner

# Import models so Base.metadata includes all tables
from app import models  # noqa: F401

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    agent_runner.install_loop(asyncio.get_running_loop())
    yield


app = FastAPI(title="Kanban AI Multi-Agent Backend", version="0.3.0", lifespan=lifespan)

_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["http://localhost:3000"],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(boards.router, prefix="/api")
app.include_router(comments.router, prefix="/api")
app.include_router(skills.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(activity.router, prefix="/api")
app.include_router(agent.router, prefix="/api")
app.include_router(ws.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
