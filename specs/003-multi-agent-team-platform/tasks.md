# Tasks: Platform Expansion — Multi-Agent Review, Team Management & Integrations

**Input**: Design documents from `/specs/003-multi-agent-team-platform/`
**Feature Branch**: `003-multi-agent-team-platform`
**Generated**: 2026-05-23 (v2 — enhanced with coder context)

**Stack**: Python 3.11 + FastAPI + SQLAlchemy async + LangGraph (backend) · TypeScript 5.6 + React 18 (frontend)

---

## 🗺️ Codebase Map (đọc trước khi bắt đầu bất kỳ task nào)

### Backend hiện tại (`backend/app/`)
```
api/v1/
  projects.py     — CRUD, dùng require_jwt từ app.middleware.auth
  tasks.py        — Kanban move/approve/reject, dùng require_jwt
  review.py       — GET /tasks/{id}/review (đã làm T033)
  dev_auth.py     — POST /dev/token (chỉ local)
  documents.py, memory.py, branches.py, agent_runs.py, backends.py, audit_logs.py, codebase.py, pause.py

routers/          — legacy routers được import vào main.py
  auth.py         — /auth/register + /auth/login, dùng security.py CŨ
  ws.py, skills.py, users.py, comments.py, agent.py, boards.py, activity.py

models/           — SQLAlchemy ORM
  user.py         — User(id UUID, email, hashed_password, display_name, created_at, last_login_at)
  project_member.py — ProjectMember(id, project_id, user_id, role, joined_at); ProjectRole(owner/leader/developer/viewer)
  invitation.py   — Invitation(id, project_id, invitee_email, role, token, created_by, expires_at, used_at, used_by)
  review_report.py — ReviewReport, ReviewComment, ReviewStatus (pending/running/complete/error)
  task_dependency.py — TaskDependency(task_id, depends_on_task_id)
  task_template.py — TaskTemplate(id, name, title_template, description_template, scope, project_id, created_by)
  notification.py — Notification(id, user_id, type, content, reference_type, reference_id, is_read, created_at)
  webhook.py      — WebhookConfig, WebhookDelivery
  github_config.py — GitHubConfig
  task.py         — Task + assigned_to FK + is_blocked bool

services/
  auth_service.py — hash_password, verify_password, create_access_token(user_id, secret, alg, days), decode_token, register_user, login_user
  reviewer_service.py — detect_test_runner, run_tests, scan_secrets, ai_review_diff, calculate_score
  kanban_service.py — KanbanService.move_task, start_coder_agent

agent/nodes/
  reviewer_node.py — run(state) -> state (đã làm T028–T030)

dependencies.py     — get_current_user, get_optional_user, require_role, require_owner, require_leader_or_above, require_developer_or_above, require_any_member
config.py           — Settings(jwt_secret_key, jwt_algorithm, jwt_expire_days, fernet_key property)
security.py         — LEGACY: hash_password, verify_password, create_access_token(subject: str) — đừng dùng cho code mới
middleware/auth.py  — require_jwt(creds) -> str: chỉ trả sub string, KHÔNG fetch User từ DB
main.py             — tất cả routers đã được mount ở đây
database.py         — get_db(), async_session_maker
```

### Frontend hiện tại (`frontend/src/`)
```
services/
  api.ts          — axios instance `api`, getAuthToken(), setAuthToken(), TOKEN_KEY='neo_kanban_jwt', resolveApiBaseURL()
  api-client.ts   — createApiClient(token), BASE_URL, resolveApiV1BaseURL()
  project-api.ts  — listProjects, getProject, createProject, updateProject
  task-api.ts     — getTasks, moveTask, approveTask, rejectTask, groupedResponseToTaskColumns
  review-api.ts   — reviewApi(token), useReviewReport hook (đã làm T034)

pages/
  login.tsx       — form với email + password, gọi /auth/login qua api.ts
  register.tsx    — form với email + password + displayName, gọi /auth/register
  project-list.tsx — danh sách + tạo project, dùng api.ts
  project-workspace.tsx — kanban/documents/memory/audit tabs
  dev-auth.tsx    — lấy dev JWT từ /dev/token

App.tsx           — BrowserRouter; RequireAuth component dùng getAuthToken(); routes: /, /login, /register, /dev/auth, /projects, /projects/:id, /projects/:id/constitution

types/index.ts    — Task, Project, User, ProjectMember, ReviewReport, etc. (đã cập nhật T021)
store/
  task-store.ts   — useTaskStore (Zustand)
  project-store.ts — useProjectStore
```

### Patterns quan trọng để follow:

**Backend FastAPI endpoint pattern:**
```python
# api/v1/projects.py — ví dụ GET /projects (dùng require_jwt)
@router.get("", response_model=list[ProjectListItem])
async def list_projects(
    _sub: Annotated[str, Depends(require_jwt)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[ProjectListItem]:
    ...

# Endpoint mới cần User object — dùng get_current_user (từ app.dependencies)
from app.dependencies import get_current_user
@router.get("", ...)
async def endpoint(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ...:
    ...
```

**Backend router registration (main.py):**
```python
# Thêm vào phần import + api_v1_router.include_router(new_router)
# Xem main.py lines 8-38 để biết pattern
```

**Frontend service pattern:**
```typescript
// Dùng api từ services/api.ts (đã có auth header injection):
import { api } from './api'
export async function getMembers(projectId: string) {
  const res = await api.get<MemberResponse[]>(`/api/v1/projects/${projectId}/members`)
  return res.data
}
```

---

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: User story — US1=AI Review, US2=Auth/Team, US3=Assignment/WIP, US4=Dependencies, US5=Templates, US6=Dashboard, US7=Notifications

---

## Phase 1: Setup (Shared Infrastructure) ✅ DONE

- [X] T001 Write Alembic migration `backend/alembic/versions/005_platform_expansion.py`
- [X] T002 [P] Update `backend/app/config.py` — jwt_secret_key, fernet_key property
- [X] T003 [P] Update `backend/.env.example`
- [X] T004 [P] Update `backend/requirements.txt`
- [X] T005 [P] Update `frontend/package.json`
- [X] T006 [P] Update `.specify/memory/constitution.md`

---

## Phase 2: Foundational (Blocking Prerequisites) ✅ DONE

- [X] T007 [P] Tạo `backend/app/models/project_member.py`
- [X] T008 [P] Tạo `backend/app/models/invitation.py`
- [X] T009 [P] Tạo `backend/app/models/review_report.py`
- [X] T010 [P] Tạo `backend/app/models/task_dependency.py`
- [X] T011 [P] Tạo `backend/app/models/task_template.py`
- [X] T012 [P] Tạo `backend/app/models/notification.py`
- [X] T013 [P] Tạo `backend/app/models/webhook.py`
- [X] T014 [P] Tạo `backend/app/models/github_config.py`
- [X] T015 Update `backend/app/models/task.py` — assigned_to FK + is_blocked
- [X] T016 Tạo `backend/app/services/auth_service.py`
- [X] T017 Thêm register_user + login_user vào `auth_service.py`
- [X] T018 Tạo `backend/app/dependencies.py` — get_current_user, get_optional_user
- [X] T019 Thêm require_role vào `backend/app/dependencies.py`
- [X] T020 [P] Tạo `backend/app/schemas/auth.py`
- [X] T021 [P] Update `frontend/src/types/index.ts`
- [X] T022 [P] Tạo `frontend/src/services/api-client.ts`

---

## Phase 3: User Story 1 — AI Tự Động Review Code ✅ DONE

- [X] T023–T038 (backend reviewer service, node, API + frontend AI Review panel)

---

## Phase 4: User Story 2 — Đăng Nhập & Phân Quyền Team

**Goal**: JWT auth; 4-role system; Owner mời thành viên qua invite link 7 ngày.

**Trạng thái hiện tại trước khi bắt đầu phase này**:
- `backend/app/routers/auth.py` đã có `/auth/register` + `/auth/login` nhưng dùng `security.py` CŨ và không có `/auth/me`
- `backend/app/schemas/auth.py` đã có `RegisterRequest`, `LoginRequest`, `UserResponse`, `TokenResponse` (đúng pattern mới)
- `backend/app/services/auth_service.py` đã hoàn chỉnh
- `backend/app/dependencies.py` đã hoàn chỉnh
- `frontend/src/pages/login.tsx` và `register.tsx` đã tồn tại
- `frontend/src/App.tsx` đã có `RequireAuth` component dùng `getAuthToken()`

---

### Backend: Auth Endpoints

- [x] T039 [US2] **Update** `backend/app/routers/auth.py` (KHÔNG tạo file mới) — Thay thế toàn bộ nội dung để dùng `auth_service` và schemas mới:
  ```python
  # Imports cần dùng:
  from app.dependencies import get_current_user
  from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, UserResponse
  from app.services import auth_service
  from app.config import settings

  router = APIRouter(prefix="/auth", tags=["auth"])

  # POST /auth/register → 201, gọi auth_service.register_user(session, email, password, display_name),
  #   sau đó auth_service.create_access_token(user.id, settings.jwt_secret_key, settings.jwt_algorithm, settings.jwt_expire_days),
  #   trả TokenResponse(access_token=token, token_type="bearer", user=UserResponse.model_validate(user)),
  #   nếu 409 từ register_user: propagate (HTTPException đã được raise bởi service)

  # POST /auth/login → gọi auth_service.login_user(session, email, password, settings),
  #   trả TokenResponse(access_token=token, token_type="bearer", user=UserResponse.model_validate(user))

  # GET /auth/me → current_user: Annotated[User, Depends(get_current_user)],
  #   trả UserResponse.model_validate(current_user)
  ```
  **Lưu ý**: `main.py` đã import `from app.routers.auth import router as auth_router` và đã register. Chỉ cần cập nhật file này.

---

### Backend: Members & Invitations

- [x] T040 [P] [US2] Tạo `backend/app/schemas/member.py` — mới hoàn toàn:
  ```python
  # File: backend/app/schemas/member.py
  import uuid
  from datetime import datetime
  from pydantic import BaseModel, ConfigDict, EmailStr
  from app.models.project_member import ProjectRole

  class InviteRequest(BaseModel):
      role: ProjectRole  # leader/developer/viewer (owner không mời được)
      invitee_email: str | None = None  # optional — nếu None thì tạo public link

  class InvitationResponse(BaseModel):
      invitation_id: uuid.UUID
      invite_url: str  # full URL: https://host/invitations/{token}
      expires_at: datetime

  class AcceptResponse(BaseModel):
      project_id: uuid.UUID
      role: ProjectRole

  class MemberResponse(BaseModel):
      model_config = ConfigDict(from_attributes=True)
      user_id: uuid.UUID
      display_name: str
      email: str
      role: ProjectRole
      joined_at: datetime

  class RoleChangeRequest(BaseModel):
      role: ProjectRole
  ```

- [x] T041 [US2] Tạo `backend/app/api/v1/members.py` — phần 1 (list, invite, get-invitation):
  ```python
  # File: backend/app/api/v1/members.py
  # Imports:
  from app.dependencies import get_current_user, require_owner, require_any_member
  from app.models.invitation import Invitation
  from app.models.project_member import ProjectMember, ProjectRole
  from app.models.user import User
  from app.schemas.member import InviteRequest, InvitationResponse, MemberResponse
  from app.database import get_db
  from app.services.project_service import ProjectService  # get(session, project_id) → Project

  router = APIRouter(prefix="/projects", tags=["members"])

  # GET /projects/{project_id}/members
  #   guard: require_any_member (Depends từ app.dependencies — tự động lấy project_id từ path)
  #   query: SELECT pm.*, u.display_name, u.email FROM project_members JOIN users WHERE project_id
  #   trả list[MemberResponse]

  # POST /projects/{project_id}/members/invite
  #   guard: require_owner
  #   tạo Invitation: token=secrets.token_hex(32), expires_at=utcnow()+timedelta(days=7)
  #   invite_url = str(request.base_url) + f"invitations/{token}"  # dùng Request từ fastapi
  #   session.add(invite); await session.commit()
  #   trả InvitationResponse

  # GET /invitations/{token}  (public — không cần auth)
  #   query Invitation by token; 404 nếu không tìm thấy
  #   trả dict: {invitation_id, project_id, role, invitee_email, is_expired, is_used}
  ```
  Sau khi tạo, thêm vào `backend/app/main.py`:
  ```python
  from app.api.v1.members import router as members_router
  api_v1_router.include_router(members_router)
  ```

- [x] T042 [US2] Thêm phần 2 vào `backend/app/api/v1/members.py` (accept, change-role, remove):
  ```python
  # POST /invitations/{token}/accept
  #   guard: get_current_user (auth required)
  #   check invite.is_expired → HTTPException 410 "Invitation expired"
  #   check invite.is_used → HTTPException 410 "Invitation already used"
  #   check existing member: SELECT FROM project_members WHERE project_id=invite.project_id AND user_id=current_user.id
  #   → 409 nếu đã là member
  #   tạo ProjectMember(project_id, user_id=current_user.id, role=invite.role)
  #   set invite.used_at=utcnow(), invite.used_by=current_user.id
  #   await session.commit()
  #   trả AcceptResponse(project_id, role)

  # PATCH /projects/{project_id}/members/{user_id}
  #   guard: require_leader_or_above
  #   body: RoleChangeRequest
  #   fetch member record; 404 nếu không có; update role; commit

  # DELETE /projects/{project_id}/members/{user_id}
  #   guard: require_owner
  #   không cho xóa owner: nếu member.role == ProjectRole.OWNER → 400
  #   delete record; commit
  ```

---

### Backend: Auth Guard Existing Routes

- [x] T043 [US2] **Update** `backend/app/api/v1/projects.py` — thêm auth + project membership:

  **Trạng thái hiện tại**: tất cả endpoints dùng `_sub: Annotated[str, Depends(require_jwt)]`

  **Thay đổi**:
  ```python
  # Thêm import:
  from app.dependencies import get_current_user, require_owner
  from app.models.user import User
  from app.models.project_member import ProjectMember, ProjectRole
  from sqlalchemy import select

  # Với GET /projects: thay require_jwt bằng get_current_user; filter theo project membership:
  #   query = select(Project).join(ProjectMember, Project.id == ProjectMember.project_id)
  #           .where(ProjectMember.user_id == current_user.id)

  # Với POST /projects: thay require_jwt bằng get_current_user; sau khi tạo project, auto-add creator:
  #   session.add(ProjectMember(project_id=project.id, user_id=current_user.id, role=ProjectRole.OWNER))

  # Với PUT /projects/{project_id}: require_owner (thay require_jwt)
  # Với DELETE /projects/{project_id}: require_owner (thay require_jwt)
  # Với GET /projects/{project_id}: require_any_member (thay require_jwt)

  # Giữ nguyên: GET /projects/{project_id}/constitution, POST /projects/{project_id}/intent, v.v.
  #   nhưng đổi require_jwt → require_any_member
  ```

- [x] T044 [US2] **Update** `backend/app/api/v1/tasks.py` — thêm auth:

  **Trạng thái hiện tại**: dùng `_sub: Annotated[str, Depends(require_jwt)]` ở mọi endpoint

  **Thay đổi**:
  ```python
  # Thêm import:
  from app.dependencies import get_current_user, require_any_member, require_developer_or_above, require_leader_or_above

  # GET /projects/{project_id}/tasks: đổi require_jwt → require_any_member
  # POST /projects/{project_id}/tasks: đổi require_jwt → require_developer_or_above
  # POST /projects/{project_id}/tasks/{task_id}/move: đổi require_jwt → require_developer_or_above
  # POST /projects/{project_id}/tasks/{task_id}/approve: đổi require_jwt → require_leader_or_above
  # POST /projects/{project_id}/tasks/{task_id}/reject: đổi require_jwt → require_leader_or_above
  # Các endpoint khác trong tasks.py: đổi require_jwt → require_any_member

  # LƯU Ý: require_leader_or_above/require_developer_or_above/require_any_member trả ProjectMember,
  # không phải User. Nếu endpoint cần User object riêng, thêm thêm current_user: Annotated[User, Depends(get_current_user)]
  ```

- [x] T045 [P] [US2] **Update** `backend/app/main.py` — startup log:
  ```python
  # CORS đã đúng (allow_headers=["*"]) — không cần sửa
  # Thêm vào lifespan hoặc startup event:
  import logging
  logger = logging.getLogger(__name__)

  @asynccontextmanager
  async def lifespan(_app: FastAPI):
      logger.info("JWT auth: secret_key=%s... algorithm=%s expire_days=%d",
                  settings.jwt_secret_key[:6] if settings.jwt_secret_key else "MISSING",
                  settings.jwt_algorithm,
                  settings.jwt_expire_days)
      yield
      await dispose_engine()
  ```

---

### Frontend: Auth Context & Pages

- [x] T046 [US2] Tạo `frontend/src/contexts/auth-context.tsx` — Context cho user session:
  ```typescript
  // File: frontend/src/contexts/auth-context.tsx
  // Imports cần:
  import { createContext, useCallback, useContext, useEffect, useState } from 'react'
  import { getAuthToken, setAuthToken } from '../services/api'  // đã có trong api.ts
  import type { User } from '../types'

  // AuthState interface:
  // { user: User | null; token: string | null; isLoading: boolean }

  // AuthContext cung cấp: user, token, isLoading, login(), logout(), register()

  // useEffect khi mount:
  //   1. token = getAuthToken()
  //   2. nếu có token → gọi GET /api/v1/auth/me với Authorization header
  //   3. set user; nếu 401 → setAuthToken(null)

  // login(email, password):
  //   POST /api/v1/auth/login (dùng api từ services/api.ts — đã có base URL và header setup)
  //   response: { access_token, token_type, user }
  //   setAuthToken(access_token)
  //   set user state

  // logout(): setAuthToken(null); set user=null

  // register(email, password, displayName):
  //   POST /api/v1/auth/register
  //   auto-login sau register

  // Export: AuthProvider component, useAuth() hook
  // KHÔNG dùng createApiClient — dùng trực tiếp axios hay api instance từ services/api.ts
  ```

- [x] T047 [P] [US2] Tạo `frontend/src/services/auth-api.ts` — API wrapper cho auth:
  ```typescript
  // File: frontend/src/services/auth-api.ts
  // Dùng api từ services/api.ts (đã có auth header injection + base URL + timeout)
  import { api, setAuthToken } from './api'
  import type { User } from '../types'

  // authApi object:
  // register(email, password, display_name): POST /api/v1/auth/register → { access_token, user }
  // login(email, password): POST /api/v1/auth/login → { access_token, user }
  // getMe(token?: string): GET /api/v1/auth/me → User
  //   nếu token được truyền: set Authorization header manually
  //   else dùng api instance (tự lấy từ localStorage)

  // Token types:
  export interface AuthTokenResponse {
    access_token: string
    token_type: string
    user: User | null
  }
  ```

- [x] T048 [US2] **Update** `frontend/src/pages/login.tsx` — wire với AuthContext:
  ```typescript
  // File hiện tại: dùng api.ts trực tiếp để POST /auth/login
  // Thay đổi:
  import { useAuth } from '../contexts/auth-context'
  import { useNavigate } from 'react-router-dom'

  // const { login } = useAuth()
  // const navigate = useNavigate()
  // onSubmit: try { await login(email, password); navigate('/projects') }
  //           catch (err) { setError('Email hoặc mật khẩu không đúng') }

  // Giữ nguyên: form structure, styling, error display
  ```

- [x] T049 [US2] **Update** `frontend/src/pages/register.tsx` — wire với AuthContext:
  ```typescript
  // Tương tự T048:
  import { useAuth } from '../contexts/auth-context'
  // const { register } = useAuth()
  // onSubmit: try { await register(email, password, displayName); navigate('/projects') }
  //           catch (err) { /* hiển thị lỗi */ }
  // Bắt 409 (email đã dùng): hiển thị "Email đã được sử dụng"
  ```

- [x] T050 [P] [US2] Tạo `frontend/src/components/molecules/auth-guard.tsx` — component wrapper:
  ```typescript
  // File: frontend/src/components/molecules/auth-guard.tsx
  // App.tsx hiện tại có RequireAuth component dùng getAuthToken() — component này tương tự
  // nhưng dùng AuthContext để có isLoading state:
  import { useAuth } from '../../contexts/auth-context'
  import { Spinner } from '../atoms/spinner'  // đã có

  export function AuthGuard({ children }: { children: React.ReactNode }) {
    const { user, isLoading } = useAuth()
    if (isLoading) return <Spinner aria-label="Authenticating..." />
    if (!user) return <Navigate to="/login" state={{ from: location }} replace />
    return <>{children}</>
  }
  ```

- [x] T051 [US2] **Update** `frontend/src/App.tsx` — wrap với AuthProvider + dùng AuthGuard:
  ```typescript
  // File hiện tại:
  // import { getAuthToken } from './services/api'
  // function RequireAuth(...) { return getAuthToken() ? ... : <Navigate to="/login" /> }

  // Thay đổi:
  // 1. Thêm import AuthProvider và AuthGuard:
  import { AuthProvider } from './contexts/auth-context'
  import { AuthGuard } from './components/molecules/auth-guard'

  // 2. Wrap BrowserRouter trong <AuthProvider>
  // 3. Thay RequireAuth component bằng AuthGuard (hoặc giữ cả hai tạm thời)
  // 4. Thêm route: <Route path="/invitations/:token" element={<AcceptInvite />} /> (component T116)
  // 5. KHÔNG thay đổi routes khác — giữ nguyên /login, /register, /dev/auth, /projects, /projects/:id

  // Kết quả:
  // export default function App() {
  //   return (
  //     <AuthProvider>
  //       <BrowserRouter>
  //         <Routes>...routes như cũ nhưng dùng AuthGuard...</Routes>
  //       </BrowserRouter>
  //     </AuthProvider>
  //   )
  // }
  ```

---

### Frontend: Member Management UI

- [x] T052 [P] [US2] Tạo `frontend/src/services/member-api.ts`:
  ```typescript
  // File: frontend/src/services/member-api.ts
  // Dùng api từ services/api.ts (đã có auth header, base URL, timeout)
  import { api } from './api'
  import type { ProjectMember, Invitation } from '../types'

  export interface InvitationResponse {
    invitation_id: string
    invite_url: string
    expires_at: string
  }

  export async function getMembers(projectId: string): Promise<ProjectMember[]> {
    const res = await api.get<ProjectMember[]>(`/api/v1/projects/${projectId}/members`)
    return res.data
  }

  export async function inviteMember(
    projectId: string,
    role: string,
    inviteeEmail?: string,
  ): Promise<InvitationResponse> {
    const res = await api.post<InvitationResponse>(
      `/api/v1/projects/${projectId}/members/invite`,
      { role, invitee_email: inviteeEmail ?? null },
    )
    return res.data
  }

  export async function acceptInvite(token: string): Promise<{ project_id: string; role: string }> {
    const res = await api.post(`/api/v1/invitations/${token}/accept`)
    return res.data
  }

  export async function changeMemberRole(
    projectId: string,
    userId: string,
    role: string,
  ): Promise<void> {
    await api.patch(`/api/v1/projects/${projectId}/members/${userId}`, { role })
  }

  export async function removeMember(projectId: string, userId: string): Promise<void> {
    await api.delete(`/api/v1/projects/${projectId}/members/${userId}`)
  }
  ```

- [x] T053 [P] [US2] Tạo `frontend/src/components/atoms/role-badge.tsx`:
  ```typescript
  // File: frontend/src/components/atoms/role-badge.tsx
  import type { ProjectRole } from '../../types'

  const ROLE_STYLES: Record<ProjectRole, string> = {
    owner: 'bg-purple-100 text-purple-700',
    leader: 'bg-blue-100 text-blue-700',
    developer: 'bg-green-100 text-green-700',
    viewer: 'bg-gray-100 text-gray-500',
  }

  export function RoleBadge({ role }: { role: ProjectRole }) {
    return (
      <span className={`inline-block text-xs font-medium px-2 py-0.5 rounded-full ${ROLE_STYLES[role]}`}>
        {role}
      </span>
    )
  }
  ```

- [x] T054 [US2] Tạo `frontend/src/components/organisms/project-members.tsx` — Members management:
  ```typescript
  // File: frontend/src/components/organisms/project-members.tsx
  // Imports:
  import { useEffect, useState } from 'react'
  import { getMembers, inviteMember, changeMemberRole, removeMember, type InvitationResponse } from '../../services/member-api'
  import { useAuth } from '../../contexts/auth-context'
  import { RoleBadge } from '../atoms/role-badge'
  import { showErrorToast } from '../../lib/toast'
  import type { ProjectMember } from '../../types'

  // Props: projectId: string
  // State: members: ProjectMember[], loading, inviteRole, inviteEmail, inviteLink: string | null

  // Render:
  // 1. Table: display_name | email | RoleBadge | actions (change role select, remove button)
  //    - change role: PATCH /projects/{id}/members/{user_id}
  //    - remove: DELETE /projects/{id}/members/{user_id}
  //    - disabled cho self và owner
  // 2. Invite section: email input + role select (leader/developer/viewer) + "Tạo link" button
  //    - POST invite → hiện inviteLink + copy button (navigator.clipboard.writeText)
  //    - toast thành công/lỗi
  // 3. Loading / empty state
  ```

- [x] T055 [US2] **Update** `frontend/src/components/organisms/project-header.tsx` — thêm member avatars + bell:

  **Trạng thái hiện tại**: project-header hiện thị project name + tab navigation

  **Thêm**:
  ```typescript
  // Imports mới:
  import { useEffect, useState } from 'react'
  import { getMembers } from '../../services/member-api'
  import type { ProjectMember } from '../../types'

  // State: members: ProjectMember[] (fetch khi mount)
  // Render: dưới project name:
  //   - Row: max 5 avatar circles (initials từ display_name, deterministic color từ name.charCodeAt(0)*137%360)
  //     + "+N" badge nếu > 5
  //   - Bell icon button (onClick → setNotifOpen(true)); NotificationBadge placeholder count=0
  //     (sẽ wire ở T110)
  ```

**Checkpoint Phase 4**: `POST /auth/register` → 201 với token; `POST /auth/login` → token; `GET /auth/me` → user. Register + login form hoạt động, chuyển hướng `/projects`. `GET /projects` lọc theo membership. Owner mời → link tạo → accept → member xuất hiện trong list. Viewer gọi move task → 403.

---

## Phase 5: User Story 3 — Assign Task & WIP per Developer

**Goal**: Leader assign task; avatar hiện trên card; WIP per-developer enforcement.

**Context trước khi bắt đầu**:
- `backend/app/services/kanban_service.py` hiện tại: WIP check đếm `count_in_progress` per PROJECT
- `backend/app/models/task.py` đã có `assigned_to` FK và `is_blocked` bool (T015)
- `backend/app/schemas/task.py` cần thêm assigned_to vào response

---

### Backend: WIP & Assignment Logic

- [X] T056 [US3] **Update** `backend/app/services/kanban_service.py` — WIP per-developer mode:
  ```python
  # Thêm imports:
  from sqlalchemy import select, func
  from app.models.project_member import ProjectMember
  from app.models.task import Task, TaskStatus

  # Thêm helper:
  async def get_wip_mode(session: AsyncSession, project_id: UUID) -> str:
      """Trả 'user' nếu có ProjectMember records, 'project' nếu single-user mode."""
      count = await session.scalar(
          select(func.count()).where(ProjectMember.project_id == project_id)
      )
      return "user" if (count or 0) > 0 else "project"

  # Trong KanbanService.move_task() khi to_status == TaskStatus.IN_PROGRESS:
  # THÊM (sau WIP check hiện tại):
  # 1. if task.is_blocked: raise WIPLimitError("Task is blocked by dependencies")
  # 2. wip_mode = await get_wip_mode(session, task.project_id)
  # 3. if wip_mode == "user" and current_user_id is not None:
  #      in_progress_count = await session.scalar(
  #          select(func.count()).where(Task.assigned_to == current_user_id, Task.status == TaskStatus.IN_PROGRESS)
  #      )
  #      nếu count >= 1: raise WIPLimitError(...)
  # (current_user_id cần được truyền vào move_task — xem T057 về signature)
  ```

- [X] T057 [US3] Thêm assignment conflict check vào `kanban_service.py` — auto-assign + conflict:
  ```python
  # Cập nhật signature move_task để nhận current_user_id:
  # async def move_task(task_id, to_status, session, *, current_user_id: UUID | None = None, ...) -> Task:

  # Trong block to_status == IN_PROGRESS:
  # 1. Nếu task.assigned_to is None → task.assigned_to = current_user_id (auto-assign)
  # 2. Nếu task.assigned_to is not None AND task.assigned_to != current_user_id:
  #    - Fetch member: SELECT FROM project_members WHERE project_id=task.project_id AND user_id=current_user_id
  #    - Nếu member is None or role NOT IN (owner, leader): raise HTTPException(403, "Task assigned to another user")
  # Cập nhật call site trong api/v1/tasks.py để truyền current_user_id
  ```

- [X] T058 [P] [US3] Thêm `PATCH /projects/{project_id}/tasks/{task_id}/assign` vào `backend/app/api/v1/tasks.py`:
  ```python
  # Schema cần thêm vào backend/app/schemas/task.py:
  class AssignRequest(BaseModel):
      user_id: UUID | None  # None để unassign

  # Endpoint:
  @router.patch("/{project_id}/tasks/{task_id}/assign", response_model=TaskResponse)
  async def assign_task(
      project_id: UUID,
      task_id: UUID,
      body: AssignRequest,
      _member: Annotated[ProjectMember, require_leader_or_above],
      session: Annotated[AsyncSession, Depends(get_db)],
  ) -> TaskResponse:
      # Nếu body.user_id is not None: validate là member của project
      # UPDATE tasks SET assigned_to=body.user_id WHERE id=task_id
      # commit + refresh
      # trả TaskResponse.model_validate(task)
  ```

- [X] T059 [P] [US3] **Update** `backend/app/schemas/task.py` — thêm assigned_to + is_blocked vào response schemas:
  ```python
  # Trong TaskKanbanItem và bất kỳ response schema nào:
  assigned_to: UUID | None = None
  is_blocked: bool = False
  # Đảm bảo model_config = ConfigDict(from_attributes=True) đã có
  ```

---

### Frontend: Assignee Avatar & Assign UI

- [X] T060 [P] [US3] Tạo `frontend/src/components/atoms/avatar.tsx`:
  ```typescript
  // File: frontend/src/components/atoms/avatar.tsx
  type AvatarSize = 'sm' | 'md' | 'lg'
  const SIZE_CLASSES: Record<AvatarSize, string> = {
    sm: 'w-6 h-6 text-xs',
    md: 'w-8 h-8 text-sm',
    lg: 'w-10 h-10 text-base',
  }

  export function Avatar({ name, size = 'md', className = '' }: {
    name: string; size?: AvatarSize; className?: string
  }) {
    const initials = name.split(' ').map(w => w[0] ?? '').join('').slice(0, 2).toUpperCase()
    const hue = name.charCodeAt(0) * 137 % 360
    return (
      <div
        className={`inline-flex items-center justify-center rounded-full font-medium ${SIZE_CLASSES[size]} ${className}`}
        style={{ backgroundColor: `hsl(${hue}, 60%, 50%)`, color: 'white' }}
        title={name}
      >
        {initials}
      </div>
    )
  }
  ```

- [X] T061 [P] [US3] Tạo `frontend/src/components/molecules/assign-member.tsx`:
  ```typescript
  // Props: members: ProjectMember[], currentAssigneeId: string | null, onAssign(userId: string | null): void
  // State: open: boolean
  // Render:
  //   Trigger button: Avatar + display_name nếu assigned, "Assign..." nếu không
  //   Dropdown: list members (Avatar + display_name) + "Unassign" option
  //   Click outside: đóng (dùng useEffect + ref)
  //   Sau khi chọn: gọi onAssign(userId | null) + close
  ```

- [X] T062 [US3] **Update** `frontend/src/components/molecules/task-card.tsx` — thêm assignee:
  ```typescript
  // Trạng thái hiện tại: task-card render title, description, agent status badge, Start button
  // Thêm vào footer:
  //   - Nếu task.assigned_to: render <Avatar name={assigneeName} size="sm" />
  //   - Nếu user có role leader/owner: <AssignMember> popover
  //   - Props mới: members?: ProjectMember[], currentUserRole?: ProjectRole
  // Disable drag nếu task.is_blocked (thêm draggable={!task.is_blocked})
  ```

**Checkpoint Phase 5**: Leader assign → avatar trên card. Developer kéo task người khác → 403. WIP limit kéo task 2 → 409 trong multi-user mode. Auto-assign khi kéo unassigned task.

---

## Phase 6: User Story 4 — Task Dependencies

**Goal**: Task có depends_on; bị lock khi dependency chưa Done; auto-unlock; cycle detection; DAG visualization.

---

### Backend: Dependency Service & API

- [X] T063 [US4] Tạo `backend/app/services/dependency_service.py` — cycle detection:
  ```python
  # File: backend/app/services/dependency_service.py
  from sqlalchemy import select
  from sqlalchemy.ext.asyncio import AsyncSession
  from app.models.task_dependency import TaskDependency
  from app.models.task import Task, TaskStatus
  import uuid

  async def _load_all_deps(session: AsyncSession, project_id: uuid.UUID) -> dict[str, list[str]]:
      """Trả adjacency list {task_id: [dep_id, ...]} cho tất cả tasks trong project."""
      rows = await session.execute(
          select(TaskDependency.task_id, TaskDependency.depends_on_task_id)
          .join(Task, Task.id == TaskDependency.task_id)
          .where(Task.project_id == project_id)
      )
      adj: dict[str, list[str]] = {}
      for task_id, dep_id in rows:
          adj.setdefault(str(task_id), []).append(str(dep_id))
      return adj

  def _has_cycle(task_id: str, new_dep_id: str, adj: dict[str, list[str]]) -> bool:
      """DFS từ new_dep_id; True nếu đến được task_id (tức là cycle)."""
      visited = set()
      stack = [new_dep_id]
      while stack:
          node = stack.pop()
          if node == task_id:
              return True
          if node in visited:
              continue
          visited.add(node)
          stack.extend(adj.get(node, []))
      return False
  ```

- [X] T064 [US4] Thêm add/remove/is_blocked vào `dependency_service.py`:
  ```python
  async def add_dependency(session, task_id: uuid.UUID, depends_on_id: uuid.UUID, project_id: uuid.UUID):
      # 1. Kiểm tra cả hai task thuộc project_id → 404 nếu không
      # 2. load adj: await _load_all_deps(session, project_id)
      # 3. _has_cycle(str(task_id), str(depends_on_id), adj) → raise HTTPException(409, "Circular dependency")
      # 4. session.add(TaskDependency(task_id=task_id, depends_on_task_id=depends_on_id))
      # 5. check if depends_on task NOT done → task.is_blocked = True; flush

  async def remove_dependency(session, task_id: uuid.UUID, dep_id: uuid.UUID):
      # DELETE TaskDependency WHERE task_id=task_id AND depends_on_task_id=dep_id
      # Recompute is_blocked: is_task_blocked()

  async def is_task_blocked(session, task_id: uuid.UUID) -> bool:
      # Query tất cả TaskDependency WHERE task_id=task_id
      # Với mỗi dep: fetch Task.status; nếu ANY status != "done" → True
      # Else False

  async def get_dependency_graph(session, project_id: uuid.UUID) -> dict:
      # Trả {"nodes": [{id, title, status}], "edges": [{from, to}]}
  ```

- [X] T065 [US4] Thêm unlock_dependents vào `dependency_service.py`:
  ```python
  async def unlock_dependents(session, completed_task_id: uuid.UUID) -> list[uuid.UUID]:
      """Gọi sau khi task move to DONE. Trả list task IDs vừa được unblock."""
      # 1. Query: SELECT task_id FROM task_dependencies WHERE depends_on_task_id=completed_task_id
      # 2. Với mỗi dependent task_id:
      #    - blocked = await is_task_blocked(session, task_id)
      #    - Nếu not blocked VÀ task.is_blocked == True: set task.is_blocked = False; append to unlocked
      # 3. await session.flush()
      # 4. return unlocked list
  ```

- [X] T066 [P] [US4] Tạo `backend/app/schemas/dependency.py`:
  ```python
  # DependencyCreate(depends_on_task_id: UUID)
  # DependencyResponse(task_id, depends_on_task_id, created_at) — from_attributes=True
  # DependencyGraphResponse(nodes: list[dict], edges: list[dict])
  ```

- [X] T067 [P] [US4] Tạo `backend/app/api/v1/dependencies.py`:
  ```python
  router = APIRouter(prefix="/projects", tags=["dependencies"])

  # GET /projects/{project_id}/tasks/{task_id}/dependencies
  #   guard: require_any_member; trả {blocks: list[Task], depends_on: list[Task]}

  # POST /projects/{project_id}/tasks/{task_id}/dependencies
  #   guard: require_developer_or_above
  #   body: DependencyCreate; gọi dependency_service.add_dependency()

  # DELETE /projects/{project_id}/tasks/{task_id}/dependencies/{dep_id}
  #   guard: require_developer_or_above; gọi remove_dependency()

  # GET /projects/{project_id}/dependency-graph
  #   guard: require_any_member; gọi get_dependency_graph()
  ```
  Đăng ký trong `main.py`: `from app.api.v1.dependencies import router as deps_router`

- [X] T068 [US4] **Update** `backend/app/services/kanban_service.py` — unlock sau approve:
  ```python
  # Trong approve_task() (hoặc tương đương khi task → DONE):
  # Sau khi task.status = TaskStatus.DONE:
  from app.services import dependency_service
  unlocked_ids = await dependency_service.unlock_dependents(session, task_id)
  # Với mỗi uid: log info; notification sẽ thêm ở T103
  ```

---

### Frontend: Blocked Badge & DAG

- [X] T069 [P] [US4] Tạo `frontend/src/services/dependency-api.ts`:
  ```typescript
  import { api } from './api'
  // getDeps(projectId, taskId) → GET /api/v1/projects/{pid}/tasks/{tid}/dependencies
  // addDep(projectId, taskId, dependsOnId) → POST ... body: {depends_on_task_id}
  // removeDep(projectId, taskId, depId) → DELETE .../dependencies/{depId}
  // getGraph(projectId) → GET /api/v1/projects/{pid}/dependency-graph
  ```

- [X] T070 [P] [US4] Tạo `frontend/src/components/molecules/dependency-badge.tsx`:
  ```typescript
  // Props: blockedByTitles: string[]
  // Nếu rỗng: không render
  // Badge: "🔒 Blocked (N)" với bg-red-100 text-red-700
  // Tooltip (hover): danh sách tối đa 3 tên + "..." nếu nhiều hơn
  ```

- [X] T071 [US4] **Update** `frontend/src/components/molecules/task-card.tsx` — blocked state:
  ```typescript
  // Nếu task.is_blocked:
  //   - Render <DependencyBadge blockedByTitles={blockedByTitles ?? []} />
  //   - Thêm class opacity-60 cursor-not-allowed vào card wrapper
  //   - draggable={false}
  //   - Ẩn Start button
  ```

- [X] T072 [US4] **Update** `frontend/src/components/organisms/kanban-board.tsx` — kiểm tra blocked khi drag:
  ```typescript
  // Trong onDragEnd handler (từ useKanban):
  // Trước khi gọi startTask(): kiểm tra task.is_blocked → toast "Task đang bị blocked" + return
  // Hoặc trong useKanban.startTask(): thêm check columns.todo.find(t => t.id === taskId)?.is_blocked
  ```

- [X] T073 [US4] Tạo `frontend/src/components/organisms/dependency-graph.tsx` — SVG DAG:
  ```typescript
  // Props: projectId: string
  // Fetch graph data khi mount: getGraph(projectId)
  // Render SVG 900x500:
  //   Column layout: todo x=100, in_progress x=300, review x=500, done x=700
  //   Node: <rect> 120x40, màu theo status (gray/blue/yellow/green), text truncated 15 chars
  //   Edges: <line> + arrowhead với <defs><marker id="arrow">
  //   Loading spinner khi fetch
  ```

- [X] T074 [US4] **Update** `frontend/src/pages/project-workspace.tsx` — thêm Dependencies tab:
  ```typescript
  // Thêm "dependencies" vào activeTab state type và tab navigation
  // Thêm trong body section:
  //   {activeTab === 'dependencies' && <DependencyGraph projectId={currentProject.id} />}
  // Thêm form nhỏ thêm/xóa dependency trong DependencyGraph component hoặc tách riêng
  ```

**Checkpoint Phase 6**: B depends A → badge đỏ + drag blocked. Approve A → B unblocked. Cycle → 409. DAG SVG render. Dependencies tab.

---

## Phase 7: User Story 5 — Task Templates

**Goal**: Lưu template từ task; dropdown chọn template khi tạo task.

---

### Backend: Template Service & API

- [X] T075 [US5] Tạo `backend/app/services/template_service.py`:
  ```python
  from app.models.task_template import TaskTemplate, TemplateScope
  from sqlalchemy import select, or_
  import uuid

  async def list_templates(session, project_id: uuid.UUID, scope: str | None = None):
      # scope=None → cả global và project
      # scope="global" → chỉ global
      # scope="project" → chỉ project này
      where = []
      if scope == "global":
          where.append(TaskTemplate.scope == TemplateScope.GLOBAL)
      elif scope == "project":
          where.append(TaskTemplate.project_id == project_id)
      else:
          where.append(or_(TaskTemplate.scope == TemplateScope.GLOBAL, TaskTemplate.project_id == project_id))
      return (await session.scalars(select(TaskTemplate).where(*where))).all()

  async def create_template(session, data, created_by: uuid.UUID) -> TaskTemplate:
      # Check name conflict trong project scope: SELECT WHERE project_id=data.project_id AND name=data.name
      # → 409 nếu đã tồn tại
      t = TaskTemplate(**data.model_dump(), created_by=created_by)
      session.add(t); await session.flush(); return t

  async def delete_template(session, template_id: uuid.UUID, current_user_id: uuid.UUID):
      # Fetch template; 404 nếu không có
      # Check: template.created_by == current_user_id HOẶC leader/owner → 403 nếu không đủ quyền
      await session.delete(template); await session.flush()
  ```

- [X] T076 [P] [US5] Tạo `backend/app/schemas/template.py`:
  ```python
  from typing import Literal
  class TemplateCreate(BaseModel):
      name: str
      title_template: str
      description_template: str
      scope: Literal["project", "global"]
      project_id: UUID | None = None

  class TemplateResponse(BaseModel):
      model_config = ConfigDict(from_attributes=True)
      id: UUID; name: str; title_template: str; description_template: str
      scope: str; project_id: UUID | None; created_by: UUID; created_at: datetime
  ```

- [X] T077 [P] [US5] Tạo `backend/app/api/v1/templates.py`:
  ```python
  router = APIRouter(prefix="/templates", tags=["templates"])
  # GET /templates?scope=&project_id= → auth required (get_current_user); gọi list_templates
  # POST /templates → auth required; gọi create_template
  # DELETE /templates/{id} → auth required; gọi delete_template
  ```
  Đăng ký trong `main.py`.

---

### Frontend: Template Selector

- [X] T078 [P] [US5] Tạo `frontend/src/services/template-api.ts`:
  ```typescript
  import { api } from './api'
  export async function listTemplates(scope?: string, projectId?: string) {
    const params: Record<string, string> = {}
    if (scope) params.scope = scope
    if (projectId) params.project_id = projectId
    const res = await api.get('/api/v1/templates', { params })
    return res.data as TemplateResponse[]
  }
  // createTemplate(data), deleteTemplate(id)
  ```

- [X] T079 [US5] Tạo `frontend/src/components/molecules/template-selector.tsx`:
  ```typescript
  // Props: projectId: string, onSelect(title: string, description: string): void
  // Mount: fetch global + project templates với Promise.all()
  // Render: <select> với 2 optgroups (Global / Project này)
  // onChange: tìm template → onSelect(title_template, description_template)
  // Không render nếu danh sách rỗng
  ```

- [X] T080 [US5] **Update** task creation form trong `project-workspace.tsx` hoặc task creation modal — thêm TemplateSelector:
  ```typescript
  // Tìm nơi nhập title + description khi tạo task mới
  // Thêm <TemplateSelector projectId={projectId} onSelect={(t, d) => { setTitle(t); setDesc(d) }} />
  // trước input title
  ```

- [X] T081 [US5] Thêm "Lưu làm template" trong task detail view:
  ```typescript
  // Modal nhỏ: name input + scope select (project/global)
  // Gọi: createTemplate({ name, title_template: task.title, description_template: task.description, scope, project_id })
  // Toast success sau khi tạo
  ```

**Checkpoint Phase 7**: Template global thấy ở mọi project. Template project chỉ thấy trong project đó. Chọn template → fields điền sẵn.

---

## Phase 8: User Story 6 — Team Dashboard & Analytics

**Goal**: Dashboard đa-project với task counts; Analytics với Recharts charts.

---

### Backend: Analytics Service & API

- [X] T082 [US6] Tạo `backend/app/services/analytics_service.py` — dashboard data:
  ```python
  # get_dashboard_data(session, user_id: UUID) -> dict:
  #   1. Query projects qua ProjectMember JOIN Project WHERE user_id=user_id
  #   2. Với mỗi project:
  #      - task counts: SELECT status, count(*) FROM tasks WHERE project_id GROUP BY status
  #      - stale: SELECT * FROM tasks WHERE project_id AND status='review' AND updated_at < now()-24h
  #      - member_count: SELECT count(*) FROM project_members WHERE project_id
  #   3. Trả {"projects": [{id, name, task_counts: {todo:N, ...}, stale_count:N, member_count:N}]}
  ```

- [X] T083 [US6] Thêm get_project_analytics vào `analytics_service.py`:
  ```python
  # get_project_analytics(session, project_id, from_dt, to_dt) -> dict:
  # 4 sub-queries:
  # 1. by_backend: SELECT agent_type, avg(extract(epoch from completed_at-started_at)) as avg_seconds,
  #    count(*) FILTER(WHERE status='success') / count(*) as first_approve_rate
  #    FROM agent_runs WHERE project_id AND started_at BETWEEN from_dt AND to_dt
  #    GROUP BY agent_type
  # 2. by_member: SELECT u.display_name, count(t.id) FILTER(WHERE t.status='done') as tasks_done,
  #    count(t.id) FILTER(WHERE t.status='in_progress') as tasks_in_progress
  #    FROM tasks t JOIN users u ON t.assigned_to=u.id WHERE t.project_id GROUP BY u.id
  # 3. reviewer_avg_score: SELECT avg(score) FROM review_reports WHERE task_id IN (SELECT id FROM tasks WHERE project_id)
  #    AND status='complete' AND created_at BETWEEN from_dt AND to_dt
  # 4. error_breakdown: SELECT action_type, count(*) FROM audit_logs WHERE project_id AND result='failure' GROUP BY action_type
  ```

- [X] T084 [P] [US6] Tạo `backend/app/schemas/analytics.py`:
  ```python
  class BackendMetric(BaseModel): agent_type: str; avg_seconds: float; first_approve_rate: float; error_count: int
  class MemberMetric(BaseModel): display_name: str; tasks_done: int; tasks_in_progress: int
  class ProjectDashboard(BaseModel): id: UUID; name: str; task_counts: dict; stale_count: int; member_count: int
  class DashboardResponse(BaseModel): projects: list[ProjectDashboard]
  class AnalyticsResponse(BaseModel): period: str; by_backend: list[BackendMetric]; by_member: list[MemberMetric]; reviewer_avg_score: float | None; error_breakdown: list[dict]
  ```

- [X] T085 [P] [US6] Tạo `backend/app/api/v1/analytics.py`:
  ```python
  # GET /dashboard → current_user required; gọi get_dashboard_data(session, current_user.id)
  # GET /projects/{id}/analytics?range=7d|30d|custom&from_date=&to_date=
  #   guard: require_leader_or_above
  #   parse range: "7d"→last 7 days, "30d"→last 30 days, "custom"→from_date/to_date params
  #   gọi get_project_analytics(session, project_id, from_dt, to_dt)
  ```
  Đăng ký trong `main.py`.

---

### Frontend: Dashboard & Analytics Pages

- [X] T086 [P] [US6] Tạo `frontend/src/services/analytics-api.ts`:
  ```typescript
  import { api } from './api'
  export async function getDashboard() {
    return (await api.get('/api/v1/dashboard')).data as DashboardResponse
  }
  export async function getProjectAnalytics(projectId: string, range: '7d'|'30d'|'custom', fromDate?: string, toDate?: string) {
    const params: Record<string, string> = { range }
    if (fromDate) params.from_date = fromDate
    if (toDate) params.to_date = toDate
    return (await api.get(`/api/v1/projects/${projectId}/analytics`, { params })).data as AnalyticsResponse
  }
  ```

- [X] T087 [US6] Tạo `frontend/src/pages/dashboard.tsx`:
  ```typescript
  // Import: getDashboard, AuthGuard (hoặc useAuth check), Link từ react-router-dom
  // Mount: fetch getDashboard()
  // Layout: grid-cols-1 md:grid-cols-2 lg:grid-cols-3
  // Card mỗi project:
  //   - Project name + primary_language badge
  //   - Task count pills (4 màu: blue=todo, yellow=in_progress, orange=review, green=done)
  //   - Stale warning (đỏ) nếu stale_count > 0
  //   - Member count text
  //   - Link tới /projects/{id}
  // Loading skeleton (3 gray cards với animate-pulse) khi loading
  // Empty state: "Chưa có project nào" + Link tới /projects khi projects.length === 0
  ```

- [X] T088 [US6] Tạo `frontend/src/pages/analytics.tsx`:
  ```typescript
  // Import từ recharts: BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, PieChart, Pie, Cell
  // Props: useParams để lấy projectId
  // State: range '7d'|'30d'|'custom'; fromDate/toDate nếu custom
  // Fetch: getProjectAnalytics() khi range/dates thay đổi
  // Render:
  //   - Range picker buttons (7d / 30d / Custom)
  //   - Custom: 2 date inputs
  //   - BarChart 500x250: avg_seconds per backend
  //   - PieChart: first_approve_rate per backend
  //   - Member table: Avatar + display_name + tasks_done + tasks_in_progress
  //   - Error breakdown: colored badges
  ```

- [X] T089 [US6] **Update** `frontend/src/App.tsx` — thêm routes mới:
  ```typescript
  // Thêm imports:
  import Dashboard from './pages/dashboard'
  import Analytics from './pages/analytics'
  // Trong Routes, thêm:
  // <Route path="/dashboard" element={<AuthGuard><Dashboard /></AuthGuard>} />
  // <Route path="/projects/:projectId/analytics" element={<AuthGuard><Analytics /></AuthGuard>} />
  // Đổi route "/" redirect về "/dashboard" thay vì "/projects"
  ```

**Checkpoint Phase 8**: Login → `/dashboard` thay vì `/projects`. Project cards với task counts. Analytics charts render. Viewer → analytics → 403.

---

## Phase 9: User Story 7 — Notifications & Webhooks

**Goal**: In-app notifications với bell icon; webhook delivery + retry; GitHub PR integration.

---

### Backend: Notification Service

- [X] T090 [US7] Tạo `backend/app/services/notification_service.py` — phần 1:
  ```python
  from app.models.notification import Notification, NotificationType
  from app.models.project_member import ProjectMember, ProjectRole
  from sqlalchemy import select

  async def create_notification(session, user_id, type: NotificationType, content: str,
                                 reference_type: str | None = None, reference_id: str | None = None) -> Notification:
      n = Notification(user_id=user_id, type=type, content=content,
                       reference_type=reference_type, reference_id=reference_id)
      session.add(n); await session.flush(); return n

  async def notify_task_assigned(session, task, assigned_to_user_id):
      await create_notification(session, assigned_to_user_id, NotificationType.TASK_ASSIGNED,
                                f"Bạn được giao task: {task.title}",
                                reference_type="task", reference_id=str(task.id))

  async def notify_task_needs_review(session, task):
      # Query Leader + Owner của project:
      members = await session.scalars(
          select(ProjectMember).where(
              ProjectMember.project_id == task.project_id,
              ProjectMember.role.in_([ProjectRole.OWNER, ProjectRole.LEADER])
          )
      )
      for m in members.all():
          await create_notification(session, m.user_id, NotificationType.TASK_NEEDS_REVIEW,
                                    f"Task cần review: {task.title}", "task", str(task.id))
  ```

- [X] T091 [US7] Thêm get/mark vào `notification_service.py`:
  ```python
  async def notify_agent_error(session, task): ...  # tương tự notify_task_needs_review nhưng type=AGENT_ERROR
  async def notify_task_unblocked(session, task, user_id): ...  # notify assignee
  async def get_notifications(session, user_id, unread_only=False, limit=20, offset=0) -> tuple[int, list]:
      # count total unread; query với optional WHERE is_read=False; return (total_unread, items)
  async def mark_read(session, notif_id, user_id): ...  # check ownership; set is_read=True
  async def mark_all_read(session, user_id) -> int: ...  # UPDATE; return rowcount
  ```

- [X] T092 [P] [US7] Tạo `backend/app/schemas/notification.py`:
  ```python
  class NotificationResponse(BaseModel):
      model_config = ConfigDict(from_attributes=True)
      id: UUID; type: str; content: str
      reference_type: str | None; reference_id: str | None
      is_read: bool; created_at: datetime

  class NotificationListResponse(BaseModel):
      total_unread: int; items: list[NotificationResponse]
  ```

- [X] T093 [P] [US7] Tạo `backend/app/api/v1/notifications.py`:
  ```python
  # GET /notifications?unread_only=false&limit=20&offset=0 → NotificationListResponse
  # PATCH /notifications/{id}/read → {"ok": true}
  # POST /notifications/read-all → {"marked": N}
  # guard: get_current_user
  ```
  Đăng ký trong `main.py`.

---

### Backend: Webhook Service

- [X] T094 [US7] Tạo `backend/app/services/webhook_service.py` — phần 1 (sign + deliver):
  ```python
  import hmac, hashlib, json
  import httpx
  from app.models.webhook import WebhookConfig, WebhookDelivery

  def _sign_payload(payload_bytes: bytes, secret: str) -> str:
      sig = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
      return f"sha256={sig}"

  async def _deliver_once(delivery_id, session) -> tuple[bool, int | None]:
      # Fetch delivery + config (selectinload)
      # Build payload_bytes = json.dumps(delivery.payload).encode()
      # headers = {"Content-Type": "application/json", "X-NeoKanban-Event": delivery.event_type}
      # if config.secret: headers["X-NeoKanban-Signature"] = _sign_payload(payload_bytes, config.secret)
      # async with httpx.AsyncClient(timeout=10) as client:
      #   resp = await client.post(config.url, content=payload_bytes, headers=headers)
      # return (resp.status_code < 400, resp.status_code)
      # except httpx.RequestError: return (False, None)
  ```

- [X] T095 [US7] Thêm enqueue_delivery vào `webhook_service.py`:
  ```python
  async def enqueue_delivery(session, project_id, event_type: str, payload: dict):
      # Query WebhookConfig WHERE project_id AND enabled=True AND event_type IN events array
      # Với mỗi config: tạo WebhookDelivery(status="pending", event_type, payload)
      # flush để get ID
      # redis = await aioredis.from_url(settings.redis_url)
      # await redis.rpush("webhook_queue", str(delivery.id))
  ```

- [X] T096 [US7] Thêm process_deliveries worker vào `webhook_service.py`:
  ```python
  async def process_deliveries():
      RETRY_DELAYS = [0, 5, 30]  # seconds trước mỗi attempt
      while True:
          # redis.blpop("webhook_queue", timeout=30) → (queue_name, delivery_id_bytes)
          # Nếu None (timeout): continue
          # Loop 3 lần:
          #   await asyncio.sleep(RETRY_DELAYS[attempt])
          #   success, status = await _deliver_once(delivery_id, session)
          #   update delivery.attempts, last_attempt_at, http_status
          #   if success: status="success"; break
          # if not success after 3: status="failed"
          # commit; except all silently; continue
  ```

- [X] T097 [P] [US7] Thêm test_webhook vào `webhook_service.py`:
  ```python
  async def test_webhook(session, webhook_id) -> dict:
      # Fetch config; 404 nếu không có
      # payload = {"event": "webhook.test", "timestamp": datetime.utcnow().isoformat()}
      # _deliver_once_direct(config, payload): gửi trực tiếp không qua DB
      # Đo elapsed_ms; trả {"delivered": bool, "http_status": N, "response_time_ms": N}
  ```

---

### Backend: Webhook & GitHub APIs

- [X] T098 [P] [US7] Tạo `backend/app/schemas/webhook.py`:
  ```python
  class WebhookCreate(BaseModel): url: str; secret: str | None = None; events: list[str]
  class WebhookResponse(BaseModel):
      model_config = ConfigDict(from_attributes=True)
      id: UUID; url: str; events: list[str]; enabled: bool; created_at: datetime
  class TestWebhookResponse(BaseModel): delivered: bool; http_status: int | None; response_time_ms: int
  ```

- [X] T099 [P] [US7] Tạo `backend/app/api/v1/webhooks.py`:
  ```python
  router = APIRouter(prefix="/projects", tags=["webhooks"])
  # GET /projects/{id}/webhooks → require_any_member
  # POST /projects/{id}/webhooks → require_leader_or_above; gọi session.add(WebhookConfig(...))
  # PATCH /projects/{id}/webhooks/{wid} → toggle enabled / update events
  # DELETE /projects/{id}/webhooks/{wid} → require_leader_or_above
  # POST /projects/{id}/webhooks/{wid}/test → gọi webhook_service.test_webhook()
  ```
  Đăng ký trong `main.py`.

- [X] T100 [P] [US7] Tạo `backend/app/services/github_service.py`:
  ```python
  from cryptography.fernet import Fernet
  from github import Github, GithubException
  from app.config import settings

  def encrypt_pat(pat: str) -> str:
      return Fernet(settings.fernet_key).encrypt(pat.encode()).decode()

  def decrypt_pat(encrypted: str) -> str:
      return Fernet(settings.fernet_key).decrypt(encrypted.encode()).decode()

  async def validate_config(repo_full_name: str, pat: str) -> bool:
      try:
          Github(pat).get_repo(repo_full_name)
          return True
      except GithubException:
          return False
  ```

- [X] T101 [P] [US7] Thêm create_pull_request vào `github_service.py`:
  ```python
  async def create_pull_request(config, task, diff_content: str, branch_name: str) -> str:
      pat = decrypt_pat(config.pat_encrypted)
      repo = Github(pat).get_repo(config.repo_full_name)
      pr = repo.create_pull(
          title=task.title,
          body=f"## {task.title}\n\n{task.description}\n\n```diff\n{diff_content[:3000]}\n```",
          head=branch_name,
          base=config.default_base_branch,
      )
      return pr.html_url
  ```

- [X] T102 [P] [US7] Tạo `backend/app/api/v1/github.py`:
  ```python
  # GET /projects/{id}/github → require_any_member; 404 nếu chưa config
  # PUT /projects/{id}/github → require_owner; validate PAT trước (validate_config()); 422 nếu fail
  #   encrypt PAT; upsert GitHubConfig (SELECT existing or INSERT new)
  ```
  Đăng ký trong `main.py`.

---

### Backend: Kanban Integration (Notifications + Webhooks)

- [X] T103 [US7] **Update** `backend/app/services/kanban_service.py` — notification calls:
  ```python
  from app.services import notification_service
  # Sau task.status = TaskStatus.REVIEW:
  #   try: await notification_service.notify_task_needs_review(session, task)
  #   except Exception: logger.exception(...)

  # Sau task.assigned_to update:
  #   try: await notification_service.notify_task_assigned(session, task, new_user_id)
  #   except Exception: logger.exception(...)
  ```

- [X] T104 [US7] Thêm webhook calls vào `kanban_service.py`:
  ```python
  from app.services import webhook_service

  def _build_webhook_payload(event: str, task, actor: dict) -> dict:
      return {
          "event": event,
          "timestamp": datetime.now(timezone.utc).isoformat(),
          "project": {"id": str(task.project_id)},
          "task": {"id": str(task.id), "title": task.title},
          "actor": actor,
      }

  # Sau task.status = REVIEW: await webhook_service.enqueue_delivery(session, project_id, "task.needs_review", payload)
  # Sau task.status = DONE: await webhook_service.enqueue_delivery(session, project_id, "task.done", payload)
  # Wrap trong try/except để không block task
  ```

- [X] T105 [US7] Thêm GitHub PR integration vào `kanban_service.py` — trong approve_task sau DONE:
  ```python
  from app.models.github_config import GitHubConfig
  from app.services import github_service
  # Trong approve_task() sau task.status = DONE:
  # config = await session.scalar(select(GitHubConfig).where(GitHubConfig.project_id == task.project_id, GitHubConfig.enabled == True))
  # if config:
  #   try:
  #     diff = await DiffService.get_latest_approved_for_task(session, task.id, task.project_id)
  #     branch = ... # fetch branch name từ task_branches
  #     pr_url = await github_service.create_pull_request(config, task, diff.content, branch)
  #     logger.info("GitHub PR created: %s", pr_url)
  #   except Exception: logger.exception("GitHub PR creation failed task_id=%s", task.id)
  ```

- [X] T106 [US7] **Update** `backend/app/main.py` — webhook worker startup/shutdown:
  ```python
  from app.services import webhook_service
  import asyncio

  _webhook_worker: asyncio.Task | None = None

  @asynccontextmanager
  async def lifespan(_app: FastAPI):
      global _webhook_worker
      _webhook_worker = asyncio.create_task(webhook_service.process_deliveries())
      logger.info("Webhook delivery worker started")
      yield
      if _webhook_worker:
          _webhook_worker.cancel()
          await asyncio.gather(_webhook_worker, return_exceptions=True)
      await dispose_engine()
  ```

---

### Frontend: Notification Panel

- [X] T107 [P] [US7] Tạo `frontend/src/services/notification-api.ts`:
  ```typescript
  import { api } from './api'
  export interface NotificationListResponse {
    total_unread: number
    items: NotificationItem[]
  }
  export async function getNotifications(params?: { unread_only?: boolean; limit?: number }) {
    return (await api.get<NotificationListResponse>('/api/v1/notifications', { params })).data
  }
  export async function markRead(id: string) { await api.patch(`/api/v1/notifications/${id}/read`) }
  export async function markAllRead() { return (await api.post<{ marked: number }>('/api/v1/notifications/read-all')).data }
  ```

- [X] T108 [P] [US7] Tạo `frontend/src/components/atoms/notification-badge.tsx`:
  ```typescript
  export function NotificationBadge({ count }: { count: number }) {
    if (count <= 0) return null
    return (
      <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
        {count > 99 ? '99+' : count}
      </span>
    )
  }
  ```

- [X] T109 [US7] Tạo `frontend/src/components/molecules/notification-panel.tsx`:
  ```typescript
  // timeAgo(isoDate): "2 phút trước" / "3 giờ trước" / "2 ngày trước"
  // TYPE_ICON map: task_assigned→📋, task_needs_review→👁, task_done→✅, agent_error→⚠, task_unblocked→🔓
  // Props: onClose(): void
  // State: items, unreadCount; fetch + poll 30s
  // Render:
  //   Header: "Thông báo" + "Đánh dấu tất cả đã đọc" button
  //   List max-h-80 overflow-y scroll:
  //     mỗi item: icon + content + timeAgo; bg-blue-50 nếu !is_read
  //     click: markRead(id) + navigate tới task nếu reference_type==="task"
  //   Empty state nếu items.length === 0
  //   onClose: click outside hoặc close button
  ```

- [X] T110 [US7] **Update** `frontend/src/components/organisms/project-header.tsx` — wire bell + NotificationPanel:
  ```typescript
  // State: notifOpen: boolean, unreadCount: number
  // useEffect: fetch getNotifications({unread_only: true}) mỗi 30s → set unreadCount
  // Render: button với BellIcon (SVG) + <NotificationBadge count={unreadCount} />
  // onClick bell: setNotifOpen(true)
  // Render NotificationPanel khi open + click-outside handler (useEffect + ref)
  ```

---

### Frontend: Webhook Settings UI

- [X] T111 [P] [US7] Tạo `frontend/src/services/webhook-api.ts`:
  ```typescript
  import { api } from './api'
  export async function listWebhooks(projectId: string) { return (await api.get(`/api/v1/projects/${projectId}/webhooks`)).data }
  export async function createWebhook(projectId: string, data: { url: string; secret?: string; events: string[] }) {
    return (await api.post(`/api/v1/projects/${projectId}/webhooks`, data)).data
  }
  export async function patchWebhook(projectId: string, id: string, data: Partial<{enabled: boolean; events: string[]}>) {
    return (await api.patch(`/api/v1/projects/${projectId}/webhooks/${id}`, data)).data
  }
  export async function deleteWebhook(projectId: string, id: string) { await api.delete(`/api/v1/projects/${projectId}/webhooks/${id}`) }
  export async function testWebhook(projectId: string, id: string) { return (await api.post(`/api/v1/projects/${projectId}/webhooks/${id}/test`)).data }
  ```

- [X] T112 [US7] Tạo `frontend/src/components/organisms/webhook-settings.tsx`:
  ```typescript
  // Props: projectId: string
  // 2 sections:
  // 1. Webhooks:
  //    - List: URL (truncated 40 chars) + events chips + enabled toggle (PATCH enabled)
  //    - Delete button với window.confirm("Xóa webhook này?")
  //    - Add form: URL input (validate starts with https://) + events checkboxes (task.done/task.needs_review/agent.error) + optional secret + Save
  //    - Test button → toast "Đã gửi: {response_time_ms}ms" hoặc "Gửi thất bại"
  // 2. GitHub:
  //    - repo_full_name input (e.g. "owner/repo")
  //    - PAT input type="password" + "Lưu & Validate" button → PUT
  //    - Hiện current config nếu exists; ẩn PAT sau save (chỉ hiện "••••••••")
  ```

- [X] T113 [US7] Tạo `frontend/src/pages/project-settings.tsx`:
  ```typescript
  // Props: useParams() để lấy projectId
  // Tabs: "Members" | "Webhooks & Integrations"
  // Tab Members: <ProjectMembers projectId={projectId} />
  // Tab Webhooks: <WebhookSettings projectId={projectId} />
  // Wrap với AuthGuard
  ```
  Thêm route trong `App.tsx`: `<Route path="/projects/:id/settings" element={<AuthGuard><ProjectSettings /></AuthGuard>} />`
  Thêm Settings link trong `project-header.tsx` → navigate `/projects/{id}/settings`

**Checkpoint Phase 9**: Assign task → GET /notifications trả 1 unread. Bell badge hiện số. Webhook test → delivered toast. Task Done → webhook fired. GitHub config → PAT encrypted.

---

## Phase 10: Polish & Cross-Cutting

- [X] T114 [P] **Update** `frontend/src/services/api-client.ts` — thêm response interceptor:
  ```typescript
  // Thêm vào createApiClient() trả về:
  client.interceptors.response.use(
    (r) => r,
    (err) => {
      if (err.response?.status === 401) {
        // import { setAuthToken } từ './api'
        setAuthToken(null)
        window.location.href = '/login'
      }
      if (err.response?.status === 403) {
        // import { showErrorToast } từ '../lib/toast'
        showErrorToast('Không đủ quyền thực hiện thao tác này')
      }
      if (err.response?.status >= 500) {
        showErrorToast('Lỗi server, vui lòng thử lại sau')
      }
      return Promise.reject(err)
    }
  )
  ```
  **Lưu ý**: api.ts cũng đã có 401 handler — đảm bảo không duplicate logic

- [X] T115 [P] **Update** `frontend/src/pages/dashboard.tsx` — loading skeleton + empty state:
  ```typescript
  // Loading: 3 gray card divs với animate-pulse className khi isLoading
  // Empty: khi projects.length === 0 và !isLoading:
  //   <div className="text-center py-16">
  //     <p>Chưa có project nào</p>
  //     <Link to="/projects">Tạo project đầu tiên →</Link>
  //   </div>
  ```

- [X] T116 [US2] Tạo `frontend/src/pages/accept-invite.tsx`:
  ```typescript
  // import: useParams, useNavigate; acceptInvite từ member-api; showErrorToast
  // useEffect khi mount: acceptInvite(token)
  //   success → navigate('/dashboard', { state: { toast: 'Bạn đã tham gia project' } })
  //   error 410 expired → render "Link đã hết hạn — Liên hệ Owner để lấy link mới"
  //   error 410 used → render "Link đã được sử dụng"
  //   Thêm route trong App.tsx: <Route path="/invitations/:token" element={<AcceptInvite />} />
  ```

- [X] T117 [P] **Update** `frontend/src/components/molecules/notification-panel.tsx` — edge cases:
  ```typescript
  // Empty state: khi items.length === 0: "Không có thông báo nào" với icon 🔔
  // Error state: nếu fetch fail: không hiện error (silent); retry tự động ở poll tiếp theo
  ```

- [X] T118 [P] **Update** `frontend/src/components/organisms/webhook-settings.tsx` — confirm + URL validation:
  ```typescript
  // Delete: window.confirm("Xóa webhook này? Thao tác không thể hoàn tác.") trước api call
  // URL validation trong form: if (!url.startsWith('https://')) setUrlError('URL phải bắt đầu với https://')
  ```

- [X] T119 Kiểm tra `backend/app/main.py` — verify tất cả routers đã được đăng ký:
  ```python
  # Danh sách phải có:
  # auth_router (từ routers/auth.py)
  # members_router (api/v1/members.py)
  # deps_router (api/v1/dependencies.py)
  # templates_router (api/v1/templates.py)
  # notifications_router (api/v1/notifications.py)
  # webhooks_router (api/v1/webhooks.py)
  # github_router (api/v1/github.py)
  # analytics_router (api/v1/analytics.py)
  # Các routers đã có: projects, tasks, review, documents, branches, audit_logs, backends, codebase, pause, agent_runs, dev_auth
  ```

- [X] T120 Smoke test toàn bộ flow:
  ```
  # Backend:
  POST /auth/register → 201
  POST /auth/login → 200 với token
  GET /auth/me → user object
  POST /projects → 201 (auto-add owner member)
  GET /projects → chỉ thấy project của mình
  POST /projects/{id}/members/invite → InvitationResponse với invite_url
  POST /invitations/{token}/accept → AcceptResponse
  GET /projects/{id}/members → 2 members

  # Kanban flow:
  GET /projects/{id}/tasks → grouped by status
  POST /projects/{id}/tasks/{tid}/move (to=in_progress) → agent chạy
  GET /tasks/{tid}/review → ReviewReport
  POST /projects/{id}/tasks/{tid}/approve → task done

  # Features mới:
  GET /notifications → NotificationListResponse
  GET /dashboard → DashboardResponse với project counts
  GET /projects/{id}/analytics?range=7d → AnalyticsResponse
  ```

---

## Dependencies & Execution Order

```
Phase 1 (Setup) → DONE
Phase 2 (Foundational) → DONE
Phase 3 (US1: AI Review) → DONE
Phase 4 (US2: Auth) → T039-T055 — sequential cho backend wiring, parallel cho frontend atoms
Phase 5 (US3: Assign) → sau T043/T044 (auth guards)
Phase 6 (US4: Dependencies) → sau Phase 2 (models đã có)
Phase 7 (US5: Templates) → sau Phase 2
Phase 8 (US6: Dashboard) → sau T046 (auth context)
Phase 9 (US7: Notifs) → sau T046 + T043
Phase 10 (Polish) → sau tất cả
```

### Parallel opportunities trong Phase 4:
```
T040 (member schemas) ──────────────────────── parallel
T047 (auth-api.ts) ────────────────────────── parallel
T052 (member-api.ts) ──────────────────────── parallel
T053 (role-badge.tsx) ─────────────────────── parallel
T039 → T041 → T042 → T043 → T044 (backend sequential, same files)
T046 → T048 → T049 → T050 → T051 (frontend sequential, depends on AuthContext)
```

---

## Notes cho Agent Coder

1. **Import pattern backend**: Luôn dùng `from app.dependencies import get_current_user, require_*` cho code mới — KHÔNG dùng `require_jwt` từ `app.middleware.auth` cho endpoints mới
2. **Import pattern frontend**: Dùng `import { api } from './api'` — `api` đã có auth header injection. KHÔNG tự tạo axios instance mới.
3. **Token storage**: Dùng `getAuthToken()` / `setAuthToken()` từ `services/api.ts` — key là `'neo_kanban_jwt'`
4. **Router registration**: Sau mỗi task tạo router backend, nhớ thêm vào `main.py`
5. **Session pattern**: `async with async_session_maker() as session:` cho background tasks; `session: AsyncSession = Depends(get_db)` cho request handlers
6. **Error pattern**: HTTPException với detail là string; services raise trực tiếp; endpoints propagate
7. **Existing auth flow**: `routers/auth.py` → đang được import làm `auth_router` trong `main.py` → chỉ update nội dung, đừng tạo file mới `api/v1/auth.py`
8. **Dev mode**: `DEV_AUTH_ENABLED=true` vẫn cho phép `/dev/token` để test — giữ nguyên, không xóa
