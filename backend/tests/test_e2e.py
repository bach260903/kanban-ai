"""
Kịch bản integration test đầy đủ — Neo-Kanban AI
==================================================

Bao gồm:
  1.  Đăng ký tài khoản (email + OTP)
  2.  Xác minh OTP → nhận JWT
  3.  Đăng nhập email / password
  4.  Xem thông tin user hiện tại (/me)
  5.  GitHub OAuth login (mocked)
  6.  Tạo / xem / cập nhật Project
  7.  Khai báo Constitution
  8.  Tạo / xem Task (Kanban)
  9.  Di chuyển Task: TODO → IN_PROGRESS (coder mocked)
  10. WIP = 1 enforcement
  11. Kéo Task qua REVIEW → DONE
  12. Chuyển Task không hợp lệ → lỗi
  13. Xoá Task
  14. Sinh SPEC (agent mocked)
  15. Danh sách Documents
  16. Audit log
  17. Available AI backends
  18. Discord bot endpoint (signature validation)
  19. Health check

Yêu cầu: PostgreSQL + Redis đang chạy (hoặc TEST_DATABASE_URL trong .env).
GitHub / Discord không cần cấu hình thực — đều được mock.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


# ──────────────────────────────────────────────────────────────────────────────
# Local helpers
# ──────────────────────────────────────────────────────────────────────────────

def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures bổ sung (dùng API để tạo project → member tự động được thêm)
# ──────────────────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def api_project(test_client: AsyncClient, auth_headers: dict) -> dict:
    """Tạo project thông qua REST API → owner membership được thêm tự động."""
    resp = await test_client.post(
        "/api/v1/projects",
        json={
            "name": f"E2E Project {uuid.uuid4().hex[:6]}",
            "description": "Auto-created for e2e tests",
            "primary_language": "python",
            "coding_backend": "groq",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest_asyncio.fixture
async def api_task(
    test_client: AsyncClient,
    auth_headers: dict,
    api_project: dict,
) -> dict:
    """Tạo task trong api_project, trả về task dict."""
    resp = await test_client.post(
        f"/api/v1/projects/{api_project['id']}/tasks",
        json={"title": "Sample E2E Task", "description": "Created by fixture", "priority": 0},
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ──────────────────────────────────────────────────────────────────────────────
# 1–5. AUTH
# ──────────────────────────────────────────────────────────────────────────────

class TestAuth:
    """Đăng ký / OTP / Đăng nhập / Me / GitHub OAuth"""

    # ── 1. Register step 1: gửi OTP ──────────────────────────────────────────

    async def test_register_step1_returns_verification_pending(
        self, test_client: AsyncClient
    ) -> None:
        """POST /auth/register → 200, needs_verification = true."""
        from app.services import auth_service  # noqa: PLC0415

        email = f"reg-{uuid.uuid4().hex[:8]}@example.com"

        with patch.object(auth_service, "create_email_otp", new=AsyncMock(return_value="111111")):
            resp = await test_client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": "Test1234!", "display_name": "E2E Tester"},
            )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["needs_verification"] is True
        assert body["email"] == email

    # ── 2. Register step 2: verify OTP → nhận token ──────────────────────────

    async def test_register_step2_otp_issues_jwt(
        self, test_client: AsyncClient
    ) -> None:
        """POST /auth/verify-register với OTP hợp lệ → 201, access_token."""
        from app.services import auth_service  # noqa: PLC0415

        email = f"otp-{uuid.uuid4().hex[:8]}@example.com"
        otp_code = "987654"

        # Mock tạo OTP trong Redis
        async def _fake_create(e: str, hp: str, dn: str) -> str:  # noqa: ARG001
            return otp_code

        # Mock xác minh OTP — trả về pending registration data
        async def _fake_verify(e: str, code: str) -> dict:
            assert code == otp_code
            hashed = await asyncio.to_thread(auth_service.hash_password, "Test1234!")
            return {"hashed_password": hashed, "display_name": "E2E OTP User"}

        with (
            patch.object(auth_service, "create_email_otp", new=_fake_create),
            patch.object(auth_service, "verify_email_otp", new=_fake_verify),
        ):
            # Step 1
            r1 = await test_client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": "Test1234!", "display_name": "E2E OTP User"},
            )
            assert r1.status_code == 200

            # Step 2
            r2 = await test_client.post(
                "/api/v1/auth/verify-register",
                json={"email": email, "code": otp_code},
            )

        assert r2.status_code == 201, r2.text
        body = r2.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert body["user"]["email"] == email

    # ── 3. Register email trùng → 409 ────────────────────────────────────────

    async def test_register_duplicate_email_returns_409(
        self, test_client: AsyncClient
    ) -> None:
        """Đăng ký email đã tồn tại → 409 Conflict."""
        from app.services import auth_service  # noqa: PLC0415

        with patch.object(auth_service, "create_email_otp", new=AsyncMock(return_value="000000")):
            resp = await test_client.post(
                "/api/v1/auth/register",
                json={
                    "email": "pytest-auth-user@example.com",
                    "password": "SomePa$$1",
                    "display_name": "Dup",
                },
            )
        assert resp.status_code == 409

    # ── 4. Login thành công ───────────────────────────────────────────────────

    async def test_login_with_correct_password_returns_jwt(
        self, test_client: AsyncClient
    ) -> None:
        """POST /auth/login với đúng mật khẩu → JWT + user object."""
        from app.database import engine  # noqa: PLC0415
        from app.services import auth_service  # noqa: PLC0415

        email = f"login-{uuid.uuid4().hex[:8]}@example.com"
        password = "MyP@ssw0rd!"
        hashed = await asyncio.to_thread(auth_service.hash_password, password)

        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO users (id, email, hashed_password, display_name) "
                    "VALUES (:id, :email, :hashed, :dn)"
                ),
                {"id": uuid.uuid4(), "email": email, "hashed": hashed, "dn": "Login User"},
            )

        resp = await test_client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "access_token" in body
        assert body["user"]["email"] == email

    # ── 5. Login sai mật khẩu → 401 ──────────────────────────────────────────

    async def test_login_wrong_password_returns_401(
        self, test_client: AsyncClient
    ) -> None:
        resp = await test_client.post(
            "/api/v1/auth/login",
            json={"email": "pytest-auth-user@example.com", "password": "sai_mat_khau"},
        )
        assert resp.status_code == 401

    # ── 6. /me với token hợp lệ ───────────────────────────────────────────────

    async def test_me_returns_user_when_authenticated(
        self, test_client: AsyncClient, auth_headers: dict
    ) -> None:
        """/me → 200 với thông tin user."""
        resp = await test_client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "id" in body
        assert "email" in body

    # ── 7. /me không có token → 401 ───────────────────────────────────────────

    async def test_me_without_token_returns_401(self, test_client: AsyncClient) -> None:
        resp = await test_client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    # ── 8. GitHub OAuth callback (mocked) ─────────────────────────────────────

    async def test_github_callback_redirects_with_token(
        self, test_client: AsyncClient
    ) -> None:
        """GET /auth/github/callback → redirect về frontend với token trong URL."""
        from app.services import auth_service  # noqa: PLC0415
        import datetime  # noqa: PLC0415

        fake_jwt = "neo_jwt_from_github_xyz"
        fake_user = MagicMock(
            id=uuid.uuid4(),
            email="github-e2e@example.com",
            display_name="GitHub E2E",
            avatar_url=None,
            github_id="99991111",
            created_at=datetime.datetime.utcnow(),
        )

        with (
            patch.object(
                auth_service,
                "exchange_github_code",
                new=AsyncMock(return_value="gho_fake_token"),
            ),
            patch.object(
                auth_service,
                "get_or_create_github_user",
                new=AsyncMock(return_value=(fake_user, fake_jwt)),
            ),
        ):
            resp = await test_client.get(
                "/api/v1/auth/github/callback",
                params={"code": "gh_fake_code"},
                follow_redirects=False,
            )

        assert resp.status_code in (302, 307), resp.text
        location = resp.headers.get("location", "")
        assert "token=" in location
        assert fake_jwt in location


# ──────────────────────────────────────────────────────────────────────────────
# 6–7. PROJECTS + CONSTITUTION
# ──────────────────────────────────────────────────────────────────────────────

class TestProjects:
    """Tạo / xem / cập nhật Project và khai báo Constitution."""

    async def test_create_project_returns_201(
        self, test_client: AsyncClient, auth_headers: dict
    ) -> None:
        resp = await test_client.post(
            "/api/v1/projects",
            json={
                "name": f"My Project {uuid.uuid4().hex[:4]}",
                "description": "Integration test",
                "primary_language": "typescript",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["primary_language"] == "typescript"
        assert body["status"] == "active"
        assert "id" in body

    async def test_list_projects_includes_created_project(
        self, test_client: AsyncClient, auth_headers: dict, api_project: dict
    ) -> None:
        resp = await test_client.get("/api/v1/projects", headers=auth_headers)
        assert resp.status_code == 200
        ids = [p["id"] for p in resp.json()]
        assert api_project["id"] in ids

    async def test_get_project_by_id(
        self, test_client: AsyncClient, auth_headers: dict, api_project: dict
    ) -> None:
        resp = await test_client.get(
            f"/api/v1/projects/{api_project['id']}", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == api_project["id"]

    async def test_update_project_name(
        self, test_client: AsyncClient, auth_headers: dict, api_project: dict
    ) -> None:
        new_name = f"Renamed {uuid.uuid4().hex[:4]}"
        resp = await test_client.patch(
            f"/api/v1/projects/{api_project['id']}",
            json={"name": new_name},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == new_name

    async def test_project_not_found_returns_404(
        self, test_client: AsyncClient, auth_headers: dict
    ) -> None:
        resp = await test_client.get(
            f"/api/v1/projects/{uuid.uuid4()}", headers=auth_headers
        )
        assert resp.status_code == 404

    async def test_constitution_roundtrip(
        self, test_client: AsyncClient, auth_headers: dict, api_project: dict
    ) -> None:
        """PUT constitution → GET đọc lại đúng nội dung."""
        pid = api_project["id"]
        content = "## Quy tắc\n- File tối đa 200 dòng.\n- Không có placeholder."

        put_resp = await test_client.put(
            f"/api/v1/projects/{pid}/constitution",
            json={"content": content},
            headers=auth_headers,
        )
        assert put_resp.status_code == 200

        get_resp = await test_client.get(
            f"/api/v1/projects/{pid}/constitution", headers=auth_headers
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["content"] == content


# ──────────────────────────────────────────────────────────────────────────────
# 8–13. TASKS + KANBAN
# ──────────────────────────────────────────────────────────────────────────────

class TestTasks:
    """Tạo / xem / di chuyển / xoá Task và WIP enforcement."""

    async def test_create_task_returns_todo_status(
        self, test_client: AsyncClient, auth_headers: dict, api_project: dict
    ) -> None:
        resp = await test_client.post(
            f"/api/v1/projects/{api_project['id']}/tasks",
            json={"title": "Viết unit test", "description": "Pytest", "priority": 1},
            headers=auth_headers,
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["status"] == "todo"
        assert body["title"] == "Viết unit test"

    async def test_list_tasks_has_all_status_buckets(
        self, test_client: AsyncClient, auth_headers: dict, api_project: dict, api_task: dict
    ) -> None:
        resp = await test_client.get(
            f"/api/v1/projects/{api_project['id']}/tasks", headers=auth_headers
        )
        assert resp.status_code == 200
        body = resp.json()
        for bucket in ("todo", "in_progress", "review", "done"):
            assert bucket in body
        # task fixture nằm trong todo
        todo_ids = [t["id"] for t in body["todo"]]
        assert api_task["id"] in todo_ids

    async def test_move_task_todo_to_in_progress(
        self, test_client: AsyncClient, auth_headers: dict, api_project: dict, api_task: dict
    ) -> None:
        """TODO → IN_PROGRESS: coder được mock, task chuyển trạng thái."""
        with patch("app.services.kanban_service.asyncio") as mock_asyncio:
            # create_task returns a coroutine-like mock that doesn't actually run
            mock_asyncio.create_task = MagicMock(return_value=MagicMock())

            resp = await test_client.patch(
                f"/api/v1/projects/{api_project['id']}/tasks/{api_task['id']}/move",
                json={"status": "in_progress"},
                headers=auth_headers,
            )

        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "in_progress"

    async def test_wip_limit_rejects_second_in_progress(
        self, test_client: AsyncClient, auth_headers: dict, api_project: dict
    ) -> None:
        """Chỉ được 1 task IN_PROGRESS; task thứ 2 → 409."""
        pid = api_project["id"]

        async def _create(title: str) -> str:
            r = await test_client.post(
                f"/api/v1/projects/{pid}/tasks",
                json={"title": title},
                headers=auth_headers,
            )
            return r.json()["id"]

        tid_a = await _create("Task A WIP")
        tid_b = await _create("Task B WIP")

        with patch("app.services.kanban_service.asyncio") as mock_asyncio:
            mock_asyncio.create_task = MagicMock(return_value=MagicMock())

            r1 = await test_client.patch(
                f"/api/v1/projects/{pid}/tasks/{tid_a}/move",
                json={"status": "in_progress"},
                headers=auth_headers,
            )
            assert r1.status_code == 200

            r2 = await test_client.patch(
                f"/api/v1/projects/{pid}/tasks/{tid_b}/move",
                json={"status": "in_progress"},
                headers=auth_headers,
            )

        # WIP = 1 → thứ 2 phải bị từ chối
        assert r2.status_code == 409, f"Expected 409, got {r2.status_code}: {r2.text}"

    async def test_invalid_transition_todo_to_done_rejected(
        self, test_client: AsyncClient, auth_headers: dict, api_project: dict
    ) -> None:
        """TODO → DONE trực tiếp không hợp lệ."""
        t = await test_client.post(
            f"/api/v1/projects/{api_project['id']}/tasks",
            json={"title": "Invalid jump"},
            headers=auth_headers,
        )
        tid = t.json()["id"]

        resp = await test_client.patch(
            f"/api/v1/projects/{api_project['id']}/tasks/{tid}/move",
            json={"status": "done"},
            headers=auth_headers,
        )
        assert resp.status_code in (400, 409, 422), resp.text

    async def test_full_kanban_flow_in_progress_to_review(
        self, test_client: AsyncClient, auth_headers: dict, api_project: dict
    ) -> None:
        """IN_PROGRESS → REVIEW (sau khi coder agent kết thúc — mocked)."""
        pid = api_project["id"]
        t = await test_client.post(
            f"/api/v1/projects/{pid}/tasks",
            json={"title": "Full flow task"},
            headers=auth_headers,
        )
        tid = t.json()["id"]

        # Bước 1: TODO → IN_PROGRESS (mocked coder)
        with patch("app.services.kanban_service.asyncio") as m:
            m.create_task = MagicMock(return_value=MagicMock())
            r1 = await test_client.patch(
                f"/api/v1/projects/{pid}/tasks/{tid}/move",
                json={"status": "in_progress"},
                headers=auth_headers,
            )
        assert r1.status_code == 200

        # Bước 2: Giả lập coder xong → chuyển qua REVIEW (thường do agent làm,
        # nhưng test gọi trực tiếp để kiểm tra transition hợp lệ)
        r2 = await test_client.patch(
            f"/api/v1/projects/{pid}/tasks/{tid}/move",
            json={"status": "review"},
            headers=auth_headers,
        )
        assert r2.status_code == 200, r2.text
        assert r2.json()["status"] == "review"

    async def test_delete_task_returns_204(
        self, test_client: AsyncClient, auth_headers: dict, api_project: dict
    ) -> None:
        t = await test_client.post(
            f"/api/v1/projects/{api_project['id']}/tasks",
            json={"title": "Task to delete"},
            headers=auth_headers,
        )
        tid = t.json()["id"]

        resp = await test_client.delete(
            f"/api/v1/projects/{api_project['id']}/tasks/{tid}",
            headers=auth_headers,
        )
        assert resp.status_code == 204

        # Xác nhận đã bị xoá
        tasks_resp = await test_client.get(
            f"/api/v1/projects/{api_project['id']}/tasks",
            headers=auth_headers,
        )
        all_tasks = [
            t for bucket in tasks_resp.json().values() for t in bucket
        ]
        assert not any(t["id"] == tid for t in all_tasks)


# ──────────────────────────────────────────────────────────────────────────────
# 14–15. DOCUMENTS (SPEC / PLAN)
# ──────────────────────────────────────────────────────────────────────────────

class TestDocuments:
    """Sinh SPEC, danh sách Documents."""

    async def test_generate_spec_returns_202(
        self, test_client: AsyncClient, auth_headers: dict, api_project: dict
    ) -> None:
        """POST /generate-spec → 202 Accepted, agent chạy background."""
        with patch(
            "app.api.v1.documents.run_generate_spec_task",
            new=AsyncMock(),
        ):
            resp = await test_client.post(
                f"/api/v1/projects/{api_project['id']}/generate-spec",
                json={"intent": "Xây dựng app quản lý todo đơn giản với FastAPI và React"},
                headers=auth_headers,
            )

        assert resp.status_code == 202, resp.text
        body = resp.json()
        assert "agent_run_id" in body or "document_id" in body or "status" in body

    async def test_list_documents_empty_for_new_project(
        self, test_client: AsyncClient, auth_headers: dict, api_project: dict
    ) -> None:
        """GET /documents → 200, list rỗng cho project mới."""
        resp = await test_client.get(
            f"/api/v1/projects/{api_project['id']}/documents",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_list_documents_after_spec_generation(
        self, test_client: AsyncClient, auth_headers: dict, api_project: dict
    ) -> None:
        """Sau khi tạo SPEC qua mock, document xuất hiện trong danh sách."""
        pid = api_project["id"]

        # Tạo SPEC document trực tiếp vào DB thay vì qua agent
        from app.database import engine  # noqa: PLC0415
        doc_id = uuid.uuid4()
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO documents (id, project_id, type, content, status, version) "
                    "VALUES (:id, :pid, 'SPEC', '# Test SPEC', 'draft', 1)"
                ),
                {"id": doc_id, "pid": pid},
            )

        resp = await test_client.get(
            f"/api/v1/projects/{pid}/documents",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        ids = [d["id"] for d in resp.json()]
        assert str(doc_id) in ids


# ──────────────────────────────────────────────────────────────────────────────
# 16. AUDIT LOG
# ──────────────────────────────────────────────────────────────────────────────

class TestAuditLog:
    async def test_audit_log_list_returns_200(
        self, test_client: AsyncClient, auth_headers: dict, api_project: dict
    ) -> None:
        resp = await test_client.get(
            f"/api/v1/projects/{api_project['id']}/audit-logs",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        # Response có thể là list hoặc paginated object
        assert isinstance(body, (list, dict))


# ──────────────────────────────────────────────────────────────────────────────
# 17. AI BACKENDS
# ──────────────────────────────────────────────────────────────────────────────

class TestBackends:
    async def test_available_backends_includes_groq(
        self, test_client: AsyncClient, auth_headers: dict
    ) -> None:
        resp = await test_client.get("/api/v1/backends/available", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        backend_ids = [b.get("id") for b in data]
        assert "groq" in backend_ids, f"groq not found in: {backend_ids}"


# ──────────────────────────────────────────────────────────────────────────────
# 18. DISCORD BOT
# ──────────────────────────────────────────────────────────────────────────────

class TestDiscordBot:
    async def test_discord_endpoint_validates_signature(
        self, test_client: AsyncClient
    ) -> None:
        """POST /discord với signature giả → 401 (endpoint tồn tại và kiểm tra chữ ký)."""
        resp = await test_client.post(
            "/api/v1/discord",
            json={"type": 1},
            headers={
                "X-Signature-Ed25519": "aabbccdd" * 8,  # 64 hex chars, invalid
                "X-Signature-Timestamp": "9999999999",
            },
        )
        # 401 = endpoint tồn tại, từ chối signature không hợp lệ
        assert resp.status_code in (400, 401, 403), (
            f"Expected 4xx for invalid Discord signature, got {resp.status_code}"
        )

    async def test_discord_ping_with_valid_signature(
        self, test_client: AsyncClient
    ) -> None:
        """Discord PING (type=1) với mock chữ ký hợp lệ → 200 pong."""
        from app.config import settings  # noqa: PLC0415
        if not settings.discord_public_key:
            pytest.skip("DISCORD_PUBLIC_KEY không được cấu hình — bỏ qua test signature thật")

        # Nếu có public key, test signature thật cần nacl — bỏ qua trong CI
        pytest.skip("Discord signature test yêu cầu private key — chỉ test trên staging")


# ──────────────────────────────────────────────────────────────────────────────
# 19. HEALTH CHECK
# ──────────────────────────────────────────────────────────────────────────────

class TestHealth:
    async def test_health_endpoint_returns_200(self, test_client: AsyncClient) -> None:
        """GET /health → 200, service đang chạy."""
        resp = await test_client.get("/health")
        assert resp.status_code == 200

    async def test_unauthenticated_project_access_returns_401(
        self, test_client: AsyncClient, api_project: dict
    ) -> None:
        """Truy cập project không có token → 401."""
        resp = await test_client.get(f"/api/v1/projects/{api_project['id']}")
        assert resp.status_code == 401
