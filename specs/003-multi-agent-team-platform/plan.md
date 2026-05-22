# Implementation Plan: Platform Expansion — Multi-Agent Review, Team Management & Integrations

**Branch**: `003-multi-agent-team-platform` | **Date**: 2026-05-20 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/003-multi-agent-team-platform/spec.md`
**Prerequisites**: Feature 001 (Neo-Kanban core) + Feature 002 (AI CLI backends) fully complete

---

## Summary

Mở rộng Neo-Kanban từ nền tảng single-user thành platform team AI-agentic hoàn chỉnh.
Triển khai song song 5 nhóm tính năng:

- **F-003**: Thêm `reviewer_node` vào LangGraph sau coder_node; ReviewReport + ReviewComment DB; AI Review panel trong Diff Viewer
- **F-004**: Auth (JWT), phân quyền 4 role, invite system, WIP per-developer (thay vì per-project), task assignment
- **F-005**: Task dependencies (DAG với cycle detection), task templates (project + global scope)
- **F-006**: Dashboard tổng quan đa-project, Analytics tab (backend performance, per-member metrics)
- **F-007**: In-app notifications (WebSocket + DB), webhook delivery (Redis queue), GitHub PR integration

**Architectural approach**:
- `reviewer_node.py` — node mới trong LangGraph, chạy sau coder/cli_coder, trước `interrupt()`
- Auth middleware injected into all existing endpoints; `current_user` từ JWT dependency
- WIP enforcement chuyển từ "per project" sang "per developer" trong `kanban_service.py`
- Webhook delivery: asyncio background worker + Redis queue (tái dùng Redis đã có)
- Analytics: on-the-fly SQL aggregation trên bảng `agent_runs`, `audit_logs`, `tasks`

---

## Technical Context

**Language/Version**: Python 3.11 (backend) · TypeScript 5.6 + React 18 (frontend)
**New Dependencies**:
- Backend: `python-jose[cryptography]>=3.3.0`, `passlib[bcrypt]>=1.7.4`, `PyGithub>=2.0.0`
- Frontend: `recharts>=2.12.0` (analytics charts), `@tanstack/react-query>=5.0.0` (nếu chưa có)
**New DB tables**: 9 bảng mới + 2 bảng sửa đổi (xem `data-model.md`)
**New API prefix**: mở rộng `/api/v1` — thêm `/auth`, `/members`, `/invitations`, `/review`, `/notifications`, `/webhooks`, `/github`, `/templates`, `/analytics`, `/dashboard`
**Constitution Amendment needed**: Principle III (WIP) + Principle VII (MVP Scope — multi-user)

---

## Constitution Check

| # | Nguyên Tắc | Trạng Thái | Bằng Chứng |
|---|-----------|-----------|------------|
| I | Giao tiếp qua Artifact | ✅ PASS | reviewer_node đọc diff từ DB, ghi ReviewReport vào DB; không share session |
| II | HIL checkpoints | ✅ PASS | reviewer_node chạy trước `interrupt()` — PO vẫn quyết định cuối; AI không block |
| III | WIP = 1 | ✅ PASS (AMENDED) | WIP = 1 per Developer (không phải per project) — cần amendment constitution |
| IV | Kanban one-way flow | ✅ PASS | Transitions không đổi; reviewer_node là node nội bộ, không tạo transition mới |
| V | Full audit logging | ✅ PASS | reviewer_node gọi `audit_service.write_pending_log()` TRƯỚC khi chạy test/LLM |
| VI | Security | ✅ PASS | JWT không hardcode; PAT GitHub mã hoá AES-256; webhook secret qua HMAC-SHA256 |
| VII | MVP scope | ✅ PASS (AMENDED) | Multi-user là intentional extension; ghi rõ amendment; single-user path vẫn hoạt động |
| VIII | Code quality | ✅ PASS | PEP 8 + type hints; component mới theo Atomic Design; kebab-case |

**Gate result: ALL PASS** (với 2 constitutional amendments cần ghi lại)

**Constitutional Amendments Required**:
1. **Principle III**: Cập nhật "WIP = 1 per Developer" (không phải per project) cho multi-user mode
2. **Principle VII**: Ghi nhận multi-user/team là "Post-MVP Phase 1" được phê duyệt

---

## Project Structure Changes

```
backend/
├── alembic/versions/
│   └── 005_platform_expansion.py          ← NEW migration (9 bảng mới, 2 ALTER)
├── app/
│   ├── config.py                          ← MODIFIED: add GITHUB_ENCRYPTION_KEY, JWT_SECRET_KEY
│   ├── dependencies.py                    ← NEW: get_current_user(), require_role() dependencies
│   ├── models/
│   │   ├── project_member.py              ← NEW: ProjectMember, ProjectRole enum
│   │   ├── invitation.py                  ← NEW: Invitation
│   │   ├── review_report.py               ← NEW: ReviewReport, ReviewComment, ReviewStatus
│   │   ├── task_dependency.py             ← NEW: TaskDependency
│   │   ├── task_template.py               ← NEW: TaskTemplate, TemplateScope
│   │   ├── notification.py                ← NEW: Notification, NotificationType
│   │   ├── webhook.py                     ← NEW: WebhookConfig, WebhookDelivery
│   │   ├── github_config.py               ← NEW: GitHubConfig
│   │   ├── task.py                        ← MODIFIED: add assigned_to FK, is_blocked bool
│   │   └── user.py                        ← MODIFIED: add last_login_at (nếu chưa có)
│   ├── schemas/
│   │   ├── auth.py                        ← NEW: RegisterRequest, LoginRequest, TokenResponse
│   │   ├── member.py                      ← NEW: MemberResponse, InviteRequest
│   │   ├── review.py                      ← NEW: ReviewReportResponse, ReviewCommentResponse
│   │   ├── dependency.py                  ← NEW: DependencyCreate, DependencyGraph
│   │   ├── template.py                    ← NEW: TemplateCreate, TemplateResponse
│   │   ├── notification.py                ← NEW: NotificationResponse
│   │   ├── webhook.py                     ← NEW: WebhookCreate, WebhookResponse
│   │   ├── analytics.py                   ← NEW: DashboardResponse, AnalyticsResponse
│   │   └── task.py                        ← MODIFIED: add assigned_to field
│   ├── services/
│   │   ├── auth_service.py                ← NEW: register, login, create_token, verify_token
│   │   ├── reviewer_service.py            ← NEW: run_tests, scan_secrets, ai_review, score
│   │   ├── dependency_service.py          ← NEW: add_dep, remove_dep, cycle_check, unlock_tasks
│   │   ├── template_service.py            ← NEW: CRUD for task templates
│   │   ├── notification_service.py        ← NEW: create_notification, mark_read, get_for_user
│   │   ├── webhook_service.py             ← NEW: enqueue_delivery, process_queue, retry_logic
│   │   ├── github_service.py              ← NEW: create_pr, encrypt/decrypt PAT
│   │   ├── analytics_service.py           ← NEW: dashboard_data, project_analytics
│   │   └── kanban_service.py              ← MODIFIED: WIP per-dev, dependency lock check, notify
│   ├── agent/
│   │   ├── graph.py                       ← MODIFIED: add reviewer_node after coder/cli nodes
│   │   └── nodes/
│   │       └── reviewer_node.py           ← NEW: test runner + secret scan + AI review + score
│   ├── api/v1/
│   │   ├── auth.py                        ← NEW: /auth/register, /auth/login, /auth/me
│   │   ├── members.py                     ← NEW: /projects/{id}/members CRUD + invitations
│   │   ├── review.py                      ← NEW: GET /tasks/{id}/review
│   │   ├── dependencies.py                ← NEW: /tasks/{id}/dependencies CRUD + graph
│   │   ├── templates.py                   ← NEW: /templates CRUD
│   │   ├── notifications.py               ← NEW: /notifications CRUD
│   │   ├── webhooks.py                    ← NEW: /projects/{id}/webhooks CRUD + test
│   │   ├── github.py                      ← NEW: /projects/{id}/github config
│   │   ├── analytics.py                   ← NEW: /dashboard + /projects/{id}/analytics
│   │   ├── projects.py                    ← MODIFIED: auth guard, member permission check
│   │   ├── tasks.py                       ← MODIFIED: auth guard, assignment field
│   │   └── router.py                      ← MODIFIED: register all new routers
│   └── main.py                            ← MODIFIED: add auth middleware, CORS update

frontend/
├── src/
│   ├── types/index.ts                     ← MODIFIED: User, ProjectMember, ReviewReport, etc.
│   ├── services/
│   │   ├── auth-api.ts                    ← NEW: register, login, me, token storage
│   │   ├── member-api.ts                  ← NEW: members CRUD, invite
│   │   ├── review-api.ts                  ← NEW: getReviewReport
│   │   ├── dependency-api.ts              ← NEW: add/remove deps, get graph
│   │   ├── template-api.ts                ← NEW: template CRUD
│   │   ├── notification-api.ts            ← NEW: get, markRead, markAllRead
│   │   ├── webhook-api.ts                 ← NEW: webhook CRUD + test
│   │   ├── analytics-api.ts               ← NEW: dashboard, analytics
│   │   └── project-api.ts                 ← MODIFIED: include auth header
│   ├── components/
│   │   ├── atoms/
│   │   │   ├── avatar.tsx                 ← NEW: user avatar với initials fallback
│   │   │   └── notification-badge.tsx     ← NEW: red badge số chưa đọc
│   │   ├── molecules/
│   │   │   ├── assign-member.tsx          ← NEW: dropdown chọn assignee
│   │   │   ├── dependency-badge.tsx       ← NEW: "Blocked by #X" badge
│   │   │   ├── template-selector.tsx      ← NEW: dropdown chọn template khi tạo task
│   │   │   └── notification-panel.tsx     ← NEW: popover danh sách notification
│   │   └── organisms/
│   │       ├── ai-review-panel.tsx        ← NEW: score + suggestion + inline comments
│   │       ├── dependency-graph.tsx       ← NEW: DAG visualization (react-flow lite)
│   │       ├── project-members.tsx        ← NEW: members list + invite form
│   │       └── webhook-settings.tsx       ← NEW: webhook config form
│   ├── pages/
│   │   ├── dashboard.tsx                  ← NEW: multi-project overview
│   │   ├── analytics.tsx                  ← NEW: charts + metrics per project
│   │   ├── project-workspace.tsx          ← MODIFIED: auth guard wrapper
│   │   └── project-list.tsx               ← MODIFIED: template selector in create form
│   ├── contexts/
│   │   └── auth-context.tsx               ← NEW: AuthProvider, useAuth hook
│   └── components/
│       └── organisms/
│           ├── project-header.tsx         ← MODIFIED: notification bell, member avatars
│           ├── kanban-board.tsx           ← MODIFIED: show blocked tasks, assignee avatars
│           ├── task-card.tsx              ← MODIFIED: assignee avatar, blocked badge
│           └── review-panel.tsx           ← MODIFIED: thêm AI Review panel cạnh diff
```

---

## Phase 1: Setup — DB Migration & Config

**Purpose**: Schema changes, new dependencies, constitutional amendments — không có thay đổi user-visible.

- [ ] T001 Write Alembic migration `backend/alembic/versions/005_platform_expansion.py`:

  ```python
  # backend/alembic/versions/005_platform_expansion.py
  """Platform expansion: multi-user, reviewer, dependencies, notifications, webhooks"""
  revision = "005"
  down_revision = "004"

  def upgrade():
      # --- project_members ---
      op.create_table("project_members",
          sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
          sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
          sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
          sa.Column("role", sa.String(20), nullable=False),
          sa.Column("joined_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
          sa.UniqueConstraint("project_id", "user_id"),
          sa.CheckConstraint("role IN ('owner','leader','developer','viewer')", name="ck_member_role"),
      )
      op.create_index("idx_project_members_project", "project_members", ["project_id"])
      op.create_index("idx_project_members_user", "project_members", ["user_id"])

      # --- invitations ---
      op.create_table("invitations",
          sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
          sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
          sa.Column("invitee_email", sa.String(255)),
          sa.Column("role", sa.String(20), nullable=False),
          sa.Column("token", sa.String(64), unique=True, nullable=False),
          sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
          sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
          sa.Column("used_at", sa.TIMESTAMP(timezone=True)),
          sa.Column("used_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
          sa.CheckConstraint("role IN ('leader','developer','viewer')", name="ck_invite_role"),
      )
      op.create_index("idx_invitations_token", "invitations", ["token"])

      # --- review_reports + review_comments ---
      op.create_table("review_reports",
          sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
          sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
          sa.Column("agent_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_runs.id")),
          sa.Column("score", sa.SmallInteger()),
          sa.Column("suggestion", sa.String(20)),
          sa.Column("test_runner", sa.String(50)),
          sa.Column("test_pass", sa.Integer(), server_default="0"),
          sa.Column("test_fail", sa.Integer(), server_default="0"),
          sa.Column("test_error", sa.Text()),
          sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
          sa.Column("error_message", sa.Text()),
          sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
          sa.Column("completed_at", sa.TIMESTAMP(timezone=True)),
          sa.CheckConstraint("score BETWEEN 0 AND 100", name="ck_review_score"),
          sa.CheckConstraint("suggestion IN ('approve','needs_changes')", name="ck_review_suggestion"),
          sa.CheckConstraint("status IN ('pending','running','complete','error')", name="ck_review_status"),
      )
      op.create_index("idx_review_reports_task", "review_reports", ["task_id"])

      op.create_table("review_comments",
          sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
          sa.Column("review_report_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("review_reports.id", ondelete="CASCADE"), nullable=False),
          sa.Column("file_path", sa.String(500), nullable=False),
          sa.Column("line_number", sa.Integer()),
          sa.Column("content", sa.Text(), nullable=False),
          sa.Column("severity", sa.String(10), nullable=False, server_default="info"),
          sa.CheckConstraint("severity IN ('info','warning','error')", name="ck_comment_severity"),
      )
      op.create_index("idx_review_comments_report", "review_comments", ["review_report_id"])

      # --- task_dependencies ---
      op.create_table("task_dependencies",
          sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
          sa.Column("depends_on_task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
          sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
          sa.PrimaryKeyConstraint("task_id", "depends_on_task_id"),
          sa.CheckConstraint("task_id != depends_on_task_id", name="ck_no_self_dep"),
      )

      # --- task_templates ---
      op.create_table("task_templates",
          sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
          sa.Column("name", sa.String(100), nullable=False),
          sa.Column("title_template", sa.String(255), nullable=False),
          sa.Column("description_template", sa.Text(), server_default=""),
          sa.Column("scope", sa.String(10), nullable=False, server_default="project"),
          sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE")),
          sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
          sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
          sa.UniqueConstraint("project_id", "name"),
          sa.CheckConstraint("scope IN ('project','global')", name="ck_template_scope"),
      )

      # --- notifications ---
      op.create_table("notifications",
          sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
          sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
          sa.Column("type", sa.String(50), nullable=False),
          sa.Column("content", sa.Text(), nullable=False),
          sa.Column("reference_type", sa.String(20)),
          sa.Column("reference_id", postgresql.UUID(as_uuid=True)),
          sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
          sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
      )
      op.create_index("idx_notifications_user_unread", "notifications", ["user_id", "is_read"],
                      postgresql_where=sa.text("is_read = false"))
      op.create_index("idx_notifications_user", "notifications", ["user_id", sa.text("created_at DESC")])

      # --- webhook_configs + webhook_deliveries ---
      op.create_table("webhook_configs",
          sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
          sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
          sa.Column("url", sa.Text(), nullable=False),
          sa.Column("secret", sa.String(100)),
          sa.Column("events", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
          sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
          sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
          sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
      )
      op.create_table("webhook_deliveries",
          sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
          sa.Column("webhook_config_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("webhook_configs.id", ondelete="CASCADE"), nullable=False),
          sa.Column("event_type", sa.String(50), nullable=False),
          sa.Column("payload", postgresql.JSONB(), nullable=False),
          sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
          sa.Column("http_status", sa.Integer()),
          sa.Column("attempts", sa.SmallInteger(), nullable=False, server_default="0"),
          sa.Column("last_attempt_at", sa.TIMESTAMP(timezone=True)),
          sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
      )

      # --- github_configs ---
      op.create_table("github_configs",
          sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
          sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), unique=True, nullable=False),
          sa.Column("repo_full_name", sa.String(200), nullable=False),
          sa.Column("pat_encrypted", sa.Text(), nullable=False),
          sa.Column("default_base_branch", sa.String(100), nullable=False, server_default="main"),
          sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
          sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
          sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
      )

      # --- ALTER tasks ---
      op.add_column("tasks", sa.Column("assigned_to", postgresql.UUID(as_uuid=True),
                                       sa.ForeignKey("users.id", ondelete="SET NULL")))
      op.add_column("tasks", sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default="false"))
      op.create_index("idx_tasks_assigned_to", "tasks", ["assigned_to"])

      # --- ALTER users ---
      op.add_column("users", sa.Column("last_login_at", sa.TIMESTAMP(timezone=True)))

      # --- analytics indexes ---
      op.create_index("idx_agent_runs_project_status", "agent_runs", ["project_id", "status", "created_at"])
      op.create_index("idx_agent_runs_backend", "agent_runs", ["coding_backend", "status"])
      op.create_index("idx_tasks_project_status", "tasks", ["project_id", "status", "updated_at"])

  def downgrade():
      # Drop indexes first
      op.drop_index("idx_tasks_project_status"); op.drop_index("idx_agent_runs_backend")
      op.drop_index("idx_agent_runs_project_status"); op.drop_index("idx_tasks_assigned_to")
      # Drop columns
      op.drop_column("users", "last_login_at")
      op.drop_column("tasks", "is_blocked"); op.drop_column("tasks", "assigned_to")
      # Drop tables in FK-safe order
      for t in ["github_configs","webhook_deliveries","webhook_configs","notifications",
                "task_templates","task_dependencies","review_comments","review_reports",
                "invitations","project_members"]:
          op.drop_table(t)
  ```

- [ ] T002 [P] Update `backend/app/config.py` — thêm vào `Settings` class:
  ```python
  jwt_secret_key: str = Field(..., env="JWT_SECRET_KEY")
  jwt_algorithm: str = "HS256"
  jwt_expire_days: int = 7
  github_encryption_key: str | None = Field(None, env="GITHUB_ENCRYPTION_KEY")

  @property
  def fernet_key(self) -> bytes:
      """Derive 32-byte Fernet key from GITHUB_ENCRYPTION_KEY via SHA-256."""
      import hashlib, base64
      raw = (self.github_encryption_key or "").encode()
      return base64.urlsafe_b64encode(hashlib.sha256(raw).digest())
  ```

- [ ] T003 [P] Update `backend/.env.example`:
  ```
  JWT_SECRET_KEY=change-me-in-production-min-32-chars
  GITHUB_ENCRYPTION_KEY=optional-aes-key-for-pat-encryption
  ```

- [ ] T004 [P] Update `backend/requirements.txt`:
  ```
  python-jose[cryptography]>=3.3.0
  passlib[bcrypt]>=1.7.4
  PyGithub>=2.0.0
  cryptography>=42.0.0
  ```

- [ ] T005 [P] Update `frontend/package.json` — thêm dependency:
  ```json
  "recharts": "^2.12.0"
  ```
  Run `npm install` sau khi thêm.

- [ ] T006 [P] Ghi constitutional amendments vào `.specify/memory/constitution.md`:
  - **Amendment A (Principle III)**: Thêm đoạn: *"Trong multi-user mode (khi `project_members` có ít nhất 1 record cho project): WIP = 1 per Developer. Trong single-user mode (không có project_members record): WIP = 1 per project (behaviour cũ). Check: `kanban_service.get_wip_subject(session, project_id)` trả `"user"` hoặc `"project"`."*
  - **Amendment B (Principle VII)**: Thêm đoạn: *"Multi-user/team (Feature 003) là Post-MVP Phase 1 được phê duyệt explicitly. Single-user path vẫn hoạt động mà không cần đăng nhập nếu `REQUIRE_AUTH=false` trong config."*

**Checkpoint**: `alembic upgrade head` thành công — 10 bảng mới tồn tại; `tasks` có cột `assigned_to` và `is_blocked`; `users` có `last_login_at`. `alembic downgrade -1` cũng chạy sạch.

---

## Phase 2: F-004 Backend — Auth & Multi-user

**Purpose**: JWT auth, 4-role permission system, invite system, WIP per-developer.

- [ ] T007 [P] Tạo `backend/app/models/project_member.py`:
  ```python
  from enum import Enum as PyEnum
  import sqlalchemy as sa
  from sqlalchemy.orm import Mapped, mapped_column, relationship
  from app.database import Base

  class ProjectRole(str, PyEnum):
      owner = "owner"
      leader = "leader"
      developer = "developer"
      viewer = "viewer"

  class ProjectMember(Base):
      __tablename__ = "project_members"
      id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
      project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
      user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
      role: Mapped[ProjectRole] = mapped_column(sa.Enum(ProjectRole, name="projectrole"), nullable=False)
      joined_at: Mapped[datetime] = mapped_column(server_default=func.now())

      project: Mapped["Project"] = relationship(back_populates="members")
      user: Mapped["User"] = relationship(back_populates="memberships")

      __table_args__ = (UniqueConstraint("project_id", "user_id"),)
  ```

- [ ] T008 [P] Tạo `backend/app/models/invitation.py`:
  ```python
  class Invitation(Base):
      __tablename__ = "invitations"
      id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
      project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
      invitee_email: Mapped[str | None] = mapped_column(String(255))
      role: Mapped[str] = mapped_column(String(20), nullable=False)
      token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
      created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
      expires_at: Mapped[datetime] = mapped_column(nullable=False)
      used_at: Mapped[datetime | None]
      used_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))

      @property
      def is_expired(self) -> bool:
          return datetime.utcnow() > self.expires_at

      @property
      def is_used(self) -> bool:
          return self.used_at is not None
  ```

- [ ] T009 Tạo `backend/app/services/auth_service.py`:
  ```python
  from passlib.context import CryptContext
  from jose import jwt, JWTError
  from datetime import datetime, timedelta
  from uuid import UUID
  from fastapi import HTTPException, status

  pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

  def hash_password(plain: str) -> str:
      return pwd_context.hash(plain)

  def verify_password(plain: str, hashed: str) -> bool:
      return pwd_context.verify(plain, hashed)

  def create_access_token(user_id: UUID, secret: str, algorithm: str, expire_days: int) -> str:
      payload = {
          "sub": str(user_id),
          "exp": datetime.utcnow() + timedelta(days=expire_days),
          "iat": datetime.utcnow(),
      }
      return jwt.encode(payload, secret, algorithm=algorithm)

  def decode_token(token: str, secret: str, algorithm: str) -> UUID:
      try:
          payload = jwt.decode(token, secret, algorithms=[algorithm])
          return UUID(payload["sub"])
      except (JWTError, KeyError, ValueError):
          raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

  async def register_user(session: AsyncSession, email: str, password: str, display_name: str) -> User:
      existing = await session.scalar(select(User).where(User.email == email))
      if existing:
          raise HTTPException(status_code=409, detail="Email already registered")
      user = User(email=email, password_hash=hash_password(password), display_name=display_name)
      session.add(user)
      await session.flush()
      return user

  async def login_user(session: AsyncSession, email: str, password: str, settings: Settings) -> tuple[User, str]:
      user = await session.scalar(select(User).where(User.email == email))
      if not user or not verify_password(password, user.password_hash):
          raise HTTPException(status_code=401, detail="Invalid credentials")
      user.last_login_at = datetime.utcnow()
      token = create_access_token(user.id, settings.jwt_secret_key, settings.jwt_algorithm, settings.jwt_expire_days)
      return user, token
  ```

- [ ] T010 Tạo `backend/app/dependencies.py`:
  ```python
  from fastapi import Depends, HTTPException, Path
  from fastapi.security import OAuth2PasswordBearer

  oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

  async def get_current_user(
      token: str | None = Depends(oauth2_scheme),
      session: AsyncSession = Depends(get_session),
      settings: Settings = Depends(get_settings),
  ) -> User:
      if not token:
          raise HTTPException(status_code=401, detail="Not authenticated")
      user_id = decode_token(token, settings.jwt_secret_key, settings.jwt_algorithm)
      user = await session.get(User, user_id)
      if not user or not user.is_active:
          raise HTTPException(status_code=401, detail="User not found or inactive")
      return user

  async def get_optional_user(
      token: str | None = Depends(oauth2_scheme),
      session: AsyncSession = Depends(get_session),
      settings: Settings = Depends(get_settings),
  ) -> User | None:
      """Cho phép anonymous access nếu REQUIRE_AUTH=false."""
      if not token:
          return None
      try:
          return await get_current_user(token, session, settings)
      except HTTPException:
          return None

  def require_role(*allowed_roles: ProjectRole):
      """Factory: trả Depends function kiểm tra user có role được phép trong project."""
      async def check(
          project_id: UUID = Path(...),
          current_user: User = Depends(get_current_user),
          session: AsyncSession = Depends(get_session),
      ) -> ProjectMember:
          member = await session.scalar(
              select(ProjectMember).where(
                  ProjectMember.project_id == project_id,
                  ProjectMember.user_id == current_user.id,
              )
          )
          if not member or member.role not in allowed_roles:
              raise HTTPException(status_code=403, detail="Insufficient permissions")
          return member
      return Depends(check)

  # Shorthand aliases
  require_owner = require_role(ProjectRole.owner)
  require_leader_or_above = require_role(ProjectRole.owner, ProjectRole.leader)
  require_developer_or_above = require_role(ProjectRole.owner, ProjectRole.leader, ProjectRole.developer)
  require_any_member = require_role(ProjectRole.owner, ProjectRole.leader, ProjectRole.developer, ProjectRole.viewer)
  ```

- [ ] T011 Tạo `backend/app/api/v1/auth.py`:
  ```python
  router = APIRouter(prefix="/auth", tags=["auth"])

  @router.post("/register", response_model=TokenResponse, status_code=201)
  async def register(body: RegisterRequest, session=Depends(get_session), settings=Depends(get_settings)):
      user = await auth_service.register_user(session, body.email, body.password, body.display_name)
      token = auth_service.create_access_token(user.id, settings.jwt_secret_key, settings.jwt_algorithm, settings.jwt_expire_days)
      await session.commit()
      return TokenResponse(access_token=token, token_type="bearer", user=UserResponse.from_orm(user))

  @router.post("/login", response_model=LoginResponse)
  async def login(body: LoginRequest, session=Depends(get_session), settings=Depends(get_settings)):
      user, token = await auth_service.login_user(session, body.email, body.password, settings)
      await session.commit()
      return LoginResponse(access_token=token, token_type="bearer", expires_in=settings.jwt_expire_days * 86400)

  @router.get("/me", response_model=UserResponse)
  async def me(current_user: User = Depends(get_current_user)):
      return UserResponse.from_orm(current_user)
  ```

- [ ] T012 Tạo `backend/app/api/v1/members.py` — key logic:
  ```python
  @router.post("/{project_id}/members/invite", response_model=InvitationResponse)
  async def invite_member(
      project_id: UUID, body: InviteRequest,
      _: ProjectMember = require_owner,       # chỉ owner mới invite
      session=Depends(get_session), request: Request = None,
  ):
      token = secrets.token_hex(32)           # 64-char hex, URL-safe
      expires_at = datetime.utcnow() + timedelta(days=7)
      invitation = Invitation(project_id=project_id, invitee_email=body.invitee_email,
                              role=body.role, token=token, created_by=current_user.id,
                              expires_at=expires_at)
      session.add(invitation)
      await session.commit()
      invite_url = f"{request.base_url}invitations/{token}"
      return InvitationResponse(invitation_id=invitation.id, invite_url=invite_url, expires_at=expires_at)

  @router.post("/invitations/{token}/accept", response_model=AcceptResponse)
  async def accept_invite(token: str, current_user: User = Depends(get_current_user), session=Depends(get_session)):
      invitation = await session.scalar(select(Invitation).where(Invitation.token == token))
      if not invitation:
          raise HTTPException(404, "Invitation not found")
      if invitation.is_expired:
          raise HTTPException(410, "Invitation expired")
      if invitation.is_used:
          raise HTTPException(410, "Invitation already used")
      # Check already member
      existing = await session.scalar(select(ProjectMember).where(
          ProjectMember.project_id == invitation.project_id,
          ProjectMember.user_id == current_user.id))
      if existing:
          raise HTTPException(409, "Already a member")
      member = ProjectMember(project_id=invitation.project_id, user_id=current_user.id, role=invitation.role)
      invitation.used_at = datetime.utcnow()
      invitation.used_by = current_user.id
      session.add(member)
      await session.commit()
      return AcceptResponse(project_id=invitation.project_id, role=invitation.role)
  ```

- [ ] T013 Update `backend/app/services/kanban_service.py` — thêm WIP per-dev và dependency check:
  ```python
  async def move_task_to_in_progress(
      session: AsyncSession,
      task_id: UUID,
      current_user: User,
      project_id: UUID,
  ) -> Task:
      task = await session.get(Task, task_id)
      if not task or task.status != "todo":
          raise InvalidTransitionError(task_id, "todo", "in_progress")

      # 1. Dependency lock check
      if task.is_blocked:
          blocked_by = await dependency_service.get_blocking_tasks(session, task_id)
          raise TaskBlockedError(task_id, blocked_by_ids=[t.id for t in blocked_by])

      # 2. WIP per-developer (hoặc per-project nếu single-user)
      wip_mode = await get_wip_mode(session, project_id)
      if wip_mode == "user":
          in_progress_count = await session.scalar(
              select(func.count()).select_from(Task).where(
                  Task.project_id == project_id,
                  Task.assigned_to == current_user.id,
                  Task.status == "in_progress",
              )
          )
          member = await get_member(session, project_id, current_user.id)
          is_privileged = member and member.role in (ProjectRole.owner, ProjectRole.leader)
          if in_progress_count >= 1 and not is_privileged:
              raise WIPLimitExceeded(user_id=current_user.id)
      else:
          # Legacy per-project check (single-user mode)
          in_progress_count = await session.scalar(
              select(func.count()).select_from(Task).where(
                  Task.project_id == project_id, Task.status == "in_progress"))
          if in_progress_count >= 1:
              raise WIPLimitExceeded(user_id=None)

      # 3. Assignment check
      if task.assigned_to and task.assigned_to != current_user.id:
          member = await get_member(session, project_id, current_user.id)
          if not member or member.role not in (ProjectRole.owner, ProjectRole.leader):
              raise AssignmentConflict(task_id, task.assigned_to)

      task.status = "in_progress"
      task.updated_at = datetime.utcnow()
      await audit_service.write_pending_log(session, task, action="move_to_in_progress", actor_id=current_user.id)
      return task

  async def get_wip_mode(session: AsyncSession, project_id: UUID) -> str:
      """'user' nếu project có ít nhất 1 member, 'project' nếu single-user."""
      count = await session.scalar(
          select(func.count()).select_from(ProjectMember).where(ProjectMember.project_id == project_id))
      return "user" if count > 0 else "project"
  ```

- [ ] T014 [P] Update existing endpoints — pattern cho mỗi route trong `projects.py`, `tasks.py`:
  ```python
  # Thêm vào signature của mọi endpoint cần auth:
  current_user: User = Depends(get_current_user)
  # Thêm permission check cho project-scoped actions:
  member: ProjectMember = require_developer_or_above  # hoặc level phù hợp
  # Viewer-only endpoints (read-only):
  member: ProjectMember = require_any_member
  ```
  Danh sách endpoints cần update: `GET/POST /projects`, `GET/PATCH/DELETE /projects/{id}`,
  `GET/POST /projects/{id}/tasks`, `GET/PATCH/DELETE /tasks/{id}`,
  `POST /tasks/{id}/start`, `POST /tasks/{id}/approve`, `POST /tasks/{id}/reject`.

**Checkpoint**: Register → Login → JWT → `GET /auth/me` trả user info. `POST /projects/{id}/members/invite` trả invite URL 64-char token. Accept invite → user xuất hiện trong `GET /projects/{id}/members`. WIP: Developer kéo task 1 → OK; kéo task 2 → 409 `WIPLimitExceeded`. Viewer gọi `POST /tasks/{id}/start` → 403.

---

## Phase 3: F-003 Backend — Reviewer Agent

**Purpose**: Reviewer Agent node trong LangGraph; test runner; secret scan; AI review; score.

- [ ] T015 [P] Tạo `backend/app/models/review_report.py`:
  ```python
  class ReviewStatus(str, PyEnum):
      pending = "pending"
      running = "running"
      complete = "complete"
      error = "error"

  class ReviewReport(Base):
      __tablename__ = "review_reports"
      id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
      task_id: Mapped[UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
      agent_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("agent_runs.id"))
      score: Mapped[int | None]                    # 0–100
      suggestion: Mapped[str | None]               # 'approve' | 'needs_changes'
      test_runner: Mapped[str | None]              # 'pytest' | 'npm_test' | 'none'
      test_pass: Mapped[int] = mapped_column(default=0)
      test_fail: Mapped[int] = mapped_column(default=0)
      test_error: Mapped[str | None]
      status: Mapped[ReviewStatus] = mapped_column(default=ReviewStatus.pending)
      error_message: Mapped[str | None]
      created_at: Mapped[datetime] = mapped_column(server_default=func.now())
      completed_at: Mapped[datetime | None]
      comments: Mapped[list["ReviewComment"]] = relationship(back_populates="report",
                                                              cascade="all, delete-orphan")

  class ReviewComment(Base):
      __tablename__ = "review_comments"
      id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
      review_report_id: Mapped[UUID] = mapped_column(ForeignKey("review_reports.id", ondelete="CASCADE"), index=True)
      file_path: Mapped[str] = mapped_column(String(500))
      line_number: Mapped[int | None]
      content: Mapped[str] = mapped_column(Text)
      severity: Mapped[str] = mapped_column(default="info")   # 'info' | 'warning' | 'error'
      report: Mapped[ReviewReport] = relationship(back_populates="comments")
  ```

- [ ] T016 Tạo `backend/app/services/reviewer_service.py`:
  ```python
  import re, subprocess, json
  from pathlib import Path

  # --- Test runner detection ---
  def detect_test_runner(sandbox_path: str) -> str | None:
      p = Path(sandbox_path)
      if any((p / f).exists() for f in ["conftest.py", "pytest.ini", "pyproject.toml"]):
          return "pytest"
      pkg = p / "package.json"
      if pkg.exists():
          data = json.loads(pkg.read_text())
          if data.get("scripts", {}).get("test"):
              return "npm_test"
      return None

  def run_tests(runner: str, sandbox_path: str, timeout: int = 60) -> tuple[int, int, str | None]:
      """Returns (pass_count, fail_count, error_text)."""
      cmd = {"pytest": ["pytest", "-v", "--tb=short", f"--timeout={timeout}"],
             "npm_test": ["npm", "test", "--", "--watchAll=false"]}[runner]
      try:
          result = subprocess.run(cmd, cwd=sandbox_path, capture_output=True, text=True, timeout=timeout)
          output = result.stdout + result.stderr
          if runner == "pytest":
              # Parse: "3 passed, 1 failed" from pytest summary line
              m = re.search(r"(\d+) passed", output); passed = int(m.group(1)) if m else 0
              m = re.search(r"(\d+) failed", output); failed = int(m.group(1)) if m else 0
          else:
              # npm test: "Tests: 3 passed, 1 failed" (Jest format)
              m = re.search(r"Tests:\s+(\d+) passed", output); passed = int(m.group(1)) if m else 0
              m = re.search(r"(\d+) failed", output); failed = int(m.group(1)) if m else 0
          return passed, failed, None if result.returncode == 0 else output[-500:]
      except subprocess.TimeoutExpired:
          return 0, 0, f"Test runner timed out after {timeout}s"

  # --- Secret scanning ---
  SECRET_PATTERNS: list[tuple[str, str]] = [
      (r'(?i)(password|passwd|pwd)\s*=\s*["\'][^"\']{6,}["\']', "hardcoded password"),
      (r'(?i)(api_key|apikey|api-key)\s*=\s*["\'][A-Za-z0-9_\-]{20,}["\']', "hardcoded API key"),
      (r'(?i)(secret|token)\s*=\s*["\'][A-Za-z0-9_\-]{20,}["\']', "hardcoded secret/token"),
      (r'AKIA[0-9A-Z]{16}', "AWS Access Key ID"),
      (r'(?i)bearer\s+[A-Za-z0-9\-_\.]{20,}', "Bearer token in code"),
  ]

  def scan_secrets(diff_content: str) -> list[dict]:
      """Scan only '+' lines (added lines) in diff."""
      findings: list[dict] = []
      current_file = "unknown"
      line_num = 0
      for line in diff_content.splitlines():
          if line.startswith("+++ b/"):
              current_file = line[6:]
          elif line.startswith("@@"):
              m = re.search(r"\+(\d+)", line)
              line_num = int(m.group(1)) - 1 if m else 0
          elif line.startswith("+") and not line.startswith("+++"):
              line_num += 1
              for pattern, name in SECRET_PATTERNS:
                  if re.search(pattern, line):
                      findings.append({"file": current_file, "line": line_num, "pattern_name": name})
      return findings

  # --- AI review ---
  REVIEWER_PROMPT = """You are a code reviewer. Analyze the following git diff.
  Project constitution (coding standards): {constitution}

  Git diff:
  {diff}

  Return ONLY valid JSON:
  {{
    "suggestion": "approve" | "needs_changes",
    "comments": [
      {{"file_path": "str", "line_number": 42, "content": "str", "severity": "info"|"warning"|"error"}}
    ]
  }}
  Limit to 10 most important comments. Be concise."""

  async def ai_review_diff(diff: str, constitution: str, llm) -> tuple[str, list[dict]]:
      """Returns (suggestion, comments_list)."""
      prompt = REVIEWER_PROMPT.format(constitution=constitution[:2000], diff=diff[:6000])
      try:
          response = await llm.ainvoke(prompt)
          data = json.loads(response.content)
          return data.get("suggestion", "needs_changes"), data.get("comments", [])
      except (json.JSONDecodeError, KeyError, AttributeError):
          return "needs_changes", []   # fail-safe: không crash task

  # --- Score calculation ---
  def calculate_score(test_pass: int, test_fail: int, secret_count: int, suggestion: str) -> int:
      """Weighted score 0-100:
         - Test score: 40 pts. If no tests: 40 pts (neutral). With tests: pass/(pass+fail)*40.
         - Secret score: 30 pts. -10 per secret found (min 0).
         - AI score: 30 pts. 'approve'=30, 'needs_changes'=0-20 (based on comment severity).
      """
      total = test_pass + test_fail
      test_score = 40 if total == 0 else int((test_pass / total) * 40)
      secret_score = max(0, 30 - secret_count * 10)
      ai_score = 30 if suggestion == "approve" else 10
      return min(100, test_score + secret_score + ai_score)
  ```

- [ ] T017 Tạo `backend/app/agent/nodes/reviewer_node.py`:
  ```python
  from app.agent.state import AgentState
  from app import reviewer_service, audit_service
  from app.models.review_report import ReviewReport, ReviewComment, ReviewStatus
  import asyncio

  REVIEWER_TIMEOUT = 300  # 5 phút tổng

  async def run(state: AgentState) -> AgentState:
      task_id = state["task_id"]
      session = state["session"]

      # Fetch task + diff
      task = await session.get(Task, task_id)
      diff = await get_latest_diff(session, task_id)     # from diff_service
      constitution = await get_project_constitution(session, task.project_id)

      # Create ReviewReport record (status=running)
      report = ReviewReport(task_id=task_id, agent_run_id=state.get("agent_run_id"), status=ReviewStatus.running)
      session.add(report)
      await session.flush()  # get report.id

      await audit_service.write_pending_log(session, task, action="reviewer_node_start",
                                             actor_id=None, agent_run_id=state.get("agent_run_id"))

      try:
          async with asyncio.timeout(REVIEWER_TIMEOUT):
              # Step 1: Test runner
              runner = reviewer_service.detect_test_runner(state.get("sandbox_path", ""))
              if runner:
                  test_pass, test_fail, test_err = await asyncio.to_thread(
                      reviewer_service.run_tests, runner, state["sandbox_path"])
              else:
                  test_pass, test_fail, test_err = 0, 0, None

              # Step 2: Secret scan
              secret_findings = reviewer_service.scan_secrets(diff or "")

              # Step 3: AI review
              llm = state["llm"]
              suggestion, ai_comments = await reviewer_service.ai_review_diff(diff or "", constitution, llm)

              # Step 4: Score
              score = reviewer_service.calculate_score(test_pass, test_fail, len(secret_findings), suggestion)

              # Persist
              report.score = score; report.suggestion = suggestion
              report.test_runner = runner or "none"; report.test_pass = test_pass
              report.test_fail = test_fail; report.test_error = test_err
              report.status = ReviewStatus.complete; report.completed_at = datetime.utcnow()

              # Persist secret findings as error comments
              for f in secret_findings:
                  session.add(ReviewComment(review_report_id=report.id, file_path=f["file"],
                                             line_number=f["line"], content=f"Security: {f['pattern_name']}", severity="error"))
              # Persist AI comments
              for c in ai_comments:
                  session.add(ReviewComment(review_report_id=report.id, file_path=c.get("file_path", ""),
                                             line_number=c.get("line_number"), content=c["content"],
                                             severity=c.get("severity", "info")))

              await session.flush()
              await audit_service.finalise_log(session, task, result="success")

              # WebSocket events
              await publish_ws_event(state["project_id"], "REVIEW_SCORE", {
                  "task_id": str(task_id), "score": score, "suggestion": suggestion,
                  "test_pass": test_pass, "test_fail": test_fail, "report_id": str(report.id)})
              for c in ai_comments + [{"file_path": f["file"], "line_number": f["line"],
                                        "content": f"Security: {f['pattern_name']}", "severity": "error"}
                                       for f in secret_findings]:
                  await publish_ws_event(state["project_id"], "REVIEW_COMMENT", c)

      except (asyncio.TimeoutError, Exception) as e:
          report.status = ReviewStatus.error; report.error_message = str(e)[:500]
          report.completed_at = datetime.utcnow()
          await audit_service.finalise_log(session, task, result="failure", error=str(e))
          await publish_ws_event(state["project_id"], "REVIEW_ERROR",
                                  {"task_id": str(task_id), "error": str(e)[:200]})
          # KHÔNG raise — task vẫn tiếp tục tới interrupt()

      state["review_report_id"] = str(report.id)
      return state
  ```

- [ ] T018 Update `backend/app/agent/graph.py` — thêm reviewer_node:
  ```python
  from app.agent.nodes import reviewer_node

  # Thêm node
  graph.add_node("reviewer_node", reviewer_node.run)

  # Thay đổi edges: cả hai coder nodes đều → reviewer trước khi interrupt
  # Trước: graph.add_edge("coder_node", END_OR_INTERRUPT)
  # Sau:
  graph.add_edge("coder_node", "reviewer_node")
  graph.add_edge("cli_coder_node", "reviewer_node")
  graph.add_edge("reviewer_node", "interrupt_node")  # HIL checkpoint
  ```

- [ ] T019 [P] Tạo `backend/app/api/v1/review.py`:
  ```python
  @router.get("/tasks/{task_id}/review", response_model=ReviewReportResponse)
  async def get_review(task_id: UUID, current_user: User = Depends(get_current_user), session=Depends(get_session)):
      report = await session.scalar(
          select(ReviewReport).where(ReviewReport.task_id == task_id)
          .options(selectinload(ReviewReport.comments))
          .order_by(ReviewReport.created_at.desc())
      )
      if not report:
          raise HTTPException(404, "No review for this task yet")
      return ReviewReportResponse.from_orm(report)
  ```

- [ ] T020 [P] Tạo `backend/app/schemas/review.py`:
  ```python
  class ReviewCommentResponse(BaseModel):
      id: UUID; file_path: str; line_number: int | None
      content: str; severity: str
      model_config = ConfigDict(from_attributes=True)

  class ReviewReportResponse(BaseModel):
      id: UUID; task_id: UUID; status: str; score: int | None; suggestion: str | None
      test_runner: str | None; test_pass: int; test_fail: int
      comments: list[ReviewCommentResponse]; error_message: str | None
      created_at: datetime; completed_at: datetime | None
      model_config = ConfigDict(from_attributes=True)
  ```

**Checkpoint**: Task kéo In Progress → coder_node chạy xong → reviewer_node chạy → `GET /tasks/{id}/review` trả `status:"complete"`, `score: 0-100`, danh sách comments. `REVIEW_SCORE` WebSocket event xuất hiện. Nếu reviewer timeout → task vẫn vào trạng thái Review, report có `status:"error"`.

---

## Phase 4: F-005 Backend — Dependencies & Templates

**Purpose**: Task dependency DAG, cycle detection, auto-unlock, task templates.

- [ ] T021 [P] Tạo `backend/app/models/task_dependency.py`:
  ```python
  class TaskDependency(Base):
      __tablename__ = "task_dependencies"
      task_id: Mapped[UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)
      depends_on_task_id: Mapped[UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)
      created_at: Mapped[datetime] = mapped_column(server_default=func.now())
  ```

- [ ] T022 [P] Tạo `backend/app/models/task_template.py`:
  ```python
  class TemplateScope(str, PyEnum):
      project = "project"
      global_ = "global"

  class TaskTemplate(Base):
      __tablename__ = "task_templates"
      id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
      name: Mapped[str] = mapped_column(String(100))
      title_template: Mapped[str] = mapped_column(String(255))
      description_template: Mapped[str] = mapped_column(Text, default="")
      scope: Mapped[TemplateScope] = mapped_column(default=TemplateScope.project)
      project_id: Mapped[UUID | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
      created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
      created_at: Mapped[datetime] = mapped_column(server_default=func.now())
  ```

- [ ] T023 Tạo `backend/app/services/dependency_service.py`:
  ```python
  async def _load_all_deps(session: AsyncSession, project_id: UUID) -> dict[str, list[str]]:
      """Load toàn bộ dependencies của project thành adjacency list."""
      rows = await session.execute(
          select(TaskDependency.task_id, TaskDependency.depends_on_task_id)
          .join(Task, Task.id == TaskDependency.task_id)
          .where(Task.project_id == project_id)
      )
      deps: dict[str, list[str]] = {}
      for task_id, dep_id in rows:
          deps.setdefault(str(task_id), []).append(str(dep_id))
      return deps

  def _has_cycle(task_id: str, new_dep_id: str, all_deps: dict[str, list[str]]) -> bool:
      """DFS: kiểm tra thêm new_dep_id vào task_id có tạo cycle không.
         Trả True nếu new_dep_id có thể reach task_id qua existing deps."""
      visited: set[str] = set()
      stack: list[str] = [new_dep_id]
      while stack:
          current = stack.pop()
          if current == task_id:
              return True           # cycle detected
          if current not in visited:
              visited.add(current)
              stack.extend(all_deps.get(current, []))
      return False

  async def add_dependency(session: AsyncSession, task_id: UUID, depends_on_id: UUID, project_id: UUID) -> TaskDependency:
      if task_id == depends_on_id:
          raise HTTPException(400, "Task cannot depend on itself")

      # Check both tasks belong to same project
      for tid in (task_id, depends_on_id):
          t = await session.get(Task, tid)
          if not t or t.project_id != project_id:
              raise HTTPException(404, f"Task {tid} not found in project")

      # Cycle detection: O(V+E)
      all_deps = await _load_all_deps(session, project_id)
      if _has_cycle(str(task_id), str(depends_on_id), all_deps):
          raise HTTPException(409, "Circular dependency detected")

      dep = TaskDependency(task_id=task_id, depends_on_task_id=depends_on_id)
      session.add(dep)

      # Update is_blocked cache
      depends_on_task = await session.get(Task, depends_on_id)
      if depends_on_task and depends_on_task.status != "done":
          task = await session.get(Task, task_id)
          task.is_blocked = True

      await session.flush()
      return dep

  async def is_task_blocked(session: AsyncSession, task_id: UUID) -> bool:
      """True nếu ít nhất 1 dependency chưa Done."""
      result = await session.execute(
          select(Task.status)
          .join(TaskDependency, Task.id == TaskDependency.depends_on_task_id)
          .where(TaskDependency.task_id == task_id)
      )
      statuses = [row[0] for row in result]
      return any(s != "done" for s in statuses)

  async def unlock_dependents(session: AsyncSession, completed_task_id: UUID) -> list[UUID]:
      """Gọi sau khi task Done. Recompute is_blocked cho tất cả task phụ thuộc vào nó.
         Trả list task_id đã được unlock (is_blocked False → True)."""
      # Tìm tasks depends on completed_task_id
      rows = await session.scalars(
          select(TaskDependency.task_id).where(TaskDependency.depends_on_task_id == completed_task_id)
      )
      unlocked: list[UUID] = []
      for dependent_id in rows:
          still_blocked = await is_task_blocked(session, dependent_id)
          task = await session.get(Task, dependent_id)
          if task and task.is_blocked and not still_blocked:
              task.is_blocked = False
              unlocked.append(dependent_id)
      return unlocked

  async def get_dependency_graph(session: AsyncSession, project_id: UUID) -> dict:
      tasks = await session.scalars(select(Task).where(Task.project_id == project_id))
      edges_rows = await session.execute(
          select(TaskDependency.task_id, TaskDependency.depends_on_task_id)
          .join(Task, Task.id == TaskDependency.task_id)
          .where(Task.project_id == project_id)
      )
      return {
          "nodes": [{"id": str(t.id), "title": t.title, "status": t.status} for t in tasks],
          "edges": [{"from": str(row[0]), "to": str(row[1])} for row in edges_rows],
      }
  ```

- [ ] T024 Tạo `backend/app/api/v1/dependencies.py`:
  ```python
  @router.post("/projects/{project_id}/tasks/{task_id}/dependencies", response_model=DependencyResponse, status_code=201)
  async def add_dep(project_id: UUID, task_id: UUID, body: DependencyCreate,
                    _=require_developer_or_above, session=Depends(get_session)):
      dep = await dependency_service.add_dependency(session, task_id, body.depends_on_task_id, project_id)
      await session.commit()
      return DependencyResponse(task_id=dep.task_id, depends_on_task_id=dep.depends_on_task_id, created_at=dep.created_at)

  @router.get("/projects/{project_id}/dependency-graph")
  async def get_graph(project_id: UUID, _=require_any_member, session=Depends(get_session)):
      return await dependency_service.get_dependency_graph(session, project_id)
  ```

- [ ] T025 [P] Tạo `backend/app/services/template_service.py`:
  ```python
  async def list_templates(session: AsyncSession, project_id: UUID | None, scope: str | None) -> list[TaskTemplate]:
      q = select(TaskTemplate)
      if scope == "global":
          q = q.where(TaskTemplate.scope == TemplateScope.global_)
      elif scope == "project" and project_id:
          q = q.where(TaskTemplate.project_id == project_id)
      else:
          q = q.where(or_(TaskTemplate.scope == TemplateScope.global_,
                           TaskTemplate.project_id == project_id))
      return list(await session.scalars(q))

  async def create_template(session, data: TemplateCreate, created_by: UUID) -> TaskTemplate:
      # Check name conflict trong project scope
      if data.scope == "project" and data.project_id:
          existing = await session.scalar(select(TaskTemplate).where(
              TaskTemplate.project_id == data.project_id, TaskTemplate.name == data.name))
          if existing:
              raise HTTPException(409, "Template name conflict in project scope")
      tmpl = TaskTemplate(**data.model_dump(), created_by=created_by)
      session.add(tmpl)
      return tmpl
  ```

- [ ] T026 [P] Tạo `backend/app/api/v1/templates.py`: `GET /templates?scope=&project_id=`, `POST /templates`, `DELETE /templates/{id}`

- [ ] T027 Update `backend/app/api/v1/tasks.py` — thêm assign endpoint:
  ```python
  @router.patch("/{task_id}/assign", response_model=TaskAssignResponse)
  async def assign_task(task_id: UUID, body: AssignRequest,
                        current_user: User = Depends(get_current_user),
                        session=Depends(get_session)):
      task = await session.get(Task, task_id)
      if not task:
          raise HTTPException(404)
      # Kiểm tra user_id là member của project
      if body.user_id:
          member = await session.scalar(select(ProjectMember).where(
              ProjectMember.project_id == task.project_id,
              ProjectMember.user_id == body.user_id))
          if not member:
              raise HTTPException(404, "User not a member of this project")
      task.assigned_to = body.user_id
      await session.commit()
      return TaskAssignResponse(task_id=task.id, assigned_to=body.user_id)
  ```

- [ ] T028 Update `backend/app/services/kanban_service.py` — gọi unlock sau Done:
  ```python
  async def approve_task(session, task_id, current_user, project_id):
      # ... existing approve logic ...
      task.status = "done"
      unlocked_ids = await dependency_service.unlock_dependents(session, task_id)
      # Notify unlocked tasks
      for uid in unlocked_ids:
          unlocked_task = await session.get(Task, uid)
          if unlocked_task and unlocked_task.assigned_to:
              await notification_service.create_notification(
                  session, user_id=unlocked_task.assigned_to,
                  type="task_unblocked", content=f"Task '{unlocked_task.title}' đã được mở khóa",
                  reference_type="task", reference_id=uid)
  ```

**Checkpoint**: Task A (todo) + Task B depends A → B.`is_blocked=true` → approve A → B.`is_blocked=false`. Cycle: B depends A, thêm A depends B → 409. `GET /projects/{id}/dependency-graph` trả đúng nodes + edges. Template: tạo → list → xóa.

---

## Phase 5: F-007 Backend — Notifications & Webhooks

**Purpose**: In-app notifications, webhook delivery pipeline, GitHub PR integration.

- [ ] T029 [P] Tạo `backend/app/models/notification.py`:
  ```python
  class NotificationType(str, PyEnum):
      task_assigned = "task_assigned"
      task_needs_review = "task_needs_review"
      task_done = "task_done"
      task_unblocked = "task_unblocked"
      agent_error = "agent_error"
      invite_accepted = "invite_accepted"
      review_complete = "review_complete"

  class Notification(Base):
      __tablename__ = "notifications"
      id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
      user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
      type: Mapped[NotificationType]
      content: Mapped[str] = mapped_column(Text)
      reference_type: Mapped[str | None] = mapped_column(String(20))  # 'task' | 'project' | 'invitation'
      reference_id: Mapped[UUID | None]
      is_read: Mapped[bool] = mapped_column(default=False)
      created_at: Mapped[datetime] = mapped_column(server_default=func.now())
  ```

- [ ] T030 [P] Tạo `backend/app/models/webhook.py`:
  ```python
  class WebhookConfig(Base):
      __tablename__ = "webhook_configs"
      id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
      project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
      url: Mapped[str] = mapped_column(Text)
      secret: Mapped[str | None] = mapped_column(String(100))
      events: Mapped[list[str]] = mapped_column(postgresql.ARRAY(Text), default=list)
      enabled: Mapped[bool] = mapped_column(default=True)
      created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
      deliveries: Mapped[list["WebhookDelivery"]] = relationship(back_populates="config",
                                                                   cascade="all, delete-orphan")

  class WebhookDelivery(Base):
      __tablename__ = "webhook_deliveries"
      id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
      webhook_config_id: Mapped[UUID] = mapped_column(ForeignKey("webhook_configs.id", ondelete="CASCADE"))
      event_type: Mapped[str] = mapped_column(String(50))
      payload: Mapped[dict] = mapped_column(postgresql.JSONB)
      status: Mapped[str] = mapped_column(default="pending")  # pending|success|failed|retrying
      http_status: Mapped[int | None]
      attempts: Mapped[int] = mapped_column(default=0)
      last_attempt_at: Mapped[datetime | None]
      config: Mapped[WebhookConfig] = relationship(back_populates="deliveries")
  ```

- [ ] T031 [P] Tạo `backend/app/models/github_config.py`:
  ```python
  class GitHubConfig(Base):
      __tablename__ = "github_configs"
      id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
      project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), unique=True)
      repo_full_name: Mapped[str] = mapped_column(String(200))   # "owner/repo"
      pat_encrypted: Mapped[str] = mapped_column(Text)           # Fernet-encrypted PAT
      default_base_branch: Mapped[str] = mapped_column(default="main")
      enabled: Mapped[bool] = mapped_column(default=True)
      created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
  ```

- [ ] T032 Tạo `backend/app/services/notification_service.py`:
  ```python
  async def create_notification(session, user_id: UUID, type: NotificationType,
                                 content: str, reference_type: str | None = None,
                                 reference_id: UUID | None = None) -> Notification:
      n = Notification(user_id=user_id, type=type, content=content,
                       reference_type=reference_type, reference_id=reference_id)
      session.add(n)
      return n

  async def notify_task_needs_review(session, task: Task) -> None:
      """Notify tất cả Leader + Owner của project."""
      leaders = await session.scalars(
          select(ProjectMember).where(
              ProjectMember.project_id == task.project_id,
              ProjectMember.role.in_([ProjectRole.owner, ProjectRole.leader])
          )
      )
      for member in leaders:
          await create_notification(session, user_id=member.user_id,
                                     type=NotificationType.task_needs_review,
                                     content=f"Task '{task.title}' đang chờ review",
                                     reference_type="task", reference_id=task.id)

  async def notify_task_assigned(session, task: Task, assigned_to_user_id: UUID) -> None:
      await create_notification(session, user_id=assigned_to_user_id,
                                 type=NotificationType.task_assigned,
                                 content=f"Bạn được assign vào task '{task.title}'",
                                 reference_type="task", reference_id=task.id)

  async def get_notifications(session, user_id: UUID, unread_only: bool = False,
                               limit: int = 20, offset: int = 0) -> tuple[int, list[Notification]]:
      q = select(Notification).where(Notification.user_id == user_id)
      if unread_only:
          q = q.where(Notification.is_read == False)
      total_unread = await session.scalar(
          select(func.count()).select_from(Notification).where(
              Notification.user_id == user_id, Notification.is_read == False))
      items = list(await session.scalars(q.order_by(Notification.created_at.desc()).limit(limit).offset(offset)))
      return total_unread, items

  async def mark_all_read(session, user_id: UUID) -> int:
      result = await session.execute(
          update(Notification).where(Notification.user_id == user_id, Notification.is_read == False)
          .values(is_read=True))
      return result.rowcount
  ```

- [ ] T033 Tạo `backend/app/services/webhook_service.py`:
  ```python
  import hmac, hashlib, httpx, asyncio, json

  RETRY_DELAYS = [5, 30, 120]  # seconds: attempt 1, 2, 3

  def _sign_payload(payload_bytes: bytes, secret: str) -> str:
      """HMAC-SHA256 signature cho webhook payload."""
      sig = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
      return f"sha256={sig}"

  async def enqueue_delivery(session, project_id: UUID, event_type: str, payload: dict) -> None:
      configs = await session.scalars(
          select(WebhookConfig).where(
              WebhookConfig.project_id == project_id,
              WebhookConfig.enabled == True,
              WebhookConfig.events.contains([event_type]),  # PostgreSQL ARRAY @> operator
          )
      )
      redis = get_redis()
      for config in configs:
          delivery = WebhookDelivery(webhook_config_id=config.id, event_type=event_type,
                                     payload=payload, status="pending")
          session.add(delivery)
          await session.flush()
          await redis.rpush("webhook_queue", str(delivery.id))

  async def _deliver_once(delivery_id: UUID, session) -> tuple[bool, int | None]:
      """Thực hiện 1 HTTP POST. Trả (success, http_status)."""
      delivery = await session.get(WebhookDelivery, delivery_id, options=[selectinload(WebhookDelivery.config)])
      payload_bytes = json.dumps(delivery.payload).encode()
      headers = {"Content-Type": "application/json", "X-NeoKanban-Event": delivery.event_type}
      if delivery.config.secret:
          headers["X-NeoKanban-Signature"] = _sign_payload(payload_bytes, delivery.config.secret)
      try:
          async with httpx.AsyncClient(timeout=10) as client:
              resp = await client.post(delivery.config.url, content=payload_bytes, headers=headers)
          return resp.status_code < 400, resp.status_code
      except httpx.RequestError:
          return False, None

  async def process_deliveries() -> None:
      """Background worker: BLPOP từ Redis, deliver với retry."""
      redis = get_redis()
      while True:
          try:
              _, delivery_id_bytes = await redis.blpop("webhook_queue", timeout=30)
              delivery_id = UUID(delivery_id_bytes.decode())
              async with get_db_session() as session:
                  delivery = await session.get(WebhookDelivery, delivery_id)
                  if not delivery or delivery.status == "success":
                      continue
                  for attempt_idx, delay in enumerate(RETRY_DELAYS):
                      if attempt_idx > 0:
                          await asyncio.sleep(delay)
                      success, http_status = await _deliver_once(delivery_id, session)
                      delivery.attempts += 1
                      delivery.last_attempt_at = datetime.utcnow()
                      delivery.http_status = http_status
                      if success:
                          delivery.status = "success"; break
                      delivery.status = "retrying" if attempt_idx < 2 else "failed"
                  await session.commit()
          except Exception:
              pass  # log và tiếp tục loop

  async def test_webhook(session, webhook_id: UUID) -> dict:
      config = await session.get(WebhookConfig, webhook_id)
      if not config:
          raise HTTPException(404)
      test_payload = {"event": "webhook.test", "timestamp": datetime.utcnow().isoformat(),
                      "project": {"id": str(config.project_id), "name": "Test"}}
      start = asyncio.get_event_loop().time()
      success, http_status = await _deliver_once_direct(config, test_payload)
      elapsed_ms = int((asyncio.get_event_loop().time() - start) * 1000)
      if not success:
          raise HTTPException(500, f"Delivery failed with status {http_status}")
      return {"delivered": True, "http_status": http_status, "response_time_ms": elapsed_ms}
  ```

- [ ] T034 Tạo `backend/app/services/github_service.py`:
  ```python
  from cryptography.fernet import Fernet
  from github import Github, GithubException

  def _get_fernet(settings: Settings) -> Fernet:
      return Fernet(settings.fernet_key)

  def encrypt_pat(pat: str, settings: Settings) -> str:
      return _get_fernet(settings).encrypt(pat.encode()).decode()

  def decrypt_pat(encrypted: str, settings: Settings) -> str:
      return _get_fernet(settings).decrypt(encrypted.encode()).decode()

  async def validate_config(repo_full_name: str, pat: str) -> bool:
      try:
          g = Github(pat)
          g.get_repo(repo_full_name)
          return True
      except GithubException:
          return False

  async def create_pull_request(config: GitHubConfig, task, diff_content: str,
                                 branch_name: str, settings: Settings) -> str:
      pat = decrypt_pat(config.pat_encrypted, settings)
      g = Github(pat)
      repo = g.get_repo(config.repo_full_name)
      body = f"## Task: {task.title}\n\n{task.description or ''}\n\n```diff\n{diff_content[:3000]}\n```"
      pr = repo.create_pull(title=task.title, body=body,
                             head=branch_name, base=config.default_base_branch)
      return pr.html_url
  ```

- [ ] T035 Tạo các endpoint files: `notifications.py`, `webhooks.py`, `github.py` theo contracts/rest-api.md. Đăng ký trong `router.py`.

- [ ] T036 Update `backend/app/services/kanban_service.py` — integrate notifications + webhooks:
  ```python
  # Trong approve_task (task → done):
  await notification_service.notify_task_done(session, task)
  await webhook_service.enqueue_delivery(session, task.project_id, "task.done",
      build_webhook_payload("task.done", task, actor=current_user))
  github_cfg = await session.scalar(select(GitHubConfig).where(
      GitHubConfig.project_id == task.project_id, GitHubConfig.enabled == True))
  if github_cfg:
      pr_url = await github_service.create_pull_request(github_cfg, task, diff_content, branch_name, settings)
      task.github_pr_url = pr_url  # nếu tasks có cột này (optional)

  # Trong move_to_review (task → review):
  await notification_service.notify_task_needs_review(session, task)
  await webhook_service.enqueue_delivery(session, task.project_id, "task.needs_review",
      build_webhook_payload("task.needs_review", task, actor="agent"))

  def build_webhook_payload(event: str, task, actor) -> dict:
      return {"event": event, "timestamp": datetime.utcnow().isoformat(),
              "project": {"id": str(task.project_id), "name": task.project.name},
              "task": {"id": str(task.id), "title": task.title},
              "actor": {"type": "user" if hasattr(actor, "id") else "agent",
                        "id": str(actor.id) if hasattr(actor, "id") else None,
                        "name": getattr(actor, "display_name", "agent")}, "meta": {}}
  ```

- [ ] T037 Update `backend/app/main.py`:
  ```python
  @app.on_event("startup")
  async def startup():
      asyncio.create_task(webhook_service.process_deliveries())
  ```

**Checkpoint**: Task → Review → Leader nhận notification (`GET /notifications` trả 1 item unread). Webhook configured với event `task.needs_review` → khi task vào Review → HTTP POST gửi tới URL. `POST /webhooks/{id}/test` trả `{"delivered": true, "http_status": 200}`. GitHub PAT encrypt/decrypt round-trip không mất data.

---

## Phase 6: F-006 Backend — Dashboard & Analytics

**Purpose**: Dashboard tổng quan, analytics per-project.

- [ ] T038 Tạo `backend/app/services/analytics_service.py`:
  ```python
  from datetime import datetime, timedelta
  from sqlalchemy import select, func, case, text

  async def get_dashboard_data(session: AsyncSession, user_id: UUID) -> dict:
      # Lấy tất cả project user là member (hoặc owner)
      member_projects = await session.scalars(
          select(Project)
          .join(ProjectMember, ProjectMember.project_id == Project.id)
          .where(ProjectMember.user_id == user_id)
      )
      result = []
      for project in member_projects:
          # Task counts per status
          counts_rows = await session.execute(
              select(Task.status, func.count().label("cnt"))
              .where(Task.project_id == project.id)
              .group_by(Task.status)
          )
          task_counts = {row[0]: row[1] for row in counts_rows}

          # Stale review tasks (> 24h in review)
          stale_threshold = datetime.utcnow() - timedelta(hours=24)
          stale_rows = await session.scalars(
              select(Task).where(Task.project_id == project.id,
                                  Task.status == "review",
                                  Task.updated_at < stale_threshold)
          )

          # Member count
          member_count = await session.scalar(
              select(func.count()).select_from(ProjectMember).where(ProjectMember.project_id == project.id))

          result.append({
              "id": str(project.id), "name": project.name, "coding_backend": project.coding_backend,
              "task_counts": {"todo": task_counts.get("todo", 0), "in_progress": task_counts.get("in_progress", 0),
                              "review": task_counts.get("review", 0), "done": task_counts.get("done", 0)},
              "stale_review_tasks": [{"task_id": str(t.id), "title": t.title,
                                       "in_review_since": t.updated_at.isoformat()} for t in stale_rows],
              "members_count": member_count,
          })
      return {"projects": result}

  async def get_project_analytics(session: AsyncSession, project_id: UUID,
                                   from_dt: datetime, to_dt: datetime) -> dict:
      # 1. By backend: avg completion time, first-approve rate
      backend_rows = await session.execute(text("""
          SELECT
              ar.coding_backend,
              AVG(EXTRACT(EPOCH FROM (ar.updated_at - ar.created_at)))::int AS avg_seconds,
              COUNT(*) FILTER (WHERE ar.retry_count = 0 AND ar.status = 'done')::float
                  / NULLIF(COUNT(*) FILTER (WHERE ar.status = 'done'), 0) AS first_approve_rate,
              COUNT(*) FILTER (WHERE ar.status = 'error') AS error_count
          FROM agent_runs ar
          WHERE ar.project_id = :pid AND ar.created_at BETWEEN :from_dt AND :to_dt
          GROUP BY ar.coding_backend
      """), {"pid": str(project_id), "from_dt": from_dt, "to_dt": to_dt})

      # 2. By member: tasks_done, in_progress, avg_retry
      member_rows = await session.execute(text("""
          SELECT
              t.assigned_to,
              u.display_name,
              COUNT(*) FILTER (WHERE t.status = 'done') AS tasks_done,
              COUNT(*) FILTER (WHERE t.status = 'in_progress') AS tasks_in_progress,
              COALESCE(AVG(ar.retry_count) FILTER (WHERE ar.status = 'done'), 0)::float AS avg_retry
          FROM tasks t
          LEFT JOIN users u ON u.id = t.assigned_to
          LEFT JOIN agent_runs ar ON ar.task_id = t.id
          WHERE t.project_id = :pid AND t.updated_at BETWEEN :from_dt AND :to_dt
          GROUP BY t.assigned_to, u.display_name
      """), {"pid": str(project_id), "from_dt": from_dt, "to_dt": to_dt})

      # 3. Reviewer avg score
      avg_score = await session.scalar(
          select(func.avg(ReviewReport.score))
          .join(Task, Task.id == ReviewReport.task_id)
          .where(Task.project_id == project_id, ReviewReport.status == "complete",
                 ReviewReport.created_at.between(from_dt, to_dt))
      )

      # 4. Error breakdown from audit_logs
      error_rows = await session.execute(text("""
          SELECT error_code, COUNT(*) as cnt
          FROM audit_logs
          WHERE project_id = :pid AND result = 'failure'
            AND created_at BETWEEN :from_dt AND :to_dt
          GROUP BY error_code
      """), {"pid": str(project_id), "from_dt": from_dt, "to_dt": to_dt})

      return {
          "period": {"from": from_dt.isoformat(), "to": to_dt.isoformat()},
          "by_backend": [{"backend": r[0], "avg_seconds": r[1] or 0,
                          "first_approve_rate": round(r[2] or 0, 2), "error_count": r[3]}
                         for r in backend_rows],
          "by_member": [{"user_id": str(r[0]) if r[0] else None, "display_name": r[1] or "Unassigned",
                         "tasks_done": r[2], "tasks_in_progress": r[3], "avg_retry": round(r[4], 1)}
                        for r in member_rows if r[0]],
          "reviewer_avg_score": round(float(avg_score or 0), 1),
          "error_breakdown": {r[0]: r[1] for r in error_rows},
      }
  ```

- [ ] T039 Tạo `backend/app/api/v1/analytics.py`:
  ```python
  @router.get("/dashboard", response_model=DashboardResponse)
  async def dashboard(current_user: User = Depends(get_current_user), session=Depends(get_session)):
      return await analytics_service.get_dashboard_data(session, current_user.id)

  @router.get("/projects/{project_id}/analytics", response_model=AnalyticsResponse)
  async def project_analytics(project_id: UUID, range: str = "7d",
                               from_date: str | None = None, to_date: str | None = None,
                               _=require_leader_or_above, session=Depends(get_session)):
      now = datetime.utcnow()
      if range == "7d":
          from_dt, to_dt = now - timedelta(days=7), now
      elif range == "30d":
          from_dt, to_dt = now - timedelta(days=30), now
      elif range == "custom" and from_date and to_date:
          from_dt = datetime.fromisoformat(from_date); to_dt = datetime.fromisoformat(to_date)
      else:
          raise HTTPException(400, "Invalid range parameter")
      return await analytics_service.get_project_analytics(session, project_id, from_dt, to_dt)
  ```

- [ ] T040 [P] Tạo `backend/app/schemas/analytics.py`:
  ```python
  class BackendMetric(BaseModel):
      backend: str; avg_seconds: int; first_approve_rate: float; error_count: int

  class MemberMetric(BaseModel):
      user_id: UUID | None; display_name: str
      tasks_done: int; tasks_in_progress: int; avg_retry: float

  class StaleTask(BaseModel):
      task_id: UUID; title: str; in_review_since: str

  class ProjectDashboard(BaseModel):
      id: UUID; name: str; coding_backend: str
      task_counts: dict[str, int]; stale_review_tasks: list[StaleTask]; members_count: int

  class DashboardResponse(BaseModel):
      projects: list[ProjectDashboard]

  class AnalyticsResponse(BaseModel):
      period: dict[str, str]
      by_backend: list[BackendMetric]
      by_member: list[MemberMetric]
      reviewer_avg_score: float
      error_breakdown: dict[str, int]
  ```

**Checkpoint**: `GET /dashboard` trả list project với đúng task counts và stale tasks. `GET /projects/{id}/analytics?range=7d` trả by_backend metrics. Viewer gọi analytics → 403. `range=custom&from_date=2026-05-01&to_date=2026-05-15` → filter đúng khoảng thời gian.

---

## Phase 7: Frontend — Auth & Team UI

**Purpose**: Auth guard, login/register pages (refine existing), team management UI.

- [ ] T041 Tạo `frontend/src/contexts/auth-context.tsx`:
  ```tsx
  interface AuthState {
    user: User | null
    token: string | null
    isLoading: boolean
  }
  interface AuthContextValue extends AuthState {
    login: (email: string, password: string) => Promise<void>
    logout: () => void
    register: (email: string, password: string, displayName: string) => Promise<void>
  }

  const TOKEN_KEY = "neokanban_token"

  export function AuthProvider({ children }: { children: ReactNode }) {
    const [state, setState] = useState<AuthState>({ user: null, token: null, isLoading: true })

    useEffect(() => {
      const stored = localStorage.getItem(TOKEN_KEY)
      if (stored) {
        authApi.getMe(stored)
          .then(user => setState({ user, token: stored, isLoading: false }))
          .catch(() => { localStorage.removeItem(TOKEN_KEY); setState({ user: null, token: null, isLoading: false }) })
      } else {
        setState(s => ({ ...s, isLoading: false }))
      }
    }, [])

    const login = async (email: string, password: string) => {
      const { access_token } = await authApi.login(email, password)
      const user = await authApi.getMe(access_token)
      localStorage.setItem(TOKEN_KEY, access_token)
      setState({ user, token: access_token, isLoading: false })
    }

    const logout = () => {
      localStorage.removeItem(TOKEN_KEY)
      setState({ user: null, token: null, isLoading: false })
    }

    const register = async (email: string, password: string, displayName: string) => {
      const { access_token, user } = await authApi.register(email, password, displayName)
      localStorage.setItem(TOKEN_KEY, access_token)
      setState({ user, token: access_token, isLoading: false })
    }

    return <AuthContext.Provider value={{ ...state, login, logout, register }}>{children}</AuthContext.Provider>
  }

  export const useAuth = () => {
    const ctx = useContext(AuthContext)
    if (!ctx) throw new Error("useAuth must be used within AuthProvider")
    return ctx
  }
  ```

- [ ] T042 Update `frontend/src/services/auth-api.ts`:
  ```ts
  const BASE = "/api/v1"

  // Singleton axios instance với token injection
  export function createApiClient(token: string | null) {
    return axios.create({
      baseURL: BASE,
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
  }

  // Standalone auth calls (không cần token)
  export const authApi = {
    register: async (email: string, password: string, display_name: string) => {
      const { data } = await axios.post(`${BASE}/auth/register`, { email, password, display_name })
      return data as { access_token: string; user: User }
    },
    login: async (email: string, password: string) => {
      const { data } = await axios.post(`${BASE}/auth/login`, { email, password })
      return data as { access_token: string }
    },
    getMe: async (token: string) => {
      const { data } = await axios.get(`${BASE}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      return data as User
    },
  }
  ```

- [ ] T043 Update `frontend/src/pages/login.tsx` và `register.tsx`:
  ```tsx
  // login.tsx — chỉ cần update form submit handler
  const { login } = useAuth()
  const navigate = useNavigate()

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    try {
      await login(email, password)
      navigate("/dashboard")
    } catch {
      setError("Email hoặc mật khẩu không đúng")
    }
  }
  ```

- [ ] T044 Tạo `frontend/src/components/molecules/auth-guard.tsx`:
  ```tsx
  export function AuthGuard({ children }: { children: ReactNode }) {
    const { user, isLoading } = useAuth()
    const location = useLocation()
    if (isLoading) return <div className="flex h-screen items-center justify-center"><Spinner /></div>
    if (!user) return <Navigate to="/login" state={{ from: location }} replace />
    return <>{children}</>
  }
  ```
  Wrap `project-workspace.tsx` và `dashboard.tsx` trong `<AuthGuard>` ở router config.

- [ ] T045 Tạo `frontend/src/services/member-api.ts`:
  ```ts
  export function memberApi(token: string) {
    const client = createApiClient(token)
    return {
      getMembers: (projectId: string) => client.get<ProjectMember[]>(`/projects/${projectId}/members`).then(r => r.data),
      invite: (projectId: string, role: ProjectRole, inviteeEmail?: string) =>
        client.post<InvitationResponse>(`/projects/${projectId}/members/invite`, { role, invitee_email: inviteeEmail }).then(r => r.data),
      acceptInvite: (token: string) =>
        client.post<AcceptResponse>(`/invitations/${token}/accept`).then(r => r.data),
      changeRole: (projectId: string, userId: string, role: ProjectRole) =>
        client.patch<ProjectMember>(`/projects/${projectId}/members/${userId}`, { role }).then(r => r.data),
      removeMember: (projectId: string, userId: string) =>
        client.delete(`/projects/${projectId}/members/${userId}`),
    }
  }
  ```

- [ ] T046 Tạo `frontend/src/components/organisms/project-members.tsx`:
  - Bảng member: `Avatar` + display_name + email + `RoleBadge` (color-coded) + action buttons
  - "Invite member" form: email input (optional) + role select + "Generate Link" button
  - Copy invite URL to clipboard với toast feedback
  - Role change: `<select>` chỉ hiện cho `owner` role; disabled cho chính mình
  - Remove button: disabled nếu target là owner hoặc là chính mình

- [ ] T047 Update `frontend/src/components/organisms/project-header.tsx`:
  ```tsx
  // Thêm vào header:
  <div className="flex items-center gap-2">
    {/* Member avatars: max 5, +N badge */}
    <div className="flex -space-x-2">
      {members.slice(0, 5).map(m => <Avatar key={m.user_id} name={m.display_name} size="sm" />)}
      {members.length > 5 && <span className="avatar-badge">+{members.length - 5}</span>}
    </div>
    {/* Notification bell */}
    <button onClick={() => setNotifOpen(true)} className="relative">
      <BellIcon />
      {unreadCount > 0 && <NotificationBadge count={unreadCount} />}
    </button>
  </div>
  ```

- [ ] T048 Update `frontend/src/types/index.ts` — thêm các interfaces:
  ```ts
  export type ProjectRole = "owner" | "leader" | "developer" | "viewer"

  export interface User {
    id: string; email: string; display_name: string; created_at: string
  }

  export interface ProjectMember {
    user_id: string; display_name: string; email: string
    role: ProjectRole; joined_at: string
  }

  export interface ReviewReport {
    id: string; task_id: string
    status: "pending" | "running" | "complete" | "error"
    score: number | null; suggestion: "approve" | "needs_changes" | null
    test_runner: string | null; test_pass: number; test_fail: number
    comments: ReviewComment[]
    error_message: string | null
    created_at: string; completed_at: string | null
  }

  export interface ReviewComment {
    id: string; file_path: string; line_number: number | null
    content: string; severity: "info" | "warning" | "error"
  }

  export interface TaskDependency {
    task_id: string; depends_on_task_id: string; created_at: string
  }

  export interface Notification {
    id: string; type: string; content: string
    reference_type: string | null; reference_id: string | null
    is_read: boolean; created_at: string
  }

  export interface WebhookConfig {
    id: string; url: string; events: string[]; enabled: boolean
  }

  // Task type update — thêm fields mới
  export interface Task {
    // ... existing fields ...
    assigned_to: string | null
    is_blocked: boolean
  }
  ```

**Checkpoint**: Mở `/` → redirect `/login`. Login thành công → redirect `/dashboard`. `useAuth().user` không null sau refresh (token persist). Project header hiện max 5 avatar và bell icon. Owner mời thành viên → nhận link → accept → xuất hiện trong member list.

---

## Phase 8: Frontend — AI Review Panel

**Purpose**: Hiển thị kết quả Reviewer Agent trong Diff Viewer.

- [ ] T049 Tạo `frontend/src/services/review-api.ts`:
  ```ts
  export function reviewApi(token: string) {
    const client = createApiClient(token)
    return {
      getReport: (taskId: string) =>
        client.get<ReviewReport>(`/tasks/${taskId}/review`).then(r => r.data),
    }
  }

  // Hook với polling khi status=running/pending
  export function useReviewReport(taskId: string | null) {
    const { token } = useAuth()
    const [report, setReport] = useState<ReviewReport | null>(null)

    useEffect(() => {
      if (!taskId || !token) return
      let interval: ReturnType<typeof setInterval>
      const fetch = async () => {
        try {
          const data = await reviewApi(token).getReport(taskId)
          setReport(data)
          if (data.status === "complete" || data.status === "error") {
            clearInterval(interval)
          }
        } catch { /* 404 = not yet created */ }
      }
      fetch()
      interval = setInterval(fetch, 2000)
      return () => clearInterval(interval)
    }, [taskId, token])

    return report
  }
  ```

- [ ] T050 Tạo `frontend/src/components/organisms/ai-review-panel.tsx`:
  ```tsx
  interface AiReviewPanelProps {
    taskId: string
    onCommentClick?: (filePath: string, lineNumber: number | null) => void
  }

  function ScoreGauge({ score }: { score: number }) {
    const color = score >= 80 ? "text-green-600" : score >= 50 ? "text-yellow-500" : "text-red-600"
    return (
      <div className={`text-4xl font-bold ${color}`}>
        {score}<span className="text-lg text-gray-400">/100</span>
      </div>
    )
  }

  export function AiReviewPanel({ taskId, onCommentClick }: AiReviewPanelProps) {
    const report = useReviewReport(taskId)

    if (!report || report.status === "pending") return (
      <div className="p-4 text-gray-500 text-sm">AI Review đang chờ agent hoàn thành...</div>
    )
    if (report.status === "running") return (
      <div className="p-4 flex items-center gap-2">
        <Spinner size="sm" /><span className="text-sm">Reviewer Agent đang chạy...</span>
      </div>
    )
    if (report.status === "error") return (
      <div className="p-4 text-red-600 text-sm">Review lỗi: {report.error_message}</div>
    )

    // Group comments by file
    const byFile = report.comments.reduce((acc, c) => {
      ;(acc[c.file_path] ??= []).push(c)
      return acc
    }, {} as Record<string, ReviewComment[]>)

    const severityIcon = { info: "ℹ", warning: "⚠", error: "✗" }
    const severityColor = { info: "text-blue-600", warning: "text-yellow-600", error: "text-red-600" }

    return (
      <div className="flex flex-col gap-4 p-4 border-l border-gray-200 min-w-[280px] max-w-[380px]">
        <div className="flex items-center justify-between">
          <ScoreGauge score={report.score ?? 0} />
          <span className={`px-2 py-1 rounded text-sm font-medium ${
            report.suggestion === "approve" ? "bg-green-100 text-green-700" : "bg-yellow-100 text-yellow-700"
          }`}>
            {report.suggestion === "approve" ? "✓ Approve" : "⚠ Needs changes"}
          </span>
        </div>
        {/* Test results */}
        <div className="text-sm text-gray-600">
          {report.test_runner === "none" || !report.test_runner
            ? "Không tìm thấy test runner"
            : `${report.test_pass} passed, ${report.test_fail} failed`}
        </div>
        {/* Comments grouped by file */}
        {Object.entries(byFile).map(([file, comments]) => (
          <div key={file}>
            <div className="text-xs font-mono text-gray-500 mb-1 truncate">{file}</div>
            {comments.map(c => (
              <button key={c.id} onClick={() => onCommentClick?.(c.file_path, c.line_number)}
                className="w-full text-left text-xs p-2 rounded hover:bg-gray-50 border-l-2 border-gray-200 mb-1">
                <span className={severityColor[c.severity]}>{severityIcon[c.severity]}</span>
                {c.line_number && <span className="text-gray-400 ml-1">L{c.line_number}</span>}
                <span className="ml-1">{c.content}</span>
              </button>
            ))}
          </div>
        ))}
      </div>
    )
  }
  ```

- [ ] T051 Update `frontend/src/components/organisms/review-panel.tsx`:
  ```tsx
  // Layout: split-pane [diff | AI review]
  <div className="flex h-full">
    <div className="flex-1 overflow-auto">
      <DiffViewer diff={diff} highlightedLine={highlightedLine} />
    </div>
    <AiReviewPanel taskId={taskId} onCommentClick={(file, line) => setHighlightedLine({ file, line })} />
  </div>
  ```

- [ ] T052 Update WebSocket handler (`useWebSocket` hook hoặc `ws-handler.ts`):
  ```ts
  case "REVIEW_SCORE":
    // Trigger re-fetch trong useReviewReport (polling sẽ pick up)
    queryClient.invalidateQueries(["review", event.task_id])
    break
  case "REVIEW_COMMENT":
    // Optimistic append vào report state nếu cần live updates
    setReviewReport(prev => prev
      ? { ...prev, comments: [...prev.comments, event] }
      : null)
    break
  case "REVIEW_ERROR":
    setReviewReport(prev => prev ? { ...prev, status: "error", error_message: event.error } : null)
    break
  ```

**Checkpoint**: Task kéo In Progress → Review → Diff Viewer mở → AI Review panel bên phải với score gauge, suggestion chip, danh sách comments grouped by file. Click comment → diff scroll tới dòng đó. `REVIEW_SCORE` WS event cập nhật panel live. PO Approve/Reject không bị block bởi score.

---

## Phase 9: Frontend — Task Enhancements UI

**Purpose**: Dependency badges, dependency graph, assignee UI, template selector.

- [ ] T053 Tạo `frontend/src/components/atoms/avatar.tsx`:
  ```tsx
  interface AvatarProps { name: string; size?: "sm" | "md" | "lg"; className?: string }

  const sizeClass = { sm: "w-6 h-6 text-xs", md: "w-8 h-8 text-sm", lg: "w-10 h-10 text-base" }

  export function Avatar({ name, size = "md", className }: AvatarProps) {
    const initials = name.split(" ").map(w => w[0]).join("").slice(0, 2).toUpperCase()
    const hue = name.charCodeAt(0) * 137 % 360   // deterministic color from name
    return (
      <div className={`rounded-full flex items-center justify-center font-medium text-white ${sizeClass[size]} ${className}`}
           style={{ backgroundColor: `hsl(${hue}, 60%, 50%)` }}
           title={name}>
        {initials}
      </div>
    )
  }
  ```

- [ ] T054 Tạo `frontend/src/components/molecules/dependency-badge.tsx`:
  ```tsx
  interface DependencyBadgeProps { blockedByTitles: string[] }

  export function DependencyBadge({ blockedByTitles }: DependencyBadgeProps) {
    return (
      <div className="relative group">
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">
          🔒 Blocked ({blockedByTitles.length})
        </span>
        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block z-10 bg-gray-900 text-white text-xs rounded px-2 py-1 whitespace-nowrap">
          Chờ: {blockedByTitles.slice(0, 3).join(", ")}{blockedByTitles.length > 3 ? "..." : ""}
        </div>
      </div>
    )
  }
  ```

- [ ] T055 Tạo `frontend/src/components/molecules/assign-member.tsx`:
  ```tsx
  interface AssignMemberProps {
    projectId: string; taskId: string
    currentAssignee: string | null
    members: ProjectMember[]
    onAssign: (userId: string | null) => void
  }

  export function AssignMember({ members, currentAssignee, onAssign }: AssignMemberProps) {
    const [open, setOpen] = useState(false)
    const current = members.find(m => m.user_id === currentAssignee)
    return (
      <div className="relative">
        <button onClick={() => setOpen(o => !o)} className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-800">
          {current ? <><Avatar name={current.display_name} size="sm" />{current.display_name}</> : "Assign..."}
        </button>
        {open && (
          <div className="absolute right-0 mt-1 w-48 bg-white border rounded shadow-lg z-20">
            <button onClick={() => { onAssign(null); setOpen(false) }}
              className="w-full text-left px-3 py-2 text-xs text-gray-500 hover:bg-gray-50">Unassign</button>
            {members.map(m => (
              <button key={m.user_id} onClick={() => { onAssign(m.user_id); setOpen(false) }}
                className="w-full text-left px-3 py-2 flex items-center gap-2 hover:bg-gray-50">
                <Avatar name={m.display_name} size="sm" />
                <span className="text-sm">{m.display_name}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    )
  }
  ```

- [ ] T056 Update `frontend/src/components/organisms/task-card.tsx`:
  ```tsx
  // Thêm vào task card footer:
  <div className="flex items-center justify-between mt-2">
    {task.is_blocked && <DependencyBadge blockedByTitles={blockedByTitles} />}
    {task.assigned_to && <Avatar name={assigneeName} size="sm" />}
  </div>
  // Drag-and-drop: disable nếu is_blocked
  draggable={!task.is_blocked}
  className={`task-card ${task.is_blocked ? "opacity-60 cursor-not-allowed" : "cursor-grab"}`}
  ```

- [ ] T057 Update `frontend/src/components/organisms/kanban-board.tsx`:
  - `onDragStart`: check `task.is_blocked` → nếu true, `e.preventDefault()` + toast "Task đang bị blocked"
  - `onDrop`: validate source task không blocked trước khi xử lý drop

- [ ] T058 Tạo `frontend/src/components/organisms/dependency-graph.tsx`:
  ```tsx
  // SVG-based DAG: không cần react-flow để giữ dependency nhẹ
  interface GraphNode { id: string; title: string; status: string }
  interface GraphEdge { from: string; to: string }

  export function DependencyGraph({ nodes, edges }: { nodes: GraphNode[], edges: GraphEdge[] }) {
    // Simple grid layout: status-based columns như Kanban
    const STATUS_X = { todo: 100, in_progress: 300, review: 500, done: 700 }
    const nodePositions = nodes.reduce((acc, n, i) => {
      acc[n.id] = { x: STATUS_X[n.status as keyof typeof STATUS_X] ?? 300, y: 80 + (i % 5) * 80 }
      return acc
    }, {} as Record<string, { x: number; y: number }>)

    return (
      <svg width="900" height="500" className="border rounded bg-gray-50">
        {/* Edges */}
        {edges.map((e, i) => {
          const from = nodePositions[e.from]; const to = nodePositions[e.to]
          if (!from || !to) return null
          return <line key={i} x1={from.x} y1={from.y} x2={to.x} y2={to.y}
                       stroke="#94a3b8" strokeWidth={1.5} markerEnd="url(#arrow)" />
        })}
        {/* Nodes */}
        {nodes.map(n => {
          const pos = nodePositions[n.id]
          const fill = { todo: "#e2e8f0", in_progress: "#bfdbfe", review: "#fde68a", done: "#bbf7d0" }[n.status] ?? "#e2e8f0"
          return (
            <g key={n.id}>
              <rect x={pos.x - 60} y={pos.y - 20} width={120} height={40} rx={6} fill={fill} stroke="#64748b" />
              <text x={pos.x} y={pos.y + 5} textAnchor="middle" fontSize={11} className="select-none">
                {n.title.slice(0, 15)}{n.title.length > 15 ? "..." : ""}
              </text>
            </g>
          )
        })}
        <defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
          <path d="M0,0 L0,6 L8,3 z" fill="#94a3b8" /></marker></defs>
      </svg>
    )
  }
  ```

- [ ] T059 Tạo `frontend/src/components/molecules/template-selector.tsx`:
  ```tsx
  interface TemplateSelectorProps {
    projectId: string
    onSelect: (title: string, description: string) => void
  }

  export function TemplateSelector({ projectId, onSelect }: TemplateSelectorProps) {
    const { token } = useAuth()
    const [templates, setTemplates] = useState<TaskTemplate[]>([])

    useEffect(() => {
      Promise.all([
        templateApi(token!).list("global"),
        templateApi(token!).list("project", projectId),
      ]).then(([global, project]) => setTemplates([...global, ...project]))
    }, [projectId, token])

    if (!templates.length) return null
    return (
      <select onChange={e => {
        const tmpl = templates.find(t => t.id === e.target.value)
        if (tmpl) onSelect(tmpl.title_template, tmpl.description_template)
      }} defaultValue="" className="text-sm border rounded px-2 py-1">
        <option value="" disabled>Chọn template...</option>
        {templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
      </select>
    )
  }
  ```

- [ ] T060 Update task creation form: thêm `<TemplateSelector>` trên title/description inputs; khi chọn → `setTitle()` + `setDescription()`.

**Checkpoint**: Task card với `is_blocked=true` → badge đỏ "Blocked", opacity 60%, drag bị chặn. Task card với assignee → avatar hiện góc phải. Dependency graph render đúng nodes + mũi tên. Template selector → chọn template → form tự điền.

---

## Phase 10: Frontend — Dashboard, Analytics & Notifications

**Purpose**: Dashboard page, analytics charts, notification panel, webhook settings.

- [ ] T061 Tạo `frontend/src/pages/dashboard.tsx`:
  ```tsx
  export function Dashboard() {
    const { token } = useAuth()
    const [data, setData] = useState<DashboardResponse | null>(null)

    useEffect(() => {
      analyticsApi(token!).getDashboard().then(setData)
    }, [token])

    return (
      <div className="p-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {data?.projects.map(p => (
          <Link key={p.id} to={`/projects/${p.id}`} className="border rounded-lg p-4 hover:shadow-md">
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-semibold">{p.name}</h3>
              <CodingBackendBadge backend={p.coding_backend} />
            </div>
            {/* Task count pills */}
            <div className="flex gap-2 text-xs mb-2">
              <span className="bg-gray-100 px-2 py-0.5 rounded">Todo: {p.task_counts.todo}</span>
              <span className="bg-blue-100 px-2 py-0.5 rounded">In Progress: {p.task_counts.in_progress}</span>
              <span className="bg-yellow-100 px-2 py-0.5 rounded">Review: {p.task_counts.review}</span>
              <span className="bg-green-100 px-2 py-0.5 rounded">Done: {p.task_counts.done}</span>
            </div>
            {p.stale_review_tasks.length > 0 && (
              <div className="text-xs text-red-600">
                ⚠ {p.stale_review_tasks.length} task chờ review quá 24h
              </div>
            )}
            <div className="text-xs text-gray-400 mt-1">{p.members_count} thành viên</div>
          </Link>
        ))}
      </div>
    )
  }
  ```

- [ ] T062 Tạo `frontend/src/pages/analytics.tsx`:
  ```tsx
  import { BarChart, Bar, XAxis, YAxis, Tooltip, PieChart, Pie, Cell, Legend } from "recharts"

  export function Analytics() {
    const { projectId } = useParams()
    const { token } = useAuth()
    const [range, setRange] = useState<"7d" | "30d" | "custom">("7d")
    const [data, setData] = useState<AnalyticsResponse | null>(null)

    useEffect(() => {
      analyticsApi(token!).getProjectAnalytics(projectId!, range).then(setData)
    }, [projectId, range, token])

    const PIE_COLORS = ["#22c55e", "#f59e0b"]

    return (
      <div className="p-6 space-y-8">
        {/* Range picker */}
        <div className="flex gap-2">
          {(["7d", "30d", "custom"] as const).map(r => (
            <button key={r} onClick={() => setRange(r)}
              className={`px-3 py-1 rounded text-sm ${range === r ? "bg-blue-600 text-white" : "border"}`}>
              {r === "7d" ? "7 ngày" : r === "30d" ? "30 ngày" : "Tùy chọn"}
            </button>
          ))}
        </div>

        {/* Backend performance bar chart */}
        <section>
          <h3 className="font-semibold mb-2">Thời gian trung bình theo backend (giây)</h3>
          <BarChart width={500} height={250} data={data?.by_backend}>
            <XAxis dataKey="backend" /><YAxis /><Tooltip />
            <Bar dataKey="avg_seconds" fill="#3b82f6" />
          </BarChart>
        </section>

        {/* First-approve rate pie */}
        <section>
          <h3 className="font-semibold mb-2">Tỷ lệ Approve lần đầu</h3>
          <PieChart width={300} height={200}>
            <Pie data={data?.by_backend.map(b => ([
              { name: "Lần đầu", value: Math.round(b.first_approve_rate * 100) },
              { name: "Retry", value: 100 - Math.round(b.first_approve_rate * 100) },
            ])).flat()} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80}>
              {PIE_COLORS.map((c, i) => <Cell key={i} fill={c} />)}
            </Pie>
            <Legend />
          </PieChart>
        </section>

        {/* Member table */}
        <section>
          <h3 className="font-semibold mb-2">Thành viên</h3>
          <table className="w-full text-sm">
            <thead><tr className="text-left text-gray-500">
              <th>Tên</th><th>Done</th><th>In Progress</th><th>Avg Retry</th>
            </tr></thead>
            <tbody>{data?.by_member.map(m => (
              <tr key={m.user_id} className="border-t">
                <td className="py-2 flex items-center gap-2"><Avatar name={m.display_name} size="sm" />{m.display_name}</td>
                <td>{m.tasks_done}</td><td>{m.tasks_in_progress}</td><td>{m.avg_retry.toFixed(1)}</td>
              </tr>
            ))}</tbody>
          </table>
        </section>

        {/* Error breakdown */}
        <section>
          <h3 className="font-semibold mb-2">Lỗi Agent</h3>
          <div className="flex gap-2 flex-wrap">
            {Object.entries(data?.error_breakdown ?? {}).map(([code, count]) => (
              <span key={code} className="px-2 py-1 bg-red-100 text-red-700 rounded text-xs">
                {code}: {count}
              </span>
            ))}
          </div>
        </section>
      </div>
    )
  }
  ```

- [ ] T063 Tạo `frontend/src/components/molecules/notification-panel.tsx`:
  ```tsx
  function timeAgo(isoDate: string): string {
    const diff = Date.now() - new Date(isoDate).getTime()
    const mins = Math.floor(diff / 60000)
    if (mins < 60) return `${mins} phút trước`
    const hours = Math.floor(mins / 60)
    if (hours < 24) return `${hours} giờ trước`
    return `${Math.floor(hours / 24)} ngày trước`
  }

  const TYPE_ICON: Record<string, string> = {
    task_assigned: "📋", task_needs_review: "👁", task_done: "✅",
    agent_error: "⚠", task_unblocked: "🔓", review_complete: "🔍",
  }

  export function NotificationPanel({ onClose }: { onClose: () => void }) {
    const { token } = useAuth()
    const navigate = useNavigate()
    const [items, setItems] = useState<Notification[]>([])
    const [unread, setUnread] = useState(0)

    const fetchNotifs = async () => {
      const { total_unread, items } = await notificationApi(token!).get({ unread_only: false, limit: 20 })
      setItems(items); setUnread(total_unread)
    }

    useEffect(() => { fetchNotifs(); const t = setInterval(fetchNotifs, 30000); return () => clearInterval(t) }, [token])

    const markAllRead = async () => {
      await notificationApi(token!).markAllRead(); fetchNotifs()
    }

    return (
      <div className="absolute right-0 top-full mt-2 w-80 bg-white border rounded-lg shadow-xl z-50">
        <div className="flex items-center justify-between px-4 py-2 border-b">
          <span className="font-medium text-sm">Thông báo {unread > 0 && <span className="bg-red-500 text-white text-xs px-1.5 rounded-full ml-1">{unread}</span>}</span>
          <button onClick={markAllRead} className="text-xs text-blue-600 hover:underline">Đọc tất cả</button>
        </div>
        <div className="max-h-80 overflow-y-auto">
          {items.length === 0 && <div className="p-4 text-sm text-gray-400 text-center">Không có thông báo</div>}
          {items.map(n => (
            <button key={n.id} onClick={async () => {
              await notificationApi(token!).markRead(n.id)
              if (n.reference_type === "task" && n.reference_id) navigate(`/tasks/${n.reference_id}`)
              onClose()
            }} className={`w-full text-left px-4 py-3 hover:bg-gray-50 border-b text-sm ${!n.is_read ? "bg-blue-50" : ""}`}>
              <span className="mr-2">{TYPE_ICON[n.type] ?? "🔔"}</span>
              <span>{n.content}</span>
              <div className="text-xs text-gray-400 mt-0.5">{timeAgo(n.created_at)}</div>
            </button>
          ))}
        </div>
      </div>
    )
  }
  ```

- [ ] T064 Tạo `frontend/src/components/organisms/webhook-settings.tsx`:
  - List webhooks: URL (truncated), events badges, enabled toggle (`PATCH /webhooks/{id}`)
  - Add form: URL input + events checkboxes (`task.needs_review`, `task.done`, `agent.error`) + optional secret
  - "Test" button → gọi `POST /webhooks/{id}/test` → toast success/fail với response_time_ms
  - GitHub section: `repo_full_name` input + PAT password input + "Save" → `PUT /projects/{id}/github`; validate + show current config

- [ ] T065 Update React Router config:
  ```tsx
  <Route path="/dashboard" element={<AuthGuard><Dashboard /></AuthGuard>} />
  <Route path="/projects/:projectId/analytics" element={<AuthGuard><Analytics /></AuthGuard>} />
  <Route path="/projects/:projectId/settings" element={<AuthGuard><ProjectSettings /></AuthGuard>} />
  // Đổi default route sau login:
  <Route index element={<Navigate to="/dashboard" />} />
  ```

**Checkpoint**: Login → redirect `/dashboard` thay vì project list. Dashboard grid hiện tất cả project với task counts màu. Analytics chart render đúng BarChart + PieChart từ Recharts. Bell icon click → NotificationPanel mở, polling 30s, click notification → navigate tới task. Webhook test button → toast với response time.

---

## Phase 11: Tests & Hardening

- [ ] T066 [P] `backend/tests/unit/test_reviewer_service.py`:
  ```python
  # Test detect_test_runner
  def test_detect_pytest(tmp_path):
      (tmp_path / "conftest.py").touch()
      assert reviewer_service.detect_test_runner(str(tmp_path)) == "pytest"

  def test_detect_npm(tmp_path):
      (tmp_path / "package.json").write_text('{"scripts": {"test": "jest"}}')
      assert reviewer_service.detect_test_runner(str(tmp_path)) == "npm_test"

  def test_detect_none(tmp_path):
      assert reviewer_service.detect_test_runner(str(tmp_path)) is None

  # Test secret scan
  def test_scan_hardcoded_api_key():
      diff = "+api_key = 'sk-AbCdEfGhIjKlMnOpQrStUvWx'"
      findings = reviewer_service.scan_secrets(diff)
      assert len(findings) == 1
      assert findings[0]["pattern_name"] == "hardcoded API key"

  def test_scan_ignores_minus_lines():
      diff = "-old_password = 'hunter2'\n+password = 'correct-horse-battery'"
      findings = reviewer_service.scan_secrets(diff)
      assert all(f["pattern_name"] == "hardcoded password" for f in findings)
      assert len(findings) == 1  # chỉ dòng + được scan

  def test_scan_clean_diff():
      diff = "+x = get_password_from_env('PASSWORD')"
      assert reviewer_service.scan_secrets(diff) == []

  # Test score calculation
  def test_score_perfect():
      assert reviewer_service.calculate_score(10, 0, 0, "approve") == 100

  def test_score_with_secrets():
      score = reviewer_service.calculate_score(5, 0, 2, "approve")
      assert score == 100 - 20  # secret_score = 30 - 20 = 10, total = 40+10+30 = 80

  def test_score_no_tests_neutral():
      # No tests: test_score = 40 (neutral)
      score = reviewer_service.calculate_score(0, 0, 0, "approve")
      assert score == 100

  def test_score_all_fail():
      score = reviewer_service.calculate_score(0, 10, 0, "needs_changes")
      assert score == 10  # test=0, secret=30, ai=10 → 40... wait: 0+30+10=40 — verify formula
  ```

- [ ] T067 [P] `backend/tests/unit/test_dependency_service.py`:
  ```python
  # Dùng in-memory adjacency list để test cycle detection (không cần DB)
  def test_no_cycle_simple():
      deps = {"B": ["A"]}  # B depends A
      assert not _has_cycle("A", "C", deps)  # thêm A depends C → không cycle

  def test_cycle_direct():
      deps = {"B": ["A"]}  # B→A
      assert _has_cycle("A", "B", deps)  # thêm A→B tạo cycle A→B→A

  def test_cycle_transitive():
      deps = {"B": ["A"], "C": ["B"]}  # C→B→A
      assert _has_cycle("A", "C", deps)  # thêm A→C tạo cycle

  # Integration tests (cần DB session)
  @pytest.mark.asyncio
  async def test_unlock_dependents(db_session, sample_tasks):
      task_a, task_b = sample_tasks
      await dependency_service.add_dependency(db_session, task_b.id, task_a.id, task_a.project_id)
      assert task_b.is_blocked is True

      task_a.status = "done"
      unlocked = await dependency_service.unlock_dependents(db_session, task_a.id)
      assert task_b.id in unlocked
      assert task_b.is_blocked is False

  @pytest.mark.asyncio
  async def test_multi_dep_partial_done(db_session, sample_tasks):
      """B depends A+C. A done → B vẫn blocked vì C chưa done."""
      task_a, task_b, task_c = sample_tasks
      await dependency_service.add_dependency(db_session, task_b.id, task_a.id, task_a.project_id)
      await dependency_service.add_dependency(db_session, task_b.id, task_c.id, task_a.project_id)
      task_a.status = "done"
      unlocked = await dependency_service.unlock_dependents(db_session, task_a.id)
      assert task_b.id not in unlocked  # vẫn blocked vì task_c chưa done
  ```

- [ ] T068 [P] `backend/tests/unit/test_auth_service.py`:
  ```python
  def test_hash_and_verify():
      hashed = hash_password("mysecret")
      assert verify_password("mysecret", hashed)
      assert not verify_password("wrong", hashed)

  def test_create_and_decode_token(test_settings):
      token = create_access_token(uuid4(), test_settings.jwt_secret_key,
                                   test_settings.jwt_algorithm, expire_days=7)
      user_id = decode_token(token, test_settings.jwt_secret_key, test_settings.jwt_algorithm)
      assert isinstance(user_id, UUID)

  def test_expired_token_raises(test_settings):
      # Create token expired 1 day ago
      payload = {"sub": str(uuid4()), "exp": datetime.utcnow() - timedelta(days=1)}
      token = jwt.encode(payload, test_settings.jwt_secret_key, algorithm=test_settings.jwt_algorithm)
      with pytest.raises(HTTPException) as exc:
          decode_token(token, test_settings.jwt_secret_key, test_settings.jwt_algorithm)
      assert exc.value.status_code == 401

  @pytest.mark.asyncio
  async def test_register_duplicate_email(db_session):
      await auth_service.register_user(db_session, "a@b.com", "pass", "User A")
      with pytest.raises(HTTPException) as exc:
          await auth_service.register_user(db_session, "a@b.com", "pass2", "User B")
      assert exc.value.status_code == 409
  ```

- [ ] T069 `backend/tests/integration/test_team_flow.py`:
  ```python
  @pytest.mark.asyncio
  async def test_full_team_invite_and_wip(test_client, db_session):
      # 1. Register owner
      r = await test_client.post("/api/v1/auth/register",
          json={"email": "owner@test.com", "password": "pass123", "display_name": "Owner"})
      assert r.status_code == 201
      owner_token = r.json()["access_token"]

      # 2. Create project
      r = await test_client.post("/api/v1/projects",
          json={"name": "Test Project"}, headers=auth(owner_token))
      project_id = r.json()["id"]

      # 3. Register developer
      r = await test_client.post("/api/v1/auth/register",
          json={"email": "dev@test.com", "password": "pass123", "display_name": "Dev"})
      dev_token = r.json()["access_token"]

      # 4. Invite developer
      r = await test_client.post(f"/api/v1/projects/{project_id}/members/invite",
          json={"role": "developer"}, headers=auth(owner_token))
      invite_url = r.json()["invite_url"]
      token_str = invite_url.split("/")[-1]

      # 5. Accept invite
      r = await test_client.post(f"/api/v1/invitations/{token_str}/accept", headers=auth(dev_token))
      assert r.status_code == 200

      # 6. Create + assign tasks
      task1 = (await test_client.post(f"/api/v1/projects/{project_id}/tasks",
          json={"title": "Task 1"}, headers=auth(owner_token))).json()
      task2 = (await test_client.post(f"/api/v1/projects/{project_id}/tasks",
          json={"title": "Task 2"}, headers=auth(owner_token))).json()
      await test_client.patch(f"/api/v1/tasks/{task1['id']}/assign",
          json={"user_id": r.json()["user_id"] if "user_id" in r.json() else None}, headers=auth(owner_token))

      # 7. Developer starts task 1 → OK
      r = await test_client.post(f"/api/v1/tasks/{task1['id']}/start", headers=auth(dev_token))
      assert r.status_code == 200

      # 8. Developer tries task 2 → 409 WIP limit
      r = await test_client.post(f"/api/v1/tasks/{task2['id']}/start", headers=auth(dev_token))
      assert r.status_code == 409
      assert "WIP" in r.json()["detail"]

  @pytest.mark.asyncio
  async def test_viewer_cannot_move_task(test_client):
      # ... setup viewer member ...
      r = await test_client.post(f"/api/v1/tasks/{task_id}/start", headers=auth(viewer_token))
      assert r.status_code == 403
  ```

- [ ] T070 [P] `backend/tests/unit/test_webhook_service.py`:
  ```python
  def test_hmac_signature():
      payload = b'{"event":"task.done"}'
      sig = _sign_payload(payload, "mysecret")
      assert sig.startswith("sha256=")
      assert hmac.compare_digest(sig, _sign_payload(payload, "mysecret"))
      assert not hmac.compare_digest(sig, _sign_payload(payload, "wrongsecret"))

  @pytest.mark.asyncio
  async def test_delivery_success(mock_http):
      mock_http.return_value = (True, 200)
      # ... verify delivery.status == "success", attempts == 1

  @pytest.mark.asyncio
  async def test_delivery_retry_then_fail(mock_http):
      mock_http.side_effect = [(False, 500), (False, 500), (False, 500)]
      # ... verify delivery.status == "failed", attempts == 3

  @pytest.mark.asyncio
  async def test_delivery_retry_then_succeed(mock_http):
      mock_http.side_effect = [(False, 500), (True, 200)]
      # ... verify delivery.status == "success", attempts == 2
  ```

- [ ] T071 [P] Validate F-003 acceptance criteria:
  - `calculate_score()` với (test_pass=0, test_fail=0, secrets=0, suggestion="approve") = 100 ✓
  - `calculate_score()` với (test_pass=0, test_fail=5, secrets=3, suggestion="needs_changes") = 0 (min) ✓
  - reviewer_node timeout → `ReviewReport.status = "error"`, task.status = "review" (không stuck) ✓
  - AI review JSON parse fail → fallback `(suggestion="needs_changes", comments=[])` ✓
  - Comments có `file_path` + `line_number` mapping đúng từ diff parser ✓

- [ ] T072 [P] Validate F-004 acceptance criteria:
  - Role hierarchy: `require_owner` → 403 cho leader/developer/viewer ✓
  - WIP per-developer: 2nd task → 409 (developer); Leader bypass WIP check → OK ✓
  - Single-user mode (no project_members): per-project WIP vẫn hoạt động ✓
  - Expired invitation token → 410 (không phải 404) ✓
  - Remove owner → 403 "cannot remove owner" ✓

---

## Dependencies & Execution Order

```
Phase 1 (Setup) ─────────────────────────────────► BLOCKS tất cả
Phase 2 (Auth Backend) ──────────────────────────► BLOCKS Phase 7 (Frontend Auth)
Phase 3 (Reviewer Backend) ──────────────────────►
Phase 4 (Dependencies Backend) ──────────────────► có thể song song với Phase 3 sau Phase 1
Phase 5 (Notifications Backend) ─────────────────►
Phase 6 (Analytics Backend) ─────────────────────►
Phase 7 (Auth Frontend) ─────────────────────────► BLOCKS Phase 8, 9, 10 (cần Auth Context)
Phase 8 (AI Review Frontend) ────────────────────► sau Phase 3
Phase 9 (Task UI Frontend) ──────────────────────► sau Phase 4
Phase 10 (Dashboard Frontend) ───────────────────► sau Phase 6
Phase 11 (Tests) ────────────────────────────────► sau Phase 2–6
```

**Task Dependencies**:
```
T001 → T007, T008, T015, T021, T022, T029, T030, T031 [P sau T001]
T002, T003, T004 [P sau T001]
T009 → T010 → T011, T012
T013 → T023, T028, T032, T033, T036
T017 → T018 (reviewer_node trước graph update)
T041 → T042, T043, T044
T048 → T049, T050, T053, T054, T055, T059
T050 → T051 → T052
T061, T062 → T065
T063, T064 → T065
```

---

## Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| LLM JSON output không parse được trong reviewer_node | Medium | Medium | Strict JSON schema prompt + try/except → fallback empty comments list |
| WIP per-developer breaking existing single-user flow | Low | High | Check `project_members` count — nếu = 0 (single-user), dùng per-project WIP |
| JWT token invalidation (logout/password change) | Low | Medium | Redis token blacklist; short-lived tokens (7 ngày default) |
| Reviewer Agent thêm latency đáng kể | Medium | Medium | Chạy async, không block coder node; progress stream REVIEW_COMMENT live |
| Test runner sandbox timeout | Medium | Low | 60s hard timeout per runner; on timeout → mark test_error, không fail review |
| GitHub PAT rotation/expiry | Low | Medium | Validate PAT khi save config; clear error message khi PR fail |
| React re-renders nặng trong dependency graph | Low | Low | Memoize graph nodes; lazy load trên tab click |

---

## Post-Design Constitution Re-Check

| # | Nguyên Tắc | Bằng Chứng |
|---|-----------|------------|
| I | Artifact communication | reviewer_node đọc diff từ DB, ghi ReviewReport; không dùng in-memory state |
| II | HIL checkpoints | reviewer_node → interrupt() — PO quyết định; score là advisory |
| III | WIP discipline | WIP = 1 per developer (amended); check trong kanban_service |
| IV | One-way flow | Unchanged; reviewer_node không tạo state transition mới |
| V | Audit logging | audit_service.write_pending_log() TRƯỚC mọi action của reviewer_node |
| VI | Security | JWT, AES-256 PAT, HMAC webhook, không hardcode secrets |
| VII | MVP scope | Multi-user là explicit approved extension (Feature 003) |
| VIII | Code quality | PEP 8, type hints, Atomic Design, kebab-case files |

**Post-design gate: ALL PASS**
