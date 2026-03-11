"""faster-whisper transcription wrapper."""

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000


@dataclass
class WordTimestamp:
    word: str
    start_ms: int   # absolute Unix ms
    end_ms: int
    probability: float


@dataclass
class TranscriptChunk:
    text: str
    words: list[WordTimestamp]
    start_ms: int   # absolute Unix ms
    end_ms: int
    language: str
    avg_log_prob: float
    conversation_id: Optional[str] = None


class Transcriber:
    """
    faster-whisper distil-large-v3 wrapper.
    Runs in a thread pool to avoid blocking the asyncio event loop.
    """

    MODEL_ID = "distil-large-v3"

    def __init__(self, model_size: str = "distil-large-v3", device: str = "auto"):
        self.model_size = model_size
        self.device = device
        self._model = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="transcriber")

    def load(self) -> None:
        """Load the faster-whisper model."""
        try:
            from faster_whisper import WhisperModel

            # Determine best device for Apple Silicon
            compute_type = "float16"
            if self.device == "auto":
                try:
                    import torch
                    if torch.backends.mps.is_available():
                        device = "mps"
                    else:
                        device = "cpu"
                        compute_type = "int8"
                except ImportError:
                    device = "cpu"
                    compute_type = "int8"
            else:
                device = self.device

            self._model = WhisperModel(
                self.model_size,
                device=device,
                compute_type=compute_type,
            )
            logger.info("Transcriber loaded: %s on %s", self.model_size, device)
        except ImportError:
            logger.warning("faster-whisper not installed; transcriber unavailable")
        except Exception as e:
            logger.error("Failed to load transcriber: %s", e)

    def transcribe_sync(
        self,
        audio: np.ndarray,
        start_ms: int,
        conversation_id: Optional[str] = None,
    ) -> Optional[TranscriptChunk]:
        """Transcribe audio synchronously (call from thread pool)."""
        if self._model is None:
            return None
        if len(audio) < SAMPLE_RATE * 0.5:
            logger.debug("Audio too short to transcribe (%d samples)", len(audio))
            return None

        try:
            segments, info = self._model.transcribe(
                audio,
                beam_size=5,
                word_timestamps=True,
                language="en",
            )

            words = []
            text_parts = []
            avg_log_prob = 0.0
            seg_count = 0

            for seg in segments:
                text_parts.append(seg.text.strip())
                avg_log_prob += seg.avg_logprob
                seg_count += 1

                if seg.words:
                    for w in seg.words:
                        words.append(WordTimestamp(
                            word=w.word,
                            start_ms=start_ms + int(w.start * 1000),
                            end_ms=start_ms + int(w.end * 1000),
                            probability=w.probability,
                        ))

            if not text_parts:
                return None

            text = " ".join(text_parts).strip()
            end_ms = start_ms + int(len(audio) / SAMPLE_RATE * 1000)

            return TranscriptChunk(
                text=text,
                words=words,
                start_ms=start_ms,
                end_ms=words[-1].end_ms if words else end_ms,
                language=info.language,
                avg_log_prob=avg_log_prob / max(seg_count, 1),
                conversation_id=conversation_id,
            )
        except Exception as e:
            logger.error("Transcription error: %s", e)
            return None

    async def transcribe(
        self,
        audio: np.ndarray,
        start_ms: int,
        conversation_id: Optional[str] = None,
    ) -> Optional[TranscriptChunk]:
        """Transcribe asynchronously by running in thread pool."""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self.transcribe_sync,
            audio,
            start_ms,
            conversation_id,
        )

    @property
    def is_loaded(self) -> bool:
        return self._model is not None
