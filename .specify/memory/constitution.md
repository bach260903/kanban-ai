<!--
  BÁO CÁO ĐỒNG BỘ
  ================
  Thay đổi phiên bản: 1.0.0 → 1.0.1
  Loại bump: PATCH — dịch toàn bộ nội dung sang tiếng Việt, không thay đổi ngữ nghĩa.

  Nguyên tắc đã sửa đổi:
  - Tất cả 8 nguyên tắc: dịch nội dung sang tiếng Việt (tiêu đề giữ nguyên để tương thích công cụ)

  Các mục đã cập nhật:
  - Nguyên tắc Cốt lõi → ngôn ngữ tiếng Việt
  - Ràng buộc Công nghệ → ngôn ngữ tiếng Việt
  - Quy trình Phát triển → ngôn ngữ tiếng Việt
  - Quản trị → ngôn ngữ tiếng Việt

  Templates đã kiểm tra:
  - .specify/templates/plan-template.md ✅ không cần thay đổi
  - .specify/templates/spec-template.md ✅ không cần thay đổi
  - .specify/templates/tasks-template.md ✅ không cần thay đổi

  TODOs còn lại:
  - Không có.
-->

# Hiến Pháp Dự Án Neo-Kanban

## Nguyên Tắc Cốt Lõi

### I. Giao Tiếp Qua Artifact (BẮT BUỘC TUYỆT ĐỐI)

Các Agent PHẢI giao tiếp độc quyền thông qua file artifact `.md` và trạng thái DB đã lưu trữ.
Các Agent KHÔNG ĐƯỢC chia sẻ hoặc truyền lịch sử hội thoại cho nhau.
Mỗi lần bàn giao giữa các Agent PHẢI có khả năng tái tạo hoàn toàn từ trạng thái DB và file artifact.
Bất kỳ Agent nào nhận nhiệm vụ đều PHẢI đọc artifact liên quan từ disk/DB trước khi hành động —
Agent KHÔNG ĐƯỢC dựa vào trạng thái bộ nhớ của lần gọi Agent trước.

**Lý do**: Ngăn chặn sự phụ thuộc ngầm giữa các Agent, đảm bảo mỗi lần chạy Agent đều có thể
kiểm tra độc lập và khởi động lại, đồng thời loại bỏ lỗi trạng thái từ ngữ cảnh dùng chung.

### II. Điểm Kiểm Tra Human-in-the-Loop (HIL) (BẮT BUỘC TUYỆT ĐỐI)

Hệ thống PHẢI tạm dừng thực thi và chờ xác nhận rõ ràng từ Project Owner (PO) tại mọi điểm
kiểm tra HIL được chỉ định trước khi bất kỳ Agent nào tiếp tục. Tự động tiếp tục qua điểm
kiểm tra là bị cấm. Quyết định của PO (chấp thuận / từ chối / sửa đổi) PHẢI được lưu vào
cơ sở dữ liệu trước khi luồng công việc tiếp tục.

**Lý do**: Hệ thống AI-agentic cần sự giám sát của con người tại các cửa quyết định quan trọng
để ngăn chặn lỗi tích lũy, duy trì trách nhiệm giải trình và bảo tồn niềm tin của người dùng.

### III. Kỷ Luật WIP

Ở MVP, hệ thống PHẢI áp dụng giới hạn WIP là chính xác 1 task ở trạng thái In Progress tại bất
kỳ thời điểm nào. Mọi chuyển đổi vi phạm giới hạn này PHẢI bị từ chối ở tầng API.
Ghi đè giới hạn yêu cầu hành động rõ ràng từ PO.

**Lý do**: Giới hạn WIP = 1 giữ phạm vi thực thi của AI hẹp và có thể kiểm chứng, phát lộ
điểm tắc nghẽn ngay lập tức và tránh chi phí chuyển ngữ cảnh cho pipeline agentic.

### IV. Tính Toàn Vẹn Luồng Kanban

Task PHẢI chỉ di chuyển tiến về phía trước qua các giai đoạn Kanban (ví dụ: Backlog → In Progress → Review → Done).
Chuyển đổi ngược duy nhất được phép là do hệ thống điều khiển: Rejected → In Progress, được kích
hoạt tự động khi PO từ chối kết quả review. Tất cả các chuyển động ngược khác đều BỊ CẤM ở
tầng API và UI. Không có tác nhân nào — con người hay AI — được kéo task ngược thủ công.

**Lý do**: Luồng một chiều bảo toàn tính toàn vẹn nhật ký kiểm tra và ngăn chặn các tổ hợp
trạng thái không xác định làm phức tạp logic Agent và báo cáo.

### V. Ghi Log Kiểm Tra Đầy Đủ Hành Động Agent (BẮT BUỘC TUYỆT ĐỐI)

Mọi hành động của bất kỳ AI Agent nào PHẢI được lưu vào cơ sở dữ liệu trước khi hành động đó
được coi là hoàn thành. Mỗi bản ghi log PHẢI bao gồm:

- Danh tính và phiên bản Agent
- Loại hành động và mô tả
- Timestamp (UTC, định dạng ISO 8601)
- Tham chiếu artifact đầu vào (đường dẫn file hoặc ID bản ghi DB)
- Tham chiếu artifact đầu ra hoặc thay đổi trạng thái kết quả
- Kết quả: `success` | `failure` | `awaiting_hil`

Bản ghi log là bất biến. Xóa hoặc sửa đổi bản ghi kiểm tra là bị cấm.

**Lý do**: Khả năng quan sát đầy đủ hành vi AI là thiết yếu để debug, tuân thủ và xây dựng
niềm tin người dùng vào hệ thống agentic viết và thực thi code.

### VI. Bảo Mật Theo Thiết Kế (BẮT BUỘC TUYỆT ĐỐI)

- API key LLM PHẢI được mã hoá AES-256 trước khi lưu vào cơ sở dữ liệu; key dạng plaintext
  KHÔNG ĐƯỢC xuất hiện trong log, code hoặc file môi trường được commit lên VCS.
- Xác thực PHẢI dùng JWT. Secret KHÔNG ĐƯỢC hardcode trong mã nguồn hoặc file cấu hình
  được theo dõi bởi version control.
- Môi trường Sandbox PHẢI không có quyền truy cập mạng ra ngoài ở MVP.
- Từng lệnh terminal thực thi bên trong sandbox PHẢI timeout sau 60 giây.
- Toàn bộ quá trình thực thi một task PHẢI timeout sau 10 phút.
- Mọi đầu vào từ nguồn bên ngoài (input người dùng, phản hồi LLM, dữ liệu VCS) PHẢI được
  xác thực và làm sạch trước khi hệ thống hành động theo đó.

**Lý do**: Hệ thống thực thi code tùy ý trong sandbox thay mặt người dùng. Một sơ hở bảo mật
duy nhất (rò rỉ key, thoát mạng, command injection) có thể gây hậu quả không cân xứng.

### VII. Kỷ Luật Phạm Vi MVP (BẮT BUỘC TUYỆT ĐỐI)

MVP được giới hạn rõ ràng trong:

- **Tác nhân**: Chính xác 1 — Project Owner (PO). Tính năng đa người dùng, nhóm hoặc vai trò
  được hoãn sang sau MVP.
- **Codebase Mapping**: Chỉ hỗ trợ dự án Python và JavaScript/TypeScript. Các ngôn ngữ khác
  nằm ngoài phạm vi.
- **Sandbox**: Chỉ thực thi trong thư mục local. Tích hợp Docker SDK được hoãn sang sau MVP.
- **Reviewer Agent**: Tuỳ chọn. Sự vắng mặt của nó KHÔNG ĐƯỢC chặn bất kỳ luồng công việc
  cốt lõi nào; PO thực hiện review thủ công khi Reviewer Agent bị tắt.

Bất kỳ yêu cầu nào mở rộng ra ngoài các ranh giới này PHẢI được ghi lại tường minh và hoãn lại
trước khi bắt đầu triển khai. "Scope creep mặc nhiên" bị từ chối.

**Lý do**: Scope creep là rủi ro triển khai chính trong phát triển nền tảng agentic.
Các ranh giới cứng ở tầng hiến pháp trao cho nhóm quyền từ chối mở rộng phạm vi mà không cần
tranh luận.

### VIII. Chất Lượng Code & Quy Ước (BẮT BUỘC TUYỆT ĐỐI)

**Backend — Python**:
- Code PHẢI tuân thủ PEP 8.
- Type hint là BẮT BUỘC trên mọi chữ ký hàm và phương thức.
- Docstring PHẢI theo Google style.
- Mọi API endpoint PHẢI được tài liệu hoá qua OpenAPI spec tự sinh của FastAPI.

**Frontend — React/TypeScript**:
- ESLint và Prettier PHẢI được cấu hình và áp dụng trong CI.
- Component PHẢI theo Atomic Design (atoms / molecules / organisms).
- File component PHẢI dùng kebab-case (ví dụ: `task-card.tsx`).

**Toàn cục**:
- File Python: `snake_case`. File React component: `kebab-case`.
- Tên biến, hàm, class và module PHẢI hoàn toàn bằng tiếng Anh.
  Cấm dùng lẫn tiếng Việt/tiếng Anh trong định danh code.

**Lý do**: Quy ước nhất quán giảm tải nhận thức cho AI Agent khi phân tích mã nguồn và cho
lập trình viên khi review output do AI tạo ra.

## Ràng Buộc Công Nghệ

Các lựa chọn công nghệ sau đây được cố định. Thay đổi yêu cầu sửa đổi hiến pháp.

| Tầng | Công nghệ | Ghi chú |
|---|---|---|
| Frontend | React (Vite) + TypeScript | Cấu trúc component theo Atomic Design |
| Backend | Python + FastAPI (async) | Mọi endpoint PHẢI là async |
| Điều phối AI | LangGraph (Python) | Chỉ dùng luồng công việc dạng đồ thị |
| Cơ sở dữ liệu chính | PostgreSQL | Toàn bộ trạng thái ứng dụng bền vững |
| Cache / Queue / Pub-Sub | Redis | Fan-out WebSocket qua Pub/Sub |
| Truyền thông Realtime | WebSocket (FastAPI + Redis Pub/Sub) | Không có polling fallback ở MVP |
| Sandbox (MVP) | Thư mục local | Cô lập; không có quyền truy cập mạng ra ngoài |
| Sandbox (Sau MVP) | Docker SDK | Ngoài phạm vi MVP |
| Tích hợp VCS | GitPython | Dùng để kiểm tra và mapping codebase |

## Quy Trình Phát Triển

1. **Spec trước code**: Một đặc tả tính năng (`spec.md`) PHẢI tồn tại và được PO phê duyệt
   trước khi bất kỳ task triển khai nào được lên lịch.
2. **Plan trước tasks**: Kế hoạch triển khai (`plan.md`) PHẢI tồn tại trước khi `tasks.md`
   được tạo ra.
3. **Cửa Kiểm Tra Hiến Pháp**: Mọi `plan.md` PHẢI có mục Constitution Check xác minh tuân thủ
   cả 8 nguyên tắc trước khi Phase 0 bắt đầu. Kiểm tra PHẢI được thực hiện lại sau Phase 1.
4. **Hành động Agent = Bản ghi DB**: Không AI Agent nào ĐƯỢC thực hiện hành động có tác dụng
   phụ mà không tạo trước một bản ghi log chờ xử lý trong cơ sở dữ liệu (xem Nguyên tắc V).
5. **HIL trước hành động không thể đảo ngược**: Bất kỳ hành động nào sửa đổi filesystem, thực
   thi code hoặc gọi API bên ngoài PHẢI được đi trước bởi điểm kiểm tra HIL nếu đó là lần đầu
   tiên xảy ra trong một lần thực thi task (xem Nguyên tắc II).
6. **Review trước Done**: Task PHẢI đi qua giai đoạn Review trước khi chuyển sang Done, ngay
   cả khi Reviewer Agent bị tắt (PO thực hiện review thủ công trong trường hợp đó).

## Quản Trị

Hiến pháp này thay thế mọi thỏa thuận bằng văn bản hoặc lời nói khác về quy ước dự án,
quyết định kiến trúc và phạm vi MVP.

**Quy trình sửa đổi**:

1. Đề xuất sửa đổi bằng văn bản, nêu rõ (các) nguyên tắc hoặc mục bị ảnh hưởng.
2. Xác định các tính năng hoặc task đang thực hiện bị ảnh hưởng và lập kế hoạch di chuyển.
3. PO phê duyệt rõ ràng sửa đổi trước khi áp dụng thay đổi.
4. Cập nhật file này: tăng phiên bản, đặt `LAST_AMENDED_DATE` về hôm nay, ghi lại thay đổi
   trong khối comment Báo cáo Đồng bộ và cập nhật mọi template hoặc artifact bị ảnh hưởng.

**Chính sách phiên bản** (semantic):

- MAJOR: Xóa hoặc tái định nghĩa không tương thích ngược một nguyên tắc hiện có.
- MINOR: Bổ sung nguyên tắc hoặc mục mới.
- PATCH: Làm rõ, cải thiện cách diễn đạt hoặc tinh chỉnh không thay đổi ngữ nghĩa.

**Kiểm tra tuân thủ**:

- Mọi `plan.md` PHẢI có mục Constitution Check xác minh sự phù hợp với hiến pháp này trước
  khi bắt đầu triển khai.
- CI PHẢI áp dụng PEP 8 (backend) và ESLint/Prettier (frontend) trên mọi pull request.
- Các kiểm soát bảo mật (mã hoá AES-256, JWT, cô lập mạng sandbox) PHẢI được xác minh bởi
  integration test trước khi bất kỳ bản build nào được đẩy lên môi trường release.
- Áp dụng giới hạn WIP và chặn chuyển đổi ngược PHẢI được bao phủ bởi automated API test.

**Phiên bản**: 1.0.1 | **Phê duyệt**: 2026-05-11 | **Sửa đổi lần cuối**: 2026-05-11
