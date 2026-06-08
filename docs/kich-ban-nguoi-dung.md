# Kịch bản người dùng — Neo Kanban AI

---

## Nhân vật

- **Minh** — Product Owner, người tạo dự án, duyệt tài liệu và code
- **Hieu** — Developer, người chạy agent và xem pipeline
- **Lan** — Thành viên mới, chỉ xem

---

## Kịch bản 1 — Đăng ký và đăng nhập

Minh mở trình duyệt, vào trang chủ của Neo Kanban.

Minh chưa có tài khoản nên nhấn **Đăng ký**. Minh điền tên, email và mật khẩu rồi nhấn xác nhận. Hệ thống gửi mã OTP về email (hoặc hiện trong console nếu đang dev). Minh nhập mã, tài khoản được tạo thành công, hệ thống tự chuyển sang trang danh sách dự án.

Minh thử đăng xuất rồi đăng nhập lại. Nhập đúng email và mật khẩu thì vào được ngay. Thử nhập sai mật khẩu thì hệ thống báo lỗi, không cho vào.

> ✅ Mong đợi: Đăng ký được, đăng nhập đúng thì vào, sai thì báo lỗi.

---

## Kịch bản 2 — Tạo dự án mới

Minh đang ở trang danh sách dự án, nhấn **Tạo dự án mới**.

Minh đặt tên "Todo App", thêm mô tả ngắn, chọn ngôn ngữ Python rồi nhấn tạo. Hệ thống tạo xong và chuyển thẳng vào workspace của dự án. Minh thấy các tab: Documents, Kanban, Pipelines, Members, Settings.

Minh vào Settings, cập nhật mô tả chi tiết hơn và nhấn lưu. F5 lại vẫn thấy mô tả mới — nghĩa là đã lưu đúng.

> ✅ Mong đợi: Tạo được dự án, lưu thông tin, các tab hiển thị đầy đủ.

---

## Kịch bản 3 — Mời thành viên vào dự án

Minh muốn cho Hieu và Lan vào dự án cùng làm.

Minh vào tab **Members**, nhấn **Mời thành viên**, copy link mời rồi gửi cho Hieu qua Zalo.

Hieu mở link, thấy thông tin dự án "Todo App" và nhấn **Chấp nhận lời mời**. Hệ thống báo Hieu đang chờ duyệt. Minh nhận thông báo có người muốn vào dự án, vào tab Members phần chờ duyệt, thấy tên Hieu và nhấn **Duyệt**. Hieu được vào với vai trò Developer.

Với Lan, Minh nhập thẳng email `lan@example.com`, chọn vai trò Viewer và gửi. Lan mở link trong email, nhấn chấp nhận, được vào ngay không cần chờ duyệt vì Minh đã chỉ định sẵn.

> ✅ Mong đợi: Link mời hoạt động, Hieu phải chờ duyệt, Lan được vào thẳng.

---

## Kịch bản 4 — Sinh đặc tả kỹ thuật (SPEC) bằng AI

Minh vào tab **Documents**.

Minh gõ vào ô ý tưởng:

> *"Xây dựng ứng dụng quản lý công việc bằng Python FastAPI. Cho phép tạo, xem, sửa, xoá task. Mỗi task có tiêu đề, mô tả, mức độ ưu tiên và trạng thái. Có API REST và test đầy đủ."*

Minh nhấn **Sinh SPEC**. Hệ thống xử lý khoảng 30 giây, sau đó hiện ra một tài liệu SPEC đầy đủ: mục tiêu, yêu cầu chức năng, tiêu chí nghiệm thu. Tài liệu đang ở trạng thái **Bản nháp**.

Minh đọc qua thấy thiếu phần xác thực JWT, nên điền vào ô góp ý:

> *"Cần thêm xác thực JWT, mỗi user chỉ thấy task của mình."*

Nhấn **Yêu cầu sửa**. Sau khoảng 30 giây, SPEC được cập nhật với phần JWT bổ sung. Minh đọc lại thấy ổn, nhấn **Duyệt**.

Ngay sau khi duyệt, hệ thống tự động bắt đầu sinh **PLAN** — Minh thấy chữ "Đang sinh kế hoạch..." xuất hiện.

> ✅ Mong đợi: AI sinh ra SPEC có nội dung, sửa được theo góp ý, duyệt xong tự sinh PLAN.

---

## Kịch bản 5 — Duyệt kế hoạch (PLAN) và tạo task tự động

Sau khoảng 30–60 giây, PLAN.md xuất hiện. Minh đọc qua, thấy kế hoạch chia thành các giai đoạn rõ ràng.

Minh nhấn **Duyệt PLAN**.

Hệ thống tự động tạo ra các task trên bảng Kanban — Minh chuyển sang tab Kanban thì thấy cột TODO đã có các việc cần làm:

- Khởi tạo project FastAPI
- Tạo model Task
- Viết CRUD endpoints
- Thêm xác thực JWT
- Viết pytest

> ✅ Mong đợi: Task tự động xuất hiện trên Kanban sau khi duyệt PLAN, không cần tạo tay.

---

## Kịch bản 6 — Giao việc và chạy AI lập trình

Minh giao task "Khởi tạo project FastAPI" cho Hieu bằng cách click vào task, chọn tên Hieu trong ô **Giao cho**.

Hieu nhận được thông báo "Bạn được giao task mới". Hieu vào Kanban, kéo task sang cột **Đang làm**.

Hệ thống tự động khởi động AI coder. Bên phải màn hình xuất hiện luồng suy nghĩ của AI đang làm việc — Hieu thấy AI đang tạo file, chạy lệnh cài thư viện, chạy test. Hieu chờ khoảng 5–10 phút.

Khi AI làm xong, task tự động chuyển sang cột **Cần review**.

> ✅ Mong đợi: AI tự chạy sau khi kéo task, thought stream hiện ra, task tự chuyển sang Cần review khi xong.

---

## Kịch bản 7 — Giới hạn làm việc song song (WIP Limit)

Trong khi task "Khởi tạo project FastAPI" đang chạy, Hieu thử kéo thêm task thứ 2 sang cột **Đang làm**.

Hệ thống không cho — task bật trở lại cột TODO, hiện thông báo rằng Hieu đang có 1 task đang chạy, cần hoàn thành trước khi bắt đầu cái khác.

> ✅ Mong đợi: Không thể có 2 task Đang làm cùng lúc với cùng 1 người.

---

## Kịch bản 8 — Tạm dừng AI và hướng dẫn thêm

AI đang chạy, Hieu chợt nhớ ra cần thêm CORS cho backend.

Hieu nhấn **Tạm dừng** trên task đang chạy. AI dừng lại. Hieu nhập hướng dẫn bổ sung:

> *"Thêm middleware CORS cho phép frontend kết nối, dùng allow_origins=['*'] cho môi trường dev."*

Hieu nhấn **Tiếp tục**. AI chạy tiếp từ chỗ dừng, lần này có thêm đoạn cấu hình CORS trong code.

> ✅ Mong đợi: Tạm dừng được, thêm hướng dẫn được, AI tiếp tục đúng hướng.

---

## Kịch bản 9 — Review code và duyệt

Task "Khởi tạo project FastAPI" đang ở cột **Cần review**. Minh nhận thông báo.

Minh vào xem phần **Code diff** — thấy những dòng code mới được tô màu xanh, dòng bị xoá tô màu đỏ. Phía dưới có nhận xét của AI reviewer với điểm chất lượng code.

Minh thấy chỗ thiếu xử lý lỗi, click vào dòng đó và thêm comment:

> *"Cần xử lý trường hợp kết nối database thất bại."*

Minh đọc hết diff, thấy tổng thể ổn, nhấn **Duyệt**. Task chuyển sang **Hoàn thành**.

> ✅ Mong đợi: Xem được diff, thêm comment được, duyệt thì task chuyển Hoàn thành.

---

## Kịch bản 10 — Từ chối code và yêu cầu sửa

Task "Viết CRUD endpoints" đang ở Cần review. Minh xem diff, phát hiện API `GET /tasks/{id}` không trả về lỗi 404 khi task không tồn tại.

Minh điền vào ô phản hồi:

> *"Hàm get_task cần kiểm tra task có tồn tại không, nếu không trả về HTTP 404."*

Nhấn **Từ chối**. Task quay lại **Đang làm**, AI chạy lại với phản hồi vừa nhập. Sau vài phút, task về lại Cần review — lần này diff có thêm đoạn kiểm tra 404.

> ✅ Mong đợi: Từ chối được, AI nhận phản hồi, sửa đúng điểm đã góp ý.

---

## Kịch bản 11 — Xem pipeline CI/CD

Minh vào tab **Pipelines** xem tiến trình kiểm thử tự động.

Thấy danh sách các lần chạy pipeline. Minh click vào lần chạy gần nhất, thấy từng bước: cài thư viện → chạy test → kiểm tra code style → build. Mỗi bước có dấu ✓ hoặc ✗ và log chi tiết.

Một lần pipeline bị lỗi ở bước test, hệ thống tự phân tích và đưa ra nguyên nhân. Minh đọc phần **AI phân tích lỗi**, thấy giải thích rõ ràng. Minh nhấn **Chạy lại**, pipeline chạy lần mới.

> ✅ Mong đợi: Xem được từng bước pipeline, có phân tích lỗi tự động, chạy lại được.

---

## Kịch bản 12 — Nhận và quản lý thông báo

Lan đăng nhập và vào xem dự án Todo App.

Lan thấy icon chuông trên góc phải có chấm đỏ. Lan click vào, thấy thông báo "Task 'Khởi tạo project FastAPI' đã hoàn thành". Lan nhấn **Đánh dấu đã đọc tất cả**, chấm đỏ biến mất.

> ✅ Mong đợi: Thông báo xuất hiện đúng lúc, đánh dấu đọc thì chấm đỏ biến mất.

---

## Kịch bản 13 — Webhook thông báo ra ngoài

Minh muốn mỗi khi có task cần review thì Zapier của công ty nhận được thông báo.

Minh vào Settings → **Webhooks**, nhấn tạo mới. Điền URL của Zapier, chọn sự kiện "Task cần review" và "Task hoàn thành". Nhấn **Test** — Zapier nhận được tin nhắn thử.

Hôm sau có task thật chuyển sang Cần review, Zapier nhận được thông báo tự động.

> ✅ Mong đợi: Webhook gửi đúng sự kiện, test được trước khi dùng thật.

---

## Kịch bản 14 — Discord Bot tra cứu tiến độ

Team dùng Discord để liên lạc. Minh đã cấu hình bot Kanban vào server.

Hieu đang họp, muốn nhanh biết tiến độ dự án mà không cần mở trình duyệt. Hieu gõ vào Discord:

`/tiendo` → chọn dự án "Todo App"

Bot trả lời ngay: *"3/8 tasks hoàn thành (37.5%) — TODO: 3 | Đang làm: 1 | Cần review: 1 | Xong: 3"*

Lan hỏi thêm: `/ask` → "API nào để tạo task mới?" → Bot trả lời dựa trên SPEC của dự án.

> ✅ Mong đợi: Bot trả lời đúng thông tin dự án, không cần mở web.

---

## Kịch bản 15 — Xem lịch sử thay đổi (Audit Log)

Cuối sprint, Minh muốn xem lại ai đã làm gì trong dự án.

Minh vào tab **Audit Log**, thấy toàn bộ lịch sử: ai tạo task lúc nào, ai duyệt code lúc nào, AI chạy mấy vòng, khi nào gặp lỗi. Mọi thao tác đều có dấu thời gian và tên người thực hiện.

> ✅ Mong đợi: Lịch sử đầy đủ, không bị mất sự kiện nào.

---

## Kịch bản 16 — Viewer bị giới hạn quyền

Lan (Viewer) thử một số thao tác để kiểm tra:

- Thử tạo task mới → nút **Tạo task** không hiện hoặc bị mờ
- Thử kéo task sang cột khác → không kéo được
- Thử duyệt code → không có nút Duyệt

Lan chỉ xem được, không làm được gì.

> ✅ Mong đợi: Viewer chỉ xem, không thể thay đổi bất cứ thứ gì.

---

## Kịch bản 17 — Ghi nhớ bài học từ dự án (Memory)

Sau khi nhiều task hoàn thành, Minh tò mò mở tab **Memory**.

Thấy hệ thống tự ghi lại những điều AI đã học được trong quá trình làm: *"Dự án dùng SQLite cho dev, cấu hình sẵn cho PostgreSQL"*, *"Cần khai báo CORS trước khi include router"*...

Minh thêm ghi chú tay: *"Không dùng thư viện requests trong test, dùng httpx thay thế."* Nhấn lưu.

> ✅ Mong đợi: Memory tự ghi được, người dùng cũng thêm tay được, AI sẽ dùng thông tin này cho các task sau.
