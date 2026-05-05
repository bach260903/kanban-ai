# ERD sơ bộ (Giai đoạn 1)

```mermaid
erDiagram
  users ||--o{ boards : owns
  users ||--o{ task_assignments : assigned
  users ||--o{ comments : writes
  users ||--o{ activity_log : performs
  users ||--o{ user_skills : has

  boards ||--o{ columns : contains
  boards ||--o{ tasks : contains
  boards ||--o{ activity_log : tracks

  columns ||--o{ tasks : orders

  tasks ||--o{ comments : has
  tasks ||--o{ task_assignments : has
  tasks ||--o{ activity_log : affects

  skills ||--o{ user_skills : tagged

  users {
    uuid id PK
    string email UK
    string hashed_password
    string display_name
    datetime created_at
  }

  boards {
    uuid id PK
    uuid owner_id FK
    string title
    text description
    datetime created_at
  }

  columns {
    uuid id PK
    uuid board_id FK
    string name
    int position
    int wip_limit
  }

  tasks {
    uuid id PK
    uuid board_id FK
    uuid column_id FK
    string title
    text description
    string priority
    datetime due_at
    int position
    datetime created_at
    datetime updated_at
  }

  comments {
    uuid id PK
    uuid task_id FK
    uuid author_id FK
    text body
    datetime created_at
  }

  skills {
    uuid id PK
    string name UK
  }

  user_skills {
    uuid user_id FK
    uuid skill_id FK
    string level
  }

  task_assignments {
    uuid id PK
    uuid task_id FK
    uuid user_id FK
    datetime assigned_at
  }

  activity_log {
    uuid id PK
    uuid board_id FK
    uuid task_id FK
    uuid actor_id FK
    string action
    json details
    datetime created_at
  }
```

Ghi chú: `task_assignments` có thể gộp vào `tasks.assignee_id` nếu mô hình 1 người/nhiệm vụ; tách bảng giúp mở rộng nhiều người sau này.

## Sẽ mở rộng ở Phase 2 (xem `docs/phase2-database-design.md`)

- Thêm `tasks.estimate_hours`, `tasks.status` (giữ song song với `column.name` để tiện query không-join), `tasks.tags` (JSON list).
- Bảng `task_dependencies (task_id, depends_on_id)` cho Planner sinh kế hoạch có thứ tự.
- Bảng `agent_runs (id, board_id, intent, status, latency_ms, tokens_in, tokens_out, cost_usd, started_at, finished_at)` để đo P50/P95/cost ở Phase 5.
- Bảng `agent_run_steps (run_id, node, input_json, output_json, started_at, finished_at)` — phục vụ trace UI và evaluation.
- Vector collections (ChromaDB): `task_chunks` (text=title+description, metadata={task_id, board_id, status}), `comment_chunks`, `decision_notes`.
- Alembic baseline migration sẽ thay cho `Base.metadata.create_all` ở `main.py`.

