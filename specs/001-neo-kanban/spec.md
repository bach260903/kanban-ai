# Đặc Tả Dự Án: Neo-Kanban — Nền Tảng Quản Lý Dự Án AI-Agentic

**Nhánh tính năng**: `001-neo-kanban`
**Ngày tạo**: 2026-05-11
**Trạng thái**: Draft
**Phạm vi**: Toàn bộ sản phẩm MVP — Phase 1 (luồng cốt lõi) + Phase 2 (tính năng AI nâng cao)

---

## Kịch Bản Người Dùng & Kiểm Thử *(bắt buộc)*

> **Ký hiệu ưu tiên**: P1 = MVP bắt buộc · P2 = nên có · P3 = tốt nếu có
> **[Phase 1]** = luồng cốt lõi · **[Phase 2]** = tính năng AI nâng cao

---

### Epic 1 — Quản Lý Dự Án

### Kịch Bản 1 — Tạo Dự Án Mới `[Phase 1]` (Ưu Tiên: P1)

PO mở ứng dụng Neo-Kanban lần đầu, nhập tên dự án, mô tả ngắn và chọn ngôn ngữ lập trình chính.
Hệ thống tạo dự án và chuyển PO vào không gian làm việc của dự án đó.

**Lý do ưu tiên**: Điều kiện tiên quyết để sử dụng mọi tính năng khác — không có dự án thì không
thể làm việc với Agent hay Kanban.

**Kiểm Thử Độc Lập**: Điền form tạo dự án → nhấn Tạo → xác nhận dự án xuất hiện trong danh sách
và mở được không gian làm việc.

**Kịch Bản Chấp Thuận**:

1. **Cho rằng** PO chưa có dự án nào, **khi** PO nhập tên, mô tả và ngôn ngữ rồi nhấn Tạo, **thì** dự án được tạo và PO được chuyển vào không gian làm việc của dự án đó.
2. **Cho rằng** PO để trống tên dự án, **khi** nhấn Tạo, **thì** hệ thống hiển thị thông báo lỗi "Tên dự án không được để trống" và không tạo dự án.
3. **Cho rằng** PO tạo dự án trùng tên với dự án đã có, **khi** nhấn Tạo, **thì** hệ thống thông báo trùng tên và yêu cầu đổi tên.

---

### Kịch Bản 2 — Xem Danh Sách & Mở Dự Án `[Phase 1]` (Ưu Tiên: P1)

PO quay lại ứng dụng sau một thời gian và thấy danh sách tất cả dự án đã tạo. PO chọn một
dự án để mở và tiếp tục làm việc từ trạng thái cuối cùng đã lưu.

**Lý do ưu tiên**: Cho phép PO quản lý nhiều dự án và không bị mất tiến trình giữa các phiên
làm việc.

**Kiểm Thử Độc Lập**: Tạo 2 dự án → đóng ứng dụng → mở lại → xác nhận cả 2 dự án xuất hiện
và mở được đúng trạng thái.

**Kịch Bản Chấp Thuận**:

1. **Cho rằng** PO có nhiều dự án, **khi** PO mở màn hình danh sách, **thì** tất cả dự án hiển thị với tên, mô tả ngắn và thời điểm cập nhật cuối.
2. **Cho rằng** PO click vào một dự án trong danh sách, **khi** mở dự án, **thì** hệ thống khôi phục đúng trạng thái Kanban, Intent và tài liệu của dự án đó.
3. **Cho rằng** PO chưa có dự án nào, **khi** mở màn hình danh sách, **thì** hiển thị màn hình trống kèm hướng dẫn tạo dự án đầu tiên.

---

### Kịch Bản 3 — Khai Báo Constitution Dự Án `[Phase 1]` (Ưu Tiên: P1)

PO mở tab Constitution trong dự án, soạn thảo các quy tắc bằng Markdown editor tích hợp sẵn,
và lưu lại. Từ lần chạy Agent tiếp theo, Agent đọc constitution này trước khi bắt đầu bất kỳ
tác vụ nào.

**Lý do ưu tiên**: Constitution đảm bảo Agent luôn tuân theo quy tắc của PO — không có nó,
Agent có thể tạo ra code không phù hợp với tiêu chuẩn của dự án.

**Kiểm Thử Độc Lập**: Soạn constitution → lưu → kích hoạt Agent cho Task → xác nhận Agent
tham chiếu constitution trong quá trình xử lý.

**Kịch Bản Chấp Thuận**:

1. **Cho rằng** PO mở tab Constitution, **khi** PO soạn nội dung và nhấn Lưu, **thì** nội dung được lưu và hiển thị đúng khi mở lại.
2. **Cho rằng** constitution đã có nội dung, **khi** Agent bắt đầu xử lý bất kỳ Task nào, **thì** constitution được đưa vào ngữ cảnh của Agent.
3. **Cho rằng** PO xóa toàn bộ nội dung constitution và lưu, **khi** Agent chạy lần tiếp theo, **thì** Agent không nhận ngữ cảnh constitution (không bị lỗi, chỉ chạy không có constitution).

---

### Epic 2 — Sinh & Duyệt Tài Liệu

### Kịch Bản 4 — Nhập Intent & Nhận SPEC.md Tự Động `[Phase 1]` (Ưu Tiên: P1)

PO nhập một câu mô tả ngắn (Intent) vào ô nhập liệu, nhấn Gửi. Architect Agent nhận Intent,
phân tích và sinh ra file SPEC.md với đầy đủ kịch bản người dùng, yêu cầu chức năng và tiêu
chí thành công. SPEC.md xuất hiện trên giao diện ở trạng thái Draft.

**Lý do ưu tiên**: Điểm khởi đầu của toàn bộ luồng agentic — không có SPEC.md thì không thể
lập kế hoạch hay tạo Task.

**Kiểm Thử Độc Lập**: Nhập Intent → chờ Agent → xác nhận SPEC.md xuất hiện với nội dung liên
quan đến Intent và trạng thái Draft.

**Kịch Bản Chấp Thuận**:

1. **Cho rằng** PO nhập Intent và nhấn Gửi, **khi** Architect Agent hoàn thành, **thì** SPEC.md xuất hiện trên giao diện với trạng thái "Draft" và nội dung liên quan trực tiếp đến Intent.
2. **Cho rằng** Agent đang sinh SPEC.md, **khi** quá trình kéo dài hơn 60 giây, **thì** hệ thống hiển thị thông báo timeout và cho phép PO thử lại.
3. **Cho rằng** SPEC.md đã tồn tại trong dự án, **khi** PO nhập Intent mới, **thì** hệ thống cảnh báo "SPEC.md hiện tại sẽ bị thay thế" và yêu cầu PO xác nhận trước khi tiếp tục.

---

### Kịch Bản 5 — Duyệt SPEC.md `[Phase 1]` (Ưu Tiên: P1)

PO đọc SPEC.md do Agent sinh ra, có thể chỉnh sửa trực tiếp nếu cần. PO chọn Approve để tiếp
tục sang bước lập kế hoạch kỹ thuật, hoặc Request Revision kèm feedback để Agent chỉnh lại.
Không thể tiến sang bước tiếp theo nếu chưa Approve.

**Lý do ưu tiên**: HIL checkpoint bắt buộc — đảm bảo PO kiểm soát chất lượng đặc tả trước khi
đầu tư công sức lập kế hoạch kỹ thuật.

**Kiểm Thử Độc Lập**: Xem SPEC.md → nhấn Approve → xác nhận trạng thái chuyển sang "Approved"
và nút "Sinh PLAN.md" xuất hiện.

**Kịch Bản Chấp Thuận**:

1. **Cho rằng** SPEC.md ở trạng thái Draft, **khi** PO nhấn Approve, **thì** SPEC.md chuyển sang trạng thái "Approved" và hệ thống mở khóa bước tiếp theo.
2. **Cho rằng** SPEC.md ở trạng thái Draft, **khi** PO nhấn Request Revision kèm feedback, **thì** SPEC.md chuyển sang "Revision Requested", Agent nhận feedback và sinh lại SPEC.md mới.
3. **Cho rằng** SPEC.md chưa được Approve, **khi** PO cố chuyển sang bước lập kế hoạch, **thì** hệ thống từ chối và hiển thị thông báo "Vui lòng Approve SPEC.md trước".
4. **Cho rằng** PO chỉnh sửa SPEC.md thủ công và lưu, **khi** trạng thái là Draft, **thì** trạng thái giữ nguyên Draft (chỉnh sửa thủ công không tự động Approve).

---

### Kịch Bản 6 — Nhận & Duyệt PLAN.md `[Phase 1]` (Ưu Tiên: P1)

Sau khi SPEC.md được Approve, PO nhấn nút kích hoạt để Architect Agent sinh PLAN.md (kiến
trúc kỹ thuật). PO đọc, có thể chỉnh sửa, rồi Approve hoặc Request Revision. Không thể phân
rã Task nếu chưa Approve PLAN.md.

**Lý do ưu tiên**: HIL checkpoint thứ hai — đảm bảo kế hoạch kỹ thuật hợp lý trước khi Agent
bắt đầu viết code.

**Kiểm Thử Độc Lập**: Approve SPEC.md → kích hoạt sinh PLAN.md → đọc và Approve PLAN.md →
xác nhận Task list xuất hiện trong cột To Do.

**Kịch Bản Chấp Thuận**:

1. **Cho rằng** SPEC.md đã Approved, **khi** PO nhấn "Sinh PLAN.md", **thì** Architect Agent chạy và PLAN.md xuất hiện ở trạng thái Draft.
2. **Cho rằng** PLAN.md ở trạng thái Draft, **khi** PO nhấn Approve, **thì** PLAN.md chuyển sang "Approved" và hệ thống tự động phân rã Task vào cột To Do.
3. **Cho rằng** PLAN.md ở trạng thái Draft, **khi** PO Request Revision kèm feedback, **thì** Agent sinh lại PLAN.md mới dựa trên feedback.
4. **Cho rằng** PLAN.md chưa Approved, **khi** PO cố xem Task list, **thì** cột To Do hiển thị thông báo "Chờ PLAN.md được Approve".

---

### Epic 3 — Kanban & Coding

### Kịch Bản 7 — Task Tự Động Xuất Hiện Trong To Do `[Phase 1]` (Ưu Tiên: P1)

Ngay sau khi PO Approve PLAN.md, hệ thống tự động phân rã kế hoạch thành danh sách Task
có thứ tự ưu tiên và hiển thị trong cột To Do trên bảng Kanban. PO không cần làm gì thêm.

**Lý do ưu tiên**: Liên kết trực tiếp giữa PLAN.md và Kanban — PO không phải nhập tay danh
sách Task.

**Kiểm Thử Độc Lập**: Approve PLAN.md → đếm số Task trong To Do → xác nhận khớp với số Task
trong PLAN.md và không có Task nào bị thiếu.

**Kịch Bản Chấp Thuận**:

1. **Cho rằng** PO vừa Approve PLAN.md, **khi** hệ thống phân rã, **thì** tất cả Task trong PLAN.md xuất hiện trong cột To Do với đúng tiêu đề, mô tả và thứ tự ưu tiên.
2. **Cho rằng** Task đã xuất hiện trong To Do, **khi** PO xem từng Task, **thì** mỗi Task hiển thị mô tả rõ ràng đủ để PO hiểu Task yêu cầu làm gì.
3. **Cho rằng** PLAN.md được Request Revision và sinh lại, **khi** PO Approve PLAN.md mới, **thì** danh sách Task cũ bị xóa và danh sách Task mới thay thế.

---

### Kịch Bản 8 — Kéo Task Vào In Progress & Kích Hoạt Agent `[Phase 1]` (Ưu Tiên: P1)

PO kéo một Task từ To Do sang In Progress. Hệ thống kiểm tra WIP limit (chỉ 1 Task In Progress
tại một thời điểm). Nếu hợp lệ, Coder Agent được kích hoạt để bắt đầu xử lý Task đó.
Agent không tự chạy — chỉ chạy sau khi PO kéo Task.

**Lý do ưu tiên**: Điểm kích hoạt agentic cốt lõi — kiểm soát khi nào AI được phép hành động.

**Kiểm Thử Độc Lập**: Kéo Task → xác nhận Task chuyển sang In Progress và Agent bắt đầu xử lý
(có thể thấy trạng thái "Agent đang chạy").

**Kịch Bản Chấp Thuận**:

1. **Cho rằng** không có Task nào đang In Progress, **khi** PO kéo Task từ To Do sang In Progress, **thì** Task chuyển trạng thái và Coder Agent được kích hoạt xử lý Task.
2. **Cho rằng** đã có 1 Task đang In Progress, **khi** PO cố kéo Task thứ hai sang In Progress, **thì** hệ thống từ chối với thông báo "WIP limit: chỉ được 1 Task In Progress. Hoàn thành Task hiện tại trước."
3. **Cho rằng** không có Task In Progress, **khi** Coder Agent chưa được PO kích hoạt, **thì** Agent không tự khởi động dù thời gian chờ bao lâu.

---

### Kịch Bản 9 — Xem Diff & Approve hoặc Reject Code `[Phase 1]` (Ưu Tiên: P1)

Sau khi Coder Agent hoàn thành xử lý Task, hệ thống chuyển Task sang Review và hiển thị Diff
Viewer. PO xem rõ từng dòng được thêm (xanh), xóa (đỏ), hoặc sửa (highlight). PO chọn Approve
(Task → Done) hoặc Reject kèm feedback văn bản (Task → In Progress để Agent sửa lại).

**Lý do ưu tiên**: HIL checkpoint cuối cùng — PO có quyết định cuối cùng về chất lượng code
trước khi chấp nhận output của AI.

**Kiểm Thử Độc Lập**: Agent hoàn thành Task → Diff Viewer hiển thị → PO Approve → xác nhận
Task chuyển sang Done và code được áp dụng.

**Kịch Bản Chấp Thuận**:

1. **Cho rằng** Agent vừa hoàn thành Task, **khi** Task chuyển sang Review, **thì** Diff Viewer tự động hiển thị với màu xanh cho dòng thêm, màu đỏ cho dòng xóa, và highlight cho dòng sửa.
2. **Cho rằng** PO xem xong Diff và hài lòng, **khi** PO nhấn Approve, **thì** Task chuyển sang Done và thay đổi code được áp dụng vào codebase.
3. **Cho rằng** PO muốn sửa lại, **khi** PO nhấn Reject kèm feedback bằng văn bản, **thì** Task trở về In Progress, Agent nhận feedback và xử lý lại.
4. **Cho rằng** Task ở trạng thái Review, **khi** PO không có hành động nào, **thì** Agent KHÔNG tự chuyển Task sang Done — luôn chờ PO quyết định.

---

### Epic 4 — Giám Sát AI

### Kịch Bản 10 — Giám Sát Hoạt Động AI Theo Thời Gian Thực `[Phase 2]` (Ưu Tiên: P1)

Khi Coder Agent đang xử lý một Task, PO có thể mở bảng Thought Stream và quan sát từng bước
Agent thực hiện theo thời gian thực: suy luận, gọi công cụ, kết quả công cụ, hành động,
lỗi và thay đổi trạng thái. Mỗi sự kiện hiển thị loại và nội dung rõ ràng.

**Lý do ưu tiên**: Cho phép PO có tầm nhìn đầy đủ về hoạt động của AI, tăng niềm tin và hỗ trợ
phát hiện sớm khi Agent đi sai hướng mà không cần chờ đến lúc code được tạo ra.

**Kiểm Thử Độc Lập**: Kích hoạt Agent xử lý một Task và xác nhận rằng tất cả loại sự kiện
xuất hiện đúng thứ tự thời gian thực trên giao diện.

**Kịch Bản Chấp Thuận**:

1. **Cho rằng** Agent đang xử lý Task, **khi** PO mở Thought Stream panel, **thì** các sự kiện THOUGHT, TOOL_CALL, TOOL_RESULT, ACTION, ERROR, STATUS_CHANGE xuất hiện theo thứ tự thời gian thực, mỗi sự kiện có nhãn loại và nội dung.
2. **Cho rằng** kết nối bị gián đoạn, **khi** kết nối được khôi phục, **thì** hệ thống tự động kết nối lại và tiếp tục nhận sự kiện từ điểm cuối đã nhận được.
3. **Cho rằng** Agent hoàn thành Task, **khi** Task chuyển sang Review, **thì** stream kết thúc và hiển thị tổng kết số lượng từng loại sự kiện.

---

### Kịch Bản 11 — Tạm Dừng & Điều Hướng Lại Agent `[Phase 2]` (Ưu Tiên: P1)

PO có thể nhấn nút Pause trên Task đang In Progress. Agent hoàn thành bước suy luận hiện tại
rồi dừng. PO nhập hướng dẫn mới và nhấn Resume. Agent tiếp tục xử lý với hướng dẫn bổ sung
trong ngữ cảnh.

**Lý do ưu tiên**: Cho phép PO can thiệp điều hướng khi phát hiện Agent đi sai hướng mà không
cần hủy toàn bộ Task và bắt đầu lại từ đầu.

**Kiểm Thử Độc Lập**: PO nhấn Pause → nhập hướng dẫn → Resume; xác nhận Agent dừng đúng lúc
(không vượt quá 1 bước) và tiếp tục với hướng dẫn mới được phản ánh trong hành động kế tiếp.

**Kịch Bản Chấp Thuận**:

1. **Cho rằng** Agent đang xử lý, **khi** PO nhấn Pause, **thì** Agent hoàn thành bước suy luận hiện tại rồi dừng — không thực thi thêm bước nào sau khi nhận lệnh Pause.
2. **Cho rằng** Agent đã Pause, **khi** PO nhập hướng dẫn mới và nhấn Resume, **thì** Agent tiếp tục với hướng dẫn bổ sung trong ngữ cảnh và hành động kế tiếp phản ánh hướng dẫn mới.
3. **Cho rằng** Agent đang Pause, **khi** PO không thao tác trong 30 phút, **thì** hệ thống hiển thị cảnh báo "Agent đang chờ — sẽ giữ trạng thái Pause cho đến khi bạn Resume hoặc hủy Task".

---

### Epic 5 — Bộ Nhớ & Ngữ Cảnh

### Kịch Bản 12 — Ghi Bài Học Tự Động Vào Bộ Nhớ `[Phase 2]` (Ưu Tiên: P2)

Sau khi PO Approve Task và Task chuyển sang Done, hệ thống tự động trích xuất bài học từ quá
trình thực thi và ghi vào MEMORY.md kèm metadata đầy đủ để Agent trong các Task sau tham chiếu.

**Lý do ưu tiên**: Cho phép Agent học từ kinh nghiệm trước, cải thiện chất lượng đề xuất theo
thời gian và giảm số lần mắc lỗi tương tự trong cùng dự án.

**Kiểm Thử Độc Lập**: Approve một Task → kiểm tra MEMORY.md có entry mới đúng định dạng với đủ
5 trường bắt buộc.

**Kịch Bản Chấp Thuận**:

1. **Cho rằng** PO vừa Approve Task, **khi** Task chuyển sang Done, **thì** MEMORY.md nhận entry mới gồm đầy đủ: timestamp, task_id, summary, files_affected, lessons_learned.
2. **Cho rằng** entry được ghi, **khi** Agent bắt đầu Task tiếp theo trong cùng dự án, **thì** Agent đọc MEMORY.md và ngữ cảnh Agent chứa các bài học liên quan.
3. **Cho rằng** nhiều Task Done gần như cùng lúc, **khi** ghi MEMORY.md, **thì** mọi entry đều được ghi đầy đủ, không entry nào bị mất hoặc ghi đè lên nhau.

---

### Kịch Bản 13 — Chỉnh Sửa Bộ Nhớ Thủ Công `[Phase 2]` (Ưu Tiên: P2)

PO có thể mở giao diện quản lý MEMORY.md, xem danh sách tất cả entry, chỉnh sửa hoặc xóa
entry không chính xác, và lưu thay đổi. Thay đổi có hiệu lực ngay cho Task tiếp theo.

**Lý do ưu tiên**: Cho phép PO duy trì chất lượng bộ nhớ bằng cách loại bỏ thông tin sai lệch
hoặc đã lỗi thời trước khi chúng ảnh hưởng đến Agent.

**Kiểm Thử Độc Lập**: Mở MEMORY.md editor → xóa một entry → lưu → kích hoạt Task mới →
xác nhận Agent không tham chiếu đến entry đã xóa.

**Kịch Bản Chấp Thuận**:

1. **Cho rằng** MEMORY.md có ít nhất 1 entry, **khi** PO xóa entry và lưu, **thì** entry không xuất hiện trong ngữ cảnh của Agent trong bất kỳ Task nào sau đó.
2. **Cho rằng** PO đang chỉnh sửa MEMORY.md, **khi** Agent cố đọc cùng lúc, **thì** Agent nhận phiên bản được lưu cuối cùng — không đọc bản đang chỉnh sửa dở.
3. **Cho rằng** PO lưu chỉnh sửa thành công, **khi** PO mở lại MEMORY.md editor, **thì** nội dung hiển thị đúng với bản đã lưu.

---

### Epic 6 — Codebase Intelligence

### Kịch Bản 14 — Phân Tích Cấu Trúc Codebase `[Phase 2]` (Ưu Tiên: P2)

Khi Agent bắt đầu xử lý Task, hệ thống tự động phân tích codebase và tạo bản đồ cấu trúc
(danh sách file, class, hàm, chữ ký). Bản đồ này được truyền cho Agent thay vì nội dung file
thô, giúp Agent hiểu cấu trúc toàn project mà không tiêu thụ quá nhiều ngữ cảnh.

**Lý do ưu tiên**: Giảm đáng kể lượng ngữ cảnh tiêu thụ và giúp Agent định vị chính xác
file/hàm cần chỉnh sửa ngay từ lần đầu.

**Kiểm Thử Độc Lập**: Kích hoạt Agent → kiểm tra ngữ cảnh truyền cho Agent chứa codebase map
dạng cấu trúc → Agent đề xuất đúng file và tên hàm.

**Kịch Bản Chấp Thuận**:

1. **Cho rằng** dự án có codebase Python hoặc JS/TS, **khi** Agent bắt đầu xử lý Task, **thì** codebase map (danh sách file, class, hàm, chữ ký hàm) được đưa vào ngữ cảnh Agent thay vì nội dung file thô.
2. **Cho rằng** codebase map có trong ngữ cảnh, **khi** Agent đề xuất thay đổi, **thì** Agent tham chiếu đúng đường dẫn file và tên hàm từ map, không tự bịa.
3. **Cho rằng** codebase thay đổi sau khi Task hoàn thành, **khi** Task mới bắt đầu, **thì** map được làm mới trước khi truyền cho Agent.

---

### Epic 7 — Git & Diff Nâng Cao

### Kịch Bản 15 — Quản Lý Git Tự Động Theo Task `[Phase 2]` (Ưu Tiên: P3)

Khi Task chuyển sang In Progress, hệ thống tự tạo nhánh Git riêng. Khi PO Approve code, hệ
thống tự động gộp toàn bộ commit của Task thành 1 commit duy nhất và merge vào nhánh chính.
Khi có xung đột, hệ thống dừng và yêu cầu PO xử lý thủ công.

**Lý do ưu tiên**: Tự động hóa quy trình Git giữ lịch sử commit sạch, mỗi Task có nhánh riêng
để review và rollback độc lập nếu cần.

**Kiểm Thử Độc Lập**: Kéo Task → xác nhận nhánh Git mới tồn tại → Approve → xác nhận 1 commit
squash được tạo và merge thành công vào nhánh chính.

**Kịch Bản Chấp Thuận**:

1. **Cho rằng** PO kéo Task sang In Progress, **khi** hệ thống xử lý, **thì** nhánh Git tên `task/<task_id>` được tạo tự động và Agent làm việc trên nhánh đó.
2. **Cho rằng** PO Approve code, **khi** hệ thống thực hiện merge, **thì** tất cả commit của Task được gộp thành đúng 1 commit duy nhất và merge vào nhánh chính.
3. **Cho rằng** merge gặp xung đột, **khi** hệ thống phát hiện, **thì** hệ thống dừng merge, gán nhãn "Conflict" cho Task, và hiển thị thông báo yêu cầu PO xử lý thủ công.

---

### Kịch Bản 16 — Inline Comment Trên Diff Khi Reject `[Phase 2]` (Ưu Tiên: P3)

Khi PO xem Diff và muốn Reject, PO có thể click vào dòng code cụ thể, nhập comment, và
gắn nhiều comment trên nhiều dòng/file khác nhau. Khi submit Reject, Agent nhận feedback
kèm danh sách comment theo vị trí dòng để sửa đúng chỗ.

**Lý do ưu tiên**: Giảm số vòng lặp review bằng cách cung cấp phản hồi chính xác tới từng
dòng code, tránh phải mô tả tổng quát không rõ ràng.

**Kiểm Thử Độc Lập**: Mở Diff Viewer → click dòng cụ thể → nhập comment → Reject → xác nhận
Agent nhận feedback chứa thông tin file, số dòng và nội dung comment chính xác.

**Kịch Bản Chấp Thuận**:

1. **Cho rằng** PO đang xem Diff, **khi** PO click vào một dòng code, **thì** ô nhập comment xuất hiện gắn với dòng đó và hiển thị inline trên Diff.
2. **Cho rằng** PO submit Reject với inline comments, **khi** Agent nhận feedback, **thì** feedback chứa danh sách chính xác `{file, line, comment}` cho từng comment PO đã nhập.
3. **Cho rằng** Agent nhận inline comments, **khi** Agent sửa lại code, **thì** Agent chỉ sửa các vùng được comment, không thay đổi phần code khác không liên quan.

---

### Trường Hợp Biên

**Phase 1:**
- Điều gì xảy ra nếu Architect Agent thất bại khi sinh SPEC.md (lỗi kết nối LLM)?
- Hệ thống xử lý thế nào nếu PO xóa một Task đang In Progress mà Agent đang chạy?
- Điều gì xảy ra nếu PO cố Request Revision SPEC.md trong khi Agent đang sinh PLAN.md?
- Nếu Coder Agent không thể hoàn thành Task trong 10 phút (timeout), hệ thống thông báo thế nào?
- Nếu PO đóng trình duyệt khi Agent đang chạy, tiến trình Agent có bị mất không?

**Phase 2:**
- Điều gì xảy ra khi Agent bị Pause và PO không Resume trong hơn 24 giờ?
- Hệ thống xử lý thế nào khi MEMORY.md vượt quá 1 MB (quá nhiều entry tích lũy)?
- Codebase map xử lý thế nào với codebase có hơn 500 file hoặc file riêng lẻ hơn 10.000 dòng?
- Điều gì xảy ra khi nhánh chính cập nhật sau khi nhánh Task được tạo, dẫn đến xung đột khi merge?
- Hệ thống xử lý thế nào nếu PO đồng thời chỉnh sửa MEMORY.md và Agent đang ghi entry mới?

---

## Yêu Cầu *(bắt buộc)*

### Yêu Cầu Chức Năng

#### Nhóm A — Quản Lý Dự Án `[Phase 1]`

- **YC-01**: PO PHẢI có thể tạo dự án mới với tối thiểu 3 thông tin: tên dự án (bắt buộc), mô tả (tùy chọn), ngôn ngữ lập trình chính (bắt buộc).
- **YC-02**: Tên dự án PHẢI là duy nhất trong phạm vi ứng dụng; hệ thống PHẢI từ chối tạo dự án trùng tên.
- **YC-03**: PO PHẢI có thể xem danh sách tất cả dự án đã tạo, mỗi dự án hiển thị tên, mô tả ngắn và thời gian cập nhật cuối.
- **YC-04**: PO PHẢI có thể mở một dự án và hệ thống PHẢI khôi phục đúng trạng thái cuối cùng đã lưu (Kanban, Intent, tài liệu).
- **YC-05**: PO PHẢI có thể soạn thảo và lưu constitution dự án dưới dạng Markdown qua editor tích hợp sẵn.
- **YC-06**: Khi Agent bắt đầu xử lý bất kỳ Task nào, hệ thống PHẢI đưa constitution hiện tại của dự án vào ngữ cảnh Agent.

#### Nhóm B — Sinh & Duyệt Tài Liệu `[Phase 1]`

- **YC-07**: PO PHẢI có thể nhập Intent (văn bản tự do) để kích hoạt Architect Agent sinh SPEC.md.
- **YC-08**: SPEC.md được sinh ra PHẢI có trạng thái "Draft" cho đến khi PO Approve.
- **YC-09**: PO PHẢI có thể chỉnh sửa SPEC.md thủ công; việc chỉnh sửa thủ công KHÔNG tự động chuyển trạng thái.
- **YC-10**: PO PHẢI có thể Approve hoặc Request Revision SPEC.md; Request Revision PHẢI kèm theo feedback bằng văn bản.
- **YC-11**: Hệ thống PHẢI ngăn PO chuyển sang bước sinh PLAN.md khi SPEC.md chưa ở trạng thái Approved.
- **YC-12**: Sau khi SPEC.md được Approve, PO PHẢI có thể kích hoạt Architect Agent sinh PLAN.md.
- **YC-13**: PLAN.md được sinh ra PHẢI có trạng thái "Draft" cho đến khi PO Approve.
- **YC-14**: PO PHẢI có thể Approve hoặc Request Revision PLAN.md; hệ thống PHẢI ngăn phân rã Task khi PLAN.md chưa Approved.

#### Nhóm C — Kanban & Coding `[Phase 1]`

- **YC-15**: Ngay sau khi PO Approve PLAN.md, hệ thống PHẢI tự động tạo danh sách Task và hiển thị trong cột To Do trên Kanban.
- **YC-16**: PO PHẢI có thể kéo Task từ To Do sang In Progress để kích hoạt Coder Agent.
- **YC-17**: Hệ thống PHẢI áp dụng WIP limit = 1: từ chối chuyển Task thứ hai sang In Progress khi đã có Task đang In Progress.
- **YC-18**: Coder Agent PHẢI CHỈ khởi động khi PO kéo Task sang In Progress — không tự chạy trong bất kỳ tình huống nào khác.
- **YC-19**: Sau khi Coder Agent hoàn thành, Task PHẢI chuyển sang Review và hệ thống PHẢI hiển thị Diff Viewer với màu sắc phân biệt rõ dòng thêm/xóa/sửa.
- **YC-20**: PO PHẢI có thể Approve (Task → Done) hoặc Reject kèm feedback (Task → In Progress) từ giao diện Diff Viewer.
- **YC-21**: Hệ thống PHẢI ghi log mọi hành động của Agent vào cơ sở dữ liệu.
- **YC-22**: Task KHÔNG ĐƯỢC tự động chuyển sang Done mà không có hành động Approve rõ ràng từ PO.

#### Nhóm D — Giám Sát AI `[Phase 2]`

- **YC-23**: Hệ thống PHẢI phát sự kiện theo thời gian thực với đúng 6 loại: THOUGHT, TOOL_CALL, TOOL_RESULT, ACTION, ERROR, STATUS_CHANGE trong quá trình Agent xử lý Task.
- **YC-24**: Giao diện PHẢI hiển thị sự kiện stream theo thứ tự thời gian với nhãn loại và timestamp rõ ràng.
- **YC-25**: Hệ thống PHẢI hỗ trợ kết nối lại tự động khi stream bị gián đoạn, tiếp tục từ sự kiện cuối đã nhận mà không mất sự kiện nào.
- **YC-26**: PO PHẢI có thể nhấn Pause để yêu cầu Agent dừng; Agent PHẢI dừng sau khi hoàn thành bước suy luận đang xử lý, không vượt quá 1 bước.
- **YC-27**: Sau khi Pause, PO PHẢI có thể nhập hướng dẫn bổ sung và nhấn Resume để Agent tiếp tục với hướng dẫn mới trong ngữ cảnh.

#### Nhóm E — Bộ Nhớ & Ngữ Cảnh `[Phase 2]`

- **YC-28**: Hệ thống PHẢI tự động tạo entry trong MEMORY.md ngay khi Task chuyển sang Done; entry PHẢI gồm đủ 5 trường: timestamp, task_id, summary, files_affected, lessons_learned.
- **YC-29**: PO PHẢI có thể xem toàn bộ danh sách entry trong MEMORY.md qua giao diện riêng.
- **YC-30**: PO PHẢI có thể chỉnh sửa hoặc xóa bất kỳ entry nào trong MEMORY.md và lưu thay đổi; thay đổi có hiệu lực ngay với Task tiếp theo.

#### Nhóm F — Codebase Intelligence `[Phase 2]`

- **YC-31**: Hệ thống PHẢI tạo bản đồ cấu trúc codebase (file, class, hàm, chữ ký) và đưa vào ngữ cảnh Agent trước khi Agent bắt đầu xử lý Task; chỉ hỗ trợ Python và JavaScript/TypeScript.
- **YC-32**: Bản đồ codebase PHẢI được làm mới tại thời điểm bắt đầu mỗi Task mới.

#### Nhóm G — Git & Diff Nâng Cao `[Phase 2]`

- **YC-33**: Hệ thống PHẢI tự động tạo nhánh Git riêng đặt tên theo task_id ngay khi Task chuyển sang In Progress; Agent thực hiện mọi thay đổi trên nhánh đó.
- **YC-34**: Khi PO Approve code, hệ thống PHẢI gộp toàn bộ commit của Task thành 1 commit duy nhất và merge vào nhánh chính.
- **YC-35**: Khi merge gặp xung đột, hệ thống PHẢI dừng merge, gán nhãn "Conflict" cho Task và thông báo PO cần xử lý thủ công; hệ thống KHÔNG TỰ giải quyết xung đột.
- **YC-36**: Trong Diff Viewer, PO PHẢI có thể click vào bất kỳ dòng code nào để mở ô nhập inline comment gắn với dòng đó.
- **YC-37**: Khi PO submit Reject kèm inline comments, hệ thống PHẢI truyền cho Agent danh sách đầy đủ `{file, line, comment}` cho từng comment đã nhập.

### Thực Thể Chính

- **Dự Án (Project)**: Đơn vị quản lý cấp cao nhất — tên (duy nhất), mô tả, ngôn ngữ lập trình, constitution, trạng thái, ngày tạo
- **Intent**: Mô tả tính năng bằng ngôn ngữ tự nhiên của PO — nội dung văn bản, project_id, ngày tạo
- **Tài Liệu (Document)**: SPEC.md hoặc PLAN.md — loại (SPEC/PLAN), nội dung Markdown, trạng thái (Draft/Approved/Revision Requested), project_id, phiên bản
- **Task**: Đơn vị công việc trên Kanban — tiêu đề, mô tả, trạng thái (To Do/In Progress/Review/Done/Rejected/Conflict), thứ tự ưu tiên, project_id
- **Lần Chạy Agent (AgentRun)**: Một lần Agent xử lý — task_id, agent_type, trạng thái, thời gian bắt đầu/kết thúc, kết quả
- **Diff**: Kết quả thay đổi code do Agent tạo ra — task_id, nội dung diff, danh sách file bị ảnh hưởng, trạng thái review
- **Phản Hồi (Feedback)**: Ý kiến PO khi Request Revision hoặc Reject — document_id hoặc task_id, nội dung văn bản, ngày tạo
- **StreamEvent**: Sự kiện real-time từ Agent — loại (THOUGHT/TOOL_CALL/TOOL_RESULT/ACTION/ERROR/STATUS_CHANGE), nội dung, timestamp UTC, task_id
- **AgentPauseState**: Trạng thái tạm dừng — task_id, trạng thái (RUNNING/PAUSED), hướng dẫn bổ sung của PO, thời điểm Pause
- **MemoryEntry**: Bài học trong MEMORY.md — timestamp, task_id, summary, files_affected, lessons_learned
- **CodebaseMap**: Bản đồ cấu trúc — danh sách file theo cây thư mục, class/hàm kèm chữ ký, ngôn ngữ
- **TaskBranch**: Liên kết Task với Git — task_id, branch_name, trạng thái (ACTIVE/MERGED/CONFLICT)
- **InlineComment**: Phản hồi theo dòng — file_path, line_number, nội dung comment, task_id, created_at

## Tiêu Chí Thành Công *(bắt buộc)*

### Kết Quả Đo Lường Được

**Phase 1:**

- **TC-01**: PO hoàn thành việc tạo dự án mới trong vòng dưới 2 phút kể từ khi mở ứng dụng.
- **TC-02**: 100% các bước chuyển trạng thái yêu cầu Approve đều có checkpoint — không có bước nào tự động bỏ qua mà không có hành động rõ ràng từ PO.
- **TC-03**: SPEC.md được sinh và hiển thị trong vòng 60 giây sau khi PO nhập Intent (hoặc hiển thị thông báo timeout rõ ràng nếu vượt quá).
- **TC-04**: WIP limit được áp dụng 100%: không có trường hợp nào hệ thống cho phép 2 Task đồng thời ở trạng thái In Progress.
- **TC-05**: Diff Viewer hiển thị đúng màu sắc phân biệt cho 100% dòng thêm (xanh), xóa (đỏ) và sửa (highlight).
- **TC-06**: PO có thể hoàn thành toàn bộ luồng từ Intent đến Task Done mà không gặp lỗi chặn trong điều kiện Agent hoạt động bình thường.
- **TC-07**: Agent không khởi động trong bất kỳ tình huống nào trừ khi PO thực hiện hành động kích hoạt rõ ràng.

**Phase 2:**

- **TC-08**: PO nhận được sự kiện stream trong vòng 2 giây kể từ khi Agent bắt đầu bước xử lý mới.
- **TC-09**: Khi PO nhấn Pause, Agent dừng sau không quá 1 bước suy luận — không có trường hợp Agent thực thi 2 bước trở lên sau lệnh Pause.
- **TC-10**: 100% Task chuyển sang Done tạo ra ít nhất 1 entry MEMORY.md với đầy đủ 5 trường bắt buộc; 0% entry thiếu trường.
- **TC-11**: Bản đồ codebase được tạo và đưa vào ngữ cảnh Agent trong vòng 10 giây với codebase lên đến 500 file.
- **TC-12**: 100% lần PO Approve có kết quả merge rõ ràng: hoặc merge thành công với đúng 1 commit squash, hoặc thông báo conflict hiển thị cho PO.
- **TC-13**: 0% sai lệch trong ánh xạ inline comment — file_path và line_number trong feedback khớp chính xác với vị trí PO đã click trong Diff Viewer.
- **TC-14**: Sau khi PO xóa entry khỏi MEMORY.md, entry đó không xuất hiện trong ngữ cảnh của bất kỳ Task nào tiếp theo.

## Giả Định

- Ứng dụng chỉ có 1 người dùng là Project Owner (PO) trong MVP; không có phân quyền hay đăng nhập nhiều tài khoản.
- LLM backend đã được cấu hình và API key đã được cung cấp; đặc tả này không mô tả quá trình cấu hình LLM.
- Sandbox thực thi code là thư mục local trên máy chủ; Docker không được dùng ở MVP.
- Codebase của dự án PO quản lý nằm trên máy cục bộ và ứng dụng có quyền đọc/ghi vào thư mục đó.
- Trạng thái của Kanban, Intent và tài liệu được lưu bền vững và không bị mất khi đóng/mở lại ứng dụng.
- Phase 2 chỉ bắt đầu sau khi Phase 1 đã hoàn chỉnh và hoạt động ổn định.
- Codebase mapping (Phase 2) chỉ hỗ trợ Python và JavaScript/TypeScript; ngôn ngữ khác ngoài phạm vi.
- MEMORY.md được lưu riêng biệt cho từng dự án và không chia sẻ giữa các dự án khác nhau.
- PO chấp nhận xử lý xung đột Git thủ công; hệ thống không tự giải quyết xung đột.
- Inline comment chỉ áp dụng khi PO chọn Reject; khi Approve không cần comment.
- Các tính năng ngoài phạm vi MVP: Reviewer Agent tự động, Docker sandbox, Multi-user/RBAC.
