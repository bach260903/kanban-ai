# Data Model: Platform Expansion — Feature 003

**Date**: 2026-05-20
**Migration target**: `005_platform_expansion`

---

## Bảng Mới

### `project_members`
```sql
CREATE TABLE project_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('owner','leader','developer','viewer')),
    joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, user_id)
);
CREATE INDEX idx_project_members_project ON project_members(project_id);
CREATE INDEX idx_project_members_user ON project_members(user_id);
```

### `invitations`
```sql
CREATE TABLE invitations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    invitee_email VARCHAR(255),          -- NULL nếu invite link không target email cụ thể
    role VARCHAR(20) NOT NULL CHECK (role IN ('leader','developer','viewer')),
    token VARCHAR(64) NOT NULL UNIQUE,   -- random hex, URL-safe
    created_by UUID NOT NULL REFERENCES users(id),
    expires_at TIMESTAMPTZ NOT NULL,     -- created_at + 7 days
    used_at TIMESTAMPTZ,                 -- NULL nếu chưa dùng
    used_by UUID REFERENCES users(id)
);
CREATE INDEX idx_invitations_token ON invitations(token);
CREATE INDEX idx_invitations_project ON invitations(project_id);
```

### `review_reports`
```sql
CREATE TABLE review_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    agent_run_id UUID REFERENCES agent_runs(id),
    score SMALLINT CHECK (score BETWEEN 0 AND 100),
    suggestion VARCHAR(20) CHECK (suggestion IN ('approve','needs_changes')),
    test_runner VARCHAR(50),              -- 'pytest', 'npm_test', 'none'
    test_pass INTEGER DEFAULT 0,
    test_fail INTEGER DEFAULT 0,
    test_error TEXT,                      -- stderr nếu runner crash
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','running','complete','error')),
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);
CREATE INDEX idx_review_reports_task ON review_reports(task_id);
```

### `review_comments`
```sql
CREATE TABLE review_comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    review_report_id UUID NOT NULL REFERENCES review_reports(id) ON DELETE CASCADE,
    file_path VARCHAR(500) NOT NULL,
    line_number INTEGER,                  -- NULL = file-level comment
    content TEXT NOT NULL,
    severity VARCHAR(10) NOT NULL DEFAULT 'info'
        CHECK (severity IN ('info','warning','error'))
);
CREATE INDEX idx_review_comments_report ON review_comments(review_report_id);
```

### `task_dependencies`
```sql
CREATE TABLE task_dependencies (
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    depends_on_task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (task_id, depends_on_task_id),
    CHECK (task_id != depends_on_task_id)   -- self-dependency cấm
);
CREATE INDEX idx_task_deps_task ON task_dependencies(task_id);
CREATE INDEX idx_task_deps_depends_on ON task_dependencies(depends_on_task_id);
```

### `task_templates`
```sql
CREATE TABLE task_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    title_template VARCHAR(255) NOT NULL,
    description_template TEXT NOT NULL DEFAULT '',
    scope VARCHAR(10) NOT NULL DEFAULT 'project'
        CHECK (scope IN ('project','global')),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,  -- NULL nếu global
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, name)
);
```

### `notifications`
```sql
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL,
        -- 'task_assigned', 'task_needs_review', 'agent_error',
        -- 'invite_accepted', 'task_done', 'review_complete'
    content TEXT NOT NULL,               -- display text
    reference_type VARCHAR(20),          -- 'task', 'project', 'invitation'
    reference_id UUID,                   -- FK không enforce (polymorphic)
    is_read BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_notifications_user_unread ON notifications(user_id, is_read)
    WHERE is_read = false;
CREATE INDEX idx_notifications_user ON notifications(user_id, created_at DESC);
```

### `webhook_configs`
```sql
CREATE TABLE webhook_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    secret VARCHAR(100),                 -- HMAC signing secret (optional)
    events TEXT[] NOT NULL DEFAULT '{}', -- ['task.review','task.done','agent.error']
    enabled BOOLEAN NOT NULL DEFAULT true,
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### `webhook_deliveries`
```sql
CREATE TABLE webhook_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    webhook_config_id UUID NOT NULL REFERENCES webhook_configs(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','success','failed','retrying')),
    http_status INTEGER,
    attempts SMALLINT NOT NULL DEFAULT 0,
    last_attempt_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_webhook_deliveries_config ON webhook_deliveries(webhook_config_id);
CREATE INDEX idx_webhook_deliveries_status ON webhook_deliveries(status)
    WHERE status IN ('pending','retrying');
```

### `github_configs`
```sql
CREATE TABLE github_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL UNIQUE REFERENCES projects(id) ON DELETE CASCADE,
    repo_full_name VARCHAR(200) NOT NULL,   -- 'owner/repo'
    pat_encrypted TEXT NOT NULL,            -- AES-256 encrypted PAT
    default_base_branch VARCHAR(100) NOT NULL DEFAULT 'main',
    enabled BOOLEAN NOT NULL DEFAULT true,
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## Bảng Sửa Đổi

### `tasks` — thêm cột
```sql
ALTER TABLE tasks
    ADD COLUMN assigned_to UUID REFERENCES users(id) ON DELETE SET NULL,
    ADD COLUMN is_blocked BOOLEAN NOT NULL DEFAULT false;  -- cache of dependency lock state

CREATE INDEX idx_tasks_assigned_to ON tasks(assigned_to);
```

> `is_blocked` là computed cache — được cập nhật khi dependency status thay đổi.
> Source of truth là `task_dependencies` table.

### `users` — kiểm tra và bổ sung (migration 003 đã tạo bảng này)
```sql
-- Xác nhận migration 003 đã có:
-- id UUID, email VARCHAR UNIQUE, password_hash VARCHAR, display_name VARCHAR,
-- created_at TIMESTAMPTZ, is_active BOOLEAN

-- Bổ sung nếu chưa có:
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ;
```

---

## State Transitions

### Task (mở rộng existing)
```
todo ──────────────────────────────► in_progress (nếu không blocked, WIP per-dev ok)
                                         │
                                         ▼
                                    [coder_node] ──► [reviewer_node] ──► review
                                                                              │
                                         ┌────────────────────────────────────┤
                                         │ reject                  approve    │
                                         ▼                                    ▼
                                    in_progress                            done
                                    (Feedback)
```

### ReviewReport
```
pending ──► running ──► complete
                 └──► error
```

### WebhookDelivery
```
pending ──► retrying ──► success
                └──────────────► failed (after 3 attempts)
```

---

## Quan Hệ Chính

```
User ──< ProjectMember >── Project
User ──< Invitation >── Project
Task ──< TaskDependency >── Task (self-referential)
Task ──< ReviewReport ──< ReviewComment
Task ── assigned_to ──► User
Project ──< WebhookConfig ──< WebhookDelivery
Project ── GitHubConfig
User ──< Notification
```

---

## Indexes Cho Analytics

```sql
-- Dùng cho analytics queries
CREATE INDEX idx_agent_runs_project_status ON agent_runs(project_id, status, created_at);
CREATE INDEX idx_agent_runs_backend ON agent_runs(coding_backend, status);
CREATE INDEX idx_tasks_project_status ON tasks(project_id, status, updated_at);
```
