# Benchmark Multi-Agent Frameworks (Giai đoạn 1.1)

## Lỗi thường gặp: Python 3.14 + `pip install -r requirements.txt` (bản cũ)

**CrewAI** (bản mới, ví dụ `>=0.76`) chỉ hỗ trợ **Python 3.10–3.13**. Trên **Python 3.14**, pip không tìm được bản CrewAI mới → lỗi `No matching distribution found for crewai`.

**Cách xử lý:**

| Demo | File cài đặt | Python |
|------|----------------|--------|
| `demo_langgraph.py` | `requirements-langgraph.txt` hoặc `requirements.txt` | 3.11+ (kể cả 3.14) |
| `demo_autogen.py` | `requirements-autogen.txt` hoặc `requirements.txt` | 3.11+ |
| `demo_crewai.py` | `requirements-crewai.txt` | **3.12 hoặc 3.13** (khuyến nghị) |

### Cài đặt chuẩn (LangGraph + AutoGen, mọi Python gần đây)

```powershell
cd d:\kanban\evaluation\agent_frameworks
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
$env:GROQ_API_KEY = "gsk_..."
python demo_langgraph.py
python demo_autogen.py
```

### CrewAI riêng (bắt buộc Python ≤ 3.13)

Cài [Python 3.12](https://www.python.org/downloads/) (tick “Add to PATH” hoặc dùng `py` launcher):

```powershell
cd d:\kanban\evaluation\agent_frameworks
py -3.12 -m venv .venv-crewai
.\.venv-crewai\Scripts\activate
pip install -r requirements-crewai.txt
$env:GROQ_API_KEY = "gsk_..."
python demo_crewai.py
```

Kiểm tra bản Python: `py -0` hoặc `python --version`.

Kết luận so sánh framework: `docs/phase1-technology-decisions.md`.
