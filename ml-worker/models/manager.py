"""Model download, verification, and loading manager."""

import hashlib
import logging
import os
import subprocess
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

MODELS = {
    "faster-whisper/distil-large-v3": {
        "required": True,
        "phase": 1,
        "hf_repo": "Systran/faster-distil-whisper-large-v3",
        "size_mb": 1500,
    },
    "pyannote/diarization-3.1": {
        "required": False,
        "phase": 3,
        "hf_repo": "pyannote/speaker-diarization-3.1",
        "size_mb": 250,
        "hf_token_required": True,
    },
    "pyannote/embedding": {
        "required": False,
        "phase": 3,
        "hf_repo": "pyannote/wespeaker-voxceleb-resnet34-LM",
        "size_mb": 100,
        "hf_token_required": True,
    },
    "nomic-embed-text": {
        "required": False,
        "phase": 5,
        "hf_repo": "nomic-ai/nomic-embed-text-v1.5",
        "size_mb": 270,
    },
}


class ModelManager:
    def __init__(self, models_dir: str):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)

    def model_path(self, name: str) -> Path:
        return self.models_dir / name.replace("/", os.sep)

    def check_model(self, name: str) -> dict:
        """Return model status: ready | missing."""
        path = self.model_path(name)
        info = MODELS.get(name, {})
        status = "ready" if path.exists() and any(path.iterdir()) else "missing"
        return {
            "name": name,
            "status": status,
            "size_mb": info.get("size_mb", 0),
            "path": str(path),
        }

    def get_hf_token(self) -> Optional[str]:
        """Retrieve HF token from macOS Keychain."""
        try:
            result = subprocess.run(
                ["security", "find-generic-password", "-a", "recall-app",
                 "-s", "huggingface-token", "-w"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            logger.debug("Keychain lookup failed: %s", e)
        return None

    def store_hf_token(self, token: str) -> bool:
        """Store HF token in macOS Keychain."""
        try:
            subprocess.run(
                ["security", "add-generic-password", "-a", "recall-app",
                 "-s", "huggingface-token", "-w", token, "-U"],
                check=True, timeout=5,
            )
            return True
        except Exception as e:
            logger.error("Failed to store HF token: %s", e)
        return False

    async def download_model(
        self,
        name: str,
        progress_callback: Optional[Callable[[str, float, int, int], None]] = None,
    ) -> bool:
        """Download a model from HuggingFace. Returns True on success."""
        info = MODELS.get(name)
        if not info:
            logger.error("Unknown model: %s", name)
            return False

        target_dir = self.model_path(name)
        target_dir.mkdir(parents=True, exist_ok=True)

        hf_token = None
        if info.get("hf_token_required"):
            hf_token = self.get_hf_token()
            if not hf_token:
                logger.error("HF token required for %s but not found", name)
                return False

        hf_repo = info["hf_repo"]
        logger.info("Downloading %s from %s to %s", name, hf_repo, target_dir)

        try:
            from huggingface_hub import snapshot_download
            kwargs = {
                "repo_id": hf_repo,
                "local_dir": str(target_dir),
                "local_dir_use_symlinks": False,
            }
            if hf_token:
                kwargs["token"] = hf_token

            snapshot_download(**kwargs)
            logger.info("Model %s downloaded successfully", name)
            return True
        except ImportError:
            logger.warning("huggingface_hub not installed; cannot download")
        except Exception as e:
            logger.error("Download failed for %s: %s", name, e)
        return False

    def all_status(self) -> list[dict]:
        return [self.check_model(name) for name in MODELS]
