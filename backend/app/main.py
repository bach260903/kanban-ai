"""FastAPI application entry: lifespan, health, API v1 shell, exception mapping."""

from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from app.api.v1.agent_runs import router as agent_runs_router
from app.api.v1.documents import router as documents_router
from app.api.v1.projects import router as projects_router
from app.api.v1.tasks import router as tasks_router
from app.database import dispose_engine, get_db  # noqa: F401 — dependency + lifespan
from app.middleware.error_handlers import register_exception_handlers

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(projects_router)
api_v1_router.include_router(documents_router)
api_v1_router.include_router(tasks_router)
api_v1_router.include_router(agent_runs_router)


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
