"""
Recall ML Worker — entry point.

Starts FastAPI on a random port, prints PORT={n} to stdout so the
Tauri Rust core can discover it.
"""

import asyncio
import logging
import os
import socket
import sys

import uvicorn

from ipc.server import app, set_pipeline, set_model_manager, emit_sse
from pipeline.orchestrator import Pipeline
from models.manager import ModelManager
from storage.db import Database
from storage.audio_store import AudioStore

logging.basicConfig(
    level=getattr(logging, os.environ.get("RECALL_WORKER_LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("recall.worker")


def find_free_port() -> int:
    """Find a free TCP port."""
    forced = os.environ.get("RECALL_WORKER_PORT")
    if forced:
        return int(forced)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def get_app_dirs() -> tuple[str, str]:
    """Return (db_path, audio_dir)."""
    db_path = os.environ.get("RECALL_DB_PATH")
    audio_dir = os.environ.get("RECALL_AUDIO_PATH")

    if not db_path:
        home = os.path.expanduser("~")
        app_support = os.path.join(home, "Library", "Application Support", "Recall")
        os.makedirs(app_support, exist_ok=True)
        db_path = os.path.join(app_support, "recall.db")

    if not audio_dir:
        home = os.path.expanduser("~")
        app_support = os.path.join(home, "Library", "Application Support", "Recall")
        audio_dir = os.path.join(app_support, "audio")

    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    os.makedirs(audio_dir, exist_ok=True)
    return db_path, audio_dir


def get_models_dir() -> str:
    home = os.path.expanduser("~")
    return os.path.join(home, "Library", "Application Support", "Recall", "models")


def get_hf_token() -> str | None:
    """
    Read HuggingFace token from macOS Keychain.
    Stored by: security add-generic-password -s recall-hf-token -a recall -w <TOKEN>
    """
    try:
        import subprocess
        result = subprocess.run(
            ["security", "find-generic-password", "-s", "recall-hf-token", "-a", "recall", "-w"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            token = result.stdout.strip()
            if token:
                logger.info("HuggingFace token found in Keychain")
                return token
    except Exception as e:
        logger.debug("Could not read HF token from Keychain: %s", e)
    return os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("HF_TOKEN")


async def startup() -> None:
    """Initialize pipeline and models before serving."""
    db_path, audio_dir = get_app_dirs()
    models_dir = get_models_dir()

    db = Database(db_path)
    audio_store = AudioStore(audio_dir)
    model_manager = ModelManager(models_dir)

    # Read settings (gracefully handle missing tables — Rust runs migrations)
    try:
        vad_threshold = float(db.get_setting("vad_threshold") or "0.5")
        gap_seconds = float(db.get_setting("conversation_gap_seconds") or "60")
        power_mode = db.get_setting("power_mode") or "balanced"
    except Exception as e:
        logger.warning("Could not read settings (DB may not be initialized yet): %s", e)
        vad_threshold = 0.5
        gap_seconds = 60.0
        power_mode = "balanced"

    hf_token = get_hf_token()

    pipeline = Pipeline(
        db=db,
        audio_store=audio_store,
        sse_emit=emit_sse,
        conversation_gap_seconds=gap_seconds,
        vad_threshold=vad_threshold,
        power_mode=power_mode,
        hf_token=hf_token,
    )

    set_pipeline(pipeline)
    set_model_manager(model_manager)

    # Load models in background
    asyncio.create_task(pipeline.load_models())

    logger.info("Worker startup complete")


def main():
    port = find_free_port()

    # Print port FIRST so Rust reads it immediately on stdout
    print(f"PORT={port}", flush=True)
    logger.info("Starting uvicorn on port %d", port)

    uvicorn.run(
        "ipc.server:app",
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
        lifespan="on",
    )


if __name__ == "__main__":
    main()
