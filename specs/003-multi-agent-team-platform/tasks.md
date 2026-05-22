# Tasks: Platform Expansion — Multi-Agent Review, Team Management & Integrations

**Input**: Design documents from `/specs/003-multi-agent-team-platform/`
**Feature Branch**: `003-multi-agent-team-platform`
**Generated**: 2026-05-22 (rewritten — smaller tasks)

**Stack**: Python 3.11 + FastAPI + SQLAlchemy + LangGraph (backend) · TypeScript 5.6 + React 18 (frontend)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: User story — US1=AI Review, US2=Auth/Team, US3=Assignment/WIP, US4=Dependencies, US5=Templates, US6=Dashboard, US7=Notifications

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: DB migration, config, dependencies, constitutional amendments — nothing user-visible yet.

- [ ] T001 Write Alembic migration `backend/alembic/versions/005_platform_expansion.py` — tạo 10 bảng mới (`project_members`, `invitations`, `review_reports`, `review_comments`, `task_dependencies`, `task_templates`, `notifications`, `webhook_configs`, `webhook_deliveries`, `github_configs`) + ALTER `tasks` (thêm `assigned_to`, `is_blocked`) + ALTER `users` (thêm `last_login_at`) + analytics indexes trên `agent_runs` và `tasks`
- [ ] T002 [P] Update `backend/app/config.py` — thêm fields vào `Settings`: `jwt_secret_key: str`, `jwt_algorithm: str = "HS256"`, `jwt_expire_days: int = 7`, `github_encryption_key: str | None`; thêm property `fernet_key` dùng SHA-256 + base64urlsafe để derive 32-byte Fernet key
- [ ] T003 [P] Update `backend/.env.example` — thêm `JWT_SECRET_KEY=change-me-in-production-min-32-chars` và `GITHUB_ENCRYPTION_KEY=optional-aes-key-for-pat-encryption`
- [ ] T004 [P] Update `backend/requirements.txt` — thêm `python-jose[cryptography]>=3.3.0`, `passlib[bcrypt]>=1.7.4`, `PyGithub>=2.0.0`, `cryptography>=42.0.0`
- [ ] T005 [P] Update `frontend/package.json` — thêm `"recharts": "^2.12.0"`; chạy `npm install`
- [ ] T006 [P] Update `.specify/memory/constitution.md` — ghi Amendment A (WIP = 1 per Developer trong multi-user mode) và Amendment B (multi-user/team là Post-MVP Phase 1 được approve)

**Checkpoint**: `alembic upgrade head` thành công; 10 bảng mới tồn tại; `tasks.assigned_to` và `tasks.is_blocked` tồn tại; `alembic downgrade -1` chạy sạch.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core models, schemas, auth service và auth middleware — PHẢI hoàn thành trước khi bắt đầu bất kỳ user story nào.

⚠️ **CRITICAL**: Tất cả user story đều phụ thuộc vào phase này.

- [ ] T007 [P] Tạo `backend/app/models/project_member.py` — `ProjectRole(str, Enum)` với 4 values (owner/leader/developer/viewer); `ProjectMember` SQLAlchemy mapped_column model với `id`, `project_id`, `user_id`, `role`, `joined_at`; relationships tới `Project` và `User`; `UniqueConstraint("project_id", "user_id")`
- [ ] T008 [P] Tạo `backend/app/models/invitation.py` — `Invitation` model với `id`, `project_id`, `invitee_email`, `role`, `token`, `created_by`, `expires_at`, `used_at`, `used_by`; properties `is_expired` (compare với `datetime.utcnow()`) và `is_used` (check `used_at is not None`)
- [ ] T009 [P] Tạo `backend/app/models/review_report.py` — `ReviewStatus(str, Enum)` với `pending/running/complete/error`; `ReviewReport` model với `score`, `suggestion`, `test_runner`, `test_pass/fail`, `status`, `error_message`; `ReviewComment` model với `file_path`, `line_number`, `content`, `severity`; relationship `comments` từ `ReviewReport`
- [ ] T010 [P] Tạo `backend/app/models/task_dependency.py` — `TaskDependency` model với composite PK `(task_id, depends_on_task_id)`, cả hai FK tới `tasks.id ON DELETE CASCADE`, `created_at`; `CheckConstraint("task_id != depends_on_task_id")`
- [ ] T011 [P] Tạo `backend/app/models/task_template.py` — `TemplateScope(str, Enum)` với `project/global`; `TaskTemplate` model với `name`, `title_template`, `description_template`, `scope`, `project_id` nullable, `created_by`, `created_at`; `UniqueConstraint("project_id", "name")`
- [ ] T012 [P] Tạo `backend/app/models/notification.py` — `NotificationType(str, Enum)` với 7 types (task_assigned/task_needs_review/task_done/task_unblocked/agent_error/invite_accepted/review_complete); `Notification` model với `user_id`, `type`, `content`, `reference_type`, `reference_id`, `is_read`, `created_at`
- [ ] T013 [P] Tạo `backend/app/models/webhook.py` — `WebhookConfig` model với `project_id`, `url`, `secret`, `events: list[str]` (postgresql ARRAY), `enabled`, `created_by`; `WebhookDelivery` model với `event_type`, `payload: JSONB`, `status`, `http_status`, `attempts`, `last_attempt_at`; relationship `deliveries` từ `WebhookConfig`
- [ ] T014 [P] Tạo `backend/app/models/github_config.py` — `GitHubConfig` model với `project_id` (unique FK), `repo_full_name`, `pat_encrypted`, `default_base_branch`, `enabled`, `created_by`
- [ ] T015 Update `backend/app/models/task.py` — thêm `assigned_to: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))` và `is_blocked: Mapped[bool] = mapped_column(default=False)`; thêm index `idx_tasks_assigned_to`; thêm relationship `assignee: Mapped["User"]`
- [ ] T016 Tạo `backend/app/services/auth_service.py` — implement 4 pure functions: `hash_password(plain: str) -> str` (bcrypt via passlib), `verify_password(plain: str, hashed: str) -> bool`, `create_access_token(user_id, secret, algorithm, expire_days) -> str` (jose JWT), `decode_token(token, secret, algorithm) -> UUID` (raise HTTPException 401 on JWTError/ValueError)
- [ ] T017 Thêm async functions vào `backend/app/services/auth_service.py` — `register_user(session, email, password, display_name) -> User`: check duplicate email → 409, hash password, add User; `login_user(session, email, password, settings) -> tuple[User, str]`: fetch user by email, verify password → 401 on fail, update `last_login_at`, create and return token
- [ ] T018 Tạo `backend/app/dependencies.py` — `get_current_user(token, session, settings) -> User`: decode token, fetch User by id, raise 401 nếu không tìm thấy; `get_optional_user(token, session, settings) -> User | None`: trả None nếu không có token hoặc decode fail
- [ ] T019 Thêm vào `backend/app/dependencies.py` — `require_role(*allowed_roles)` factory function trả `Depends(check)` inner async function: fetch `ProjectMember` by `project_id + user_id`, raise 403 nếu không có hoặc role không trong allowed_roles; shorthand aliases `require_owner`, `require_leader_or_above`, `require_developer_or_above`, `require_any_member`
- [ ] T020 [P] Tạo `backend/app/schemas/auth.py` — `RegisterRequest(email, password, display_name)`, `LoginRequest(email, password)`, `TokenResponse(access_token, token_type, user)`, `LoginResponse(access_token, token_type, expires_in)`, `UserResponse(id, email, display_name, created_at)` với `ConfigDict(from_attributes=True)`
- [ ] T021 [P] Update `frontend/src/types/index.ts` — thêm interfaces: `User`, `ProjectMember`, `ProjectRole` type, `Invitation`, `ReviewReport`, `ReviewComment`, `TaskDependency`, `TaskTemplate`, `Notification`, `WebhookConfig`; update `Task` interface thêm `assigned_to: string | null` và `is_blocked: boolean`
- [ ] T022 [P] Tạo `frontend/src/services/api-client.ts` — `createApiClient(token: string | null)` trả axios instance với `baseURL="/api/v1"` và Bearer header injection; export `BASE_URL` constant

**Checkpoint**: Models import không lỗi; `auth_service.hash_password("x")` trả bcrypt hash; `require_role` factory không lỗi khi khởi tạo; TypeScript types compile.

---

## Phase 3: User Story 1 — AI Tự Động Review Code (Priority: P1) 🎯 MVP

**Goal**: Reviewer Agent tự động chạy sau Coder Agent; PO thấy panel AI Review với score, suggestion và inline comments trong Diff Viewer.

**Independent Test**: Kéo task vào In Progress → Coder Agent xong → `GET /tasks/{id}/review` trả `status:"complete"`, `score: 0-100`, `comments` → panel "AI Review" xuất hiện bên cạnh diff → PO Approve bình thường.

### Backend: Reviewer Service (parallel, different functions)

- [ ] T023 [P] [US1] Tạo `backend/app/services/reviewer_service.py` — hàm `detect_test_runner(sandbox_path: str) -> str | None`: kiểm tra `conftest.py`/`pytest.ini`/`pyproject.toml` → trả `"pytest"`; kiểm tra `package.json` có `scripts.test` → trả `"npm_test"`; else trả `None`
- [ ] T024 [P] [US1] Thêm `run_tests(runner: str, sandbox_path: str, timeout: int = 60) -> tuple[int, int, str | None]` vào `backend/app/services/reviewer_service.py` — `subprocess.run()` với `capture_output=True`; parse pytest output với regex `r"(\d+) passed"` và `r"(\d+) failed"`; parse jest `"Tests: N passed"` tương tự; `subprocess.TimeoutExpired` → trả `(0, 0, "Test runner timed out...")`
- [ ] T025 [P] [US1] Thêm `scan_secrets(diff_content: str) -> list[dict]` vào `backend/app/services/reviewer_service.py` — define `SECRET_PATTERNS` list với 5 regex patterns (password, api_key, secret/token, AWS AKIA, Bearer token); chỉ scan dòng bắt đầu bằng `+` (không `+++`); track `current_file` từ `+++ b/` và `line_num` từ `@@ +N @@`; trả list `{"file", "line", "pattern_name"}`
- [ ] T026 [P] [US1] Thêm `ai_review_diff(diff: str, constitution: str, llm) -> tuple[str, list[dict]]` vào `backend/app/services/reviewer_service.py` — define `REVIEWER_PROMPT` template với `{constitution[:2000]}` và `{diff[:6000]}`; `await llm.ainvoke(prompt)`; parse JSON response `{"suggestion", "comments"}`; fallback `("needs_changes", [])` nếu `JSONDecodeError` hoặc key missing
- [ ] T027 [P] [US1] Thêm `calculate_score(test_pass: int, test_fail: int, secret_count: int, suggestion: str) -> int` vào `backend/app/services/reviewer_service.py` — test score: 40pts neutral nếu total=0 else `pass/(pass+fail)*40`; secret score: `max(0, 30 - secret_count*10)`; AI score: approve=30, needs_changes=10; `return min(100, test_score + secret_score + ai_score)`

### Backend: Reviewer Agent Node

- [ ] T028 [US1] Tạo `backend/app/agent/nodes/reviewer_node.py` — imports (AgentState, reviewer_service, audit_service, ReviewReport/ReviewComment/ReviewStatus); `async def run(state: AgentState) -> AgentState`; fetch `task` và `diff` từ DB; fetch `constitution`; tạo `ReviewReport(task_id, agent_run_id, status=ReviewStatus.running)`; `session.add(report); await session.flush()`; gọi `audit_service.write_pending_log(action="reviewer_node_start")`
- [ ] T029 [US1] Thêm main execution block vào `backend/app/agent/nodes/reviewer_node.py` trong `async with asyncio.timeout(300)`: detect runner → run_tests → scan_secrets → ai_review_diff → calculate_score; update `report.score/suggestion/test_runner/test_pass/test_fail/status=complete/completed_at`; persist `ReviewComment` records cho cả secret findings và AI comments; `await session.flush()`; `await audit_service.finalise_log(result="success")`
- [ ] T030 [US1] Thêm error handling và WebSocket events vào `backend/app/agent/nodes/reviewer_node.py` — sau execution block: publish `REVIEW_SCORE` và `REVIEW_COMMENT` WS events; `except (asyncio.TimeoutError, Exception) as e`: set `report.status=error, report.error_message=str(e)[:500]`; publish `REVIEW_ERROR` event; KHÔNG raise exception để task tiếp tục sang interrupt(); `state["review_report_id"] = str(report.id); return state`
- [ ] T031 [US1] Update `backend/app/agent/graph.py` — `from app.agent.nodes import reviewer_node`; `graph.add_node("reviewer_node", reviewer_node.run)`; thay đổi edges: `graph.add_edge("coder_node", "reviewer_node")` và `graph.add_edge("cli_coder_node", "reviewer_node")`; `graph.add_edge("reviewer_node", "interrupt_node")`

### Backend: Review API & Schemas

- [ ] T032 [P] [US1] Tạo `backend/app/schemas/review.py` — `ReviewCommentResponse(id, file_path, line_number, content, severity)` và `ReviewReportResponse(id, task_id, status, score, suggestion, test_runner, test_pass, test_fail, comments, error_message, created_at, completed_at)` với `ConfigDict(from_attributes=True)`
- [ ] T033 [P] [US1] Tạo `backend/app/api/v1/review.py` — `GET /tasks/{task_id}/review` endpoint: query `ReviewReport` mới nhất với `selectinload(ReviewReport.comments)` và `.order_by(created_at.desc())`; 404 nếu không có; `current_user` required; đăng ký trong `backend/app/api/v1/router.py`

### Frontend: AI Review Panel

- [ ] T034 [P] [US1] Tạo `frontend/src/services/review-api.ts` — `reviewApi(token)` object với `getReport(taskId: string) -> Promise<ReviewReport>`; `useReviewReport(taskId: string | null)` hook: fetch ngay khi mount, `setInterval` 2s polling khi `status === "running"|"pending"`, `clearInterval` khi `"complete"|"error"`, handle 404 silently (report chưa tạo)
- [ ] T035 [P] [US1] Tạo `frontend/src/components/atoms/score-gauge.tsx` — `ScoreGauge({ score: number })`: hiển thị số điểm lớn `text-4xl font-bold` với màu `text-green-600` (≥80), `text-yellow-500` (50–79), `text-red-600` (<50); thêm `/100` suffix nhỏ `text-gray-400`
- [ ] T036 [US1] Tạo `frontend/src/components/organisms/ai-review-panel.tsx` — nhận `taskId: string` và `onCommentClick?: (file: string, line: number | null) => void`; dùng `useReviewReport`; render states: pending (text "Đang chờ agent..."), running (Spinner + text), error (đỏ + error_message), complete (ScoreGauge + suggestion chip màu + test result line + comments grouped by file với icon severity); max-width 380px, border-l
- [ ] T037 [US1] Update `frontend/src/components/organisms/review-panel.tsx` — thay single-pane thành flex layout: `<div className="flex h-full">` với `DiffViewer` (flex-1) bên trái và `AiReviewPanel` (fixed width) bên phải; wire `onCommentClick` để `setHighlightedLine({ file, line })` trong DiffViewer
- [ ] T038 [P] [US1] Update WebSocket handler trong `frontend/src/services/ws-handler.ts` (hoặc `useWebSocket` hook) — thêm cases: `"REVIEW_SCORE"` → `queryClient.invalidateQueries(["review", event.task_id])`; `"REVIEW_COMMENT"` → optimistic append comment vào report state; `"REVIEW_ERROR"` → set `status: "error", error_message: event.error`

**Checkpoint**: Coder Agent xong → reviewer_node chạy → `GET /tasks/{id}/review` trả `status:"complete"` với score 0-100 và comments. Panel AI Review xuất hiện bên phải diff với ScoreGauge + suggestion. Reviewer timeout → task sang Review với `status:"error"`, panel hiện error message. PO Approve/Reject không bị block.

---

## Phase 4: User Story 2 — Đăng Nhập & Phân Quyền Team (Priority: P1)

**Goal**: JWT auth; 4-role system; Owner mời thành viên qua invite link 7 ngày; existing pages được bảo vệ.

**Independent Test**: Register → Login → `GET /auth/me` → nhận user. Owner tạo invite link → Developer accept → thấy trong `GET /projects/{id}/members`. Viewer gọi `POST /tasks/{id}/start` → 403.

### Backend: Auth Endpoints

- [ ] T039 [US2] Tạo `backend/app/api/v1/auth.py` — 3 endpoints: `POST /auth/register` (201, gọi `auth_service.register_user()`, tạo token, return `TokenResponse`; 409 nếu email trùng); `POST /auth/login` (gọi `auth_service.login_user()`; 401 on wrong creds); `GET /auth/me` (`current_user = Depends(get_current_user)`, return `UserResponse`); đăng ký router trong `backend/app/api/v1/router.py`

### Backend: Members & Invitations

- [ ] T040 [P] [US2] Tạo `backend/app/schemas/member.py` — `InviteRequest(role, invitee_email: str | None)`, `InvitationResponse(invitation_id, invite_url, expires_at)`, `AcceptResponse(project_id, role)`, `MemberResponse(user_id, display_name, email, role, joined_at)`, `RoleChangeRequest(role)`
- [ ] T041 [US2] Tạo `backend/app/api/v1/members.py` phần 1 — `GET /projects/{id}/members` (require_any_member, trả list `MemberResponse`); `POST /projects/{id}/members/invite` (require_owner, tạo `Invitation` với `secrets.token_hex(32)`, `expires_at = utcnow + 7 days`, build `invite_url` từ `request.base_url`, return `InvitationResponse`); `GET /invitations/{token}` (public, trả invitation info + is_expired)
- [ ] T042 [US2] Thêm vào `backend/app/api/v1/members.py` phần 2 — `POST /invitations/{token}/accept` (auth required: check expired → 410, check used → 410, check already_member → 409, tạo `ProjectMember`, mark invitation `used_at/used_by`); `PATCH /projects/{id}/members/{user_id}` (require_leader_or_above, update role); `DELETE /projects/{id}/members/{user_id}` (require_owner, không cho xóa owner); đăng ký trong `router.py`

### Backend: Auth Guard Existing Routes

- [ ] T043 [US2] Update `backend/app/api/v1/projects.py` — thêm `current_user: User = Depends(get_current_user)` vào tất cả endpoints; `GET /projects` chỉ trả projects của current_user qua JOIN `ProjectMember`; `POST /projects` auto-add creator vào `project_members` với role `owner`; `PATCH/DELETE /projects/{id}` require_owner
- [ ] T044 [US2] Update `backend/app/api/v1/tasks.py` — thêm `current_user` dependency; GET endpoints dùng `require_any_member`; `POST /tasks` và `PATCH /tasks/{id}` dùng `require_developer_or_above`; approve/reject dùng `require_leader_or_above`
- [ ] T045 [P] [US2] Update `backend/app/main.py` — update CORS `allow_headers` để accept `Authorization`; thêm startup log xác nhận JWT key loaded (không print key)

### Frontend: Auth Context & Pages

- [ ] T046 [US2] Tạo `frontend/src/contexts/auth-context.tsx` — `AuthState { user, token, isLoading }`; `AuthProvider`: `useState` cho state; `useEffect` khởi động: đọc `localStorage.getItem("neokanban_token")` → `authApi.getMe(token)` → set state hoặc clear token nếu 401; `login()` → gọi `authApi.login()` + `getMe()` + `localStorage.setItem()`; `logout()` → clear localStorage + reset state; `register()` → `authApi.register()` + set state; export `useAuth()` hook
- [ ] T047 [P] [US2] Tạo `frontend/src/services/auth-api.ts` — `authApi` object với 3 methods gọi axios trực tiếp (không qua `createApiClient` để tránh circular dep): `register(email, password, display_name)`, `login(email, password)`, `getMe(token)` với explicit Authorization header
- [ ] T048 [US2] Update `frontend/src/pages/login.tsx` — import `useAuth`; `const { login } = useAuth()`; `onSubmit`: gọi `login(email, password)` → `navigate("/dashboard")` on success; catch lỗi → `setError("Email hoặc mật khẩu không đúng")`
- [ ] T049 [US2] Update `frontend/src/pages/register.tsx` — import `useAuth`; `onSubmit`: gọi `register(email, password, displayName)` → `navigate("/dashboard")`; catch 409 → "Email đã được sử dụng"
- [ ] T050 [P] [US2] Tạo `frontend/src/components/molecules/auth-guard.tsx` — `AuthGuard({ children })`: dùng `useAuth()`; nếu `isLoading` → render full-screen spinner; nếu `!user` → `<Navigate to="/login" state={{ from: location }} replace />`; else render children
- [ ] T051 [US2] Update `frontend/src/App.tsx` (hoặc `main.tsx`) — wrap toàn bộ app trong `<AuthProvider>`; wrap routes `/projects/:id`, `/dashboard`, `/projects/:id/analytics` trong `<AuthGuard>`; đổi default route `/` redirect về `/dashboard`; thêm route `/invitations/:token` → `<AcceptInvite>` (component tạo ở Phase 10)

### Frontend: Member Management UI

- [ ] T052 [P] [US2] Tạo `frontend/src/services/member-api.ts` — `memberApi(token)` với 5 methods: `getMembers(projectId)`, `invite(projectId, role, inviteeEmail?)` trả `InvitationResponse`, `acceptInvite(token)`, `changeRole(projectId, userId, role)`, `removeMember(projectId, userId)`
- [ ] T053 [P] [US2] Tạo `frontend/src/components/atoms/role-badge.tsx` — colored chip: owner=purple-100/700, leader=blue-100/700, developer=green-100/700, viewer=gray-100/500; prop `role: ProjectRole`; text nhỏ `text-xs font-medium px-2 py-0.5 rounded-full`
- [ ] T054 [US2] Tạo `frontend/src/components/organisms/project-members.tsx` — fetch members khi mount; table với `Avatar` + display_name + email + `RoleBadge` + actions; "Invite member" section: email input (optional) + role select + "Tạo link" button → hiển thị URL + copy-to-clipboard + toast; role change `<select>` chỉ visible cho owner, disabled cho self; remove button disabled nếu target=owner hoặc self
- [ ] T055 [US2] Update `frontend/src/components/organisms/project-header.tsx` — fetch members list; thêm member avatar row (max 5 `Avatar` với `-space-x-2` + "+N" badge nếu > 5); thêm notification bell `<button>` (icon `BellIcon`) với `NotificationBadge` placeholder count=0 (sẽ wire ở Phase 9)

**Checkpoint**: Register → Login → redirect `/dashboard`. JWT persist qua refresh. Owner invite → Developer accept → member list cập nhật. Viewer token → `POST /tasks/start` → 403. Role badge màu đúng.

---

## Phase 5: User Story 3 — Assign Task & WIP per Developer (Priority: P1)

**Goal**: Leader assign task; avatar hiện trên card; WIP per-developer enforcement; assignment conflict check.

**Independent Test**: Leader assign Task A → Developer X → Developer Y kéo → blocked. Developer X kéo Task A → OK. Developer X kéo Task B → 409 WIP. Leader kéo Task B → OK (bypass).

### Backend: WIP & Assignment Logic

- [ ] T056 [US3] Update `backend/app/services/kanban_service.py` — thêm `get_wip_mode(session, project_id) -> str`: query count `ProjectMember` → trả `"user"` nếu > 0 else `"project"`; trong `move_task_to_in_progress()`: (1) thêm `if task.is_blocked: raise TaskBlockedError()`; (2) thêm WIP check dựa trên `get_wip_mode()`: mode `"user"` → count `Task` where `assigned_to=current_user.id AND status="in_progress"` → raise `WIPLimitExceeded` nếu ≥ 1 và user không phải owner/leader; mode `"project"` → count tasks `in_progress` per project (backward compat)
- [ ] T057 [US3] Thêm assignment conflict check vào `backend/app/services/kanban_service.py` — trong `move_task_to_in_progress()` sau WIP check: `if task.assigned_to and task.assigned_to != current_user.id` → fetch member → nếu không phải owner/leader → raise `AssignmentConflict(task_id, assigned_to_id)`; nếu `task.assigned_to is None` → auto-assign `task.assigned_to = current_user.id`
- [ ] T058 [P] [US3] Thêm `PATCH /tasks/{task_id}/assign` vào `backend/app/api/v1/tasks.py` — body `AssignRequest(user_id: UUID | None)`; validate user_id là member của project (nếu not None); update `task.assigned_to`; gọi `notification_service.notify_task_assigned()` trong try/except ImportError (service chưa có); return `TaskResponse`
- [ ] T059 [P] [US3] Update `backend/app/schemas/task.py` — thêm `assigned_to: UUID | None` và `is_blocked: bool = False` vào `TaskResponse`

### Frontend: Assignee Avatar & Assign UI

- [ ] T060 [P] [US3] Tạo `frontend/src/components/atoms/avatar.tsx` — `Avatar({ name, size?, className? })`: tính initials (2 ký tự đầu của các từ, uppercase); tính `hue = name.charCodeAt(0) * 137 % 360` deterministic; render `div` tròn với `hsl(hue, 60%, 50%)` background; `title={name}` tooltip; sizes: sm=w-6/h-6/text-xs, md=w-8/h-8/text-sm, lg=w-10/h-10/text-base
- [ ] T061 [P] [US3] Tạo `frontend/src/components/molecules/assign-member.tsx` — `AssignMember({ members, currentAssignee, onAssign })`: nút trigger hiển thị `Avatar` + tên nếu assigned hoặc "Assign..."; popover dropdown list members (Avatar + tên) + "Unassign" option; `onAssign(userId | null)` callback; đóng sau khi chọn; click-outside to close
- [ ] T062 [US3] Update `frontend/src/components/organisms/task-card.tsx` — thêm `Avatar` của assignee ở footer nếu `task.assigned_to` tồn tại; thêm `AssignMember` popover trigger cho Leader/Owner; prop `members: ProjectMember[]`; disable drag nếu user không phải assignee và không có quyền leader/owner (check qua `useAuth()`)

**Checkpoint**: Leader assign task → avatar xuất hiện trên card. Developer kéo task không phải của mình → toast + 403. WIP limit: kéo task 2 → 409. Leader kéo task thứ 2 → OK. Auto-assign khi kéo task chưa assign.

---

## Phase 6: User Story 4 — Task Dependencies (Priority: P2)

**Goal**: Task có `depends_on`; bị lock khi dependency chưa Done; auto-unlock khi Done; cycle detection; DAG visualization.

**Independent Test**: B depends A → B.`is_blocked=true`, drag blocked → Approve A → B.`is_blocked=false`, drag OK. A→B + B→A → 409.

### Backend: Dependency Service

- [ ] T063 [US4] Tạo `backend/app/services/dependency_service.py` — `_load_all_deps(session, project_id) -> dict[str, list[str]]`: query `TaskDependency JOIN Task WHERE project_id` → build adjacency list `{task_id: [dep_id, ...]}`; `_has_cycle(task_id: str, new_dep_id: str, all_deps) -> bool`: DFS từ `new_dep_id` qua existing deps, trả `True` nếu đến được `task_id`
- [ ] T064 [US4] Thêm vào `backend/app/services/dependency_service.py` — `add_dependency(session, task_id, depends_on_id, project_id)`: check same-project, check `_has_cycle()` → 409 `CircularDependencyError`, tạo `TaskDependency`, update `task.is_blocked=True` nếu dep task chưa done; `remove_dependency(session, task_id, dep_id)`: xóa record, recompute `is_blocked`; `is_task_blocked(session, task_id) -> bool`: query tất cả dep statuses → `any(s != "done")`
- [ ] T065 [US4] Thêm vào `backend/app/services/dependency_service.py` — `unlock_dependents(session, completed_task_id) -> list[UUID]`: query `TaskDependency.task_id WHERE depends_on_task_id=completed_task_id`, với mỗi dependent: gọi `is_task_blocked()`, nếu trước blocked + sau not blocked → set `task.is_blocked=False` + append to unlocked list; trả unlocked IDs; `get_dependency_graph(session, project_id) -> dict`: trả `{"nodes": [{id, title, status}], "edges": [{from, to}]}`

### Backend: Dependency API & Kanban Integration

- [ ] T066 [P] [US4] Tạo `backend/app/schemas/dependency.py` — `DependencyCreate(depends_on_task_id: UUID)`, `DependencyResponse(task_id, depends_on_task_id, created_at)`, `DependencyGraphResponse(nodes: list[dict], edges: list[dict])`
- [ ] T067 [P] [US4] Tạo `backend/app/api/v1/dependencies.py` — `GET /projects/{pid}/tasks/{tid}/dependencies` (require_any_member, trả {blocks: [], depends_on: []}); `POST /projects/{pid}/tasks/{tid}/dependencies` (require_developer_or_above, gọi `add_dependency()`); `DELETE /projects/{pid}/tasks/{tid}/dependencies/{dep_id}` (require_developer_or_above); `GET /projects/{pid}/dependency-graph` (require_any_member); đăng ký trong `router.py`
- [ ] T068 [US4] Update `backend/app/services/kanban_service.py` — trong `approve_task()` sau `task.status = "done"`: gọi `unlocked_ids = await dependency_service.unlock_dependents(session, task_id)`; với mỗi `uid` trong `unlocked_ids`: fetch task, nếu có `assigned_to` → gọi `notification_service.create_notification(type="task_unblocked", ...)` trong try/except

### Frontend: Blocked Badge & DAG

- [ ] T069 [P] [US4] Tạo `frontend/src/services/dependency-api.ts` — `dependencyApi(token)` với: `getDeps(projectId, taskId)`, `addDep(projectId, taskId, dependsOnId)`, `removeDep(projectId, taskId, depId)`, `getGraph(projectId)` trả `DependencyGraphResponse`
- [ ] T070 [P] [US4] Tạo `frontend/src/components/molecules/dependency-badge.tsx` — `DependencyBadge({ blockedByTitles: string[] })`: badge đỏ `bg-red-100 text-red-700` "🔒 Blocked (N)"; tooltip `group-hover:block` hiển thị tối đa 3 tên task + "..." nếu nhiều hơn; prop empty → không render
- [ ] T071 [US4] Update `frontend/src/components/organisms/task-card.tsx` — render `DependencyBadge` nếu `task.is_blocked` (truyền `blockedByTitles` fetch từ deps API hoặc placeholder); thêm `opacity-60 cursor-not-allowed` class và `draggable={!task.is_blocked}`
- [ ] T072 [US4] Update `frontend/src/components/organisms/kanban-board.tsx` — trong `onDragStart` handler: check `task.is_blocked` → `e.preventDefault()` + toast "Task đang bị blocked"; trong `onDrop`: revalidate source task không blocked trước khi process
- [ ] T073 [US4] Tạo `frontend/src/components/organisms/dependency-graph.tsx` — SVG DAG 900×500; column layout theo status (todo/in_progress/review/done ở x=100/300/500/700); `rect` nodes 120×40 với màu theo status (gray/blue/yellow/green); `line` edges với `<marker id="arrow">` arrowhead; node label truncated 15 chars; `defs` arrowhead định nghĩa
- [ ] T074 [US4] Update `frontend/src/pages/project-workspace.tsx` hoặc task detail modal — thêm "Dependencies" tab: `DependencyGraph` component; form thêm dependency (autocomplete task list trong project); button xóa từng dependency; fetch graph data khi tab mở

**Checkpoint**: B depends A → badge đỏ + drag blocked. Approve A → B unlocked, badge mất, drag OK. Cycle → 409. DAG render nodes + arrows. Dependencies tab trong project workspace.

---

## Phase 7: User Story 5 — Task Templates (Priority: P2)

**Goal**: Lưu template từ task; dropdown chọn template khi tạo task; global và project scope.

**Independent Test**: Tạo template "Unit Test" → tạo task mới → chọn template → title + description điền sẵn → vẫn chỉnh được → lưu thành công.

### Backend: Template Service & API

- [ ] T075 [US5] Tạo `backend/app/services/template_service.py` — `list_templates(session, project_id, scope: str | None) -> list[TaskTemplate]`: filter theo `scope="global"` hoặc `scope="project"` hoặc cả hai; `create_template(session, data: TemplateCreate, created_by: UUID) -> TaskTemplate`: check name conflict trong project scope → 409; `delete_template(session, template_id, current_user: User) -> None`: check ownership hoặc role leader/owner → 403 nếu không đủ quyền
- [ ] T076 [P] [US5] Tạo `backend/app/schemas/template.py` — `TemplateCreate(name, title_template, description_template, scope: Literal["project","global"], project_id: UUID | None)`, `TemplateResponse(id, name, title_template, description_template, scope, project_id, created_by, created_at)` với `from_attributes=True`
- [ ] T077 [P] [US5] Tạo `backend/app/api/v1/templates.py` — `GET /templates?scope=&project_id=` (auth required); `POST /templates` (require_developer_or_above nếu project-scoped, auth-only nếu global); `DELETE /templates/{id}` (gọi `template_service.delete_template()`); đăng ký trong `router.py`

### Frontend: Template Selector

- [ ] T078 [P] [US5] Tạo `frontend/src/services/template-api.ts` — `templateApi(token)` với: `list(scope?: string, projectId?: string)`, `create(data: TemplateCreate)`, `delete(id: string)`
- [ ] T079 [US5] Tạo `frontend/src/components/molecules/template-selector.tsx` — `TemplateSelector({ projectId, onSelect(title, desc) })`: fetch global + project templates khi mount với `Promise.all()`; `<select>` với grouped optgroups (Global / Project này); `onChange` → tìm template by id → `onSelect(title_template, description_template)`; không render nếu templates rỗng
- [ ] T080 [US5] Update task creation form (trong modal hoặc `frontend/src/pages/project-workspace.tsx`) — thêm `<TemplateSelector>` phía trên title input; khi chọn → `setTitle(tmpl.title_template)` + `setDescription(tmpl.description_template)`
- [ ] T081 [US5] Thêm "Lưu làm template" button trong task detail view — khi click: hiện modal nhỏ nhập tên template + chọn scope; gọi `templateApi(token).create({ name, title_template: task.title, description_template: task.description, scope, project_id })`; toast success

**Checkpoint**: Tạo template scope=project → chỉ thấy trong project đó. scope=global → thấy mọi project. Chọn template → fields điền sẵn nhưng vẫn chỉnh được.

---

## Phase 8: User Story 6 — Team Dashboard & Agent Analytics (Priority: P2)

**Goal**: Dashboard đa-project với task counts; Analytics với Recharts charts; filter theo thời gian.

**Independent Test**: Login → `/dashboard` thấy tất cả project với đúng task counts. `/projects/{id}/analytics?range=7d` trả BarChart backend performance + member table.

### Backend: Analytics Service & API

- [ ] T082 [US6] Tạo `backend/app/services/analytics_service.py` — `get_dashboard_data(session, user_id) -> dict`: query projects qua `ProjectMember JOIN Project WHERE user_id`; với mỗi project: task counts per status (GROUP BY), stale tasks (status=review AND updated_at < now-24h), member_count; trả `{"projects": [...]}`
- [ ] T083 [US6] Thêm `get_project_analytics(session, project_id, from_dt, to_dt) -> dict` vào `backend/app/services/analytics_service.py` — 4 queries: (1) by_backend SQL: `avg_seconds`, `first_approve_rate`, `error_count` từ `agent_runs`; (2) by_member SQL: `tasks_done`, `tasks_in_progress`, `avg_retry` từ `tasks JOIN users`; (3) `reviewer_avg_score`: `AVG(ReviewReport.score)` filter complete; (4) error_breakdown từ `audit_logs GROUP BY error_code`; trả dict tổng hợp
- [ ] T084 [P] [US6] Tạo `backend/app/schemas/analytics.py` — `BackendMetric`, `MemberMetric`, `StaleTask`, `ProjectDashboard`, `DashboardResponse(projects: list[ProjectDashboard])`, `AnalyticsResponse(period, by_backend, by_member, reviewer_avg_score, error_breakdown)`
- [ ] T085 [P] [US6] Tạo `backend/app/api/v1/analytics.py` — `GET /dashboard` (current_user required, gọi `get_dashboard_data()`); `GET /projects/{id}/analytics?range=7d|30d|custom&from_date=&to_date=` (require_leader_or_above, parse range params, gọi `get_project_analytics()`); đăng ký trong `router.py`

### Frontend: Dashboard & Analytics Pages

- [ ] T086 [P] [US6] Tạo `frontend/src/services/analytics-api.ts` — `analyticsApi(token)` với: `getDashboard() -> Promise<DashboardResponse>`, `getProjectAnalytics(projectId, range, fromDate?, toDate?) -> Promise<AnalyticsResponse>`
- [ ] T087 [US6] Tạo `frontend/src/pages/dashboard.tsx` — fetch `getDashboard()` on mount; grid layout `grid-cols-1 md:grid-cols-2 lg:grid-cols-3`; mỗi project card: tên + `CodingBackendBadge` + task count pills (4 màu) + stale warning `>0` với đỏ + member count + link tới workspace; `<AuthGuard>` wrapper
- [ ] T088 [US6] Tạo `frontend/src/pages/analytics.tsx` — range picker (7d/30d/custom); fetch khi range thay đổi; Recharts `BarChart` avg_seconds per backend (500×250); `PieChart` first-approve rate per backend; member table (Avatar + tên + done + in_progress + avg_retry); error breakdown colored badges; `<AuthGuard>` wrapper
- [ ] T089 [US6] Update React Router — thêm `<Route path="/dashboard" element={<AuthGuard><Dashboard /></AuthGuard>} />`; `<Route path="/projects/:projectId/analytics" element={<AuthGuard><Analytics /></AuthGuard>} />`; `<Route path="/invitations/:token" element={<AcceptInvite />} />`; đổi index route redirect về `/dashboard`

**Checkpoint**: Login → redirect `/dashboard` thay vì project list. Project card đúng task counts. Analytics BarChart + PieChart render. Viewer role gọi analytics → 403. Range=custom với date params → filter đúng.

---

## Phase 9: User Story 7 — Notifications & Webhooks (Priority: P2)

**Goal**: In-app notifications với bell icon; webhook delivery + retry; GitHub PR integration.

**Independent Test**: Assign task → `GET /notifications` trả 1 unread. Webhook → task Done → HTTP POST đi ra. `POST /webhooks/{id}/test` → `{"delivered": true}`.

### Backend: Notification Service

- [ ] T090 [US7] Tạo `backend/app/services/notification_service.py` — `create_notification(session, user_id, type, content, reference_type?, reference_id?) -> Notification`: tạo và add `Notification` record; `notify_task_assigned(session, task, assigned_to_user_id)`: gọi `create_notification` với type=task_assigned; `notify_task_needs_review(session, task)`: query tất cả Leader+Owner của project → gọi `create_notification` cho mỗi người với type=task_needs_review
- [ ] T091 [US7] Thêm vào `backend/app/services/notification_service.py` — `notify_agent_error(session, task)`: notify Leader+Owner với type=agent_error; `notify_task_unblocked(session, task, user_id)`: notify assignee; `get_notifications(session, user_id, unread_only, limit, offset) -> tuple[int, list]`: query với optional WHERE is_read=false, return (total_unread, items); `mark_read(session, notif_id, user_id)`: update is_read=True, check ownership; `mark_all_read(session, user_id) -> int`: UPDATE WHERE user_id AND is_read=false, return rowcount
- [ ] T092 [P] [US7] Tạo `backend/app/schemas/notification.py` — `NotificationResponse(id, type, content, reference_type, reference_id, is_read, created_at)`, `NotificationListResponse(total_unread: int, items: list[NotificationResponse])`
- [ ] T093 [P] [US7] Tạo `backend/app/api/v1/notifications.py` — `GET /notifications?unread_only=false&limit=20&offset=0` (current_user required, trả `NotificationListResponse`); `PATCH /notifications/{id}/read` (current_user, gọi mark_read); `POST /notifications/read-all` (current_user, gọi mark_all_read, trả `{"marked": N}`); đăng ký trong `router.py`

### Backend: Webhook Service

- [ ] T094 [US7] Tạo `backend/app/services/webhook_service.py` — `_sign_payload(payload_bytes: bytes, secret: str) -> str`: `hmac.new(secret.encode(), payload_bytes, sha256).hexdigest()` → `f"sha256={sig}"`; `_deliver_once(delivery_id, session) -> tuple[bool, int | None]`: fetch delivery + config với selectinload; build JSON bytes + headers (Content-Type, X-NeoKanban-Event, X-NeoKanban-Signature nếu có secret); `httpx.AsyncClient(timeout=10)` POST; trả `(status < 400, status_code)`; except `RequestError` → trả `(False, None)`
- [ ] T095 [US7] Thêm `enqueue_delivery(session, project_id, event_type, payload)` vào `backend/app/services/webhook_service.py` — query `WebhookConfig` WHERE `project_id AND enabled AND events @> [event_type]`; với mỗi config: tạo `WebhookDelivery(status="pending")`, flush để get ID, `await redis.rpush("webhook_queue", str(delivery.id))`
- [ ] T096 [US7] Thêm `process_deliveries()` background worker vào `backend/app/services/webhook_service.py` — `while True` loop với `await redis.blpop("webhook_queue", timeout=30)`; fetch delivery, skip nếu không tồn tại hoặc đã success; `RETRY_DELAYS = [5, 30, 120]`: loop qua attempts với `asyncio.sleep(delay)` trước retry 2+; update `delivery.attempts/last_attempt_at/http_status`; set `status="success"` nếu succeed hoặc `status="failed"` sau 3 lần thất bại; `await session.commit()`; catch all exceptions silently để loop tiếp tục
- [ ] T097 [P] [US7] Thêm `test_webhook(session, webhook_id) -> dict` vào `backend/app/services/webhook_service.py` — fetch config; build test payload `{"event": "webhook.test", "timestamp": ...}`; `_deliver_once_direct(config, test_payload)` (không tạo DB record); đo elapsed_ms; trả `{"delivered": true, "http_status": N, "response_time_ms": N}`; raise 500 nếu fail

### Backend: Webhook & GitHub APIs

- [ ] T098 [P] [US7] Tạo `backend/app/schemas/webhook.py` — `WebhookCreate(url, secret?, events: list[str])`, `WebhookResponse(id, url, events, enabled, created_at)`, `TestWebhookResponse(delivered, http_status, response_time_ms)`
- [ ] T099 [P] [US7] Tạo `backend/app/api/v1/webhooks.py` — `GET /projects/{id}/webhooks` (require_any_member); `POST /projects/{id}/webhooks` (require_leader_or_above, gọi `enqueue_delivery`); `PATCH /projects/{id}/webhooks/{wid}` (toggle enabled, update events); `DELETE /projects/{id}/webhooks/{wid}` (require_leader_or_above); `POST /projects/{id}/webhooks/{wid}/test` (gọi `test_webhook()`); đăng ký trong `router.py`
- [ ] T100 [P] [US7] Tạo `backend/app/services/github_service.py` — `encrypt_pat(pat, settings) -> str`: `Fernet(settings.fernet_key).encrypt(pat.encode()).decode()`; `decrypt_pat(encrypted, settings) -> str`: reverse; `validate_config(repo_full_name, pat) -> bool`: `Github(pat).get_repo(repo_full_name)` → True; except `GithubException` → False
- [ ] T101 [P] [US7] Thêm `create_pull_request(config: GitHubConfig, task, diff_content, branch_name, settings) -> str` vào `backend/app/services/github_service.py` — decrypt PAT; `Github(pat).get_repo(repo_full_name)`; `repo.create_pull(title=task.title, body=f"## {task.title}\n\n{task.description}\n\n```diff\n{diff[:3000]}\n```", head=branch_name, base=config.default_base_branch)`; trả `pr.html_url`
- [ ] T102 [P] [US7] Tạo `backend/app/api/v1/github.py` — `GET /projects/{id}/github` (require_any_member, 404 nếu chưa config); `PUT /projects/{id}/github` (require_owner, validate PAT trước khi save → 422 nếu fail, encrypt PAT, upsert `GitHubConfig`); đăng ký trong `router.py`

### Backend: Kanban Integration

- [ ] T103 [US7] Update `backend/app/services/kanban_service.py` — thêm notification calls: sau `task.status = "review"` → `await notification_service.notify_task_needs_review(session, task)`; sau agent error event → `await notification_service.notify_agent_error(session, task)`; sau `task.assigned_to` update → `await notification_service.notify_task_assigned(session, task, new_user_id)`
- [ ] T104 [US7] Thêm webhook calls vào `backend/app/services/kanban_service.py` — helper `build_webhook_payload(event, task, actor) -> dict` trả JSON với `event`, `timestamp`, `project: {id, name}`, `task: {id, title}`, `actor: {type, id, name}`; sau `status = "review"` → `enqueue_delivery("task.needs_review", ...)`; sau `status = "done"` → `enqueue_delivery("task.done", ...)`; sau agent error → `enqueue_delivery("agent.error", ...)`
- [ ] T105 [US7] Thêm GitHub PR integration vào `backend/app/services/kanban_service.py` — trong `approve_task()`: sau `task.status = "done"` và webhook enqueue, query `GitHubConfig WHERE project_id AND enabled`; nếu có config → `pr_url = await github_service.create_pull_request(config, task, diff, branch, settings)` trong try/except GithubException; log error thay vì raise
- [ ] T106 [US7] Update `backend/app/main.py` — `@app.on_event("startup")` async: `_webhook_task = asyncio.create_task(webhook_service.process_deliveries())`; `@app.on_event("shutdown")` async: `_webhook_task.cancel(); await asyncio.gather(_webhook_task, return_exceptions=True)`

### Frontend: Notification Panel

- [ ] T107 [P] [US7] Tạo `frontend/src/services/notification-api.ts` — `notificationApi(token)` với: `get({ unread_only?: boolean, limit?: number }) -> Promise<NotificationListResponse>`, `markRead(id: string)`, `markAllRead()`
- [ ] T108 [P] [US7] Tạo `frontend/src/components/atoms/notification-badge.tsx` — `NotificationBadge({ count: number })`: red circle `bg-red-500 text-white text-xs` absolute positioned; không render nếu `count <= 0`; `>99` hiện "99+"
- [ ] T109 [US7] Tạo `frontend/src/components/molecules/notification-panel.tsx` — `timeAgo(isoDate)` helper (phút/giờ/ngày); `TYPE_ICON` map (📋👁✅⚠🔓🔍); fetch + poll mỗi 30s; "Đánh dấu tất cả" button; scroll list max-h-80; mỗi item: icon + content + timeAgo + `bg-blue-50` nếu unread; click → `markRead()` + navigate tới reference task; `onClose` prop
- [ ] T110 [US7] Update `frontend/src/components/organisms/project-header.tsx` — wire `NotificationBadge` với `unreadCount` từ periodic fetch (hoặc từ NotificationPanel state); `useState<boolean>(false)` cho panel open; render `<NotificationPanel onClose={() => setOpen(false)}>` khi open; click outside → đóng

### Frontend: Webhook Settings UI

- [ ] T111 [P] [US7] Tạo `frontend/src/services/webhook-api.ts` — `webhookApi(token)` với: `list(projectId)`, `create(projectId, data)`, `patch(projectId, id, data)`, `delete(projectId, id)`, `test(projectId, id) -> Promise<TestWebhookResponse>`
- [ ] T112 [US7] Tạo `frontend/src/components/organisms/webhook-settings.tsx` — 2 sections: Webhooks (list: URL truncated + events badges + enabled toggle gọi PATCH; add form: URL + events checkboxes + optional secret + Save; Test button → gọi `test()` → toast với `response_time_ms`); GitHub (repo_full_name input + PAT `type="password"` input + "Lưu & Validate" button → PUT, show current config nếu exists, ẩn PAT sau save)
- [ ] T113 [US7] Tạo `frontend/src/pages/project-settings.tsx` — tabs: "Members" (`<ProjectMembers>`), "Webhooks & Integrations" (`<WebhookSettings>`); `<AuthGuard>` wrapper; thêm route `/projects/:id/settings` trong App.tsx; thêm Settings link trong project header

**Checkpoint**: Assign task → `GET /notifications` trả 1 unread. Bell badge hiện số. Notification panel polling 30s. Webhook test → delivered toast. Task Done → webhook POST fired. GitHub config lưu PAT encrypted.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: UX improvements, error handling, missing pieces.

- [ ] T114 [P] Update `frontend/src/services/api-client.ts` — thêm axios response interceptor: 401 → `auth.logout()` + `window.location.href = "/login"`; 403 → toast "Không đủ quyền"; 5xx → toast "Lỗi server, vui lòng thử lại"
- [ ] T115 [P] Update `frontend/src/pages/dashboard.tsx` — thêm loading skeleton (3 gray card placeholders với animate-pulse khi `isLoading`); thêm empty state "Chưa có project nào — Tạo project đầu tiên" với CTA button nếu `projects.length === 0`
- [ ] T116 [US2] Tạo `frontend/src/pages/accept-invite.tsx` — `useParams` lấy `token`; `useEffect` auto-call `memberApi(token).acceptInvite(inviteToken)`; success → navigate `/dashboard` với toast "Bạn đã tham gia project"; error expired → hiển thị "Link đã hết hạn"; error used → "Link đã được sử dụng"
- [ ] T117 [P] Update `frontend/src/components/molecules/notification-panel.tsx` — empty state "Không có thông báo nào" với icon khi `items.length === 0`; error state nếu fetch fail (silently retry)
- [ ] T118 [P] Add confirm dialog trước khi xóa webhook trong `frontend/src/components/organisms/webhook-settings.tsx` — `window.confirm("Xóa webhook này?")` trước khi call delete; thêm validation cho URL field (phải bắt đầu với `https://`)
- [ ] T119 Kiểm tra `backend/app/api/v1/router.py` — verify tất cả routers đã được đăng ký: auth, members, review, dependencies, templates, notifications, webhooks, github, analytics; mỗi router có đúng prefix
- [ ] T120 Chạy `alembic upgrade head` và smoke test toàn bộ API flow — register → login → create project → invite → accept → assign task → start task (reviewer chạy) → approve → verify dependency unlock → verify notification → verify webhook delivery log

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)          ───────────────────────────► BLOCKS tất cả
Phase 2 (Foundational)   ─── sau Phase 1 ───────────► BLOCKS tất cả User Stories
Phase 3 (US1: AI Review) ─── sau Phase 2 ───────────► Độc lập, MVP ngay
Phase 4 (US2: Auth)      ─── sau Phase 2 ───────────► BLOCKS Phase 5, 8, 9
Phase 5 (US3: Assign)    ─── sau Phase 4 ───────────► Cần auth system
Phase 6 (US4: Deps)      ─── sau Phase 2 ───────────► Độc lập
Phase 7 (US5: Templates) ─── sau Phase 2 ───────────► Độc lập
Phase 8 (US6: Dashboard) ─── sau Phase 4 ───────────► Cần analytics + auth
Phase 9 (US7: Notifs)    ─── sau Phase 4 ───────────► Cần kanban + auth
Phase 10 (Polish)        ─── sau tất cả ────────────►
```

### User Story Dependencies

- **US1** (P1): Độc lập — implement sau Phase 2, không cần auth hoàn chỉnh
- **US2** (P1): Độc lập — song song với US1
- **US3** (P1): Phụ thuộc US2 (cần auth để biết ai đang kéo task)
- **US4** (P2): Phụ thuộc Phase 2 (models); không phụ thuộc auth
- **US5** (P2): Phụ thuộc Phase 2; không phụ thuộc auth
- **US6** (P2): Phụ thuộc US2 (cần user identity) + US1 (review scores)
- **US7** (P2): Phụ thuộc US2 (cần user_id) + US3 (assign triggers notif)

### Parallel Opportunities

```
# Sau Phase 1 — song song (tất cả models):
T007, T008, T009, T010, T011, T012, T013, T014, T021, T022

# Reviewer service methods — tất cả parallel (different functions, same file):
T023, T024, T025, T026, T027

# reviewer_node — phải sequential:
T028 → T029 → T030 → T031

# Trong Phase 4 (US2) — song song:
T040, T047, T052, T053 [schemas + services + atoms]
T043, T044 [existing route updates]

# Trong Phase 9 (US7) — nhiều items song song:
T092, T093 [notification schemas + API]
T094, T095, T096, T097 [webhook service — sequential, same file]
T098, T099 [webhook schemas + API — parallel]
T100, T101, T102 [github service + API]
T107, T108, T111 [frontend notification/webhook APIs — parallel]
```

---

## Parallel Execution Examples

### Example: Phase 2 Foundational Models (all parallel)

```
Task T007: backend/app/models/project_member.py
Task T008: backend/app/models/invitation.py
Task T009: backend/app/models/review_report.py
Task T010: backend/app/models/task_dependency.py
Task T011: backend/app/models/task_template.py
Task T012: backend/app/models/notification.py
Task T013: backend/app/models/webhook.py
Task T014: backend/app/models/github_config.py
Task T021: frontend/src/types/index.ts (all new interfaces)
Task T022: frontend/src/services/api-client.ts
```

### Example: User Story 1 — reviewer_service functions (all parallel)

```
Task T023: detect_test_runner() — conftest/package.json detection
Task T024: run_tests() — subprocess + output parsing
Task T025: scan_secrets() — regex patterns on diff +lines
Task T026: ai_review_diff() — LLM prompt + JSON parse
Task T027: calculate_score() — weighted 40/30/30 formula
```

---

## Implementation Strategy

### MVP First (US1 — AI Review, không cần auth)

1. Phase 1: Setup (T001–T006)
2. Phase 2: Foundational (T007–T022)
3. Phase 3: US1 hoàn chỉnh (T023–T038)
4. **STOP & VALIDATE**: Kéo task → reviewer chạy → panel hiện score
5. Demo/deploy MVP với single user

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. US1 (AI Review) → Demo MVP
3. US2 (Auth/Team) → Team onboarding
4. US3 (Assignment/WIP) → Team workflow
5. US4 (Dependencies) → Advanced planning
6. US5 (Templates) → Productivity boost
7. US6 (Dashboard) → Management visibility
8. US7 (Notifications/Webhooks) → External integrations

### Single-Developer Sequential Order

```
T001–T006 (Setup) →
T007–T022 (Foundation) →
T023–T038 (US1: AI Review) →
T039–T055 (US2: Auth/Team) →
T056–T062 (US3: Assign/WIP) →
T063–T074 (US4: Dependencies) →
T075–T081 (US5: Templates) →
T082–T089 (US6: Dashboard) →
T090–T113 (US7: Notifications/Webhooks) →
T114–T120 (Polish)
```

---

## Notes

- `[P]` = file riêng biệt, không dependency → có thể chạy song song
- `[USN]` label = traceability về user story trong spec.md
- Mỗi phase có **Checkpoint** — dừng để verify trước khi tiếp
- US1 (AI Review) là MVP: value ngay cả với single user, không cần auth
- Commit sau mỗi task hoặc nhóm logic nhỏ
- reviewer_node (T028→T029→T030) phải sequential vì cùng file, khác concerns
- dependency_service (T063→T064→T065) phải sequential vì build-on nhau
- webhook_service (T094→T095→T096→T097) phải sequential vì cùng file
