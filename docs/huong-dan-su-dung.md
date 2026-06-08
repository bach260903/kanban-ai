# Hướng dẫn sử dụng Neo Kanban AI — từ đầu đến cuối

> Dự án mẫu: **BMI Calculator** (tính chỉ số cơ thể)  
> Môi trường: `http://localhost:5173`

---

## PHẦN 1 — TẠO TÀI KHOẢN

### Bước 1.1 — Mở trang đăng ký

Mở trình duyệt, truy cập:
```
http://localhost:5173/register
```

Bạn thấy form với 3 ô: **Display name**, **Email**, **Password**.

---

### Bước 1.2 — Điền thông tin

Điền vào form như sau:

```
Display name : Tran Thi Mai
Email        : mai@test.com
Password     : Mai@12345
```

Nhấn nút **Register**.

---

### Bước 1.3 — Xác minh OTP

Hệ thống gửi mã OTP. Vì đang chạy môi trường dev, mã hiện thẳng trong terminal:

```
[DEV] OTP for mai@test.com: 736291
```

Quay lại trình duyệt, nhập `736291` vào ô OTP, nhấn **Verify**.

✅ Tài khoản tạo thành công. Hệ thống tự chuyển sang trang `/projects`.  
Góc trên bên phải hiện tên **Tran Thi Mai**.

---

## PHẦN 2 — TẠO DỰ ÁN

### Bước 2.1 — Tạo dự án mới

Ở trang `/projects`, nhấn nút **+ New Project** (góc trên phải).

Một form hiện ra. Điền:

```
Project Name : BMI Calculator
Description  : Tính chỉ số khối cơ thể (BMI) và phân loại kết quả
Language     : Python
```

Nhấn **Create Project**.

✅ Hệ thống tạo xong và chuyển thẳng vào workspace của dự án.  
Bạn thấy thanh tab phía trên: **Documents · Kanban · Pipelines · Members · Settings**.



## PHẦN 3 — SINH ĐẶC TẢ KỸ THUẬT (SPEC)

### Bước 3.1 — Vào tab Documents

Nhấn tab **Documents**.

Bạn thấy 2 phần: **SPEC** và **PLAN** (cả 2 đang trống).

---

### Bước 3.2 — Nhập ý tưởng dự án

Ở phần SPEC, tìm ô **Intent** (hoặc **Mô tả yêu cầu**), gõ vào:

```
Build a BMI calculator CLI tool in Python.

The user runs:
  python bmi.py --weight 70 --height 175

Output:
  BMI: 22.9 → Normal

Categories:
  Underweight : BMI < 18.5
  Normal      : 18.5 – 24.9
  Overweight  : 25 – 29.9
  Obese       : BMI ≥ 30

Rules:
  - Raise error if weight or height ≤ 0
  - Round BMI to 1 decimal place

Tests:
  - pytest covering all 4 categories + invalid input
```

Nhấn **Generate SPEC**.

---

### Bước 3.3 — Chờ AI sinh SPEC

Một progress bar hoặc spinner xuất hiện. Chờ khoảng **20–40 giây**.

Khi xong, tài liệu SPEC hiện ra với badge màu vàng **Draft**:

```markdown SAMPLE
# BMI Calculator — Specification

## Overview
A Python module to calculate Body Mass Index (BMI) from
weight (kg) and height (cm), returning the numeric value
and a descriptive health category.

## Functional Requirements
- FR-01: Accept weight in kilograms (float)
- FR-02: Accept height in centimeters (float)
- FR-03: Calculate BMI using formula: weight / (height/100)²
- FR-04: Return category "Underweight" when BMI < 18.5
- FR-05: Return category "Normal" when 18.5 ≤ BMI < 25
- FR-06: Return category "Overweight" when 25 ≤ BMI < 30
- FR-07: Return category "Obese" when BMI ≥ 30

## Acceptance Criteria
- BMI rounded to 1 decimal place
- Raise ValueError for non-positive weight or height
- pytest covers all 4 categories and error cases
```

---

### Bước 3.4 — Yêu cầu bổ sung (nếu cần)

Bạn muốn thêm phần nhập liệu từ command line. Tìm ô **Request revision**, gõ:

```
Please also add a CLI interface so users can run:
  python bmi.py --weight 70 --height 175
and see the result printed in the terminal.
```

Nhấn **Submit revision**.

Chờ ~20 giây. SPEC cập nhật thêm:

```markdown SAMPLE
## Functional Requirements (cập nhật)
- FR-08: CLI interface via argparse (--weight, --height flags)
- FR-09: Print result: "BMI: 22.9 → Normal"
```

---

### Bước 3.5 — Duyệt SPEC

Đọc lại SPEC thấy ổn, nhấn **Approve**.

Badge đổi thành màu xanh lá **Approved**.  
Ngay bên dưới, phần PLAN hiện spinner **"Generating..."** — AI đang tự động sinh kế hoạch.

---

## PHẦN 4 — DUYỆT KẾ HOẠCH (PLAN)

### Bước 4.1 — Chờ PLAN sinh xong

Chờ thêm ~30 giây. PLAN.md hiện ra với badge **Draft**:

```markdown SAMPLE
# BMI Calculator — Implementation Plan

## Phase 1: Core Module
- Create bmi.py with function calculate_bmi(weight, height)
- Implement category logic with if/elif chain

## Phase 2: CLI Interface
- Add argparse in bmi.py __main__ block
- Handle invalid input gracefully

## Phase 3: Testing
- Create test_bmi.py
- Test cases: underweight, normal, overweight, obese, invalid input
```

---

### Bước 4.2 — Duyệt PLAN

Nhấn **Approve PLAN**.

✅ Hệ thống tự động tạo tasks trên bảng Kanban.

---

## PHẦN 5 — LÀM VIỆC TRÊN KANBAN

### Bước 5.1 — Xem tasks vừa được tạo

Nhấn tab **Kanban**.

Cột **Todo** hiện 4 tasks:

```
📋 Tạo bmi.py và hàm calculate_bmi()
📋 Implement phân loại BMI (4 categories)
📋 Thêm CLI với argparse
📋 Viết pytest trong test_bmi.py
```

---

### Bước 5.2 — Tạo thêm task thủ công (tuỳ chọn)

Muốn thêm task viết README, nhấn **+ New Task**:

```
Title       : Viết README hướng dẫn sử dụng
Description : Mô tả cách cài đặt và chạy chương trình
Priority    : Low
```

Nhấn **Create**. Task xuất hiện ở cột **Todo**.

---

### Bước 5.3 — Bắt đầu task đầu tiên

Click vào task **"Tạo bmi.py và hàm calculate_bmi()"**.

Trong ô **Assignee**, chọn **Tran Thi Mai**.

Nhấn **Save**.

Kéo task từ cột **Todo** sang cột **In Progress**.

---

## PHẦN 6 — AI CODER TỰ ĐỘNG VIẾT CODE

### Bước 6.1 — Quan sát AI làm việc

Ngay khi kéo task sang In Progress, panel **Thought Stream** xuất hiện bên phải màn hình. Bạn thấy AI đang làm từng bước:

```
[CODER] Task started: Tạo bmi.py và hàm calculate_bmi()
[TOOL]  write_file → bmi.py
        def calculate_bmi(weight: float, height: float) -> tuple[float, str]:
            ...
[TOOL]  run_terminal → python -c "from bmi import calculate_bmi; print(calculate_bmi(70,175))"
        result: (22.9, 'Normal')
[TOOL]  write_file → test_bmi.py
        (basic test)
[TOOL]  run_terminal → python -m pytest test_bmi.py -q
        result: "1 passed in 0.12s"
[DONE]  Diff ready, moving to Review...
```

Quá trình mất khoảng **3–7 phút**.

---

### Bước 6.2 — Task tự chuyển sang Review

Khi AI xong việc, task tự động chuyển sang cột **Review** — bạn không cần làm gì.

Bạn nhận được thông báo (icon chuông 🔔 ở góc phải): *"Task 'Tạo bmi.py...' đã sẵn sàng để review"*.

---

## PHẦN 7 — REVIEW VÀ DUYỆT CODE

### Bước 7.1 — Xem code AI vừa viết

Click vào task đang ở cột **Review**.

Chọn tab **Diff**. Bạn thấy toàn bộ code mới tô màu **xanh lá** (dòng được thêm):

```diff
+ # bmi.py
+
+ def calculate_bmi(weight: float, height: float) -> tuple[float, str]:
+     """Calculate BMI and return (value, category)."""
+     if weight <= 0 or height <= 0:
+         raise ValueError("Weight and height must be positive")
+     bmi = round(weight / (height / 100) ** 2, 1)
+     if bmi < 18.5:
+         category = "Underweight"
+     elif bmi < 25:
+         category = "Normal"
+     elif bmi < 30:
+         category = "Overweight"
+     else:
+         category = "Obese"
+     return bmi, category
```

---

### Bước 7.2 — Xem nhận xét của AI Reviewer

Chọn tab **AI Review**:

```
Score: 91/100

✓ All 4 BMI categories implemented correctly
✓ Input validation with ValueError
✓ Type hints present
✓ Docstring added
⚠ Missing: edge case test for BMI exactly = 18.5 (boundary)
```

---

### Bước 7.3 — Thêm comment vào một dòng code

Bạn muốn nhắc nhở về dòng tính BMI. Trong Diff Viewer, click vào dòng:

```python
bmi = round(weight / (height / 100) ** 2, 1)
```

Một ô comment hiện ra. Nhập:

```
Đây là công thức chuẩn WHO. Giữ nguyên, không sửa.
```

Nhấn **Add Comment**. Comment ghim vào đúng dòng đó.

---

### Bước 7.4 — Duyệt code

Đọc diff xong thấy ổn, nhấn **Approve**.

✅ Task chuyển sang cột **Done**.  
Audit log ghi nhận: `task_diff_approve — SUCCESS`.

---

## PHẦN 8 — TỪ CHỐI VÀ YÊU CẦU SỬA

### Bước 8.1 — Reject task tiếp theo

Task **"Thêm CLI với argparse"** đang ở Review. Xem diff thấy khi nhập sai (ví dụ `--weight abc`) app bị crash thay vì báo lỗi đẹp.

Điền vào ô **Feedback**:

```
When user types:  python bmi.py --weight abc --height 175
The app crashes with a TypeError.
Please catch the error and print:
  "Error: weight and height must be numbers"
Then exit with code 1.
```

Nhấn **Reject**.

---

### Bước 8.2 — AI tự sửa theo feedback

Task quay về **In Progress**. AI nhận feedback và chạy lại.

Thought stream hiện:

```
[CODER] PO feedback received:
        "When user types: python bmi.py --weight abc..."
[TOOL]  edit_file → bmi.py  (thêm try/except trong main())
[TOOL]  run_terminal → python bmi.py --weight abc --height 175
        result: "Error: weight and height must be numbers"
[TOOL]  run_terminal → python -m pytest -q
        result: "3 passed"
[DONE]  Diff ready...
```

Task tự chuyển về **Review**. Diff lần này có thêm:

```diff
+ try:
+     weight = float(args.weight)
+     height = float(args.height)
+ except ValueError:
+     print("Error: weight and height must be numbers")
+     sys.exit(1)
```

Nhấn **Approve**. Task → **Done**.

---

## PHẦN 9 — XEM PIPELINE CI/CD

### Bước 9.1 — Mở tab Pipelines

Nhấn tab **Pipelines**.

Thấy danh sách các lần chạy. Pipeline mới nhất:

```
Run #5 — Thêm CLI với argparse     ● Passed
├─ install     ✓   2s
├─ lint        ✓   1s
├─ test        ✓   3s   (3 passed)
└─ build       ✓   1s
Total: 7s
```

---

### Bước 9.2 — Xem chi tiết log test

Click vào bước **test** trong pipeline:

```
test_bmi_underweight     PASSED
test_bmi_normal          PASSED
test_bmi_obese           PASSED
===== 3 passed in 0.28s =====
```

---

### Bước 9.3 — Khi pipeline thất bại

Nếu thấy pipeline có dấu ✗, click vào run đó.

Ví dụ bước lint lỗi:

```
Run #3 — Implement phân loại BMI   ✗ Failed
├─ install   ✓
└─ lint      ✗   E501 line too long (95 > 79 characters)
```

Mục **AI Failure Analysis**:

```
Root cause: Line 12 in bmi.py exceeds PEP8 max line length (79 chars).
Fix: Break the long string into multiple lines or use a shorter variable name.
```

Nhấn **Re-run** sau khi AI coder tự sửa xong → pipeline pass.

---

## PHẦN 10 — TẠM DỪNG AI VÀ HƯỚNG DẪN THÊM

### Tình huống

AI đang chạy task "Viết pytest". Bạn chợt muốn AI test thêm boundary value (BMI đúng bằng 18.5 và 25.0).

---

### Bước 10.1 — Tạm dừng

Nhấn nút **Pause** trên task đang chạy.

AI dừng. Task hiện badge **Paused**.

---

### Bước 10.2 — Thêm hướng dẫn

Ô **Steering** hiện ra. Gõ vào:

```
Please also test boundary values:
- calculate_bmi(54.5, 171.5) should give BMI=18.5, category="Normal"
- calculate_bmi(69.4, 166.7) should give BMI=25.0, category="Overweight"
```

Nhấn **Resume**.

---

### Bước 10.3 — Xem kết quả

AI tiếp tục, diff bổ sung thêm 2 test case boundary:

```diff
+ def test_boundary_normal_low():
+     bmi, cat = calculate_bmi(54.5, 171.5)
+     assert bmi == 18.5
+     assert cat == "Normal"
+
+ def test_boundary_overweight_low():
+     bmi, cat = calculate_bmi(69.4, 166.7)
+     assert bmi == 25.0
+     assert cat == "Overweight"
```

---

## PHẦN 11 — MỜI THÀNH VIÊN VÀO DỰ ÁN

### Bước 11.1 — Tạo link mời

Nhấn tab **Members**, rồi nhấn **Invite Member**.

Chọn **Copy invite link**. Link trông như:

```
http://localhost:5173/accept-invite?token=eyJhbGciOiJIUzI1...
```

Gửi link cho đồng nghiệp qua Zalo/Telegram.

---

### Bước 11.2 — Đồng nghiệp chấp nhận lời mời

Đồng nghiệp mở link trong trình duyệt (đã đăng nhập tài khoản riêng).

Thấy trang: *"Bạn được mời vào dự án BMI Calculator"*.

Nhấn **Accept Invitation**.

---

### Bước 11.3 — Duyệt yêu cầu tham gia

Bạn (Mai) nhận notification: *"Nguyen Van An muốn tham gia dự án BMI Calculator"*.

Vào tab **Members → Pending**, thấy tên **Nguyen Van An**.

Nhấn **Approve**. An được vào với role **Developer**.

---

## PHẦN 12 — THIẾT LẬP WEBHOOK

### Bước 12.1 — Tạo webhook

Vào **Settings → Webhooks**, nhấn **+ New Webhook**:

```
URL    : https://webhook.site/unique-id-cua-ban
Events : ☑ task.needs_review   ☑ task.done   ☑ agent.error
Active : ON
```

Nhấn **Save**.

---

### Bước 12.2 — Kiểm tra webhook hoạt động

Nhấn **Test** ngay trên webhook vừa tạo.

Mở tab mới vào `https://webhook.site/unique-id-cua-ban`.

Thấy request POST vừa tới:

```json
{
  "event": "test",
  "project_id": "uuid-...",
  "project_name": "BMI Calculator",
  "timestamp": "2026-06-08T10:00:00Z"
}
```

✅ Webhook hoạt động.

---

### Bước 12.3 — Nhận event thật

Khi AI xong task và chuyển sang Review, `webhook.site` tự nhận:

```json
{
  "event": "task.needs_review",
  "task_id": "uuid-...",
  "task_title": "Viết pytest trong test_bmi.py",
  "project_name": "BMI Calculator",
  "timestamp": "2026-06-08T10:35:00Z"
}
```

---

## PHẦN 13 — DISCORD BOT

> Cần cấu hình Discord Bot Token trong file `.env` trước.

### Bước 13.1 — Xem tiến độ nhanh

Trong Discord server, gõ:

```
/tiendo
```

Chọn project **BMI Calculator** từ dropdown autocomplete.

Bot trả lời ngay:

```
📊 BMI Calculator
─────────────────────
✅ Done        : 2 tasks
👀 Review      : 1 task
⚙️  In Progress : 1 task
📋 Todo        : 1 task
─────────────────────
Tiến độ: 2 / 5 (40%)
```

---

### Bước 13.2 — Hỏi AI về dự án

Gõ:

```
/ask
```

Chọn project **BMI Calculator**, nhập câu hỏi:

```
Công thức tính BMI là gì?
```

Bot xử lý ~5 giây, trả lời:

```
Theo SPEC của dự án:
BMI = weight(kg) / (height(m))²
Ví dụ: nặng 70kg, cao 175cm → BMI = 70 / 1.75² = 22.9 → Normal
```

---

### Bước 13.3 — Xem danh sách tasks

Gõ `/tasks` → chọn **BMI Calculator**:

```
📋 BMI Calculator — Tasks
✅ Tạo bmi.py và hàm calculate_bmi()
✅ Thêm CLI với argparse
⚙️  Implement phân loại BMI (4 categories)
👀 Viết pytest trong test_bmi.py
📋 Viết README hướng dẫn sử dụng
```

---

## PHẦN 14 — THÔNG BÁO

### Bước 14.1 — Nhận thông báo

Icon chuông 🔔 ở góc trên phải hiện số đỏ.

Click vào chuông, thấy danh sách:

```
● Task "Viết pytest" đã sẵn sàng review     vừa xong
● Task "Thêm CLI" đã hoàn thành              10 phút trước
● Nguyen Van An vừa tham gia dự án           30 phút trước
```

---

### Bước 14.2 — Đánh dấu đã đọc

Nhấn **Mark all as read**. Số đỏ biến mất, tất cả thông báo chuyển sang màu xám.

---

## PHẦN 15 — XEM LỊCH SỬ THAY ĐỔI

### Bước 15.1 — Mở Audit Log

Nhấn tab **Audit Log**.

Thấy toàn bộ lịch sử từ đầu dự án:

```
Thời gian        Người dùng       Hành động                    Kết quả
──────────────────────────────────────────────────────────────────────
08/06 09:01      mai@test.com     Tạo dự án                    ✓
08/06 09:05      mai@test.com     Duyệt SPEC                   ✓
08/06 09:06      system           Sinh PLAN tự động            ✓
08/06 09:07      mai@test.com     Duyệt PLAN                   ✓
08/06 09:07      system           Tạo 5 tasks từ PLAN          ✓
08/06 09:10      mai@test.com     Chuyển task → In Progress    ✓
08/06 09:17      system           AI coder hoàn thành          ✓
08/06 09:17      mai@test.com     Duyệt code                   ✓
08/06 09:22      mai@test.com     Từ chối code (có feedback)   ✓
08/06 09:28      system           AI coder chạy lại            ✓
08/06 09:28      mai@test.com     Duyệt code                   ✓
```

---

## PHẦN 16 — MEMORY (BỘ NHỚ DỰ ÁN)

### Bước 16.1 — Xem bài học AI ghi lại

Nhấn tab **Memory**.

Sau khi có tasks DONE, hệ thống tự ghi:

```
Entry 1
  Tóm tắt    : BMI module in bmi.py, CLI in __main__ block
  Bài học    : Use (height/100)**2 not height**2 in BMI formula.
               argparse type=float handles conversion automatically.

Entry 2
  Tóm tắt    : Test file test_bmi.py with 5 test cases
  Bài học    : Always test boundary values (18.5, 25.0, 30.0).
               Use pytest.raises(ValueError) for invalid input tests.
```

---

### Bước 16.2 — Thêm ghi chú thủ công

Click **Edit** trên Entry 1, thêm vào ô **Bài học**:

```
If user enters height in meters by mistake (e.g. 1.75 instead of 175),
BMI becomes 22857 — should add a sanity check: height must be > 50.
```

Nhấn **Save**. AI sẽ dùng ghi chú này cho các task tiếp theo.

---

## TỔNG KẾT — TRẠNG THÁI DỰ ÁN SAU KHI CHẠY XONG

Tab Kanban hiển thị:

```
Todo              In Progress       Review              Done
────────────      ───────────       ──────────          ──────────────────────────────
Viết README       (trống)           Viết pytest    →    Tạo bmi.py  ✅
                                                        Phân loại   ✅
                                                        CLI argparse ✅
```

Tab Pipelines:

```
#5  Viết pytest          ✓ Passed   (5 passed)
#4  Thêm CLI argparse    ✓ Passed   (3 passed)
#3  Implement phân loại  ✓ Passed   (re-run after fix)
#2  Tạo bmi.py           ✓ Passed
```

Discord `/tiendo`:

```
Tiến độ: 3 / 5 (60%) — 1 đang review, 1 còn todo
```
