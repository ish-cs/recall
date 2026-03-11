"""Tests for pipeline/segmenter.py."""

from pipeline.segmenter import Segmenter, ConversationBoundary


def test_no_boundary_without_active_conversation():
    seg = Segmenter(conversation_gap_seconds=60.0)
    assert seg.check_boundary(120.0) is None


def test_starts_conversation_returns_id():
    seg = Segmenter()
    cid = seg.start_conversation("conv-abc")
    assert cid == "conv-abc"
    assert seg.current_conversation_id == "conv-abc"


def test_starts_conversation_generates_id_if_none():
    seg = Segmenter()
    cid = seg.start_conversation()
    assert cid is not None
    assert len(cid) > 0
    assert seg.current_conversation_id == cid


def test_no_boundary_below_threshold():
    seg = Segmenter(conversation_gap_seconds=60.0)
    seg.start_conversation("conv-1")
    result = seg.check_boundary(59.9)
    assert result is None


def test_boundary_at_threshold():
    seg = Segmenter(conversation_gap_seconds=60.0)
    seg.start_conversation("conv-1")
    result = seg.check_boundary(60.0)
    assert result is not None
    assert isinstance(result, ConversationBoundary)
    assert result.close_conversation_id == "conv-1"
    assert result.reason == "silence_gap"


def test_boundary_above_threshold():
    seg = Segmenter(conversation_gap_seconds=60.0)
    seg.start_conversation("conv-2")
    result = seg.check_boundary(120.0)
    assert result is not None
    assert result.close_conversation_id == "conv-2"


def test_close_conversation_returns_id():
    seg = Segmenter()
    seg.start_conversation("conv-x")
    cid = seg.close_conversation()
    assert cid == "conv-x"
    assert seg.current_conversation_id is None


def test_close_conversation_no_op_when_none():
    seg = Segmenter()
    result = seg.close_conversation()
    assert result is None


def test_custom_gap_threshold():
    seg = Segmenter(conversation_gap_seconds=30.0)
    seg.start_conversation("conv-3")
    # 29s — no boundary
    assert seg.check_boundary(29.0) is None
    # 30s — boundary
    result = seg.check_boundary(30.0)
    assert result is not None
    assert result.reason == "silence_gap"
