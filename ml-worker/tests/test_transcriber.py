"""Tests for pipeline/transcriber.py — no model required (model not loaded)."""

import numpy as np
import pytest

from pipeline.transcriber import Transcriber, TranscriptChunk, SAMPLE_RATE


@pytest.fixture
def transcriber_no_model():
    """Transcriber without loading a model (simulates model not yet downloaded)."""
    t = Transcriber(model_size="distil-large-v3")
    # Do NOT call .load() — model stays None
    return t


class TestTranscriberNoModel:
    def test_is_loaded_false_without_load(self, transcriber_no_model):
        assert not transcriber_no_model.is_loaded

    def test_transcribe_sync_returns_none_when_no_model(self, transcriber_no_model):
        audio = np.zeros(SAMPLE_RATE * 2, dtype=np.float32)  # 2s silence
        result = transcriber_no_model.transcribe_sync(audio, start_ms=0)
        assert result is None

    def test_transcribe_sync_too_short_returns_none(self, transcriber_no_model):
        # Inject a mock model so we test the short-audio guard
        class FakeModel:
            pass

        transcriber_no_model._model = FakeModel()
        # 0.3s — below 0.5s minimum
        audio = np.zeros(int(SAMPLE_RATE * 0.3), dtype=np.float32)
        result = transcriber_no_model.transcribe_sync(audio, start_ms=0)
        assert result is None

    @pytest.mark.asyncio
    async def test_transcribe_async_returns_none_when_no_model(self, transcriber_no_model):
        audio = np.zeros(SAMPLE_RATE, dtype=np.float32)
        result = await transcriber_no_model.transcribe(audio, start_ms=0)
        assert result is None


class TestTranscriberMocked:
    """Tests using a mock model to verify output shape without real inference."""

    def test_transcribe_sync_with_mock_model(self):
        from pipeline.transcriber import WordTimestamp

        t = Transcriber()

        class FakeSegment:
            text = " hello world"
            avg_logprob = -0.2
            words = [
                type("W", (), {"word": "hello", "start": 0.1, "end": 0.5, "probability": 0.95})(),
                type("W", (), {"word": "world", "start": 0.6, "end": 1.0, "probability": 0.93})(),
            ]

        class FakeInfo:
            language = "en"

        class FakeModel:
            def transcribe(self, audio, **kwargs):
                return [FakeSegment()], FakeInfo()

        t._model = FakeModel()
        audio = np.zeros(SAMPLE_RATE * 2, dtype=np.float32)
        result = t.transcribe_sync(audio, start_ms=1000, conversation_id="conv-1")

        assert result is not None
        assert isinstance(result, TranscriptChunk)
        assert result.text == "hello world"
        assert result.language == "en"
        assert result.conversation_id == "conv-1"
        assert len(result.words) == 2
        assert result.words[0].word == "hello"
        assert result.start_ms == 1000

    def test_transcribe_sync_empty_segments_returns_none(self):
        t = Transcriber()

        class FakeInfo:
            language = "en"

        class FakeModel:
            def transcribe(self, audio, **kwargs):
                return [], FakeInfo()

        t._model = FakeModel()
        audio = np.zeros(SAMPLE_RATE * 2, dtype=np.float32)
        result = t.transcribe_sync(audio, start_ms=0)
        assert result is None
