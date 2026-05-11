# Pre-Implementation Checklist: Neo-Kanban

**Purpose**: Kiểm tra chất lượng đặc tả trước khi bắt đầu implement — đảm bảo mọi hành vi kỳ vọng đều được ghi rõ trong spec/plan/research, không chỉ tồn tại trong đầu người viết.
**Ngày tạo**: 2026-05-11
**Tính năng**: [spec.md](../spec.md) · [plan.md](../plan.md) · [research.md](../research.md) · [data-model.md](../data-model.md)

---

## 1. Human-in-the-Loop Compliance

*Mỗi HIL checkpoint phải có đặc tả rõ ràng về CƠ CHẾ CHẶN — không chỉ là "cần approve trước khi tiếp tục".*

- [ ] CHK001 - Cơ chế chặn tại checkpoint "Spec Draft → Approve" có được đặc tả ở đúng lớp không? Spec §YC-11 nêu rằng hệ thống PHẢI ngăn bước tiếp theo, nhưng KHÔNG chỉ rõ lớp nào chịu trách nhiệm (API gateway, service layer, hay chỉ UI)? [Clarity, Spec §YC-11]

- [ ] CHK002 - Cơ chế chặn tại checkpoint "Plan Draft → Approve" có xác định trạng thái trung gian khi Task decomposition bị ngăn không? Spec §YC-14 chỉ nêu kết quả, không mô tả cách cột To Do phản hồi khi cố truy cập trước khi Approve. [Completeness, Spec §YC-14, Kịch Bản 6-4]

- [ ] CHK003 - Spec có định nghĩa rõ PO được hoặc không được chỉnh sửa Task List sau khi PLAN.md Approved nhưng trước khi Agent bắt đầu chạy Task đầu tiên không? Kịch Bản 7 mô tả Task xuất hiện tự động nhưng không nêu quyền chỉnh sửa. [Gap, Spec §Kịch Bản 7]

- [ ] CHK004 - Yêu cầu "Agent bị block khi chờ PO action trong Code Review" có được phát biểu đo lường được không? TC-02 nêu "100% bước chuyển trạng thái yêu cầu Approve đều có checkpoint" nhưng không định lượng thời gian chờ tối đa hay hành vi timeout. [Clarity, Spec §TC-02]

- [ ] CHK005 - Spec có mô tả trạng thái của in-flight Agent operations khi `interrupt()` được kích hoạt không? (Ví dụ: file writes đang dở, DB transactions chưa commit?) [Gap, Research D-01]

- [ ] CHK006 - Ba HIL checkpoint (SPEC approve, PLAN approve, Code review) có được đặc tả nhất quán về blocking semantics không? Spec §YC-11 dùng "ngăn PO chuyển sang", §YC-14 dùng "ngăn phân rã Task", §YC-22 dùng "không được tự động" — ba cách diễn đạt khác nhau cho cùng một khái niệm. [Consistency, Spec §YC-11, §YC-14, §YC-22]

---

## 2. Agent Isolation

*Mỗi Agent phải có boundary rõ ràng về state nào được phép đọc/ghi — phải có trong đặc tả, không chỉ trong implementation.*

- [ ] CHK007 - Spec có yêu cầu tường minh rằng mỗi Agent chỉ nhận context qua artifact references và DB state (cấm dùng shared conversational history) không? §YC-06 chỉ nêu constitution được inject, không phát biểu tổng quát về isolation model. [Gap, Spec §YC-06]

- [ ] CHK008 - Ràng buộc "tại 1 thời điểm chỉ có 1 Agent active trên 1 Task" có được đặc tả như một yêu cầu kiểm thử được không? (Không thấy YC nào phát biểu trực tiếp ràng buộc này.) [Gap]

- [ ] CHK009 - Yêu cầu inject Constitution vào Agent System Prompt (§YC-06) có xác định rõ phạm vi không? "Mọi Agent" có bao gồm cả Architect Agent khi sinh SPEC/PLAN, hay chỉ Coder Agent khi xử lý Task? [Ambiguity, Spec §YC-06, §Kịch Bản 3-2]

- [ ] CHK010 - Spec có định nghĩa chiến lược lọc nội dung MEMORY.md trước khi inject vào Agent context không? §YC-28 mô tả cách ghi, §YC-30 mô tả cách PO quản lý, nhưng không nêu tiêu chí "relevance" khi inject. [Gap, Spec §YC-28–30]

- [ ] CHK011 - Spec có yêu cầu Agent của project A không được đọc artifacts hoặc DB rows của project B không? (Giả định single-user MVP, nhưng isolation theo project_id có được phát biểu như một yêu cầu bảo mật hay chỉ là implementation detail?) [Gap, Spec §Giả Định]

- [ ] CHK012 - Kịch Bản 3-3 nêu "Agent chạy không có constitution" là valid state — spec có mô tả hành vi kỳ vọng của Agent trong trường hợp này không? (Chỉ nêu "không bị lỗi" nhưng không nêu output quality expectations.) [Clarity, Spec §Kịch Bản 3-3]

---

## 3. Data Integrity

*Ràng buộc dữ liệu phải được ghi rõ ở đúng lớp — không để implementer tự suy luận lớp nào enforce.*

- [ ] CHK013 - Yêu cầu "tên dự án duy nhất" tại §YC-02 phát biểu là duy nhất "trong phạm vi ứng dụng" — spec có làm rõ đây là system-wide uniqueness (không phải per-user) và tại sao với single-user MVP lại cần system-wide không? [Clarity, Spec §YC-02, §Giả Định]

- [ ] CHK014 - Spec có định nghĩa Task dependency (Task A phải Done trước khi Task B có thể chuyển In Progress) không? Spec mô tả "thứ tự ưu tiên" (§YC-15) nhưng không phát biểu ràng buộc dependency ordering như một requirement. [Gap, Spec §YC-15]

- [ ] CHK015 - Yêu cầu WIP limit = 1 tại §YC-17 có chỉ định lớp enforcement (DB constraint, service layer, hay cả hai) không? Spec phát biểu kết quả nhưng Research D-02 mới nêu cơ chế — là một gap giữa spec và research. [Completeness, Spec §YC-17, Research D-02]

- [ ] CHK016 - Điều kiện lock SPEC.md (chỉ lock khi Approved, không lock khi Draft) có được phát biểu rõ ràng và nhất quán với §YC-09 ("chỉnh sửa thủ công không tự động chuyển trạng thái") không? [Consistency, Spec §YC-08, §YC-09]

- [ ] CHK017 - Spec có định nghĩa hành vi khi `version` của Document tăng không? §Documents entity nêu "tăng khi Agent regenerates" — nhưng không nêu rõ version cũ có được giữ lại hay bị ghi đè. [Clarity, Spec §Documents entity]

- [ ] CHK018 - Kịch Bản 7-3 nêu "Task cũ bị xóa và Task mới thay thế" khi PLAN.md được regenerate — spec có định nghĩa trạng thái của Task đang In Progress khi PLAN.md bị Request Revision không? (Là một edge case quan trọng chưa có acceptance criteria.) [Gap, Spec §Kịch Bản 7-3, §Edge Cases Phase 1]

---

## 4. Error Handling

*Mỗi failure mode phải có acceptance criteria đo lường được — "hệ thống thông báo lỗi" không đủ.*

- [ ] CHK019 - Spec có định nghĩa retry behavior khi LLM API timeout không? TC-03 chỉ nêu "hiển thị thông báo timeout" sau 60 giây — không nêu số lần retry, backoff strategy, hay phân biệt transient vs permanent failure. [Gap, Spec §TC-03]

- [ ] CHK020 - Spec có yêu cầu tường minh về auto-pause khi Agent lặp quá N vòng ReAct không? Edge Case Phase 1 đặt câu hỏi "nếu Coder Agent không thể hoàn thành trong 10 phút" nhưng không có acceptance criteria cho câu trả lời. [Gap, Spec §Edge Cases Phase 1]

- [ ] CHK021 - Spec có định nghĩa timeout cho từng terminal command trong sandbox không? Không có YC hay TC nào đề cập đến per-command timeout trong Coder Agent execution. [Gap]

- [ ] CHK022 - Yêu cầu xử lý merge conflict tại §YC-35 có xác định đầy đủ intermediate states không? (Ví dụ: Task chuyển sang "Conflict" ngay lập tức hay sau khi PO được notify? Nhánh Task bị xóa hay giữ lại?) [Completeness, Spec §YC-35, §Kịch Bản 15-3]

- [ ] CHK023 - Edge Case "PO đóng trình duyệt khi Agent đang chạy" được liệt kê nhưng không có acceptance criteria — spec có trả lời câu hỏi này không? (Research D-05 mô tả background task pattern nhưng spec không phát biểu user-facing requirement.) [Gap, Spec §Edge Cases Phase 1, Research D-05]

- [ ] CHK024 - Spec có định nghĩa hành vi của hệ thống khi background asyncio task cho Agent kết thúc với exception không? (Status của agent_run record, notification cho PO, state của Task.) [Gap]

---

## 5. Security

*Security requirements phải được phát biểu trong spec/plan như requirements, không chỉ là implementation notes.*

- [ ] CHK025 - Spec có yêu cầu tường minh về bảo mật lưu trữ LLM API key không? §Giả Định chỉ nêu "API key đã được cung cấp" — không có YC nào yêu cầu encryption at rest hay access control cho key. [Gap, Spec §Giả Định]

- [ ] CHK026 - Spec có phát biểu rõ ràng về authentication/authorization không? §Giả Định nêu single-user, không có đăng nhập — nhưng không rõ điều này có nghĩa là "không cần auth" hay "auth được defer ra ngoài scope MVP". [Ambiguity, Spec §Giả Định]

- [ ] CHK027 - Sandbox isolation requirements có được phát biểu trong spec như requirements không? Research D-03 mô tả path validation implementation nhưng spec.md không có YC tương ứng yêu cầu sandbox isolation. [Gap, Research D-03]

- [ ] CHK028 - Spec có yêu cầu Agent-generated code không chứa hardcoded secrets không? (Constitution có thể có điều khoản này, nhưng spec bản thân không phát biểu requirement này.) [Gap]

- [ ] CHK029 - Audit log immutability được mô tả ở Data Model level — spec có phát biểu immutability như một yêu cầu (requirement) hay chỉ là implementation choice? [Completeness, Data Model §audit_logs, Spec §YC-21]

- [ ] CHK030 - Spec có định nghĩa ai/cái gì được phép đọc audit_log records không? Không có YC nào giới hạn truy cập audit log — là potential gap nếu tương lai mở rộng multi-user. [Gap, Spec §YC-21]
