"""Load repo .env, then call Groq once (key is never printed)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

_EVAL = Path(__file__).resolve().parent.parent
if str(_EVAL) not in sys.path:
    sys.path.insert(0, str(_EVAL))
from load_repo_env import REPO_ROOT, load_repo_env


def main() -> None:
    load_repo_env()
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key:
        print("FAIL: GROQ_API_KEY missing or empty in", REPO_ROOT / ".env")
        print("  Add line: GROQ_API_KEY=gsk_...")
        print("  If you use copy .env.example .env, paste your key after the = sign.")
        sys.exit(1)
    if not key.startswith("gsk_"):
        print("WARN: Groq keys usually start with gsk_ -- check your value.")
    try:
        from groq import Groq
    except ImportError:
        print("FAIL: run: pip install groq")
        sys.exit(1)
    client = Groq(api_key=key)
    r = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": 'Reply with exactly: OK'}],
        max_tokens=8,
        temperature=0,
    )
    text = (r.choices[0].message.content or "").strip()
    print("OK: Groq response:", repr(text[:80]))


if __name__ == "__main__":
    main()
