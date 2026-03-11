"""WAV file storage for conversation audio."""

import soundfile as sf
import numpy as np
from pathlib import Path
from typing import Optional
import time


class AudioStore:
    """Manages WAV file writing for a single conversation."""

    SAMPLE_RATE = 16000
    CHANNELS = 1

    def __init__(self, audio_dir: str):
        self.audio_dir = Path(audio_dir)
        self._file: Optional[sf.SoundFile] = None
        self._path: Optional[Path] = None
        self._conversation_id: Optional[str] = None

    def open(self, conversation_id: str, started_at_ms: int) -> str:
        """Open a new WAV file for a conversation. Returns the file path."""
        self.close()

        dt = time.gmtime(started_at_ms / 1000)
        dir_path = self.audio_dir / f"{dt.tm_year:04d}" / f"{dt.tm_mon:02d}" / f"{dt.tm_mday:02d}"
        dir_path.mkdir(parents=True, exist_ok=True)

        self._path = dir_path / f"{conversation_id}.wav"
        self._conversation_id = conversation_id
        self._file = sf.SoundFile(
            str(self._path),
            mode="w",
            samplerate=self.SAMPLE_RATE,
            channels=self.CHANNELS,
            format="WAV",
            subtype="PCM_16",
        )
        return str(self._path)

    def write(self, audio_chunk: np.ndarray) -> None:
        """Write a float32 audio chunk to the current WAV file."""
        if self._file is None:
            return
        # Convert float32 to int16 for storage
        audio_int16 = (audio_chunk * 32767).astype(np.int16)
        self._file.write(audio_int16)

    def close(self) -> Optional[str]:
        """Close the current WAV file. Returns the path if a file was open."""
        if self._file is not None:
            self._file.close()
            self._file = None
            path = str(self._path)
            self._path = None
            self._conversation_id = None
            return path
        return None

    @property
    def current_path(self) -> Optional[str]:
        return str(self._path) if self._path else None

    @property
    def is_open(self) -> bool:
        return self._file is not None
