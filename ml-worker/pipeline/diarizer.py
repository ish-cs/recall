"""pyannote.audio diarization wrapper with 30s windowed processing."""

import logging
from dataclasses import dataclass
from collections import deque
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
WINDOW_SECONDS = 30
OVERLAP_SECONDS = 5
MIN_SEGMENT_SECONDS = 0.1


@dataclass
class DiarizationSegment:
    speaker_label: str   # SPEAKER_00, SPEAKER_01, ...
    start_sec: float     # relative to window start
    end_sec: float
    start_ms_absolute: int  # absolute wall-clock ms
    end_ms_absolute: int


class Diarizer:
    """
    pyannote.audio 3.1 wrapper.
    Runs diarization on 30-second windows with 5-second overlap.
    Requires HuggingFace token.
    """

    def __init__(self, hf_token: Optional[str] = None):
        self.hf_token = hf_token
        self._pipeline = None
        self._audio_buffer: deque = deque()  # (audio_chunk, start_ms)
        self._buffer_duration_s: float = 0.0

    def load(self) -> bool:
        """Load pyannote diarization pipeline. Returns True on success."""
        if not self.hf_token:
            logger.warning("No HF token provided; diarization disabled")
            return False

        try:
            from pyannote.audio import Pipeline
            import torch

            device = "cpu"
            try:
                if torch.backends.mps.is_available():
                    device = "mps"
            except Exception:
                pass

            self._pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=self.hf_token,
            )
            self._pipeline.to(torch.device(device))
            logger.info("Diarizer loaded on %s", device)
            return True
        except ImportError:
            logger.warning("pyannote.audio not installed; diarization disabled")
        except Exception as e:
            logger.error("Failed to load diarizer: %s", e)
        return False

    def add_chunk(self, audio: np.ndarray, start_ms: int) -> None:
        """Add an audio chunk to the rolling buffer."""
        self._audio_buffer.append((audio.copy(), start_ms))
        self._buffer_duration_s += len(audio) / SAMPLE_RATE

    def should_run(self) -> bool:
        """Returns True if enough audio has accumulated for a window."""
        return self._buffer_duration_s >= WINDOW_SECONDS

    def run_window(self) -> list[DiarizationSegment]:
        """
        Run diarization on the current window.
        Returns list of DiarizationSegment.
        """
        if not self._audio_buffer or self._pipeline is None:
            return []

        # Collect audio for the window
        chunks = []
        window_start_ms = self._audio_buffer[0][1]
        total_samples = 0

        for chunk, _ in self._audio_buffer:
            chunks.append(chunk)
            total_samples += len(chunk)
            if total_samples >= WINDOW_SECONDS * SAMPLE_RATE:
                break

        audio = np.concatenate(chunks, axis=0)

        # Keep overlap in buffer
        overlap_samples = int(OVERLAP_SECONDS * SAMPLE_RATE)
        retained_samples = 0
        retained = deque()
        for chunk, start_ms in reversed(self._audio_buffer):
            if retained_samples >= overlap_samples:
                break
            retained.appendleft((chunk, start_ms))
            retained_samples += len(chunk)

        self._audio_buffer = retained
        self._buffer_duration_s = retained_samples / SAMPLE_RATE

        return self._run_diarization(audio, window_start_ms)

    def _run_diarization(
        self, audio: np.ndarray, window_start_ms: int
    ) -> list[DiarizationSegment]:
        try:
            import torch

            audio_tensor = torch.from_numpy(audio).float().unsqueeze(0)
            input_ = {"waveform": audio_tensor, "sample_rate": SAMPLE_RATE}

            diarization = self._pipeline(input_)
            segments = []

            for turn, _, speaker in diarization.itertracks(yield_label=True):
                if (turn.end - turn.start) < MIN_SEGMENT_SECONDS:
                    continue
                segments.append(DiarizationSegment(
                    speaker_label=speaker,
                    start_sec=turn.start,
                    end_sec=turn.end,
                    start_ms_absolute=window_start_ms + int(turn.start * 1000),
                    end_ms_absolute=window_start_ms + int(turn.end * 1000),
                ))

            return segments
        except Exception as e:
            logger.error("Diarization error: %s", e)
            return []

    @property
    def is_loaded(self) -> bool:
        return self._pipeline is not None
