"""Silero VAD v5 wrapper with speech/silence state machine."""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
SPEECH_PAD_MS = 300          # pad speech windows on each side
MIN_SPEECH_DURATION_MS = 250
MAX_SILENCE_DURATION_MS = 2000  # close speech window after 2s silence
HYSTERESIS_DURATION_MS = 2000   # must see silence for 2s before switching


@dataclass
class SpeechSegment:
    """A buffered speech segment ready for transcription."""
    data: np.ndarray        # float32 audio
    start_ms: int           # wall-clock start
    end_ms: int             # wall-clock end
    conversation_id: Optional[str] = None


class VAD:
    """
    Silero VAD v5 wrapper.

    Implements a hysteretic SILENCE ↔ SPEECH state machine.
    Accumulates speech chunks and emits SpeechSegments to the output queue.
    """

    def __init__(self, threshold: float = 0.5):
        self.threshold = threshold
        self._model = None
        self._in_speech = False
        self._speech_buffer: list[np.ndarray] = []
        self._speech_start_ms: Optional[int] = None
        self._silence_start_ms: Optional[int] = None
        self._total_silence_since_last_speech: float = 0.0  # seconds
        self._last_chunk_ms: Optional[int] = None

    def load(self) -> None:
        """Load the Silero VAD ONNX model."""
        try:
            import silero_vad
            self._model = silero_vad.load_silero_vad()
            logger.info("Silero VAD loaded")
        except ImportError:
            logger.warning("silero_vad not installed; VAD will pass all audio through")
            self._model = None

    def _get_speech_probability(self, audio: np.ndarray) -> float:
        """Get speech probability for an audio chunk."""
        if self._model is None:
            return 1.0  # pass-through if model not available

        import torch
        audio_tensor = torch.from_numpy(audio).float()
        with torch.no_grad():
            prob = self._model(audio_tensor, SAMPLE_RATE).item()
        return prob

    def process_chunk(
        self,
        audio: np.ndarray,
        captured_at_ms: int,
        conversation_id: Optional[str] = None,
    ) -> Optional[SpeechSegment]:
        """
        Process one audio chunk.
        Returns a SpeechSegment when a natural speech window ends, else None.
        """
        prob = self._get_speech_probability(audio)
        chunk_duration_s = len(audio) / SAMPLE_RATE

        if self._last_chunk_ms is not None:
            elapsed_s = (captured_at_ms - self._last_chunk_ms) / 1000.0
        else:
            elapsed_s = chunk_duration_s
        self._last_chunk_ms = captured_at_ms

        is_speech = prob > self.threshold

        if is_speech:
            # Track cumulative silence (for conversation boundary detection)
            self._total_silence_since_last_speech = 0.0

            if not self._in_speech:
                self._in_speech = True
                self._speech_start_ms = captured_at_ms
                logger.debug("Speech started (prob=%.3f)", prob)
            self._speech_buffer.append(audio.copy())
            self._silence_start_ms = None
        else:
            # Silence
            self._total_silence_since_last_speech += elapsed_s

            if self._in_speech:
                # Track how long we've been silent
                if self._silence_start_ms is None:
                    self._silence_start_ms = captured_at_ms

                silence_duration_ms = captured_at_ms - self._silence_start_ms

                if silence_duration_ms > HYSTERESIS_DURATION_MS:
                    # Switch to silence — emit accumulated speech
                    logger.debug("Speech ended after %.1fs", (captured_at_ms - self._speech_start_ms) / 1000)
                    return self._emit_speech_segment(captured_at_ms, conversation_id)
                else:
                    # Keep buffering (might be mid-word pause)
                    self._speech_buffer.append(audio.copy())

        return None

    def flush(self, current_ms: int, conversation_id: Optional[str] = None) -> Optional[SpeechSegment]:
        """Force-emit any buffered speech (e.g. when conversation ends)."""
        if self._in_speech and self._speech_buffer:
            return self._emit_speech_segment(current_ms, conversation_id)
        return None

    def _emit_speech_segment(
        self, end_ms: int, conversation_id: Optional[str]
    ) -> SpeechSegment:
        combined = np.concatenate(self._speech_buffer, axis=0)
        segment = SpeechSegment(
            data=combined,
            start_ms=self._speech_start_ms or end_ms,
            end_ms=end_ms,
            conversation_id=conversation_id,
        )
        self._in_speech = False
        self._speech_buffer = []
        self._speech_start_ms = None
        self._silence_start_ms = None
        return segment

    @property
    def silence_duration_seconds(self) -> float:
        """Cumulative silence since last speech (for conversation boundary detection)."""
        return self._total_silence_since_last_speech
