"""FastAPI application entry (routers and lifespan wired in T015)."""

from fastapi import APIRouter, FastAPI

api_v1_router = APIRouter(prefix="/api/v1")

app = FastAPI(title="Neo-Kanban API")
app.include_router(api_v1_router)
