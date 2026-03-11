"""Conversation segmentation based on silence gaps and clock boundaries."""

import logging
import time
import uuid
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ConversationBoundary:
    """Signals that a conversation should be closed and a new one opened."""
    close_conversation_id: Optional[str]
    reason: str  # "silence_gap" | "midnight" | "manual"


class Segmenter:
    """
    Determines when to close the current conversation and start a new one.

    Triggers:
    1. Silence gap exceeds conversation_gap_seconds (default 60s)
    2. Clock crosses midnight
    3. Manual split (via external call)
    """

    def __init__(self, conversation_gap_seconds: float = 60.0):
        self.conversation_gap_seconds = conversation_gap_seconds
        self._current_conversation_id: Optional[str] = None
        self._conversation_start_ms: Optional[int] = None
        self._last_day: Optional[int] = None

    @property
    def current_conversation_id(self) -> Optional[str]:
        return self._current_conversation_id

    def start_conversation(self, conversation_id: Optional[str] = None) -> str:
        """Start a new conversation. Returns the conversation ID."""
        cid = conversation_id or str(uuid.uuid4())
        self._current_conversation_id = cid
        self._conversation_start_ms = int(time.time() * 1000)
        self._last_day = time.gmtime().tm_yday
        logger.info("Conversation started: %s", cid)
        return cid

    def check_boundary(
        self, silence_duration_seconds: float
    ) -> Optional[ConversationBoundary]:
        """
        Check if a conversation boundary should be triggered.
        Returns a ConversationBoundary if yes, else None.
        """
        if self._current_conversation_id is None:
            return None

        # Check midnight boundary
        current_day = time.gmtime().tm_yday
        if self._last_day is not None and current_day != self._last_day:
            logger.info("Midnight boundary detected")
            return ConversationBoundary(
                close_conversation_id=self._current_conversation_id,
                reason="midnight",
            )

        # Check silence gap
        if silence_duration_seconds >= self.conversation_gap_seconds:
            logger.info(
                "Conversation boundary: %.1fs silence (threshold=%.1fs)",
                silence_duration_seconds,
                self.conversation_gap_seconds,
            )
            return ConversationBoundary(
                close_conversation_id=self._current_conversation_id,
                reason="silence_gap",
            )

        return None

    def close_conversation(self) -> Optional[str]:
        """Close current conversation. Returns closed conversation ID."""
        if self._current_conversation_id is None:
            return None
        cid = self._current_conversation_id
        self._current_conversation_id = None
        self._conversation_start_ms = None
        logger.info("Conversation closed: %s", cid)
        return cid


# ----------- tests (run with pytest) -----------

def _make_segmenter(gap: float = 60.0) -> Segmenter:
    return Segmenter(conversation_gap_seconds=gap)


def test_segmenter_closes_conversation_on_60s_gap():
    seg = _make_segmenter(gap=60.0)
    cid = seg.start_conversation("conv-1")
    assert seg.current_conversation_id == "conv-1"

    # 59s silence — no boundary
    result = seg.check_boundary(59.0)
    assert result is None

    # 60s silence — boundary
    result = seg.check_boundary(60.0)
    assert result is not None
    assert result.close_conversation_id == "conv-1"
    assert result.reason == "silence_gap"


def test_segmenter_no_boundary_without_conversation():
    seg = _make_segmenter()
    result = seg.check_boundary(120.0)
    assert result is None
