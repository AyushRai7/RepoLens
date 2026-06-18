from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional
from app.core.rate_limit import check_rate_limit, get_ws_client_ip

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

try:
    from langchain_huggingface import HuggingFaceEmbeddings
except ImportError:
    from langchain_community.embeddings import HuggingFaceEmbeddings  # noqa

from langchain_community.vectorstores import FAISS
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy.orm import Session

from app.agent.graph_agent import build_agent
from app.config import get_settings
from app.db.cache import get_cache, get_job_status, get_redis, set_cache
from app.db.models import CodeFile, Repository
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])
settings = get_settings()

_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
_MAX_HISTORY_TURNS = 20
_HISTORY_TTL = 60 * 60 * 24 * 7  # 7 days
_JOB_STATUS_TTL = 60 * 60 * 2  # 2 hours

_WAIT_ATTEMPTS = 150  # 150 × 2 s = 5 minutes max
_WAIT_INTERVAL = 2

_retriever_cache: dict = {}
_agent_cache: dict = {}

_retriever_locks: dict[str, asyncio.Lock] = {}


def _get_retriever_lock(full_name: str) -> asyncio.Lock:
    if full_name not in _retriever_locks:
        _retriever_locks[full_name] = asyncio.Lock()
    return _retriever_locks[full_name]



def _history_key(full_name: str) -> str:
    return f"chat:history:v2:{full_name}"


def _load_history(full_name: str, analysed_at=None) -> list:
    raw = get_cache(_history_key(full_name))
    if not raw or not isinstance(raw, dict):
        return []

    if analysed_at:
        saved_at = raw.get("saved_at")
        if saved_at:
            try:
                from datetime import datetime

                saved_dt = datetime.fromisoformat(saved_at)
                if saved_dt.tzinfo is not None:
                    saved_dt = saved_dt.replace(tzinfo=None)
                analysed_naive = (
                    analysed_at.replace(tzinfo=None)
                    if hasattr(analysed_at, "tzinfo") and analysed_at.tzinfo
                    else analysed_at
                )
                if analysed_naive > saved_dt:
                    logger.info("History for %s is stale, discarding", full_name)
                    get_redis().delete(_history_key(full_name))
                    return []
            except Exception:
                pass

    history = []
    for item in raw.get("messages", []):
        if item["role"] == "human":
            history.append(HumanMessage(content=item["content"]))
        else:
            history.append(AIMessage(content=item["content"]))
    return history


def _save_history(full_name: str, history: list) -> None:
    from datetime import datetime, timezone

    trimmed = history[-(_MAX_HISTORY_TURNS * 2) :]
    payload = {
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "messages": [
            {
                "role": "human" if isinstance(m, HumanMessage) else "ai",
                "content": m.content if isinstance(m.content, str) else "",
            }
            for m in trimmed
        ],
    }
    set_cache(_history_key(full_name), payload, ttl_seconds=_HISTORY_TTL)


# ── Repo status helpers ────────────────────────────────────────────────────────


def _get_repo_status(full_name: str, db: Session) -> tuple[str, str | None]:
    job = get_job_status(full_name)
    if job and job.get("status"):
        return job["status"], job.get("message")

    repo = db.query(Repository).filter_by(full_name=full_name).first()
    if not repo:
        return "not_found", None
    db.expire(repo)
    repo = db.query(Repository).filter_by(full_name=full_name).first()
    return (repo.status if repo else "not_found"), (
        repo.status_message if repo else None
    )


# ── Retriever builder (async-safe) ────────────────────────────────────────────


def _build_retriever_sync(repo_id: str, db: Session):
    """Blocking — must be called via asyncio.to_thread()."""
    files = db.query(CodeFile).filter_by(repo_id=repo_id).limit(300).all()
    texts, metas = [], []
    for f in files:
        if not f.content:
            continue
        chunk = f"File: {f.path}\nLanguage: {f.language}\n\n{f.content[:1500]}"
        texts.append(chunk)
        metas.append({"path": f.path, "language": f.language or "unknown"})

    if not texts:
        return None

    embeddings = HuggingFaceEmbeddings(
        model_name=_EMBED_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    vs = FAISS.from_texts(texts, embeddings, metadatas=metas)
    return vs.as_retriever(search_kwargs={"k": 4})


async def _get_or_build_retriever(full_name: str, repo_id: str, db: Session):
    """
    Return cached retriever or build one without blocking the event loop.
    Uses a per-repo asyncio.Lock to prevent concurrent cold-start builds.
    """
    if full_name in _retriever_cache:
        return _retriever_cache[full_name]

    lock = _get_retriever_lock(full_name)
    async with lock:
        # Double-check after acquiring lock
        if full_name in _retriever_cache:
            return _retriever_cache[full_name]

        logger.info("Building retriever for %s (offloaded to thread)", full_name)
        retriever = await asyncio.to_thread(_build_retriever_sync, repo_id, db)
        _retriever_cache[full_name] = retriever
        return retriever


def _get_or_build_agent(full_name: str, repo_id: str, retriever, db: Session):
    if full_name not in _agent_cache:
        logger.info("Building agent for %s", full_name)
        _agent_cache[full_name] = build_agent(db, repo_id, full_name, retriever)
    return _agent_cache[full_name]


# ── Selected-file content injection ───────────────────────────────────────────


def _augment_with_files(
    user_text: str,
    selected_files: list[str],
    repo_id: str,
    db: Session,
) -> str:
    if not selected_files:
        return user_text

    snippets = []
    for path in selected_files[:5]:
        f = db.query(CodeFile).filter_by(repo_id=repo_id, path=path).first()
        if f and f.content:
            preview = f.content[:3000]
            snippets.append(
                f"=== {path} ({f.language}) ===\n{preview}\n"
                + ("… [truncated]\n" if len(f.content) > 3000 else "")
            )

    if not snippets:
        return user_text

    file_block = "\n".join(snippets)
    return (
        f"[Selected files for context]\n{file_block}\n" f"[User question]\n{user_text}"
    )


# ── WebSocket endpoint ────────────────────────────────────────────────────────


@router.websocket("/ws/{owner}/{name}")
async def chat_websocket(websocket: WebSocket, owner: str, name: str):
    await websocket.accept()
    client_ip = get_ws_client_ip(websocket)
    if not check_rate_limit(
        f"ws_connect:{client_ip}", max_requests=10, window_seconds=60
    ):
        await websocket.send_json(
            {
                "type": "error",
                "content": "Too many connection attempts. Please wait a moment and try again.",
            }
        )
        await websocket.close(code=4429)
        return
    db = SessionLocal()

    try:
        full_name = f"{owner}/{name}"
        repo: Optional[Repository] = None

        # ── Wait for pipeline ──────────────────────────────────────────────
        for attempt in range(_WAIT_ATTEMPTS):
            status, status_msg = _get_repo_status(full_name, db)

            if status == "not_found":
                if attempt < 5:
                    await websocket.send_json(
                        {
                            "type": "status",
                            "content": f"Waiting for analysis to start… ({attempt * _WAIT_INTERVAL}s)",
                        }
                    )
                    await asyncio.sleep(_WAIT_INTERVAL)
                    continue
                await websocket.send_json(
                    {
                        "type": "error",
                        "content": f"Repository '{full_name}' not found. Submit it for analysis first.",
                    }
                )
                return

            if status == "ready":
                repo = db.query(Repository).filter_by(full_name=full_name).first()
                break

            if status == "failed":
                await websocket.send_json(
                    {
                        "type": "error",
                        "content": f"Analysis failed: {status_msg or 'unknown error'}",
                    }
                )
                return

            elapsed = attempt * _WAIT_INTERVAL
            await websocket.send_json(
                {
                    "type": "status",
                    "content": f"{status_msg or status} ({elapsed}s elapsed…)",
                }
            )
            await asyncio.sleep(_WAIT_INTERVAL)
        else:
            await websocket.send_json(
                {
                    "type": "error",
                    "content": "Analysis still running after 5 minutes. Refresh the chat tab once it's done.",
                }
            )
            return

        if not repo:
            await websocket.send_json(
                {"type": "error", "content": "Repository record not found."}
            )
            return

        repo_id = str(repo.id)
        analysed_at = repo.analysed_at

        # ── Build retriever (non-blocking) ─────────────────────────────────
        await websocket.send_json({"type": "status", "content": "Loading code index…"})
        retriever = await _get_or_build_retriever(full_name, repo_id, db)

        if not retriever:
            await websocket.send_json(
                {
                    "type": "error",
                    "content": "No source files indexed for this repository.",
                }
            )
            return

        await websocket.send_json(
            {"type": "status", "content": "Initialising AI agent…"}
        )
        agent = _get_or_build_agent(full_name, repo_id, retriever, db)

        history = _load_history(full_name, analysed_at=analysed_at)

        await websocket.send_json(
            {
                "type": "ready",
                "content": "Chat ready",
                # Always include analysed_at so frontend can detect stale history.
                # Send null explicitly if not set — don't omit the key.
                "analysed_at": analysed_at.isoformat() if analysed_at else None,
            }
        )

        # ── Message loop ───────────────────────────────────────────────────
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if msg.get("type") != "message":
                continue

            user_text = (msg.get("content") or "").strip()
            if not user_text:
                continue

            selected_files: list[str] = msg.get("selected_files") or []

            if not check_rate_limit(
                f"chat_msg:{client_ip}", max_requests=15, window_seconds=60
            ):
                await websocket.send_json(
                    {
                        "type": "error",
                        "content": "You're sending messages too quickly — please slow down.",
                    }
                )
                continue

            augmented_text = _augment_with_files(user_text, selected_files, repo_id, db)
            history.append(HumanMessage(content=augmented_text))

            full_response = ""
            try:
                async for chunk in agent.astream(
                    {
                        "messages": history,
                        "repo_full_name": full_name,
                        "scoped_file": None,
                    }
                ):
                    if "agent" in chunk:
                        for m in chunk["agent"].get("messages", []):
                            content = m.content if hasattr(m, "content") else ""
                            if not content or not isinstance(content, str):
                                continue
                            text = content.strip()
                            if not text:
                                continue
                            full_response += text
                            await websocket.send_json(
                                {"type": "token", "content": text}
                            )

            except Exception as stream_err:
                logger.error(
                    "Agent streaming error for %s: %s",
                    full_name,
                    stream_err,
                    exc_info=True,
                )
                # Send done first so frontend clears isLoading, then error
                if not full_response:
                    full_response = "An error occurred while generating a response."
                    await websocket.send_json(
                        {"type": "token", "content": full_response}
                    )
                await websocket.send_json({"type": "done", "content": full_response})
                await websocket.send_json(
                    {
                        "type": "error",
                        "content": f"Agent error: {str(stream_err)[:300]}",
                    }
                )
                if history and isinstance(history[-1], HumanMessage):
                    history.pop()
                continue

            # Guarantee non-empty response
            if not full_response:
                full_response = (
                    "I wasn't able to generate a response for that question. "
                    "Please try rephrasing it."
                )
                await websocket.send_json({"type": "token", "content": full_response})

            await websocket.send_json({"type": "done", "content": full_response})
            history.append(AIMessage(content=full_response))
            _save_history(full_name, history)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for %s/%s", owner, name)
    except Exception as e:
        logger.error("chat_websocket unhandled error: %s", e, exc_info=True)
        try:
            await websocket.send_json({"type": "error", "content": str(e)[:300]})
        except Exception:
            pass
    finally:
        db.close()


# ── REST helpers ───────────────────────────────────────────────────────────────


@router.delete("/{owner}/{name}/history")
async def clear_history(owner: str, name: str):
    """Clear persisted chat history for a repo."""
    full_name = f"{owner}/{name}"
    try:
        get_redis().delete(_history_key(full_name))
    except Exception:
        pass
    _agent_cache.pop(full_name, None)
    _retriever_cache.pop(full_name, None)
    return {"status": "cleared", "repo": full_name}


@router.get("/{owner}/{name}/history")
async def get_history(owner: str, name: str):
    """Return raw persisted history (for debugging)."""
    full_name = f"{owner}/{name}"
    raw = get_cache(_history_key(full_name)) or {}
    messages = raw.get("messages", []) if isinstance(raw, dict) else []
    return {
        "repo": full_name,
        "turns": len(messages) // 2,
        "saved_at": raw.get("saved_at") if isinstance(raw, dict) else None,
        "messages": messages,
    }
