# Kịch bản thực tế — Neo Kanban AI
> Dự án mẫu: **Simple Calculator** bằng Python

---

## 1. Đăng ký tài khoản

Người dùng vào trang đăng ký, điền:

```
Display name : Nguyen Van Minh
Email        : minh@test.com
Password     : Minh@1234
```

Nhấn **Register**.

Mở terminal backend, tìm dòng:
```
[DEV] OTP for minh@test.com: 847392
```

Nhập `847392` vào ô OTP → nhấn **Verify**.

→ Hệ thống chuyển sang trang `/projects`. Góc trên phải hiện tên **Nguyen Van Minh**.

---

## 2. Tạo dự án

Nhấn **New Project**, điền:

```
Project Name : Simple Calculator
Description  : Máy tính Python hỗ trợ 4 phép tính cơ bản
Language     : Python
```

Nhấn **Create**.

→ Vào workspace, thấy các tab: **Documents · Kanban · Pipelines · Members · Settings**.

---

## 3. Sinh SPEC

Vào tab **Documents**, ô **Intent** gõ:

```
Build a simple calculator in Python that supports 
addition, subtraction, multiplication, and division.
Include input validation (e.g. division by zero).
Write pytest tests for all operations.
```

Nhấn **Generate SPEC**.

Chờ ~30 giây. SPEC.md xuất hiện, nội dung trông như sau:

```
# Simple Calculator — Specification

## Overview
A command-line calculator written in Python that performs
the four basic arithmetic operations with input validation.

## Functional Requirements
- FR-01: Add two numbers
- FR-02: Subtract two numbers
- FR-03: Multiply two numbers
- FR-04: Divide two numbers; raise ValueError on division by zero

## Acceptance Criteria
- All operations return correct numeric results
- Division by zero raises a clear error message
- 100% test coverage for all four operations
```

Badge hiện **Draft**.

---

## 4. Yêu cầu sửa SPEC

Thấy thiếu phần xử lý số thực, điền vào ô **Request revision**:

```
Please add support for floating point numbers.
Results should be rounded to 2 decimal places.
```

Nhấn **Submit revision**.

Chờ ~20 giây. SPEC cập nhật thêm:

```
- FR-05: Support float inputs
- FR-06: Round results to 2 decimal places
```

---

## 5. Duyệt SPEC → sinh PLAN tự động

Nhấn **Approve SPEC**.

Badge đổi thành **Approved**. Ngay bên dưới PLAN.md bắt đầu xuất hiện với trạng thái **Generating...**

Sau ~30 giây, PLAN.md hiện ra:

```
# Implementation Plan — Simple Calculator

## Phase 1: Project Setup
- Create calculator.py with Calculator class
- Setup pytest and requirements.txt

## Phase 2: Core Logic
- Implement add(), subtract(), multiply(), divide()
- Add float support and rounding

## Phase 3: Testing
- Write test_calculator.py with pytest
- Cover edge cases: division by zero, negative numbers
```

---

## 6. Duyệt PLAN → task tự động tạo

Nhấn **Approve PLAN**.

Chuyển sang tab **Kanban**. Cột **TODO** tự động có các task:

```
[ ] Khởi tạo project và requirements.txt
[ ] Tạo class Calculator trong calculator.py
[ ] Implement 4 phép tính cơ bản
[ ] Xử lý division by zero và float
[ ] Viết pytest trong test_calculator.py
```

---

## 7. Giao task và chạy AI coder

Click vào task **"Khởi tạo project và requirements.txt"**, chọn **Assignee: Nguyen Van Minh**, nhấn Save.

Kéo task sang cột **In Progress**.

Panel bên phải bắt đầu hiện thought stream của AI:

```
[CODER] Starting task: Khởi tạo project và requirements.txt
[TOOL] write_file → requirements.txt
       content: "pytest==7.4.0\n"
[TOOL] write_file → calculator.py
       content: "class Calculator:\n    pass\n"
[TOOL] run_terminal → pip install -r requirements.txt
       result: "Successfully installed pytest-7.4.0"
[TOOL] run_terminal → python -m pytest -q
       result: "no tests ran"
[DONE] Task complete, creating diff...
```

Task tự chuyển sang cột **Review**.

---

## 8. Xem diff và duyệt code

Click vào task đang ở **Review** → tab **Diff**:

```diff
+ # requirements.txt
+ pytest==7.4.0

+ # calculator.py
+ class Calculator:
+     def add(self, a, b):
+         return round(a + b, 2)
+
+     def subtract(self, a, b):
+         return round(a - b, 2)
+
+     def multiply(self, a, b):
+         return round(a * b, 2)
+
+     def divide(self, a, b):
+         if b == 0:
+             raise ValueError("Cannot divide by zero")
+         return round(a / b, 2)
```

Tab **AI Review** hiện:
```
Score: 88/100
✓ Division by zero handled correctly
✓ Float rounding implemented
⚠ Missing type hints — minor issue
```

Nhấn **Approve**. Task chuyển sang **Done**.

---

## 9. Từ chối và yêu cầu sửa

Task **"Viết pytest"** đang ở Review. Xem diff thấy test chưa cover trường hợp số âm.

Điền vào ô feedback:

```
Missing test cases for negative numbers.
Please add:
- test_add_negative: assert calc.add(-1, -2) == -3
- test_divide_negative: assert calc.divide(-6, 2) == -3.0
```

Nhấn **Reject**.

Task về **In Progress**. AI chạy lại, sau ~3 phút task về Review lần nữa. Diff lần này có thêm:

```diff
+ def test_add_negative():
+     assert calc.add(-1, -2) == -3.0
+
+ def test_divide_negative():
+     assert calc.divide(-6, 2) == -3.0
```

Nhấn **Approve**. Task sang **Done**.

---

## 10. Xem pipeline chạy test tự động

Vào tab **Pipelines**. Thấy pipeline run mới nhất:

```
Run #3 — Viết pytest              ● Passed
├─ install    ✓  3s
├─ lint       ✓  2s
├─ test       ✓  5s   (4 passed, 0 failed)
└─ build      ✓  1s
```

Click vào bước **test** xem log:

```
test_add_positive PASSED
test_subtract PASSED
test_multiply PASSED
test_divide_negative PASSED
===== 4 passed in 0.42s =====
```

---

## 11. Pipeline thất bại và chạy lại

Giả sử task "Implement 4 phép tính" có lỗi syntax, pipeline hiện:

```
Run #2 — Implement 4 phép tính    ✗ Failed
├─ install    ✓  3s
├─ lint       ✗  1s   ← dừng ở đây
└─ ...
```

Mục **AI Failure Analysis**:
```
Root cause: SyntaxError on line 8 of calculator.py
    def multiply(a, b)   ← missing self parameter
Suggested fix: Change to def multiply(self, a, b)
```

Nhấn **Re-run**. Pipeline mới bắt đầu chạy, lần này qua hết.

---

## 12. Tạm dừng AI và hướng dẫn thêm

AI đang chạy task "Implement 4 phép tính". Nhận ra quên dặn AI thêm docstring, nhấn **Pause**.

AI dừng. Điền vào ô steering:

```
Please add docstrings to each method explaining 
what it does and what parameters it takes.
```

Nhấn **Resume**. AI tiếp tục, code sinh ra có thêm:

```python
def add(self, a: float, b: float) -> float:
    """Return the sum of a and b, rounded to 2 decimal places."""
    return round(a + b, 2)
```

---

## 13. Webhook báo ra ngoài

Vào **Settings → Webhooks**, nhấn **New Webhook**:

```
URL    : https://webhook.site/abc-xyz-123
Events : task.needs_review, task.done
Active : ON
```

Nhấn **Test** → mở `webhook.site` thấy request:

```json
{
  "event": "test",
  "project": "Simple Calculator",
  "timestamp": "2026-06-08T10:30:00Z"
}
```

Sau đó khi task thật chuyển sang Review, `webhook.site` nhận:

```json
{
  "event": "task.needs_review",
  "task_id": "uuid-...",
  "task_title": "Viết pytest trong test_calculator.py",
  "project_id": "uuid-..."
}
```

---

## 14. Discord Bot

Trong Discord server, bot đã được thêm vào. Gõ:

```
/tiendo
```
→ chọn project **Simple Calculator**

Bot trả lời:
```
📊 Simple Calculator
──────────────────
✅ Done        : 2
👀 Review      : 1
⚙️  In Progress : 1
📋 Todo        : 1
──────────────────
Tiến độ: 2/5 (40%)
```

Gõ tiếp:
```
/ask  project: Simple Calculator
      question: hàm nào xử lý chia cho 0?
```

Bot trả lời sau ~5 giây:
```
Hàm divide() trong class Calculator (file calculator.py).
Khi b == 0, hàm raise ValueError("Cannot divide by zero").
```

---

## 15. Mời thành viên

Vào **Members → Invite**, copy link:
```
http://localhost:5173/accept-invite?token=eyJhbGci...
```

Gửi link cho đồng nghiệp. Đồng nghiệp mở link, nhấn **Accept**. Xuất hiện trong tab **Pending**. Nhấn **Approve** → đồng nghiệp vào với role **Developer**.

---

## 16. Xem lịch sử (Audit Log)

Vào tab **Audit Log**:

```
2026-06-08 10:05  minh@test.com   spec_approved          ✓ SUCCESS
2026-06-08 10:06  minh@test.com   plan_approved          ✓ SUCCESS
2026-06-08 10:06  system          task_breakdown         ✓ 5 tasks created
2026-06-08 10:10  minh@test.com   task_move → in_progress  ✓ SUCCESS
2026-06-08 10:18  system          coder_run              ✓ SUCCESS
2026-06-08 10:18  minh@test.com   task_diff_approve      ✓ SUCCESS
2026-06-08 10:22  minh@test.com   task_diff_reject       ✓ feedback sent
2026-06-08 10:28  system          coder_rerun            ✓ SUCCESS
2026-06-08 10:28  minh@test.com   task_diff_approve      ✓ SUCCESS
```

---

## 17. Memory — bài học AI ghi lại

Vào tab **Memory**:

```
Entry 1:
  Summary       : Calculator class with 4 operations in calculator.py
  Lessons learned: Always add self parameter in class methods.
                   Use round(result, 2) for float precision.

Entry 2:
  Summary       : pytest setup with fixtures in test_calculator.py
  Lessons learned: Test negative numbers and edge cases, not just happy path.
```

Nhấn **Edit** trên Entry 1, thêm:
```
Also: import pytest at top of test file, not inside test functions.
```
Nhấn **Save**.

---

## Kết quả tổng hợp

| Tính năng | Kết quả |
|-----------|---------|
| Đăng ký / Đăng nhập | |
| Tạo dự án | |
| Sinh SPEC từ intent | |
| Sửa SPEC theo góp ý | |
| Approve SPEC → sinh PLAN | |
| Approve PLAN → tạo tasks | |
| Coder Agent chạy tự động | |
| Thought stream hiển thị | |
| WIP Limit chặn task thứ 2 | |
| Pause / Resume / Steer | |
| Diff viewer hiển thị đúng | |
| Approve code → Done | |
| Reject + AI sửa lại | |
| Pipeline chạy test tự động | |
| AI phân tích lỗi pipeline | |
| Re-run pipeline | |
| Webhook gửi đúng event | |
| Discord /tiendo, /ask | |
| Mời thành viên + duyệt | |
| Audit Log đầy đủ | |
| Memory ghi bài học | |
