"""Tests for pipeline/vad.py — no real model required (pass-through mode)."""

import numpy as np
import pytest

from pipeline.vad import VAD, SpeechSegment, SAMPLE_RATE, HYSTERESIS_DURATION_MS


def make_chunk(duration_s: float, value: float = 0.0) -> np.ndarray:
    """Create a constant-value float32 audio chunk."""
    n = int(SAMPLE_RATE * duration_s)
    return np.full(n, value, dtype=np.float32)


@pytest.fixture
def vad_passthrough():
    """VAD with no model loaded (pass-through: all audio classified as speech)."""
    v = VAD(threshold=0.5)
    # Don't call .load() — _model stays None → prob=1.0 always
    return v


class TestVADPassthrough:
    """When model is None, all audio passes as speech (prob=1.0)."""

    def test_no_emission_on_first_speech_chunk(self, vad_passthrough):
        chunk = make_chunk(0.5)
        result = vad_passthrough.process_chunk(chunk, captured_at_ms=0)
        assert result is None, "Should not emit on first speech chunk"

    def test_emits_segment_after_hysteresis_silence(self, vad_passthrough):
        """After speech, silence for HYSTERESIS_DURATION_MS should trigger emission."""
        v = vad_passthrough

        # Manually override _get_speech_probability to return speech then silence
        call_count = [0]
        def mock_prob(audio):
            call_count[0] += 1
            # First 3 calls: speech, remaining: silence
            return 1.0 if call_count[0] <= 3 else 0.0

        v._get_speech_probability = mock_prob

        # Feed speech chunks
        for i in range(3):
            seg = v.process_chunk(make_chunk(0.5), captured_at_ms=i * 500)
            assert seg is None

        # Feed silence for just under hysteresis — no emit
        silence_start = 1500
        seg = v.process_chunk(make_chunk(0.5), captured_at_ms=silence_start)
        assert seg is None

        # Feed silence past hysteresis threshold
        past_hysteresis = silence_start + HYSTERESIS_DURATION_MS + 100
        seg = v.process_chunk(make_chunk(0.5), captured_at_ms=past_hysteresis)
        assert seg is not None, "Should emit segment after hysteresis"
        assert isinstance(seg, SpeechSegment)
        assert len(seg.data) > 0

    def test_flush_returns_buffered_speech(self, vad_passthrough):
        v = vad_passthrough
        chunk = make_chunk(1.0)
        # Feed one chunk (speech, no emission yet)
        v.process_chunk(chunk, captured_at_ms=0)
        # Flush
        seg = v.flush(current_ms=1000)
        assert seg is not None
        assert isinstance(seg, SpeechSegment)

    def test_flush_returns_none_when_not_in_speech(self, vad_passthrough):
        v = vad_passthrough
        seg = v.flush(current_ms=0)
        assert seg is None

    def test_silence_duration_accumulates_without_speech(self, vad_passthrough):
        v = vad_passthrough
        # Override to return silence
        v._get_speech_probability = lambda _: 0.0

        chunk = make_chunk(0.5)  # 0.5s
        v.process_chunk(chunk, captured_at_ms=0)
        v.process_chunk(chunk, captured_at_ms=500)

        # Should have accumulated ~0.5s (elapsed between chunks)
        assert v.silence_duration_seconds > 0

    def test_conversation_id_carried_through(self, vad_passthrough):
        v = vad_passthrough
        v._get_speech_probability = lambda _: 1.0

        v.process_chunk(make_chunk(0.5), captured_at_ms=0, conversation_id="conv-1")
        seg = v.flush(current_ms=500, conversation_id="conv-1")
        assert seg is not None
        assert seg.conversation_id == "conv-1"
