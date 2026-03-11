"""FastAPI server with SSE endpoint for the Python ML worker."""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize pipeline and models on startup."""
    from main import startup as do_startup
    await do_startup()
    yield


app = FastAPI(title="Recall ML Worker", version="0.1.0", lifespan=lifespan)

# Global pipeline reference (set in main.py after initialization)
_pipeline = None
_model_manager = None
_sse_clients: list[asyncio.Queue] = []


def set_pipeline(pipeline) -> None:
    global _pipeline
    _pipeline = pipeline


def set_model_manager(manager) -> None:
    global _model_manager
    _model_manager = manager


def emit_sse(event_type: str, data: dict) -> None:
    """Emit an SSE event to all connected clients."""
    payload = json.dumps(data)
    for q in list(_sse_clients):
        try:
            q.put_nowait(f"event: {event_type}\ndata: {payload}\n\n")
        except asyncio.QueueFull:
            pass


# ── Health ──────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"ok": True}


# ── Pipeline ──────────────────────────────────────────────────────────

@app.post("/pipeline/start")
async def pipeline_start():
    if _pipeline is None:
        raise HTTPException(503, "Pipeline not initialized")
    _pipeline.start()
    return {"ok": True}


@app.post("/pipeline/stop")
async def pipeline_stop():
    if _pipeline is None:
        raise HTTPException(503, "Pipeline not initialized")
    _pipeline.stop()
    return {"ok": True}


@app.post("/pipeline/pause")
async def pipeline_pause():
    if _pipeline is None:
        raise HTTPException(503, "Pipeline not initialized")
    _pipeline.pause()
    return {"ok": True}


@app.post("/pipeline/resume")
async def pipeline_resume():
    if _pipeline is None:
        raise HTTPException(503, "Pipeline not initialized")
    _pipeline.resume()
    return {"ok": True}


@app.get("/pipeline/status")
async def pipeline_status():
    if _pipeline is None:
        return {
            "recording": False,
            "paused": False,
            "current_conversation_id": None,
            "hot_queue_depth": 0,
            "cold_queue_depth": 0,
            "models_ready": False,
        }
    return _pipeline.status


# ── SSE Events ────────────────────────────────────────────────────────

@app.get("/events")
async def events():
    """Server-Sent Events stream."""
    client_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    _sse_clients.append(client_queue)

    async def generate():
        try:
            # Send initial connection event
            yield "event: connected\ndata: {\"type\": \"connected\"}\n\n"
            while True:
                try:
                    msg = await asyncio.wait_for(client_queue.get(), timeout=30.0)
                    yield msg
                except asyncio.TimeoutError:
                    # Heartbeat comment to keep connection alive
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            _sse_clients.remove(client_queue)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Models ──────────────────────────────────────────────────────────

@app.get("/models/status")
async def models_status():
    if _model_manager is None:
        return {"models": []}
    return {"models": _model_manager.all_status()}


@app.post("/models/download")
async def models_download(body: dict):
    if _model_manager is None:
        raise HTTPException(503, "Model manager not initialized")
    name = body.get("name")
    if not name:
        raise HTTPException(400, "name required")

    async def do_download():
        def progress(model_name, pct, downloaded, total):
            emit_sse("model.download_progress", {
                "type": "model.download_progress",
                "model_name": model_name,
                "progress_pct": pct,
                "bytes_downloaded": downloaded,
                "total_bytes": total,
            })
        await _model_manager.download_model(name, progress_callback=progress)

    asyncio.create_task(do_download())
    return {"ok": True, "queued": name}


# ── Text Embedding ───────────────────────────────────────────────────

class EmbedRequest(BaseModel):
    text: str


@app.post("/embed")
async def embed_text(req: EmbedRequest):
    """Generate text embedding (for semantic search queries)."""
    if _pipeline is None or _pipeline.text_embedder is None:
        raise HTTPException(503, "Text embedder not available")

    loop = asyncio.get_event_loop()
    embedding = await loop.run_in_executor(
        None, lambda: _pipeline.text_embedder.embed(req.text, is_query=True)
    )
    if embedding is None:
        raise HTTPException(500, "Embedding failed")

    return {"embedding": embedding.tolist()}


# ── Speakers ─────────────────────────────────────────────────────────

class SpeakerConfirmRequest(BaseModel):
    speaker_instance_id: str
    speaker_profile_id: Optional[str] = None
    display_name: Optional[str] = None


@app.post("/speakers/confirm")
async def speakers_confirm(req: SpeakerConfirmRequest):
    # Delegate to DB
    if _pipeline is None:
        raise HTTPException(503, "Pipeline not initialized")
    # Implementation: update speaker_instance → speaker_profile link
    import sqlite3
    import uuid
    import time

    db = _pipeline.db
    now = int(time.time() * 1000)

    if req.speaker_profile_id is None:
        # Create new profile
        profile_id = str(uuid.uuid4())
        with db.connection() as conn:
            conn.execute(
                "INSERT INTO speaker_profiles (id, display_name, is_user, created_at, updated_at) VALUES (?, ?, 0, ?, ?)",
                (profile_id, req.display_name, now, now),
            )
    else:
        profile_id = req.speaker_profile_id
        if req.display_name:
            with db.connection() as conn:
                conn.execute(
                    "UPDATE speaker_profiles SET display_name = ?, updated_at = ? WHERE id = ?",
                    (req.display_name, now, profile_id),
                )

    with db.connection() as conn:
        conn.execute(
            "UPDATE speaker_instances SET speaker_profile_id = ? WHERE id = ?",
            (profile_id, req.speaker_instance_id),
        )

    return {"speaker_profile_id": profile_id}


class MergeRequest(BaseModel):
    from_profile_id: str
    to_profile_id: str


@app.post("/speakers/merge")
async def speakers_merge(req: MergeRequest):
    if _pipeline is None:
        raise HTTPException(503, "Pipeline not initialized")
    db = _pipeline.db
    import time
    now = int(time.time() * 1000)
    with db.connection() as conn:
        conn.execute(
            "UPDATE speaker_instances SET speaker_profile_id = ? WHERE speaker_profile_id = ?",
            (req.to_profile_id, req.from_profile_id),
        )
        conn.execute(
            "UPDATE speaker_embeddings SET speaker_profile_id = ? WHERE speaker_profile_id = ?",
            (req.to_profile_id, req.from_profile_id),
        )
        conn.execute(
            "DELETE FROM speaker_profiles WHERE id = ?",
            (req.from_profile_id,),
        )
        conn.execute(
            "UPDATE speaker_profiles SET updated_at = ? WHERE id = ?",
            (now, req.to_profile_id),
        )
    return {"ok": True}
