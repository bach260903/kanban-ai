# Feature Specification: AI CLI Integration — Vibe Coding Backends

**Feature ID**: 002  
**Date**: 2026-05-18  
**Status**: Draft  
**Priority**: P1  
**Linked plan**: [plan.md](plan.md)

---

## Tóm Tắt

Neo-Kanban hiện dùng Groq API + LangGraph làm engine sinh code cho Coder Agent. Tính năng này
mở rộng nền tảng để hỗ trợ ba AI coding CLI phổ biến làm **coding backend** thay thế — cho phép
Project Owner chọn "vibe coding" với Claude Code, OpenAI, hoặc Gemini CLI.

---

## Mục Tiêu Người Dùng

| ID | Vai trò | Nhu cầu | Giá trị |
|----|---------|---------|---------|
| US-01 | Project Owner | Chọn AI CLI backend khi tạo hoặc cập nhật project | Không bị ràng buộc vào Groq |
| US-02 | Project Owner | Kéo task vào In Progress và thấy Claude Code / OpenAI / Gemini thực hiện code | Vibe coding thực sự với CLI quen thuộc |
| US-03 | Project Owner | Xem output streaming từ CLI trong Thought Stream panel | Quan sát AI đang làm gì |
| US-04 | Project Owner | Cấu hình API key / path của từng CLI trong .env | Sử dụng token/key cá nhân |
| US-05 | Project Owner | Chuyển backend bất kỳ lúc nào (per project) mà không mất dữ liệu | Linh hoạt thử nghiệm |

---

## Yêu Cầu Chức Năng

### YC-01 — Backend Selection
- Project có field `coding_backend`: `groq` (mặc định) | `claude_code` | `openai` | `gemini`
- Có thể chọn khi tạo project hoặc cập nhật project settings
- Backend hiển thị rõ trong Project Header

### YC-02 — Claude Code Integration
- Khi `coding_backend = claude_code`: Coder Agent gọi `claude --print -p "{task_description}"` trong sandbox directory
- Biến môi trường: `ANTHROPIC_API_KEY` (hoặc dùng session token từ `claude auth login`)
- Timeout: 10 phút (giống rule hiện tại của coder_node)
- Claude Code output được parse để trích xuất file thay đổi → sinh diff

### YC-03 — OpenAI Integration
- Khi `coding_backend = openai`: Coder Agent gọi OpenAI Responses API (gpt-4o-mini mặc định, cấu hình qua `OPENAI_MODEL`)
- Biến môi trường: `OPENAI_API_KEY`, `OPENAI_MODEL` (tuỳ chọn)
- Dùng OpenAI Python SDK (không qua CLI binary), với `file_tools` và `sandbox_tools` làm function tools
- Timeout: 10 phút

### YC-04 — Gemini Integration
- Khi `coding_backend = gemini`: Coder Agent gọi Gemini CLI: `gemini -p "{task_description}"` trong sandbox directory
- Biến môi trường: `GOOGLE_AI_API_KEY`, `GEMINI_MODEL` (tuỳ chọn, mặc định `gemini-2.0-flash`)
- Timeout: 10 phút

### YC-05 — Streaming & Observability
- stdout/stderr từ CLI được streaming qua WebSocket event publisher hiện tại (loại `THOUGHT` / `ACTION` / `TOOL_RESULT`)
- Không cần thay đổi giao thức WebSocket frontend
- Thought Stream panel hoạt động như nhau với mọi backend

### YC-06 — Diff Generation
- Sau khi CLI hoàn thành, hệ thống chạy `git diff` trong sandbox để sinh Diff record
- Logic giống coder_node hiện tại — không thay đổi review flow

### YC-07 — Fallback & Error
- Nếu CLI không khả dụng (binary không tìm thấy, API key sai): task chuyển sang `rejected`, audit log ghi lỗi, WebSocket gửi `ERROR` event
- Cung cấp thông báo lỗi rõ ràng (CLI missing vs auth failure)

### YC-08 — Backward Compatibility
- Projects hiện tại với `coding_backend = groq` tiếp tục hoạt động không thay đổi
- Không có migration bắt buộc

---

## Yêu Cầu Phi Chức Năng

| ID | Yêu cầu |
|----|---------|
| TC-01 | CLI invocation overhead ≤ 500 ms (thời gian từ drag-to-In-Progress đến CLI start) |
| TC-02 | WebSocket events bắt đầu stream trong ≤ 2 s từ khi CLI khởi động |
| TC-03 | Tất cả backends đều timeout sau 10 phút và chuyển task sang `rejected` |
| TC-04 | Diff generated sau ≤ 5 s kể từ khi CLI exit |
| TC-05 | Switching backend không mất dữ liệu dự án hoặc task |

---

## Kịch Bản Chấp Thuận (Acceptance Scenarios)

### Kịch Bản 1 — Chọn Claude Code khi tạo project
1. PO tạo project mới, chọn "Claude Code" trong Backend Selector
2. System lưu `coding_backend = claude_code`
3. Project Header hiển thị badge "Claude Code"

### Kịch Bản 2 — Vibe code với Claude Code
1. PO kéo task vào In Progress (project dùng Claude Code backend)
2. System chạy `claude --print -p "<task>"` trong sandbox
3. Thought Stream panel hiển thị output
4. Khi hoàn thành, diff xuất hiện trong Review column

### Kịch Bản 3 — Đổi backend giữa chừng
1. PO cập nhật project settings, đổi từ Groq sang Gemini
2. Task tiếp theo kéo vào In Progress sẽ dùng Gemini CLI
3. Task trước (nếu có) không bị ảnh hưởng

### Kịch Bản 4 — CLI không khả dụng
1. PO chọn Claude Code nhưng `ANTHROPIC_API_KEY` chưa set
2. Khi kéo task: WebSocket gửi ERROR event với message rõ ràng
3. Task chuyển về `todo` với trạng thái lỗi, PO thấy thông báo

---

## Giả Định

- CLI binary đã được cài sẵn trong môi trường server (hoặc Docker image)
- API key được set trong `.env` server-side, không expose qua API
- Single-user MVP — không có per-user API key management
- OpenAI sử dụng Python SDK (không cần binary riêng)
- Gemini CLI là `gemini` CLI từ Google (`npm install -g @google/gemini-cli`)

---

## Ngoài Phạm Vi

- Multi-provider load balancing hoặc fallback tự động
- Per-user API key storage
- Claude Code với file-level context (chỉ dùng `--print` mode)
- Custom prompt engineering per-backend (dùng chung prompt từ `context_builder`)
- OpenAI Codex CLI (deprecated)
