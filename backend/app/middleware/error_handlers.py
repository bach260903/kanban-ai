"""Map domain exceptions to HTTP error responses."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.exceptions import (
    InvalidTransitionError,
    NotFoundError,
    SandboxEscapeError,
    WIPLimitError,
)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def _not_found(_request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc) or "Not found."})

    @app.exception_handler(WIPLimitError)
    async def _wip(_request: Request, exc: WIPLimitError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc) or "Conflict."})

    @app.exception_handler(InvalidTransitionError)
    async def _invalid_transition(_request: Request, exc: InvalidTransitionError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc) or "Bad request."})

    @app.exception_handler(SandboxEscapeError)
    async def _sandbox(_request: Request, exc: SandboxEscapeError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc) or "Bad request."})
