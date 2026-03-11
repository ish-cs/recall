"""Audio capture via sounddevice (microphone)."""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
CHANNELS = 1
BLOCKSIZE = 48000  # 3 seconds of audio
DTYPE = np.float32


@dataclass
class AudioChunk:
    data: np.ndarray        # float32 array, shape (n_samples,)
    captured_at_ms: int     # wall-clock ms when chunk was captured
    conversation_id: Optional[str] = None


class AudioCapture:
    """
    Captures microphone audio and queues 3-second chunks.

    Accepts device_id=None (system default) or a specific device index
    for future system audio support.
    """

    def __init__(
        self,
        raw_audio_queue: asyncio.Queue,
        device_id: Optional[int] = None,
    ):
        self.raw_audio_queue = raw_audio_queue
        self.device_id = device_id
        self._stream: Optional[sd.InputStream] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._current_conversation_id: Optional[str] = None

    def set_conversation_id(self, conversation_id: Optional[str]) -> None:
        self._current_conversation_id = conversation_id

    def _callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        if status:
            logger.warning("Audio capture status: %s", status)

        chunk = AudioChunk(
            data=indata[:, 0].copy() if indata.ndim > 1 else indata.copy(),
            captured_at_ms=int(time.time() * 1000),
            conversation_id=self._current_conversation_id,
        )

        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.raw_audio_queue.put(chunk), self._loop
            )

    def start(self) -> None:
        self._loop = asyncio.get_event_loop()
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=BLOCKSIZE,
            device=self.device_id,
            callback=self._callback,
        )
        self._stream.start()
        logger.info("Audio capture started (device=%s, rate=%d)", self.device_id, SAMPLE_RATE)

    def stop(self) -> None:
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
            logger.info("Audio capture stopped")

    @property
    def is_active(self) -> bool:
        return self._stream is not None and self._stream.active
