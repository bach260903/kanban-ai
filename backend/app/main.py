"""FastAPI application entry: lifespan, health, API v1 shell, exception mapping."""

from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from app.database import dispose_engine, get_db  # noqa: F401 — dependency + lifespan
from app.middleware.error_handlers import register_exception_handlers

api_v1_router = APIRouter(prefix="/api/v1")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Shutdown: dispose async engine pool (startup is lazy-connect on first query)."""
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    application = FastAPI(title="Neo-Kanban API", lifespan=lifespan)
    register_exception_handlers(application)

    @application.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    application.include_router(api_v1_router)
    return application


app = create_app()
