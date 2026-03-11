"""Shared test fixtures for ml-worker tests."""

import struct
import sys
import wave
from pathlib import Path

import numpy as np
import pytest

# Add ml-worker root to path so imports work without installing the package
ML_WORKER_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ML_WORKER_ROOT))

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _write_wav(path: Path, audio: np.ndarray, sample_rate: int = 16000) -> None:
    """Write a float32 numpy array to a 16-bit WAV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = (audio * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())


@pytest.fixture(scope="session", autouse=True)
def create_fixtures():
    """Generate WAV fixtures used across tests."""
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    # silence.wav — 3 seconds of silence
    silence_path = FIXTURES_DIR / "silence.wav"
    if not silence_path.exists():
        silence = np.zeros(3 * 16000, dtype=np.float32)
        _write_wav(silence_path, silence)

    # speech_single.wav — 2 seconds of a 440 Hz sine tone (simulates speech energy)
    speech_path = FIXTURES_DIR / "speech_single.wav"
    if not speech_path.exists():
        t = np.linspace(0, 2.0, 2 * 16000, endpoint=False)
        tone = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        _write_wav(speech_path, tone)

    return {"silence": silence_path, "speech_single": speech_path}


@pytest.fixture
def silence_wav(create_fixtures) -> Path:
    return FIXTURES_DIR / "silence.wav"


@pytest.fixture
def speech_wav(create_fixtures) -> Path:
    return FIXTURES_DIR / "speech_single.wav"


def load_wav_as_float32(path: Path) -> np.ndarray:
    """Load a WAV file and return float32 audio normalized to [-1, 1]."""
    with wave.open(str(path), "rb") as wf:
        frames = wf.readframes(wf.getnframes())
        sampwidth = wf.getsampwidth()
        nframes = wf.getnframes()

    if sampwidth == 2:
        audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    elif sampwidth == 4:
        audio = np.frombuffer(frames, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"Unsupported sample width: {sampwidth}")

    return audio
