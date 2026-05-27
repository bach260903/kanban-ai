"""FastAPI application entry: lifespan, health, API v1 shell, exception mapping."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.dev_auth import router as dev_auth_router
from app.api.v1.agent_runs import router as agent_runs_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.audit_logs import router as audit_logs_router
from app.api.v1.backends import router as backends_router
from app.api.v1.branches import router as branches_router
from app.api.v1.codebase import router as codebase_router
from app.api.v1.dependencies import router as dependencies_router
from app.api.v1.documents import router as documents_router
from app.api.v1.github import router as github_router
from app.api.v1.members import router as members_router
from app.api.v1.memory import router as memory_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.pause import pause_router
from app.api.v1.projects import router as projects_router
from app.api.v1.review import router as review_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.templates import router as templates_router
from app.api.v1.webhooks import router as webhooks_router
from app.config import settings
from app.database import dispose_engine, get_db  # noqa: F401 — dependency + lifespan
from app.middleware.error_handlers import register_exception_handlers
from app.routers.auth import router as auth_router
from app.services import webhook_service
from app.websocket import ws_handler

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(auth_router)
api_v1_router.include_router(projects_router)
api_v1_router.include_router(members_router)
api_v1_router.include_router(backends_router)
api_v1_router.include_router(audit_logs_router)
api_v1_router.include_router(documents_router)
api_v1_router.include_router(memory_router)
api_v1_router.include_router(codebase_router)
api_v1_router.include_router(branches_router)
api_v1_router.include_router(tasks_router)
api_v1_router.include_router(dependencies_router)
api_v1_router.include_router(templates_router)
api_v1_router.include_router(analytics_router)
api_v1_router.include_router(notifications_router)
api_v1_router.include_router(webhooks_router)
api_v1_router.include_router(github_router)
api_v1_router.include_router(review_router)
api_v1_router.include_router(pause_router)
api_v1_router.include_router(agent_runs_router)
api_v1_router.include_router(dev_auth_router)

logger = logging.getLogger(__name__)

_webhook_worker: asyncio.Task | None = None


def _webhook_worker_enabled() -> bool:
    return os.environ.get("DISABLE_WEBHOOK_WORKER", "").lower() not in ("1", "true", "yes")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Startup: webhook worker; shutdown: cancel worker and dispose DB pool."""
    global _webhook_worker
    logger.info(
        "JWT auth: secret_key=%s... algorithm=%s expire_days=%d",
        settings.jwt_secret_key[:6] if settings.jwt_secret_key else "MISSING",
        settings.jwt_algorithm,
        settings.jwt_expire_days,
    )
    if _webhook_worker_enabled():
        _webhook_worker = asyncio.create_task(webhook_service.process_deliveries())
        logger.info("Webhook delivery worker started")
    else:
        logger.info("Webhook delivery worker disabled")
    yield
    if _webhook_worker is not None:
        _webhook_worker.cancel()
        await asyncio.gather(_webhook_worker, return_exceptions=True)
    await dispose_engine()


def create_app() -> FastAPI:
    application = FastAPI(title="Neo-Kanban API", lifespan=lifespan)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(application)

    @application.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    application.include_router(api_v1_router)
    application.add_api_websocket_route("/ws/tasks/{task_id}/stream", ws_handler.handle)
    return application


app = create_app()
