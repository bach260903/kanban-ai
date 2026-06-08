# Kịch bản thực tế — Dự án Todo List CLI

---

## Bước 1 — Đăng ký & đăng nhập

Mở trình duyệt vào `http://localhost:5173/register`, điền:

```
Display name : Le Van Hung
Email        : hung@test.com
Password     : Hung@2024
```

Nhấn **Register**. Terminal backend hiện:
```
[DEV] OTP for hung@test.com: 512847
```

Nhập `512847` → **Verify** → vào trang `/projects`.

---

## Bước 2 — Tạo dự án

Nhấn **New Project**:

```
Project Name : Todo List CLI
Description  : Ứng dụng quản lý công việc chạy trên terminal
Language     : Python
```

Nhấn **Create**.

---

## Bước 3 — Sinh SPEC

Vào tab **Documents**, gõ vào ô Intent:

```
Build a command-line todo list app in Python.
User can: add a task, list all tasks, mark task as done, delete a task.
Tasks are saved to a JSON file so they persist between runs.
Write pytest tests for all commands.
```

Nhấn **Generate SPEC**. Sau ~30 giây:

```markdown
# Todo List CLI — Specification

## Overview
A Python CLI app to manage personal tasks, persisted in tasks.json.

## Functional Requirements
- FR-01: Add task with title
- FR-02: List all tasks (show index, title, status)
- FR-03: Mark task as done by index
- FR-04: Delete task by index
- FR-05: Persist tasks to tasks.json

## Acceptance Criteria
- tasks.json updated after every operation
- Graceful error when index out of range
- All commands covered by pytest
```

Badge: **Draft**

---

## Bước 4 — Approve SPEC → sinh PLAN

Nhấn **Approve**. PLAN tự động sinh ra:

```markdown
# Implementation Plan

## Phase 1 — Setup
- Create todo.py with CLI entry point (argparse)
- Create storage.py to read/write tasks.json

## Phase 2 — Commands
- Implement: add, list, done, delete

## Phase 3 — Tests
- Write test_todo.py using pytest and tmp_path fixture
```

Nhấn **Approve PLAN**. Tab Kanban hiện tasks:

```
[ ] Tạo todo.py và argparse CLI
[ ] Tạo storage.py đọc/ghi tasks.json
[ ] Implement lệnh add và list
[ ] Implement lệnh done và delete
[ ] Viết pytest với tmp_path
```

---

## Bước 5 — Chạy AI coder

Kéo task **"Tạo todo.py và argparse CLI"** sang **In Progress**.

Thought stream hiện:

```
[CODER] Starting: Tạo todo.py và argparse CLI
[TOOL]  write_file → todo.py
[TOOL]  write_file → storage.py
        content: load_tasks() / save_tasks()
[TOOL]  run_terminal → python todo.py add "Buy milk"
        result: "Added: Buy milk"
[TOOL]  run_terminal → python todo.py list
        result: "[ ] 1. Buy milk"
[TOOL]  run_terminal → python -m pytest -q
        result: "2 passed"
[DONE]  creating diff...
```

Task sang **Review**.

---

## Bước 6 — Xem diff và duyệt

Tab **Diff**:

```diff
+ # todo.py
+ import argparse
+ from storage import load_tasks, save_tasks
+
+ def main():
+     parser = argparse.ArgumentParser(prog="todo")
+     sub = parser.add_subparsers(dest="command")
+
+     add_p = sub.add_parser("add")
+     add_p.add_argument("title")
+
+     sub.add_parser("list")
+     ...

+ # storage.py
+ import json, os
+
+ FILE = "tasks.json"
+
+ def load_tasks():
+     if not os.path.exists(FILE):
+         return []
+     with open(FILE) as f:
+         return json.load(f)
+
+ def save_tasks(tasks):
+     with open(FILE, "w") as f:
+         json.dump(tasks, f, indent=2)
```

AI Review:
```
Score: 85/100
✓ File persistence works correctly
✓ argparse structure clean
⚠ No error handling when tasks.json is corrupted
```

Nhấn **Approve**. Task → **Done**.

---

## Bước 7 — Reject và yêu cầu sửa

Task **"Implement lệnh done và delete"** đang ở Review. Thấy thiếu kiểm tra index hợp lệ.

Điền feedback:

```
When user runs: python todo.py done 99
(and there are only 2 tasks), the app crashes.
Please add index validation and print a clear error:
"Error: task index 99 does not exist"
```

Nhấn **Reject**. AI chạy lại, diff mới thêm:

```diff
+ def mark_done(index):
+     tasks = load_tasks()
+     if index < 1 or index > len(tasks):
+         print(f"Error: task index {index} does not exist")
+         return
+     tasks[index - 1]["done"] = True
+     save_tasks(tasks)
+     print(f"Done: {tasks[index - 1]['title']}")
```

Nhấn **Approve**. Task → **Done**.

---

## Bước 8 — Pipeline

Tab **Pipelines**:

```
Run #4 — Viết pytest         ● Passed
├─ install   ✓  2s
├─ lint      ✓  1s
├─ test      ✓  4s    (5 passed, 0 failed)
└─ build     ✓  1s
```

Log bước test:
```
test_add_task           PASSED
test_list_tasks         PASSED
test_mark_done          PASSED
test_delete_task        PASSED
test_invalid_index      PASSED
===== 5 passed in 0.31s =====
```

---

## Bước 9 — Webhook

**Settings → Webhooks → New**:

```
URL    : https://webhook.site/hung-todo-123
Events : task.done
```

Nhấn **Test** → `webhook.site` nhận:
```json
{ "event": "test", "project": "Todo List CLI" }
```

Khi approve task thật, nhận:
```json
{
  "event": "task.done",
  "task_title": "Viết pytest với tmp_path",
  "project": "Todo List CLI"
}
```

---

## Bước 10 — Discord Bot

```
/tiendo  →  Todo List CLI

📊 Todo List CLI
✅ Done       : 3
👀 Review     : 1
⚙️  In Progress: 1
📋 Todo       : 0
Tiến độ: 3/5 (60%)
```

```
/ask  →  "lệnh nào để xoá task?"

→ python todo.py delete <index>
  Ví dụ: python todo.py delete 2
  (xoá task số 2 trong danh sách)
```

---

## Bước 11 — Audit Log

```
10:01  hung@test.com   spec_approved          ✓
10:02  hung@test.com   plan_approved          ✓
10:02  system          task_breakdown         ✓  5 tasks created
10:05  hung@test.com   task_move → in_progress  ✓
10:14  system          coder_run              ✓
10:14  hung@test.com   task_diff_approve      ✓
10:20  hung@test.com   task_diff_reject       ✓  feedback sent
10:26  system          coder_rerun            ✓
10:26  hung@test.com   task_diff_approve      ✓
```

---

## Kết quả

| | Tính năng | Kết quả |
|--|-----------|---------|
| | Đăng ký / Đăng nhập | |
| | Tạo dự án | |
| | Sinh SPEC + Approve | |
| | Sinh PLAN + Approve | |
| | Tasks tự tạo trên Kanban | |
| | Coder Agent chạy | |
| | Thought stream hiện | |
| | Diff viewer | |
| | Approve code | |
| | Reject + sửa lại | |
| | Pipeline pass | |
| | Webhook gửi event | |
| | Discord /tiendo /ask | |
| | Audit Log | |
