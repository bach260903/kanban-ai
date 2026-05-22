"""ChromaDB persistent vector store wrapper.

Keeps three collections: task_chunks, comment_chunks, decision_notes.
Falls back to a no-op store if `EMBEDDING_MODEL=none` or no key is available.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Optional

from app.config import settings

log = logging.getLogger(__name__)


class _NoopCollection:
    name: str = "noop"

    def upsert(self, **_: Any) -> None: ...
    def delete(self, **_: Any) -> None: ...
    def query(self, **_: Any) -> dict[str, Any]:
        return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
    def count(self) -> int:
        return 0


class _NoopChroma:
    def get_or_create_collection(self, name: str, **_: Any) -> _NoopCollection:
        return _NoopCollection()


def _embedding_function():
    spec = (settings.embedding_model or "").strip()
    if not spec or spec == "none":
        return None
    if spec.startswith("openai:"):
        if not settings.openai_api_key:
            log.warning("OpenAI embedding requested but OPENAI_API_KEY missing; vector disabled")
            return None
        try:
            from chromadb.utils import embedding_functions  # type: ignore

            return embedding_functions.OpenAIEmbeddingFunction(
                api_key=settings.openai_api_key,
                model_name=spec.split(":", 1)[1],
            )
        except Exception as e:  # pragma: no cover
            log.error("OpenAI embedding init failed: %s", e)
            return None
    log.warning("Unknown embedding spec %s; vector disabled", spec)
    return None


@lru_cache(maxsize=1)
def get_chroma() -> Any:
    try:
        import chromadb  # type: ignore

        client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        return client
    except Exception as e:  # pragma: no cover
        log.warning("Chroma init failed (%s); using noop store", e)
        return _NoopChroma()


def _collection(name: str) -> Any:
    client = get_chroma()
    ef = _embedding_function()
    try:
        if ef is not None:
            return client.get_or_create_collection(name=name, embedding_function=ef)
        return client.get_or_create_collection(name=name)
    except TypeError:
        return client.get_or_create_collection(name=name)


def upsert_task(
    task_id: str,
    board_id: str,
    title: str,
    description: str,
    status: str,
    priority: str,
    tags: Optional[list[str]] = None,
) -> None:
    if _embedding_function() is None:
        return
    coll = _collection("task_chunks")
    text = f"{title}\n\n{description or ''}".strip()
    if not text:
        return
    coll.upsert(
        ids=[f"{task_id}:0"],
        documents=[text],
        metadatas=[{
            "task_id": task_id,
            "board_id": board_id,
            "status": status,
            "priority": priority,
            "tags": ",".join(tags or []),
        }],
    )


def delete_task(task_id: str) -> None:
    if _embedding_function() is None:
        return
    coll = _collection("task_chunks")
    try:
        coll.delete(where={"task_id": task_id})
    except Exception as e:  # pragma: no cover
        log.debug("delete_task vector ignore: %s", e)


def upsert_comment(comment_id: str, task_id: str, board_id: str, body: str, author_id: str) -> None:
    if _embedding_function() is None:
        return
    coll = _collection("comment_chunks")
    if not body.strip():
        return
    coll.upsert(
        ids=[comment_id],
        documents=[body],
        metadatas=[{"comment_id": comment_id, "task_id": task_id, "board_id": board_id, "author_id": author_id}],
    )


def search_tasks(query: str, top_k: int = 5, board_id: Optional[str] = None) -> list[dict[str, Any]]:
    if _embedding_function() is None or not query.strip():
        return []
    coll = _collection("task_chunks")
    where: dict[str, Any] | None = None
    if board_id:
        where = {"board_id": board_id}
    try:
        res = coll.query(query_texts=[query], n_results=top_k, where=where)
    except Exception as e:  # pragma: no cover
        log.warning("Chroma query failed: %s", e)
        return []
    out: list[dict[str, Any]] = []
    ids = (res.get("ids") or [[]])[0]
    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]
    for cid, doc, meta, dist in zip(ids, docs, metas, dists):
        score = 1.0 - float(dist) if dist is not None else 0.0
        task_id = (meta or {}).get("task_id") or cid.split(":", 1)[0]
        out.append({"task_id": task_id, "score": round(score, 4), "snippet": (doc or "")[:240]})
    return out
