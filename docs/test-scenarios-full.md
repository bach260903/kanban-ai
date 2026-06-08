# KỊCH BẢN KIỂM THỬ TOÀN DIỆN — KANBAN-AI

> Chạy theo thứ tự từ trên xuống. Mỗi bước ghi rõ **PASS / FAIL / SKIP**.  
> Môi trường: `http://localhost:5173` (frontend) · `http://localhost:8000` (backend API)

---

## NHÂN VẬT TRONG KỊCH BẢN

| Tên | Vai trò | Tài khoản |
|-----|---------|-----------|
| **Minh** (PO) | Product Owner — duyệt SPEC, PLAN, code | minh@example.com / Test1234! |
| **Hieu** (Dev) | Developer — chạy coder agent, xem pipeline | hieu@example.com / Test1234! |
| **Lan** (Viewer) | Viewer — chỉ xem | lan@example.com / Test1234! |

---

## PHẦN 1 — XÁC THỰC (AUTHENTICATION)

### TC-01: Đăng ký tài khoản mới

**Người dùng:** Minh mở trình duyệt, vào `http://localhost:5173/register`

**Hành động:**
1. Điền `Email: minh@example.com`, `Password: Test1234!`, `Display name: Nguyen Van Minh`
2. Nhấn **Register**
3. Kiểm tra terminal backend → tìm dòng `DEV MODE — Email OTP:` → ghi lại mã 6 số (ví dụ: `382719`)
4. Nhập mã OTP → nhấn **Verify**

**Kết quả mong đợi:**
- Chuyển hướng sang `/projects`
- Hiển thị tên `Nguyen Van Minh` góc trên phải
- Toast "Đăng ký thành công"

`PASS [ ]  FAIL [ ]`

---

### TC-02: Đăng ký tài khoản Dev và Viewer

**Hành động:** Lặp lại TC-01 cho:
- `hieu@example.com` / `Test1234!` / `Tran Van Hieu`
- `lan@example.com` / `Test1234!` / `Le Thi Lan`

`PASS [ ]  FAIL [ ]`

---

### TC-03: Đăng nhập đúng

**Người dùng:** Minh nhấn Logout → vào `/login`

**Hành động:**
1. Điền `minh@example.com` / `Test1234!`
2. Nhấn **Login**

**Kết quả mong đợi:** Vào `/projects`, tên "Nguyen Van Minh" hiển thị

`PASS [ ]  FAIL [ ]`

---

### TC-04: Đăng nhập sai mật khẩu

**Hành động:**
1. Vào `/login`, điền `minh@example.com` / `SaiMatKhau999`
2. Nhấn **Login**

**Kết quả mong đợi:**
- Toast lỗi "Sai email hoặc mật khẩu"
- **Không** được vào trang `/projects`

`PASS [ ]  FAIL [ ]`

---

### TC-05: JWT token tồn tại trong localStorage

**Hành động:**
1. Đăng nhập thành công (TC-03)
2. Mở DevTools → Application → Local Storage → `http://localhost:5173`
3. Kiểm tra có key `token` (hoặc `access_token`)

**Kết quả mong đợi:** Có JWT token dạng `eyJ...`

`PASS [ ]  FAIL [ ]`

---

## PHẦN 2 — QUẢN LÝ DỰ ÁN

### TC-06: Tạo dự án mới

**Người dùng:** Minh đang ở `/projects`

**Hành động:**
1. Nhấn **New Project**
2. Điền:
   - `Project Name: Todo App`
   - `Description: Ứng dụng quản lý công việc đơn giản`
   - `Language: Python`
3. Nhấn **Create**

**Kết quả mong đợi:**
- Chuyển sang workspace với tabs: Documents · Kanban · Pipelines · Deployments · DevOps · Members · Settings · Audit Log

`PASS [ ]  FAIL [ ]`

---

### TC-07: Cập nhật thông tin dự án

**Hành động:**
1. Vào tab **Settings**
2. Đổi `Description: Ứng dụng quản lý công việc với FastAPI + PostgreSQL`
3. Nhấn **Save**

**Kết quả mong đợi:** Toast "Đã lưu", F5 vẫn giữ mô tả mới

`PASS [ ]  FAIL [ ]`

---

### TC-08: Khai báo Constitution (quy tắc dự án)

**Hành động:**
1. Vào tab **Settings** → phần **Constitution**
2. Nhập:
   ```
   ## Quy tắc kỹ thuật
   - Mỗi file tối đa 200 dòng
   - Viết pytest cho mọi endpoint
   - Không dùng thư viện ngoài danh sách đã phê duyệt
   - Đặt tên biến theo snake_case
   ```
3. Nhấn **Save Constitution**

**Kết quả mong đợi:** Nội dung lưu thành công, agent sẽ tuân theo khi sinh code

`PASS [ ]  FAIL [ ]`

---

## PHẦN 3 — QUẢN LÝ THÀNH VIÊN

### TC-09: Tạo link mời thành viên

**Người dùng:** Minh (Owner) ở tab **Members**

**Hành động:**
1. Nhấn **Invite Member**
2. Chọn **Copy invite link** (không nhập email cụ thể)
3. Sao chép link dạng `http://localhost:5173/accept-invite?token=abc123...`

**Kết quả mong đợi:** Link được copy vào clipboard, hạn dùng 7 ngày

`PASS [ ]  FAIL [ ]`

---

### TC-10: Hieu tự tham gia qua invite link

**Người dùng:** Hieu mở link trong trình duyệt mới (tab ẩn danh, đã đăng nhập)

**Hành động:**
1. Dán link vào thanh địa chỉ → Enter
2. Trang hiện thông tin dự án "Todo App" và nút **Accept Invitation**
3. Nhấn **Accept**

**Kết quả mong đợi:**
- Hieu thấy thông báo "Yêu cầu của bạn đang chờ duyệt"
- Minh nhận thông báo (notification bell) "Hieu muốn tham gia dự án"

`PASS [ ]  FAIL [ ]`

---

### TC-11: Minh duyệt yêu cầu tham gia

**Người dùng:** Minh → tab **Members** → sub-tab **Pending**

**Hành động:**
1. Thấy "Tran Van Hieu" trong danh sách chờ
2. Nhấn **Approve**

**Kết quả mong đợi:**
- Hieu xuất hiện trong danh sách Members với role **Developer**
- Hieu nhận notification "Bạn đã được duyệt vào dự án Todo App"

`PASS [ ]  FAIL [ ]`

---

### TC-12: Mời Lan với email cụ thể và gán role Viewer

**Hành động:**
1. Minh → **Invite Member** → nhập `lan@example.com`
2. Chọn role **Viewer** → nhấn **Send Invite**
3. Lan vào link invite (kiểm tra console backend)
4. Nhấn **Accept**

**Kết quả mong đợi:** Lan tự động được approve (targeted invite), role = Viewer

`PASS [ ]  FAIL [ ]`

---

### TC-13: Thay đổi role thành viên

**Hành động:**
1. Minh → tab Members → tìm Hieu
2. Dropdown Role → chọn **Leader** → xác nhận

**Kết quả mong đợi:** Hieu hiển thị badge "Leader"

`PASS [ ]  FAIL [ ]`

---

### TC-14: Viewer không thể tạo task

**Người dùng:** Lan đăng nhập → vào workspace dự án "Todo App"

**Hành động:**
1. Vào tab **Kanban**
2. Thử nhấn **+ New Task** (nếu hiển thị)

**Kết quả mong đợi:**
- Nút **+ New Task** bị ẩn hoặc disabled
- Nếu cố gọi API trực tiếp: nhận `403 Forbidden`

`PASS [ ]  FAIL [ ]`

---

## PHẦN 4 — SINH SPEC & PLAN (AI ARCHITECT)

### TC-15: Sinh SPEC từ intent

**Người dùng:** Minh (PO) → tab **Documents**

**Hành động:**
1. Tìm phần **SPEC** → ô **Intent**
2. Nhập:
   ```
   Xây dựng ứng dụng Todo đơn giản bằng Python và FastAPI.
   Cho phép tạo, xem, cập nhật, xoá task (CRUD đầy đủ).
   Mỗi task có: tiêu đề, mô tả, trạng thái (todo/done), ngày tạo.
   Có API REST, SQLite storage, và file test pytest đầy đủ.
   ```
3. Nhấn **Generate SPEC**
4. Quan sát stream (nếu có progress bar hoặc loading indicator)
5. Chờ 20–60 giây

**Kết quả mong đợi:**
- SPEC.md xuất hiện với badge `Draft`
- Nội dung có đủ các mục:
  - `# Overview`, `## Goals`, `## Functional Requirements`, `## Acceptance Criteria`
- Không bị trắng hoặc timeout

`PASS [ ]  FAIL [ ]`

---

### TC-16: Yêu cầu sửa SPEC (Revision)

**Hành động:**
1. Tại SPEC đang Draft, điền vào ô **Request revision**:
   ```
   Bổ sung thêm: mỗi task có priority (low/medium/high).
   API cần trả về thêm trường created_at dạng ISO 8601.
   ```
2. Nhấn **Submit revision**
3. Chờ SPEC sinh lại

**Kết quả mong đợi:**
- SPEC mới có đề cập `priority` và `created_at`
- Badge vẫn là `Draft`
- Nội dung cũ (Goals, Overview) được giữ nguyên, chỉ mở rộng

`PASS [ ]  FAIL [ ]`

---

### TC-17: Approve SPEC → tự động sinh PLAN

**Hành động:**
1. Đọc SPEC, nhấn **Approve**

**Kết quả mong đợi:**
- SPEC badge đổi thành `Approved` (màu xanh lá)
- PLAN.md bắt đầu hiện spinner `Generating...`
- Sau 20–60 giây: PLAN.md xuất hiện với badge `Draft`

`PASS [ ]  FAIL [ ]`

---

### TC-18: Approve PLAN → tự động tạo tasks

**Hành động:**
1. Đọc PLAN.md
2. Nhấn **Approve**

**Kết quả mong đợi:**
- PLAN badge đổi thành `Approved`
- Tab **Kanban** tự động có tasks ở cột **TODO**, ví dụ:
  - "Khởi tạo project FastAPI"
  - "Tạo model Task với SQLAlchemy"
  - "Implement CRUD endpoints"
  - "Viết pytest cho các endpoint"
- Tasks có title, description, priority

`PASS [ ]  FAIL [ ]`

---

### TC-19: LLM Failover (Groq → Gemini)

> **Chỉ test được nếu có cả GROQ_API_KEY và GOOGLE_API_KEY và quota Groq đã hết.**

**Hành động:**
1. Xem logs backend khi đang chạy Generate SPEC
2. Nếu thấy `Groq quota exceeded (429), switching to gemini...`

**Kết quả mong đợi:**
- SPEC vẫn sinh thành công (không lỗi cho user)
- Log hiển thị `[FAILOVER] architect switched to google`

`PASS [ ]  FAIL [ ]  SKIP [ ]`

---

## PHẦN 5 — KANBAN BOARD & TASK MANAGEMENT

### TC-20: Tạo task thủ công

**Người dùng:** Hieu → tab **Kanban**

**Hành động:**
1. Nhấn **+ New Task**
2. Điền:
   - `Title: Viết tài liệu API`
   - `Description: Tạo file README.md mô tả các endpoint`
   - `Priority: Low`
3. Nhấn **Create**

**Kết quả mong đợi:** Task xuất hiện trong cột TODO

`PASS [ ]  FAIL [ ]`

---

### TC-21: Drag & drop task giữa các cột

**Hành động:**
1. Kéo task "Viết tài liệu API" từ **TODO** sang **REVIEW**

**Kết quả mong đợi:**
- Task di chuyển sang cột REVIEW
- Status cập nhật real-time
- Không cần reload trang

`PASS [ ]  FAIL [ ]`

---

### TC-22: Assign task cho thành viên

**Hành động:**
1. Click vào task "Khởi tạo project FastAPI"
2. Ở trường **Assignee**, chọn **Tran Van Hieu**
3. Nhấn **Save**

**Kết quả mong đợi:**
- Avatar Hieu hiện trên task card
- Hieu nhận notification "Bạn được giao task: Khởi tạo project FastAPI"

`PASS [ ]  FAIL [ ]`

---

### TC-23: Thiết lập task dependencies

**Hành động:**
1. Click task "Implement CRUD endpoints"
2. Tab **Dependencies** → **Add dependency**
3. Chọn "Tạo model Task" làm **depends on**
4. Nhấn **Save**

**Kết quả mong đợi:**
- Task "Implement CRUD endpoints" bị block (hiển thị icon khóa) nếu "Tạo model Task" chưa DONE
- Tab **Dependency Graph** hiển thị sơ đồ mũi tên giữa 2 task

`PASS [ ]  FAIL [ ]`

---

### TC-24: AI gợi ý dependencies tự động

**Hành động:**
1. Vào tab **Dependency Graph**
2. Nhấn **AI Suggest Dependencies**

**Kết quả mong đợi:**
- AI phân tích tiêu đề/mô tả các tasks
- Đề xuất ít nhất 2-3 cặp dependency hợp lý
- User có thể Accept/Reject từng gợi ý

`PASS [ ]  FAIL [ ]`

---

## PHẦN 6 — CODER AGENT

### TC-25: Chạy Coder Agent trên task

**Người dùng:** Hieu → Kanban

**Hành động:**
1. Task "Khởi tạo project FastAPI" đang ở TODO, đã assign cho Hieu
2. Kéo sang cột **IN PROGRESS** (hoặc nhấn **Start**)
3. Quan sát **Thought Stream** panel (bên phải màn hình hoặc popup):
   - Dòng 1: `[CODER] Starting task: Khởi tạo project FastAPI`
   - Tiếp theo: `TOOL_CALL: write_file → main.py`
   - Tiếp theo: `TOOL_CALL: run_terminal → pip install fastapi uvicorn`
   - Tiếp theo: `TOOL_CALL: run_terminal → python -m pytest -q`
   - Cuối: `STATUS_CHANGE: CODING → REVIEWING`

**Kết quả mong đợi:**
- Task tự chuyển sang cột **REVIEW** sau 5–10 phút
- Thought stream hiển thị ít nhất 5 events
- Không trống màn hình

`PASS [ ]  FAIL [ ]`

---

### TC-26: WIP Limit — chỉ 1 task IN PROGRESS mỗi người

**Hành động:**
1. Trong khi task "Khởi tạo project FastAPI" đang ở IN PROGRESS
2. Hieu thử kéo task thứ 2 ("Tạo model Task") sang IN PROGRESS

**Kết quả mong đợi:**
- Task thứ 2 bật trở lại **TODO**
- Toast cảnh báo: "Bạn đang có 1 task IN PROGRESS. Hoàn thành hoặc huỷ trước khi bắt đầu task mới."

`PASS [ ]  FAIL [ ]`

---

### TC-27: Pause Coder Agent

**Hành động:**
1. Khi Coder đang chạy (thấy stream đang chạy)
2. Nhấn nút **Pause** (hoặc gửi lệnh qua WebSocket)

**Kết quả mong đợi:**
- Stream dừng lại
- Task hiện badge `Paused`
- Log: `[CODER] Agent paused at iteration X`

`PASS [ ]  FAIL [ ]`

---

### TC-28: Resume với Steering Instructions

**Hành động:**
1. Task đang ở trạng thái Paused
2. Nhập vào ô **Steering**:
   ```
   Hãy thêm middleware CORS cho FastAPI để frontend có thể kết nối.
   Dùng allow_origins=["*"] cho môi trường dev.
   ```
3. Nhấn **Resume**

**Kết quả mong đợi:**
- Stream tiếp tục từ điểm dừng
- Coder nhận được steering instructions (thấy trong log)
- Code sinh ra có CORS middleware

`PASS [ ]  FAIL [ ]`

---

### TC-29: Hủy task đang chạy

**Hành động:**
1. Khi Coder đang chạy task khác
2. Nhấn **Cancel Task**

**Kết quả mong đợi:**
- Agent dừng ngay lập tức
- Task về lại **TODO**
- Toast: "Đã huỷ task"

`PASS [ ]  FAIL [ ]`

---

## PHẦN 7 — CODE REVIEW

### TC-30: Xem Diff và AI Review

**Người dùng:** Minh (PO) → Kanban → task ở REVIEW

**Hành động:**
1. Click vào task đang REVIEW
2. Tab **Diff** → xem code diff:
   - Dòng thêm: nền xanh lá
   - Dòng xoá: nền đỏ
3. Tab **AI Review** → đọc báo cáo:
   - Score (ví dụ: 85/100)
   - Nhận xét về code quality, security, performance

**Kết quả mong đợi:** Diff hiển thị syntax-highlighted, AI Review có nội dung cụ thể

`PASS [ ]  FAIL [ ]`

---

### TC-31: Thêm Inline Comment vào diff

**Hành động:**
1. Trong Diff Viewer, click vào dòng code cụ thể (ví dụ dòng 15 trong `main.py`)
2. Nhập comment:
   ```
   Thiếu exception handler cho trường hợp DB connection fail.
   ```
3. Nhấn **Add Comment**

**Kết quả mong đợi:**
- Comment hiện ra ngay tại dòng 15
- Comment lưu vào DB (F5 vẫn còn)

`PASS [ ]  FAIL [ ]`

---

### TC-32: Approve Code

**Hành động:**
1. Minh đọc diff → nhấn **Approve**

**Kết quả mong đợi:**
- Task chuyển sang **DONE**
- Audit log ghi: `task_diff_approve — SUCCESS`

`PASS [ ]  FAIL [ ]`

---

### TC-33: Reject Code với feedback

**Hành động:**
1. Task thứ 2 đang ở REVIEW
2. Minh nhập feedback:
   ```
   Hàm get_task không trả về 404 khi task_id không tồn tại.
   Cần thêm: if not task: raise HTTPException(status_code=404)
   ```
3. Nhấn **Reject**

**Kết quả mong đợi:**
- Task về **IN PROGRESS**
- Coder chạy lại, thought stream hiển thị `PO feedback received: ...`
- Sau khi xong → task về REVIEW với code đã sửa
- Diff mới có dòng `if not task: raise HTTPException(status_code=404)`

`PASS [ ]  FAIL [ ]`

---

## PHẦN 8 — CI/CD PIPELINE

### TC-34: Xem Pipeline Run

**Người dùng:** Hieu → tab **Pipelines**

**Hành động:**
1. Tìm pipeline run gần nhất (của task vừa DONE)
2. Click để xem chi tiết

**Kết quả mong đợi:**
- Hiển thị từng bước: `install` → `lint` → `test` → `build`
- Mỗi bước có trạng thái: ✓ passed / ✗ failed
- Có log output của từng bước (stdout/stderr)

`PASS [ ]  FAIL [ ]`

---

### TC-35: SSE Stream cho Pipeline đang chạy

**Hành động:**
1. Khi một pipeline đang chạy (task vừa move sang IN PROGRESS)
2. Vào tab Pipelines → click run đang chạy
3. Quan sát live log stream

**Kết quả mong đợi:**
- Log cuộn tự động theo thời gian thực
- Events: `pipeline_started`, `step_started`, `step_completed`
- `ping` event mỗi 30 giây để giữ kết nối

`PASS [ ]  FAIL [ ]`

---

### TC-36: Chạy lại Pipeline thất bại

**Hành động:**
1. Tìm pipeline run có trạng thái **FAILED** (tạo situation: cố ý viết code lỗi syntax)
2. Xem mục **AI Failure Analysis** → đọc nguyên nhân AI phân tích
3. Nhấn **Re-run Pipeline**

**Kết quả mong đợi:**
- Spinner xuất hiện, không màn hình đen/trắng
- Pipeline run mới tạo ra và bắt đầu chạy
- AI Failure Analysis có nội dung cụ thể (không rỗng)

`PASS [ ]  FAIL [ ]`

---

## PHẦN 9 — DEPLOYMENT & DEVOPS

### TC-37: Cấu hình GitHub Integration

**Người dùng:** Minh → **Settings** → **GitHub**

**Hành động:**
1. Nhập:
   - `Personal Access Token: ghp_xxxxxxxx` (token thật có quyền repo)
   - `Repository: username/todo-app`
   - `Default Base Branch: main`
2. Nhấn **Save**

**Kết quả mong đợi:**
- Hiện `✓ GitHub connected`
- Nếu project đã có tasks DONE: tự động backfill push code lên GitHub

`PASS [ ]  FAIL [ ]  SKIP [ ]` *(nếu không có GitHub token)*

---

### TC-38: Cấu hình Deployment

**Hành động:**
1. Tab **Settings** → **Deployment**
2. Chọn Provider: `Vercel` (hoặc `Custom VPS`)
3. Nhập token, project name
4. Nhấn **Test Credentials**

**Kết quả mong đợi:**
- Hiện `✓ Credentials valid` nếu đúng
- Hiện thông báo lỗi rõ ràng nếu sai (không crash)

`PASS [ ]  FAIL [ ]  SKIP [ ]`

---

### TC-39: Xem lịch sử Deployment

**Hành động:** Tab **Deployments**

**Kết quả mong đợi:**
- Danh sách deployment với trạng thái: `PENDING / RUNNING / SUCCESS / FAILED`
- Mỗi deployment có commit hash, thời gian, môi trường

`PASS [ ]  FAIL [ ]`

---

### TC-40: DevOps Health Dashboard

**Hành động:** Tab **DevOps**

**Kết quả mong đợi:**
- Hiển thị **Health Summary**: deployment nào đang HEALTHY / DEGRADED / DOWN
- Có biểu đồ uptime (nếu có deployment đang chạy)

`PASS [ ]  FAIL [ ]`

---

### TC-41: Cấu hình Alert (Discord/Slack Webhook)

**Hành động:**
1. Tab **DevOps** → **Alert Config**
2. Nhập:
   - `Discord Webhook URL: https://discord.com/api/webhooks/...`
   - `Health check path: /health`
   - `Alert threshold: 2 consecutive failures`
3. Nhấn **Save**

**Kết quả mong đợi:** Config lưu, toast "Đã lưu cấu hình cảnh báo"

`PASS [ ]  FAIL [ ]  SKIP [ ]` *(nếu không có Discord webhook)*

---

### TC-42: Manual Rollback

**Hành động:**
1. Có ít nhất 2 deployment SUCCESS
2. Nhấn **Rollback** trên deployment hiện tại
3. Chọn version muốn quay về

**Kết quả mong đợi:**
- Rollback event được ghi vào lịch sử
- Deployment config trỏ về version cũ
- Toast "Đã rollback thành công"

`PASS [ ]  FAIL [ ]  SKIP [ ]`

---

## PHẦN 10 — WEBHOOKS

### TC-43: Tạo Webhook

**Người dùng:** Minh → **Settings** → **Webhooks**

**Hành động:**
1. Nhấn **New Webhook**
2. Điền:
   - `URL: https://webhook.site/xxxxxxxx` *(dùng webhook.site để test)*
   - `Events: task.needs_review, task.done, agent.error`
3. Nhấn **Save**

**Kết quả mong đợi:** Webhook xuất hiện trong danh sách với trạng thái **Active**

`PASS [ ]  FAIL [ ]`

---

### TC-44: Test Webhook Delivery

**Hành động:**
1. Click webhook vừa tạo
2. Nhấn **Test**
3. Mở `webhook.site` để xem request nhận được

**Kết quả mong đợi:**
- `webhook.site` nhận 1 POST request
- Body có dạng:
  ```json
  {
    "event": "test",
    "project_id": "...",
    "timestamp": "..."
  }
  ```
- Header có `X-Kanban-Signature` (HMAC-SHA256)

`PASS [ ]  FAIL [ ]`

---

### TC-45: Webhook kích hoạt khi Task REVIEW

**Hành động:**
1. Coder agent chạy xong → task chuyển sang REVIEW

**Kết quả mong đợi:**
- `webhook.site` nhận POST với:
  ```json
  {
    "event": "task.needs_review",
    "task_id": "...",
    "task_title": "...",
    "project_id": "..."
  }
  ```

`PASS [ ]  FAIL [ ]`

---

### TC-46: Webhook kích hoạt khi Task DONE

**Hành động:** Minh approve code → task chuyển sang DONE

**Kết quả mong đợi:**
- `webhook.site` nhận POST với `"event": "task.done"`

`PASS [ ]  FAIL [ ]`

---

### TC-47: Webhook Retry khi endpoint lỗi

**Hành động:**
1. Sửa Webhook URL sang URL không tồn tại: `https://localhost:9999/fail`
2. Trigger event (approve task)
3. Chờ 5 phút, kiểm tra Webhook Delivery History

**Kết quả mong đợi:**
- Thấy ít nhất 3 lần retry trong delivery history
- Mỗi attempt có timestamp và response code (ví dụ `503` hoặc `connection error`)
- Sau 5 attempts: status = `FAILED`

`PASS [ ]  FAIL [ ]`

---

### TC-48: Cập nhật và vô hiệu hóa Webhook

**Hành động:**
1. Click webhook → **Edit**
2. Toggle **Active** sang OFF
3. Nhấn **Save**

**Kết quả mong đợi:**
- Webhook hiển thị badge **Inactive**
- Trigger event mới → `webhook.site` **không** nhận được request

`PASS [ ]  FAIL [ ]`

---

## PHẦN 11 — DISCORD BOT

> **Yêu cầu:** Cần cấu hình `DISCORD_BOT_TOKEN` và `DISCORD_APPLICATION_ID` trong `.env`

### TC-49: Bot online và respond /help

**Hành động:**
1. Mở Discord server nơi bot đã được mời
2. Gõ lệnh: `/help`

**Kết quả mong đợi:**
- Bot trả lời embed với danh sách commands:
  - `/spec [project_id]` — Xem SPEC.md
  - `/plan [project_id]` — Xem PLAN.md
  - `/tiendo [project_id]` — Tiến độ tasks
  - `/tasks [project_id]` — Danh sách tasks
  - `/github [project_id]` — Link GitHub
  - `/ask [project_id] [question]` — Hỏi AI

`PASS [ ]  FAIL [ ]  SKIP [ ]`

---

### TC-50: /spec — Lấy nội dung SPEC.md

**Hành động:**
1. Gõ: `/spec` → chọn project `Todo App` từ autocomplete

**Kết quả mong đợi:**
- Bot trả về embed màu xanh dương
- Nội dung tóm tắt SPEC.md (Overview, Goals, Requirements)
- Có tên project và trạng thái SPEC (Approved/Draft)

`PASS [ ]  FAIL [ ]  SKIP [ ]`

---

### TC-51: /plan — Lấy nội dung PLAN.md

**Hành động:** Gõ `/plan` → chọn project

**Kết quả mong đợi:**
- Embed màu tím với nội dung PLAN.md
- Các phases và tasks được liệt kê

`PASS [ ]  FAIL [ ]  SKIP [ ]`

---

### TC-52: /tiendo — Xem tiến độ tasks

**Hành động:** Gõ `/tiendo` → chọn project

**Kết quả mong đợi:**
- Embed hiển thị: `3/8 tasks completed (37.5%)`
- Breakdown: `TODO: 3 | IN PROGRESS: 1 | REVIEW: 1 | DONE: 3`

`PASS [ ]  FAIL [ ]  SKIP [ ]`

---

### TC-53: /tasks — Liệt kê tất cả tasks

**Hành động:** Gõ `/tasks` → chọn project

**Kết quả mong đợi:**
- Embed màu vàng với danh sách tasks và status emoji:
  - 📋 TODO: Khởi tạo project FastAPI
  - ⚙️ IN PROGRESS: Tạo model Task
  - 👀 REVIEW: Implement CRUD endpoints
  - ✅ DONE: Viết pytest

`PASS [ ]  FAIL [ ]  SKIP [ ]`

---

### TC-54: /ask — Hỏi AI về dự án

**Hành động:**
1. Gõ: `/ask` → project: `Todo App` → question: `API nào để tạo task mới?`

**Kết quả mong đợi:**
- Bot deferred response (hiện "đang xử lý...")
- Sau 5–15 giây: trả lời dựa trên SPEC/PLAN của dự án
- Ví dụ: "POST /api/tasks với body { title, description, priority }"

`PASS [ ]  FAIL [ ]  SKIP [ ]`

---

### TC-55: /github — Lấy link GitHub repo

**Hành động:** Gõ `/github` → chọn project

**Kết quả mong đợi:**
- Embed với URL GitHub repo (nếu đã cấu hình)
- Hoặc thông báo "Chưa kết nối GitHub"

`PASS [ ]  FAIL [ ]  SKIP [ ]`

---

## PHẦN 12 — NOTIFICATIONS (THÔNG BÁO)

### TC-56: Nhận thông báo task được assign

**Người dùng:** Hieu (DevTools → Application, đã đăng nhập)

**Hành động:**
1. Minh assign 1 task cho Hieu từ tab Kanban

**Kết quả mong đợi (Hieu thấy):**
- Icon chuông (🔔) hiện số đỏ `1`
- Dropdown: "Bạn được giao task: [tên task]"

`PASS [ ]  FAIL [ ]`

---

### TC-57: Đánh dấu đã đọc

**Hành động:**
1. Hieu click vào chuông → thấy danh sách thông báo
2. Nhấn **Mark all as read**

**Kết quả mong đợi:**
- Số đỏ biến mất
- Các notification chuyển trạng thái đã đọc

`PASS [ ]  FAIL [ ]`

---

### TC-58: Thông báo task cần review

**Hành động:** Coder agent xong → task chuyển REVIEW

**Kết quả mong đợi (Minh thấy):**
- Notification: "Task [tên] cần review"

`PASS [ ]  FAIL [ ]`

---

## PHẦN 13 — ANALYTICS & AUDIT LOG

### TC-59: Analytics — Tổng quan dự án

**Người dùng:** Minh → tab **Analytics**

**Hành động:**
1. Chọn khoảng thời gian: **Last 7 days**
2. Xem dashboard

**Kết quả mong đợi:**
- Task completion rate (%)
- Average cycle time (giờ từ TODO → DONE)
- Velocity chart (số tasks/ngày)
- Bottleneck analysis

`PASS [ ]  FAIL [ ]`

---

### TC-60: AI Review Metrics

**Hành động:** Tab **Analytics** → **AI Review**

**Kết quả mong đợi:**
- Code quality score trung bình
- Test pass rate
- Số lần reject/approve

`PASS [ ]  FAIL [ ]`

---

### TC-61: Audit Log — Xem lịch sử hành động

**Hành động:** Tab **Audit Log**

**Kết quả mong đợi:**
- Danh sách có đầy đủ events từ đầu session:
  - `spec_generated — SUCCESS`
  - `spec_approved — SUCCESS`
  - `plan_generated — SUCCESS`
  - `task_move — SUCCESS`
  - `coder_run — SUCCESS`
  - `task_diff_approve — SUCCESS`
- Có timestamp, user, action, result

`PASS [ ]  FAIL [ ]`

---

## PHẦN 14 — MEMORY (BỘ NHỚ DỰ ÁN)

### TC-62: Xem Memory entries sau khi agent chạy

**Hành động:** Tab **Memory** (sau khi ít nhất 1 task DONE)

**Kết quả mong đợi:**
- Có ít nhất 1 entry, ví dụ:
  - "Added FastAPI project structure with lifespan startup"
  - "Used SQLite for development, PostgreSQL ready config"
- Entry có summary và lessons_learned

`PASS [ ]  FAIL [ ]`

---

### TC-63: Chỉnh sửa Memory entry

**Hành động:**
1. Click **Edit** trên 1 memory entry
2. Thêm vào `lessons_learned`:
   ```
   Cần khai báo allow_origins trước khi include router.
   ```
3. Nhấn **Save**

**Kết quả mong đợi:** Nội dung cập nhật, F5 vẫn còn

`PASS [ ]  FAIL [ ]`

---

## PHẦN 15 — CODEBASE MAP

### TC-64: Xem AST Codebase Map

**Hành động:**
1. Vào **Settings** → **Codebase Map** (hoặc gọi `GET /api/v1/projects/{id}/codebase-map`)
2. Xem cấu trúc file của sandbox

**Kết quả mong đợi:**
- Tree structure hiển thị các file `.py`
- Có danh sách functions, classes trong mỗi file
- Timestamp của lần scan gần nhất

`PASS [ ]  FAIL [ ]`

---

### TC-65: Refresh Codebase Map

**Hành động:** Nhấn **Refresh** (hoặc gọi với `?refresh=true`)

**Kết quả mong đợi:**
- Map được re-scan
- Timestamp cập nhật

`PASS [ ]  FAIL [ ]`

---

## PHẦN 16 — REAL-TIME WEBSOCKET

### TC-66: WebSocket Stream hiển thị đúng

**Hành động:**
1. Mở DevTools → Network → WS tab
2. Chạy Coder agent
3. Quan sát WebSocket frames

**Kết quả mong đợi:**
- Kết nối tới `/ws/tasks/{task_id}/stream?token=...`
- Nhận frame `{"type": "CONNECTED"}`
- Nhận frames `{"type": "STREAM_EVENT", "event": "thought", ...}`
- Nhận frame `{"type": "STREAM_END"}` khi agent xong

`PASS [ ]  FAIL [ ]`

---

### TC-67: Replay history khi reconnect

**Hành động:**
1. Đang xem stream, đóng tab → mở lại
2. Reconnect WebSocket

**Kết quả mong đợi:**
- Nhận đầy đủ history của stream từ đầu (replay)
- Không bị mất events đã xảy ra trước khi reconnect

`PASS [ ]  FAIL [ ]`

---

## PHẦN 17 — BACKEND APIS EDGE CASES

### TC-68: List Available LLM Backends

**Hành động:**
```http
GET /api/v1/backends/available
Authorization: Bearer {token}
```

**Kết quả mong đợi:**
```json
{
  "groq": true,
  "gemini": true,
  "claude_code": false,
  "openai": false
}
```
*(tuỳ API keys cấu hình)*

`PASS [ ]  FAIL [ ]`

---

### TC-69: Tạo task từ template

**Hành động:**
1. `GET /api/v1/templates` → lấy danh sách
2. Click **Use Template** trên 1 template → tạo task với nội dung sẵn

`PASS [ ]  FAIL [ ]`

---

### TC-70: Rate limit và error handling

**Hành động:**
1. Gọi `POST /api/v1/auth/login` 10 lần liên tiếp với sai password
2. Xem response sau lần thứ 6+

**Kết quả mong đợi:**
- Trả về `429 Too Many Requests` hoặc `403 Account temporarily locked`
- Không crash server

`PASS [ ]  FAIL [ ]`

---

## TỔNG KẾT KẾT QUẢ

### Xác thực
| # | Test Case | PASS | FAIL | SKIP | Ghi chú |
|---|-----------|------|------|------|---------|
| TC-01 | Đăng ký + OTP | | | | |
| TC-02 | Đăng ký Dev/Viewer | | | | |
| TC-03 | Đăng nhập đúng | | | | |
| TC-04 | Đăng nhập sai | | | | |
| TC-05 | JWT localStorage | | | | |

### Dự án & Thành viên
| # | Test Case | PASS | FAIL | SKIP | Ghi chú |
|---|-----------|------|------|------|---------|
| TC-06 | Tạo dự án | | | | |
| TC-07 | Cập nhật dự án | | | | |
| TC-08 | Constitution | | | | |
| TC-09 | Tạo invite link | | | | |
| TC-10 | Tham gia qua link | | | | |
| TC-11 | Duyệt thành viên | | | | |
| TC-12 | Mời email cụ thể | | | | |
| TC-13 | Thay đổi role | | | | |
| TC-14 | Viewer bị chặn | | | | |

### Spec & Plan (AI Architect)
| # | Test Case | PASS | FAIL | SKIP | Ghi chú |
|---|-----------|------|------|------|---------|
| TC-15 | Sinh SPEC | | | | |
| TC-16 | Revision SPEC | | | | |
| TC-17 | Approve SPEC | | | | |
| TC-18 | Approve PLAN → tasks | | | | |
| TC-19 | LLM Failover | | | | |

### Kanban & Tasks
| # | Test Case | PASS | FAIL | SKIP | Ghi chú |
|---|-----------|------|------|------|---------|
| TC-20 | Tạo task thủ công | | | | |
| TC-21 | Drag & drop | | | | |
| TC-22 | Assign task | | | | |
| TC-23 | Task dependencies | | | | |
| TC-24 | AI suggest dependencies | | | | |

### Coder Agent
| # | Test Case | PASS | FAIL | SKIP | Ghi chú |
|---|-----------|------|------|------|---------|
| TC-25 | Chạy Coder Agent | | | | |
| TC-26 | WIP Limit | | | | |
| TC-27 | Pause Agent | | | | |
| TC-28 | Resume + Steer | | | | |
| TC-29 | Cancel Task | | | | |

### Code Review
| # | Test Case | PASS | FAIL | SKIP | Ghi chú |
|---|-----------|------|------|------|---------|
| TC-30 | Xem Diff + AI Review | | | | |
| TC-31 | Inline Comment | | | | |
| TC-32 | Approve Code | | | | |
| TC-33 | Reject + Feedback | | | | |

### CI/CD Pipeline
| # | Test Case | PASS | FAIL | SKIP | Ghi chú |
|---|-----------|------|------|------|---------|
| TC-34 | Xem Pipeline Run | | | | |
| TC-35 | SSE Live Stream | | | | |
| TC-36 | Re-run Pipeline | | | | |

### Deployment & DevOps
| # | Test Case | PASS | FAIL | SKIP | Ghi chú |
|---|-----------|------|------|------|---------|
| TC-37 | GitHub Integration | | | | |
| TC-38 | Deployment Config | | | | |
| TC-39 | Lịch sử Deployment | | | | |
| TC-40 | Health Dashboard | | | | |
| TC-41 | Alert Config | | | | |
| TC-42 | Manual Rollback | | | | |

### Webhooks
| # | Test Case | PASS | FAIL | SKIP | Ghi chú |
|---|-----------|------|------|------|---------|
| TC-43 | Tạo Webhook | | | | |
| TC-44 | Test Delivery | | | | |
| TC-45 | Event: task.needs_review | | | | |
| TC-46 | Event: task.done | | | | |
| TC-47 | Retry on failure | | | | |
| TC-48 | Disable Webhook | | | | |

### Discord Bot
| # | Test Case | PASS | FAIL | SKIP | Ghi chú |
|---|-----------|------|------|------|---------|
| TC-49 | /help | | | | |
| TC-50 | /spec | | | | |
| TC-51 | /plan | | | | |
| TC-52 | /tiendo | | | | |
| TC-53 | /tasks | | | | |
| TC-54 | /ask | | | | |
| TC-55 | /github | | | | |

### Notifications
| # | Test Case | PASS | FAIL | SKIP | Ghi chú |
|---|-----------|------|------|------|---------|
| TC-56 | Nhận thông báo assign | | | | |
| TC-57 | Mark as read | | | | |
| TC-58 | Thông báo REVIEW | | | | |

### Analytics & Audit
| # | Test Case | PASS | FAIL | SKIP | Ghi chú |
|---|-----------|------|------|------|---------|
| TC-59 | Analytics tổng quan | | | | |
| TC-60 | AI Review Metrics | | | | |
| TC-61 | Audit Log | | | | |

### Memory & Codebase
| # | Test Case | PASS | FAIL | SKIP | Ghi chú |
|---|-----------|------|------|------|---------|
| TC-62 | Xem Memory entries | | | | |
| TC-63 | Edit Memory | | | | |
| TC-64 | Codebase Map | | | | |
| TC-65 | Refresh Map | | | | |

### WebSocket & APIs
| # | Test Case | PASS | FAIL | SKIP | Ghi chú |
|---|-----------|------|------|------|---------|
| TC-66 | WS Stream frames | | | | |
| TC-67 | WS Replay history | | | | |
| TC-68 | Available backends | | | | |
| TC-69 | Task templates | | | | |
| TC-70 | Rate limiting | | | | |

---

**Tổng số test cases: 70**  
**PASS: ___ / FAIL: ___ / SKIP: ___**

---

## LỖI GẶP PHẢI

| # | Test Case | Mô tả lỗi | Mức độ | Đã fix |
|---|-----------|-----------|--------|--------|
| | | | Critical/Major/Minor | |
| | | | | |
| | | | | |

---

*Tạo bởi: Kanban-AI Test Team*  
*Ngày: 2026-06-08*
