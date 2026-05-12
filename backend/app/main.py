"""FastAPI application entry (routers and lifespan wired in T015)."""

from fastapi import APIRouter, FastAPI

from app.database import get_db  # noqa: F401 — used by routes (T015+) and test overrides

api_v1_router = APIRouter(prefix="/api/v1")

app = FastAPI(title="Neo-Kanban API")
app.include_router(api_v1_router)
