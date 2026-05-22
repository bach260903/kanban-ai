# Feature Specification: Platform Expansion — Multi-Agent Review, Team Management & Integrations

**Feature Branch**: `003-multi-agent-team-platform`
**Created**: 2026-05-20
**Status**: Draft
**Priority**: P1 (Multi-Agent Review) · P1 (Multi-user Team) · P2 (Dependencies & Templates) · P2 (Dashboard) · P2 (Notifications)

---

## Tóm Tắt

Mở rộng Neo-Kanban từ công cụ single-user thành nền tảng team AI-agentic hoàn chỉnh. Bao gồm 5 nhóm tính năng:

- **F-003**: Multi-Agent Review Pipeline — AI thứ hai tự động review code trước khi PO quyết định
- **F-004**: Multi-user & Team Management — Phân quyền, invite, task assignment cho team
- **F-005**: Task Dependencies & Templates — Khóa task theo thứ tự, mẫu task tái sử dụng
- **F-006**: Team Dashboard & Analytics — Tổng quan đa project, hiệu suất Agent, metrics team
- **F-007**: Notifications & Integrations — Thông báo in-app, Slack/Discord webhook, GitHub PR

---

## Mục Tiêu Người Dùng

| ID | Vai trò | Nhu cầu | Giá trị |
|----|---------|---------|---------|
| US-01 | Project Owner / Leader | Nhận báo cáo review tự động từ AI trước khi duyệt code | Giảm công sức review thủ công |
| US-02 | Owner | Mời thành viên vào project với vai trò cụ thể | Làm việc nhóm có kiểm soát |
| US-03 | Leader | Assign task cho Developer, theo dõi tiến độ toàn team | Quản lý dự án hiệu quả |
| US-04 | Developer | Nhận task được giao, kéo vào In Progress và xem AI làm việc | Tập trung vào task của mình |
| US-05 | Leader / Owner | Xem dashboard tổng quan tất cả project và hiệu suất Agent | Ra quyết định dựa trên dữ liệu |
| US-06 | Owner / Leader | Nhận thông báo khi task cần review hoặc Agent lỗi | Không bỏ lỡ sự kiện quan trọng |
| US-07 | Leader | Đặt task B phụ thuộc Task A — tránh code sai thứ tự | Đảm bảo luồng phát triển đúng |

---

## Kịch Bản Người Dùng & Kiểm Thử *(bắt buộc)*

---

### User Story 1 — AI Tự Động Review Code (Priority: P1) 🎯 MVP

Sau khi Coder Agent hoàn thành task, Reviewer Agent tự động phân tích diff: chạy test, kiểm tra
style theo constitution, quét bảo mật cơ bản và đưa ra nhận xét từng dòng. PO/Leader thấy báo
cáo AI ngay trong Diff Viewer trước khi quyết định Approve hay Reject.

**Lý do ưu tiên**: Giảm đáng kể gánh nặng review cho PO, tăng chất lượng code đưa vào Done.
Giá trị ngay lập tức ngay cả với single-user — không phụ thuộc vào multi-user.

**Independent Test**: Kéo task vào In Progress với backend bất kỳ → Coder Agent xong → Reviewer
Agent tự động chạy → panel "AI Review" xuất hiện trong Diff Viewer với điểm số và nhận xét →
PO vẫn có thể Approve hoặc Reject độc lập với gợi ý của AI.

**Acceptance Scenarios**:

1. **Given** Coder Agent vừa hoàn thành task và diff đã được tạo, **When** hệ thống tự động kích hoạt Reviewer Agent, **Then** Reviewer Agent phân tích diff và trả về: điểm tổng hợp 0–100, danh sách nhận xét theo file/dòng, và gợi ý "Approve" hoặc "Needs changes".
2. **Given** Reviewer Agent đang chạy, **When** PO mở Diff Viewer, **Then** panel "AI Review" hiển thị song song với diff, bao gồm: kết quả test (pass/fail với số lượng), cảnh báo bảo mật (nếu có), và inline comments trên từng dòng diff được đánh dấu.
3. **Given** Reviewer Agent đề xuất "Needs changes", **When** PO vẫn muốn Approve, **Then** PO có thể Approve bình thường — quyết định cuối thuộc về PO, không bị AI khóa.
4. **Given** test runner không được cấu hình trong project, **When** Reviewer Agent chạy, **Then** phần kết quả test được bỏ qua; các phần khác (AI review, security scan) vẫn hoạt động bình thường.
5. **Given** Reviewer Agent gặp lỗi (timeout, sandbox issue), **When** lỗi xảy ra, **Then** task vẫn chuyển sang Review; panel AI Review hiển thị thông báo "Review không khả dụng" thay vì block PO.

---

### User Story 2 — Đăng Nhập & Phân Quyền Team (Priority: P1)

Owner tạo tài khoản và đăng nhập vào Neo-Kanban. Owner mời thành viên qua email hoặc invite link
có thời hạn. Mỗi thành viên có vai trò: Owner, Leader, Developer, Viewer — với quyền khác nhau
trên từng project.

**Lý do ưu tiên**: Nền tảng cho toàn bộ luồng team — không có auth/roles thì không có multi-user.

**Independent Test**: Tạo tài khoản → đăng nhập → tạo project → gửi invite link → thành viên
đăng ký qua link → thấy project trong dashboard → xác nhận quyền hạn theo role hoạt động đúng.

**Acceptance Scenarios**:

1. **Given** chưa có tài khoản, **When** PO đăng ký bằng email và mật khẩu, **Then** tài khoản được tạo và PO tự động là Owner của mọi project tự tạo.
2. **Given** Owner mở trang Members của project, **When** Owner nhập email hoặc tạo invite link (hết hạn 7 ngày), **Then** người được mời nhận được link; khi click, họ được yêu cầu đăng ký/đăng nhập rồi tự động join project với role được chỉ định.
3. **Given** thành viên có role Developer, **When** thành viên thử xóa project hoặc thay đổi project settings, **Then** hệ thống từ chối với thông báo "Không đủ quyền".
4. **Given** thành viên có role Viewer, **When** Viewer mở Kanban, **Then** Viewer thấy đầy đủ nội dung (task, diff, stream) nhưng không có nút Approve, Reject, hay kéo task.
5. **Given** invite link đã hết hạn (7 ngày), **When** người dùng click link, **Then** hệ thống báo "Link đã hết hạn" và hướng dẫn liên hệ Owner để lấy link mới.

---

### User Story 3 — Assign Task & WIP per Developer (Priority: P1)

Leader assign task cho Developer cụ thể từ Kanban. Developer chỉ thấy nổi bật task được assign
cho mình. WIP limit áp dụng per-developer: mỗi developer tối đa 1 task In Progress cùng lúc.

**Lý do ưu tiên**: Phân công rõ ràng giúp team tránh conflict và Leader kiểm soát được tải công việc.

**Independent Test**: Leader assign Task A cho Developer X → Developer Y cố kéo Task A → hệ thống
từ chối → Developer X kéo Task A vào In Progress → Developer X thử kéo Task B → hệ thống từ
chối vì WIP limit.

**Acceptance Scenarios**:

1. **Given** Leader xem Kanban, **When** Leader click vào task và chọn "Assign to" rồi chọn thành viên, **Then** task hiển thị avatar của người được assign; thành viên nhận notification trong app.
2. **Given** task đã được assign cho Developer X, **When** Developer Y (khác) cố kéo task đó vào In Progress, **Then** hệ thống từ chối với thông báo "Task này được assign cho [tên Developer X]". Leader/Owner có thể override.
3. **Given** Developer X đang có 1 task In Progress, **When** Developer X cố kéo task thứ hai, **Then** hệ thống từ chối: "WIP limit: bạn đang có 1 task In Progress. Hoàn thành task hiện tại trước."
4. **Given** task chưa được assign, **When** Developer kéo task vào In Progress, **Then** task tự động assign cho Developer đó.

---

### User Story 4 — Task Dependencies (Priority: P2)

Leader/PO có thể đặt quan hệ phụ thuộc giữa các task: Task B không thể bắt đầu khi Task A chưa
Done. Kanban hiển thị task bị lock với badge "Blocked by #A". Khi A Done, B tự động unlock.

**Lý do ưu tiên**: Đảm bảo luồng phát triển đúng thứ tự, tránh Agent code trên nền tảng chưa tồn tại.

**Independent Test**: Tạo Task A và Task B → đặt B depends_on A → xác nhận B bị lock trên Kanban →
Approve Task A (Done) → xác nhận B tự động unlock → kéo B vào In Progress thành công.

**Acceptance Scenarios**:

1. **Given** Leader đang xem hoặc chỉnh sửa task, **When** Leader thêm dependency "Depends on Task #X", **Then** task bị lock trên Kanban với badge "Blocked by #X"; Developer không thể kéo task đó.
2. **Given** Task A là dependency của Task B, **When** Task A chuyển sang Done, **Then** Task B tự động unlock và badge "Blocked by #A" biến mất.
3. **Given** Task B phụ thuộc Task A và Task C, **When** chỉ Task A Done (Task C chưa Done), **Then** Task B vẫn bị lock với badge "Blocked by #C".
4. **Given** Leader muốn xem quan hệ phụ thuộc, **When** Leader mở tab Dependencies, **Then** sơ đồ DAG đơn giản hiển thị toàn bộ task và mũi tên phụ thuộc giữa chúng.

---

### User Story 5 — Task Templates (Priority: P2)

PO hoặc Leader lưu một task hiện tại làm template (tiêu đề + mô tả mẫu). Khi tạo task mới,
có thể chọn từ danh sách template để điền sẵn nội dung, giảm thời gian soạn task lặp lại.

**Lý do ưu tiên**: Tăng tốc độ tạo task cho team, đảm bảo nhất quán trong mô tả task cùng loại.

**Independent Test**: Lưu task "Viết unit test" làm template → tạo task mới → chọn template →
xác nhận tiêu đề và mô tả được điền sẵn → lưu task mới thành công.

**Acceptance Scenarios**:

1. **Given** Leader mở một task, **When** Leader chọn "Lưu làm template" và đặt tên, **Then** template được lưu và xuất hiện trong danh sách template của project (hoặc global nếu chọn).
2. **Given** tạo task mới, **When** PO chọn template từ dropdown, **Then** tiêu đề và mô tả được điền sẵn từ template; PO vẫn có thể chỉnh sửa trước khi lưu.
3. **Given** template được đặt ở scope "global", **When** PO mở project khác và tạo task, **Then** template vẫn xuất hiện trong danh sách để chọn.

---

### User Story 6 — Team Dashboard & Agent Analytics (Priority: P2)

Leader và Owner có màn hình tổng quan hiển thị tất cả project: số task theo cột, task nào đang
chờ review, ai đang làm gì. Tab Analytics hiển thị hiệu suất Agent theo backend và theo thành viên.

**Lý do ưu tiên**: Leader cần nhìn thấy toàn cảnh để điều phối team; Analytics giúp chọn backend tốt nhất.

**Independent Test**: Vào Dashboard → xác nhận tất cả project hiển thị với số task đúng →
vào Analytics → xác nhận biểu đồ hiển thị dữ liệu thực từ agent_runs và audit_logs.

**Acceptance Scenarios**:

1. **Given** Leader/Owner mở Dashboard, **When** trang tải, **Then** tất cả project hiển thị card với: tên project, số task theo cột (To Do / In Progress / Review / Done), AI backend đang dùng, task nào đang chờ review lâu nhất.
2. **Given** Leader mở tab Analytics, **When** chọn khoảng thời gian (7 ngày / 30 ngày), **Then** biểu đồ hiển thị: thời gian trung bình từ drag → Done theo từng backend, tỷ lệ Approve lần đầu vs. số lần retry, số lần Agent lỗi theo loại lỗi.
3. **Given** tab Analytics có section "Thành viên", **When** Leader xem, **Then** mỗi Developer hiển thị: số task Done, số task In Progress, tỷ lệ retry trung bình.

---

### User Story 7 — Notifications & Webhook (Priority: P2)

Thành viên nhận thông báo in-app khi được assign task, khi task cần review, hoặc khi Agent lỗi.
Owner/Leader cấu hình webhook để gửi thông báo ra Slack, Discord, hoặc endpoint tùy chỉnh.

**Lý do ưu tiên**: Giúp team phản hồi nhanh với sự kiện quan trọng mà không cần mở app liên tục.

**Independent Test**: Assign task → xác nhận Developer nhận notification in-app → cấu hình Slack
webhook → Agent hoàn thành task → xác nhận tin nhắn xuất hiện trong Slack channel.

**Acceptance Scenarios**:

1. **Given** task vừa được assign cho Developer, **When** Developer mở app, **Then** bell icon góc phải hiển thị badge số chưa đọc; click vào thấy thông báo "@tên: bạn được assign Task #12 — [tiêu đề task]".
2. **Given** Agent hoàn thành task và task chuyển sang Review, **When** sự kiện xảy ra, **Then** Leader/Owner nhận notification in-app: "Task #12 cần review".
3. **Given** Owner đã cấu hình Slack webhook URL, **When** task chuyển sang Review, **Then** bot gửi message vào Slack channel với: tên project, tên task, link trực tiếp vào Diff Viewer.
4. **Given** webhook endpoint trả về lỗi (timeout, 5xx), **When** retry xảy ra, **Then** hệ thống retry tối đa 3 lần với exponential backoff; sau đó ghi lỗi vào webhook log mà không crash hệ thống.
5. **Given** Owner muốn tích hợp GitHub, **When** PO Approve task, **Then** hệ thống tự động tạo Pull Request trên GitHub repo tương ứng với diff content và description từ task.

---

### Edge Cases

- Điều gì xảy ra nếu Reviewer Agent timeout (> 5 phút)? Task vẫn sang Review hay bị block?
- Nếu Owner bị xóa tài khoản, project và task sẽ xử lý thế nào?
- Nếu Developer bị xóa khỏi project khi đang có task In Progress, task đó sẽ ra sao?
- Nếu dependency tạo vòng lặp (A depends B, B depends A), hệ thống phát hiện và xử lý thế nào?
- Nếu webhook endpoint luôn fail, hệ thống có tiếp tục gửi không? Cấu hình tắt tự động?
- Analytics khi không có dữ liệu (project mới, chưa có task Done) hiển thị gì?
- Nếu GitHub API token hết hạn, PR tạo thất bại — hệ thống thông báo gì cho Owner?

---

## Yêu Cầu Chức Năng

### F-003 — Multi-Agent Review Pipeline

- **FR-001**: Hệ thống PHẢI tự động kích hoạt Reviewer Agent ngay sau khi Coder Agent hoàn thành và diff được lưu.
- **FR-002**: Reviewer Agent PHẢI chạy test suite của project (pytest / npm test) và báo cáo số test pass/fail.
- **FR-003**: Reviewer Agent PHẢI phân tích diff bằng AI và sinh danh sách nhận xét kèm file_path và line_number.
- **FR-004**: Reviewer Agent PHẢI quét hardcoded secrets (token, password, API key dạng plain text trong diff) và cảnh báo nếu phát hiện.
- **FR-005**: Reviewer Agent PHẢI tính điểm tổng hợp 0–100 và gợi ý "Approve" hoặc "Needs changes".
- **FR-006**: Diff Viewer PHẢI hiển thị panel "AI Review" song song với diff, chứa điểm, gợi ý, và inline comments.
- **FR-007**: PO/Leader PHẢI có thể Approve hoặc Reject bất kể gợi ý của Reviewer Agent — AI không được block quyết định của người dùng.
- **FR-008**: Nếu Reviewer Agent lỗi hoặc timeout, task PHẢI vẫn chuyển sang Review và thông báo lỗi review rõ ràng.
- **FR-009**: Kết quả review PHẢI được lưu vào cơ sở dữ liệu để tham chiếu sau.

### F-004 — Multi-user & Team Management

- **FR-010**: Hệ thống PHẢI hỗ trợ đăng ký và đăng nhập bằng email và mật khẩu.
- **FR-011**: Hệ thống PHẢI duy trì phiên đăng nhập an toàn không yêu cầu đăng nhập lại sau mỗi lần đóng tab.
- **FR-012**: Owner PHẢI có thể tạo invite link cho project với thời hạn 7 ngày; link hết hạn sau đó.
- **FR-013**: Hệ thống PHẢI hỗ trợ 4 vai trò: Owner, Leader, Developer, Viewer — với quyền như đặc tả.
- **FR-014**: Task PHẢI có trường `assigned_to` để gán cho một thành viên cụ thể.
- **FR-015**: Hệ thống PHẢI áp dụng WIP limit = 1 per Developer (không phải per project): mỗi Developer tối đa 1 task In Progress.
- **FR-016**: Hệ thống PHẢI ghi Activity Feed cho mọi hành động quan trọng (assign, approve, reject, kéo task), hiển thị cho Leader/Owner.
- **FR-017**: Developer chỉ được kéo task đã được assign cho mình vào In Progress (trừ task chưa được assign — tự động assign khi kéo).
- **FR-018**: Leader và Owner PHẢI có thể override WIP limit và assign restriction nếu cần.

### F-005 — Task Dependencies & Templates

- **FR-019**: Hệ thống PHẢI cho phép đặt quan hệ `depends_on` giữa các task trong cùng project.
- **FR-020**: Task có dependency chưa Done PHẢI bị lock trên Kanban — không thể kéo vào In Progress.
- **FR-021**: Khi task dependency chuyển sang Done, hệ thống PHẢI tự động unlock task phụ thuộc.
- **FR-022**: Hệ thống PHẢI phát hiện và từ chối dependency vòng lặp (circular dependency).
- **FR-023**: Leader PHẢI có thể xem sơ đồ dependency dạng DAG trong project.
- **FR-024**: PO/Leader PHẢI có thể lưu task làm template (tiêu đề + mô tả).
- **FR-025**: Template PHẢI có thể được áp dụng cho toàn project (project-scoped) hoặc toàn workspace (global).
- **FR-026**: Khi tạo task mới, người dùng PHẢI có thể chọn template từ dropdown để điền sẵn nội dung.

### F-006 — Team Dashboard & Analytics

- **FR-027**: Dashboard PHẢI hiển thị tất cả project người dùng có quyền xem, với số task theo cột.
- **FR-028**: Dashboard PHẢI đánh dấu task nào đang chờ review lâu nhất (> 24 giờ) theo màu cảnh báo.
- **FR-029**: Tab Analytics PHẢI hiển thị thời gian trung bình từ In Progress → Done, theo từng AI backend.
- **FR-030**: Tab Analytics PHẢI hiển thị tỷ lệ Approve lần đầu vs tổng số lần hoàn thành, theo project và theo developer.
- **FR-031**: Tab Analytics PHẢI hiển thị Reviewer Agent score trung bình theo project.
- **FR-032**: Tab Analytics PHẢI hiển thị số lần Agent lỗi theo loại (timeout, CLI not found, auth error).
- **FR-033**: Người dùng PHẢI có thể lọc Analytics theo khoảng thời gian (7 ngày / 30 ngày / tùy chỉnh).

### F-007 — Notifications & Integrations

- **FR-034**: Hệ thống PHẢI gửi notification in-app khi: task được assign, task sang Review, Agent lỗi, invite được chấp nhận.
- **FR-035**: Bell icon PHẢI hiển thị số thông báo chưa đọc; click vào hiện danh sách với link đến task liên quan.
- **FR-036**: Owner/Leader PHẢI có thể cấu hình webhook URL (Slack, Discord, custom HTTP) per project.
- **FR-037**: Webhook PHẢI gửi payload JSON chuẩn khi: task sang Review, task sang Done, Agent lỗi.
- **FR-038**: Hệ thống PHẢI retry webhook tối đa 3 lần với exponential backoff nếu endpoint fail.
- **FR-039**: Owner PHẢI có thể cấu hình GitHub repo + Personal Access Token để tự động tạo PR sau khi Approve.
- **FR-040**: Khi PR tạo thành công, link PR PHẢI hiển thị trong task card.

### Thực Thể Chính

- **User**: Tài khoản người dùng — email, password_hash, display_name, created_at
- **ProjectMember**: Quan hệ user–project–role — user_id, project_id, role (owner/leader/developer/viewer), joined_at
- **Invitation**: Lời mời join project — project_id, invitee_email, role, token, expires_at, used_at
- **ReviewReport**: Kết quả Reviewer Agent — task_id, agent_run_id, score, suggestion, test_pass, test_fail, created_at
- **ReviewComment**: Nhận xét inline — review_report_id, file_path, line_number, content, severity (info/warning/error)
- **TaskDependency**: Quan hệ phụ thuộc — task_id, depends_on_task_id
- **TaskTemplate**: Mẫu task — name, title_template, description_template, scope (project/global), project_id (nullable), created_by
- **Notification**: Thông báo in-app — user_id, type, content, reference_id, is_read, created_at
- **ActivityLog**: Audit trail team — user_id, project_id, action, entity_type, entity_id, created_at
- **WebhookConfig**: Cấu hình webhook — project_id, url, secret, events (JSON array), enabled
- **WebhookDelivery**: Log gửi webhook — webhook_config_id, event_type, payload, status, attempts, last_attempt_at

---

## Yêu Cầu Phi Chức Năng

| ID | Yêu cầu |
|----|---------|
| TC-01 | Reviewer Agent hoàn thành trong ≤ 5 phút; timeout → task vẫn sang Review, không bị block |
| TC-02 | Dashboard tải trong ≤ 3 giây với tối đa 20 project và 500 task |
| TC-03 | Notification in-app xuất hiện trong ≤ 5 giây kể từ khi sự kiện xảy ra |
| TC-04 | Webhook được gửi trong ≤ 10 giây sau sự kiện trigger |
| TC-05 | Dependency check (lock/unlock) phải hoàn thành trong ≤ 1 giây sau khi task Done |
| TC-06 | Auth session tồn tại ít nhất 7 ngày kể từ lần đăng nhập cuối |
| TC-07 | Hệ thống hỗ trợ tối thiểu 50 người dùng đồng thời trên cùng platform |

---

## Kịch Bản Chấp Thuận Tổng Hợp

### Kịch Bản A — Luồng Team Đầy Đủ (End-to-End)

1. Owner tạo tài khoản → tạo project → mời Leader và 2 Developer qua invite link
2. Leader tạo task với dependency (Task B depends_on Task A), assign Task A cho Developer X
3. Developer X thấy Task A → kéo vào In Progress → Coder Agent chạy
4. Coder Agent xong → Reviewer Agent tự động phân tích → panel AI Review xuất hiện
5. Leader nhận notification → mở Diff Viewer → xem báo cáo AI → Approve
6. Task A Done → Task B tự động unlock → Developer Y nhận notification được assign
7. Slack channel nhận message: "Task A Done trong Project XYZ"
8. Leader xem Dashboard → thấy 1 Done, 1 In Progress → Analytics cập nhật

### Kịch Bản B — Reviewer Agent Phát Hiện Vấn Đề

1. Coder Agent sinh code có hardcoded API key
2. Reviewer Agent scan phát hiện → cảnh báo đỏ trong panel AI Review
3. Score: 45/100, gợi ý "Needs changes" với comment tại dòng cụ thể
4. Leader đọc cảnh báo → Reject kèm feedback: "Xóa API key khỏi code"
5. Agent nhận feedback → fix → Reviewer Agent chạy lại lần 2 → score 88/100
6. Leader Approve

### Kịch Bản C — Xung Đột Phân Quyền

1. Developer Y cố kéo Task A đã assign cho Developer X
2. Hệ thống từ chối: "Task được assign cho Developer X"
3. Developer Y đang có 1 task In Progress, cố kéo task thứ hai
4. Hệ thống từ chối: "WIP limit đã đạt"
5. Viewer mở Diff Viewer → thấy đầy đủ nhưng không có nút Approve/Reject

---

## Giả Định

- Reviewer Agent sử dụng cùng AI backend đang được cấu hình cho project (không tạo thêm API key mới).
- Test runner detection tự động dựa trên file trong sandbox (package.json → npm test; conftest.py → pytest).
- Security scan chỉ phát hiện pattern đơn giản (hardcoded key, password = "...") — không phải SAST đầy đủ.
- WIP limit per-developer áp dụng trên toàn platform, không phân biệt project.
- GitHub PR Integration là tính năng tùy chọn (opt-in); không bắt buộc cấu hình.
- Dashboard chỉ hiển thị project mà người dùng là thành viên (không có admin view toàn hệ thống).
- Notification in-app không hỗ trợ push notification trình duyệt trong phiên bản đầu — chỉ in-app khi đang mở tab.
- Analytics dữ liệu lấy từ các bảng `agent_runs` và `audit_logs` đã có — không cần bảng mới cho metrics.
- Mật khẩu được hash bằng thuật toán tiêu chuẩn ngành; không lưu plain text.
- Phase 1 (Feature 001 + 002) phải hoàn chỉnh và ổn định trước khi triển khai feature này.

---

## Ngoài Phạm Vi

- SSO / OAuth2 (Google, GitHub login) — có thể thêm sau
- Push notification trình duyệt (Web Push API)
- Per-user API key management cho AI backends
- Admin panel toàn hệ thống (xem tất cả user, tất cả project)
- Billing / subscription management
- Mobile app
- Reviewer Agent tự động apply fix (chỉ report, không tự sửa)
- Full SAST/DAST security scanning
- CI/CD pipeline integration ngoài GitHub PR
