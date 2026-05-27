"""T119: verify required API v1 routers are registered on the FastAPI app."""

from __future__ import annotations

from fastapi.routing import APIRoute

from app.main import app

# Representative paths per router (prefix /api/v1 is applied in main.py).
REQUIRED_ROUTE_FRAGMENTS = [
    "/auth/",  # auth_router
    "/projects/{project_id}/members",  # members_router
    "/invitations/{token}/accept",  # members_router
    "/projects/{project_id}/tasks/{task_id}/dependencies",  # dependencies_router
    "/templates",  # templates_router
    "/notifications",  # notifications_router
    "/projects/{project_id}/webhooks",  # webhooks_router
    "/projects/{project_id}/github",  # github_router
    "/dashboard",  # analytics_router
    "/projects",  # projects_router
    "/projects/{project_id}/tasks",  # tasks_router
    "/tasks/{task_id}/review",  # review_router
    "/projects/{project_id}/documents",  # documents_router
    "/tasks/{task_id}/branch",  # branches_router
    "/projects/{project_id}/audit-logs",  # audit_logs_router
    "/backends",  # backends_router
    "/projects/{project_id}/codebase-map",  # codebase_router
    "/projects/{project_id}/tasks/{task_id}/pause",  # pause_router
    "/agent-runs",  # agent_runs_router
    "/dev/",  # dev_auth_router
]


def _collect_api_paths() -> set[str]:
    paths: set[str] = set()

    def walk(routes: list) -> None:
        for route in routes:
            if isinstance(route, APIRoute):
                paths.add(route.path)
            elif hasattr(route, "routes"):
                walk(route.routes)

    walk(app.routes)
    return paths


def test_phase10_required_routers_registered() -> None:
    paths = _collect_api_paths()
    missing: list[str] = []
    for fragment in REQUIRED_ROUTE_FRAGMENTS:
        if not any(fragment in path for path in paths):
            missing.append(fragment)
    assert not missing, f"Missing routes for fragments: {missing}. Registered: {sorted(paths)}"
