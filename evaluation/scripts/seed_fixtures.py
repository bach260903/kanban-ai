"""Load `_fixtures/seed.json` into a running backend.

Usage:
    python evaluation/scripts/seed_fixtures.py [--api http://localhost:8000]

Idempotent: skips users that already exist (login if account taken).
Outputs a JSON map { actor_email -> token, board_id -> id, user_email -> id, ... }
to ``evaluation/results/seed.json`` for downstream scripts.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[2]
SEED_PATH = REPO / "evaluation" / "datasets" / "_fixtures" / "seed.json"
OUT_PATH = REPO / "evaluation" / "results" / "seed.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:8000")
    args = parser.parse_args()
    api = args.api.rstrip("/")

    seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    state: dict = {"users": {}, "tokens": {}, "boards": [], "skills": {}}

    with httpx.Client(timeout=30) as client:
        # Users
        for u in seed["users"]:
            try:
                client.post(f"{api}/api/auth/register", json={
                    "email": u["email"], "password": u["password"], "display_name": u["display_name"]
                })
            except httpx.HTTPError:
                pass
            r = client.post(f"{api}/api/auth/login", json={"email": u["email"], "password": u["password"]})
            r.raise_for_status()
            token = r.json()["access_token"]
            state["tokens"][u["email"]] = token

            me = client.get(f"{api}/api/users/me", headers={"Authorization": f"Bearer {token}"}).json()
            state["users"][u["email"]] = me["id"]

            # Skills
            for sk_name, level in u.get("skills", []):
                r = client.post(f"{api}/api/skills", json={"name": sk_name},
                                headers={"Authorization": f"Bearer {token}"})
                if r.status_code in (200, 201):
                    state["skills"][sk_name] = r.json()["id"]
            # Apply user_skills
            mapping = []
            for sk_name, level in u.get("skills", []):
                sid = state["skills"].get(sk_name)
                if sid:
                    mapping.append({"skill_id": sid, "level": level})
            if mapping:
                client.put(f"{api}/api/users/{me['id']}/skills", json=mapping,
                           headers={"Authorization": f"Bearer {token}"}).raise_for_status()

        # Boards (owned by first user)
        first_email = seed["users"][0]["email"]
        owner_token = state["tokens"][first_email]
        for b in seed["boards"]:
            r = client.post(f"{api}/api/boards", json={"title": b["title"], "description": b.get("description", "")},
                            headers={"Authorization": f"Bearer {owner_token}"})
            r.raise_for_status()
            board = r.json()
            state["boards"].append({"id": board["id"], "title": board["title"]})
            first_col = board["columns"][0]["id"]
            for t in b.get("tasks", []):
                client.post(
                    f"{api}/api/boards/{board['id']}/tasks",
                    json={
                        "column_id": first_col,
                        "title": t["title"],
                        "description": t.get("description", ""),
                        "priority": t.get("priority", "medium"),
                        "tags": t.get("tags"),
                        "est_hours": t.get("est_hours"),
                    },
                    headers={"Authorization": f"Bearer {owner_token}"},
                ).raise_for_status()

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(f"Seeded. State -> {OUT_PATH}")


if __name__ == "__main__":
    main()
