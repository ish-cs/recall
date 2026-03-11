"""Async pipeline orchestrator: hot path + cold path workers."""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Optional

from pipeline.capture import AudioCapture, AudioChunk
from pipeline.vad import VAD, SpeechSegment
from pipeline.transcriber import Transcriber, TranscriptChunk
from pipeline.segmenter import Segmenter
from storage.db import Database
from storage.audio_store import AudioStore

logger = logging.getLogger(__name__)

COLD_QUEUE_MAX = 100
STATUS_HEARTBEAT_INTERVAL = 5.0  # seconds


@dataclass
class ColdTask:
    task_type: str  # "embed_segment" | "summarize_conversation" | "match_speaker"
    data: dict


class Pipeline:
    """
    Wires together the hot path:
    capture → VAD → transcriber → persist → SSE emit

    Cold path (async workers):
    → text embedding
    → speaker matching
    → summarization
    """

    def __init__(
        self,
        db: Database,
        audio_store: AudioStore,
        sse_emit: Callable[[str, dict], None],
        conversation_gap_seconds: float = 60.0,
        vad_threshold: float = 0.5,
        power_mode: str = "balanced",
        hf_token: Optional[str] = None,
    ):
        self.db = db
        self.audio_store = audio_store
        self.sse_emit = sse_emit
        self.power_mode = power_mode
        self._hf_token = hf_token

        # Components
        self.vad = VAD(threshold=vad_threshold)
        self.transcriber = Transcriber()
        self.segmenter = Segmenter(conversation_gap_seconds=conversation_gap_seconds)

        # Optional components (loaded separately)
        self.diarizer = None
        self.embedder = None
        self.text_embedder = None
        self.summarizer = None

        # Queues
        self.raw_audio_queue: asyncio.Queue[AudioChunk] = asyncio.Queue()
        self.speech_queue: asyncio.Queue[SpeechSegment] = asyncio.Queue()
        self.cold_queue: asyncio.Queue[ColdTask] = asyncio.Queue(maxsize=COLD_QUEUE_MAX)

        # Capture
        self.capture = AudioCapture(self.raw_audio_queue)

        # State
        self._recording = False
        self._paused = False
        self._tasks: list[asyncio.Task] = []
        self._models_ready = False

    async def load_models(self) -> None:
        """Load all ML models. Non-blocking — called at startup."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.vad.load)
        await loop.run_in_executor(None, self.transcriber.load)

        if self.power_mode != "low_power":
            # Load diarizer if HF token available
            if self._hf_token:
                try:
                    from pipeline.diarizer import Diarizer
                    self.diarizer = Diarizer(hf_token=self._hf_token)
                    await loop.run_in_executor(None, self.diarizer.load)
                except Exception as e:
                    logger.warning("Diarizer unavailable: %s", e)

            # Load cold-path models
            try:
                from pipeline.embedder import SpeakerEmbedder
                self.embedder = SpeakerEmbedder()
                await loop.run_in_executor(None, self.embedder.load)
            except Exception as e:
                logger.warning("Speaker embedder unavailable: %s", e)

            try:
                from pipeline.text_embedder import TextEmbedder
                self.text_embedder = TextEmbedder()
                await loop.run_in_executor(None, self.text_embedder.load)
            except Exception as e:
                logger.warning("Text embedder unavailable: %s", e)

            try:
                from pipeline.summarizer import Summarizer
                self.summarizer = Summarizer()
            except Exception as e:
                logger.warning("Summarizer unavailable: %s", e)

        self._models_ready = True
        logger.info("Models loaded (power_mode=%s)", self.power_mode)

    def start(self) -> None:
        """Start the pipeline (begin recording)."""
        if self._recording:
            logger.warning("Pipeline already recording")
            return

        # Start or resume conversation
        if self.segmenter.current_conversation_id is None:
            cid = self.segmenter.start_conversation()
            started_at = int(time.time() * 1000)
            audio_path = self.audio_store.open(cid, started_at)
            self.db.insert_conversation(cid, started_at, audio_path)
            self.capture.set_conversation_id(cid)
            self.sse_emit("conversation.started", {
                "type": "conversation.started",
                "conversation_id": cid,
                "started_at": started_at,
            })

        self._recording = True
        self._paused = False
        self.capture.start()
        self._start_workers()
        logger.info("Pipeline started")

    def pause(self) -> None:
        """Pause audio capture (keep conversation open)."""
        if not self._recording or self._paused:
            return
        self._paused = True
        self.capture.stop()
        logger.info("Pipeline paused")

    def resume(self) -> None:
        """Resume from pause."""
        if not self._paused:
            return
        self._paused = False
        self.capture.start()
        logger.info("Pipeline resumed")

    def stop(self) -> None:
        """Stop recording and close current conversation."""
        if not self._recording:
            return
        self._recording = False
        self._paused = False
        self.capture.stop()

        # Close conversation
        cid = self.segmenter.current_conversation_id
        if cid:
            ended_at = int(time.time() * 1000)
            self.db.close_conversation(cid, ended_at)
            self.audio_store.close()
            self.segmenter.close_conversation()
            self.sse_emit("conversation.ended", {
                "type": "conversation.ended",
                "conversation_id": cid,
                "ended_at": ended_at,
            })

        for task in self._tasks:
            task.cancel()
        self._tasks.clear()
        logger.info("Pipeline stopped")

    def _start_workers(self) -> None:
        """Start all async worker tasks."""
        self._tasks = [
            asyncio.create_task(self._vad_worker(), name="vad_worker"),
            asyncio.create_task(self._transcribe_worker(), name="transcribe_worker"),
            asyncio.create_task(self._heartbeat_worker(), name="heartbeat_worker"),
        ]
        if self.power_mode != "low_power":
            self._tasks.append(
                asyncio.create_task(self._cold_worker(), name="cold_worker")
            )

    async def _vad_worker(self) -> None:
        """Read raw audio, run VAD, emit speech segments."""
        while True:
            try:
                chunk: AudioChunk = await asyncio.wait_for(
                    self.raw_audio_queue.get(), timeout=1.0
                )
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            if self._paused:
                continue

            # Write to WAV
            if self.audio_store.is_open:
                self.audio_store.write(chunk.data)

            # Feed diarizer buffer
            if self.diarizer and self.diarizer.is_loaded:
                self.diarizer.add_chunk(chunk.data, chunk.captured_at_ms)
                if self.diarizer.should_run():
                    try:
                        await self.cold_queue.put_nowait(ColdTask(
                            task_type="diarize_window",
                            data={"conversation_id": chunk.conversation_id},
                        ))
                    except asyncio.QueueFull:
                        logger.debug("Cold queue full; skipping diarization window")

            # Run VAD
            speech_seg = self.vad.process_chunk(
                chunk.data, chunk.captured_at_ms, chunk.conversation_id
            )

            if speech_seg:
                await self.speech_queue.put(speech_seg)

            # Check for conversation boundary
            boundary = self.segmenter.check_boundary(self.vad.silence_duration_seconds)
            if boundary:
                await self._handle_boundary(boundary)

    async def _handle_boundary(self, boundary) -> None:
        """Close current conversation and start a new one."""
        old_cid = boundary.close_conversation_id
        ended_at = int(time.time() * 1000)

        if old_cid:
            self.db.close_conversation(old_cid, ended_at)
            self.audio_store.close()
            self.segmenter.close_conversation()
            self.sse_emit("conversation.ended", {
                "type": "conversation.ended",
                "conversation_id": old_cid,
                "ended_at": ended_at,
            })

            # Enqueue cold tasks
            if self.summarizer and self.power_mode != "low_power":
                try:
                    await self.cold_queue.put_nowait(ColdTask(
                        task_type="summarize_conversation",
                        data={"conversation_id": old_cid},
                    ))
                except asyncio.QueueFull:
                    logger.warning("Cold queue full; dropping summarization task")

        # Start new conversation
        new_cid = self.segmenter.start_conversation()
        started_at = int(time.time() * 1000)
        audio_path = self.audio_store.open(new_cid, started_at)
        self.db.insert_conversation(new_cid, started_at, audio_path)
        self.capture.set_conversation_id(new_cid)
        self.sse_emit("conversation.started", {
            "type": "conversation.started",
            "conversation_id": new_cid,
            "started_at": started_at,
        })

    async def _transcribe_worker(self) -> None:
        """Read speech segments, transcribe, persist, emit SSE."""
        while True:
            try:
                speech: SpeechSegment = await asyncio.wait_for(
                    self.speech_queue.get(), timeout=1.0
                )
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            conv_id = speech.conversation_id or self.segmenter.current_conversation_id
            if not conv_id:
                logger.warning("No active conversation for transcription")
                continue

            chunk: Optional[TranscriptChunk] = await self.transcriber.transcribe(
                speech.data, speech.start_ms, conv_id
            )

            if chunk and chunk.text.strip():
                segment_id = self.db.insert_segment(
                    conversation_id=conv_id,
                    started_at=chunk.start_ms,
                    ended_at=chunk.end_ms,
                    raw_text=chunk.text,
                    confidence=chunk.avg_log_prob,
                )

                self.sse_emit("transcript.segment", {
                    "type": "transcript.segment",
                    "segment_id": segment_id,
                    "conversation_id": conv_id,
                    "text": chunk.text,
                    "started_at": chunk.start_ms,
                    "ended_at": chunk.end_ms,
                })

                # Enqueue for text embedding
                if self.text_embedder and self.text_embedder.is_loaded:
                    try:
                        await self.cold_queue.put_nowait(ColdTask(
                            task_type="embed_segment",
                            data={"segment_id": segment_id, "text": chunk.text},
                        ))
                    except asyncio.QueueFull:
                        logger.debug("Cold queue full; dropping embed task")

                # Enqueue speaker matching
                if self.embedder and self.embedder.is_loaded:
                    try:
                        await self.cold_queue.put_nowait(ColdTask(
                            task_type="match_speaker",
                            data={
                                "segment_id": segment_id,
                                "conversation_id": conv_id,
                                "audio_data": speech.data.tobytes(),
                                "started_at": chunk.start_ms,
                                "ended_at": chunk.end_ms,
                            },
                        ))
                    except asyncio.QueueFull:
                        logger.debug("Cold queue full; dropping speaker match task")

    async def _cold_worker(self) -> None:
        """Process cold-path tasks (embeddings, summarization)."""
        while True:
            try:
                task: ColdTask = await asyncio.wait_for(
                    self.cold_queue.get(), timeout=2.0
                )
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            try:
                if task.task_type == "embed_segment":
                    await self._embed_segment(task.data)
                elif task.task_type == "summarize_conversation":
                    await self._summarize_conversation(task.data)
                elif task.task_type == "diarize_window":
                    await self._diarize_window(task.data)
                elif task.task_type == "match_speaker":
                    await self._match_speaker(task.data)
            except Exception as e:
                logger.error("Cold task error (%s): %s", task.task_type, e)

    async def _embed_segment(self, data: dict) -> None:
        """Generate and store text embedding for a segment."""
        if not self.text_embedder or not self.text_embedder.is_loaded:
            return
        segment_id = data["segment_id"]
        text = data["text"]
        embedding = await asyncio.get_event_loop().run_in_executor(
            None, self.text_embedder.embed, text
        )
        if embedding is None:
            return
        # Store in sqlite-vec (via direct DB write)
        import sqlite3
        try:
            conn = sqlite3.connect(self.db.db_path, timeout=10)
            conn.execute("PRAGMA journal_mode = WAL")
            blob = embedding.tobytes()
            conn.execute(
                "INSERT OR REPLACE INTO segment_embeddings (segment_id, embedding) VALUES (?, ?)",
                (segment_id, blob),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning("Failed to store text embedding: %s", e)

    async def _summarize_conversation(self, data: dict) -> None:
        """Summarize a completed conversation."""
        if not self.summarizer:
            return
        conv_id = data["conversation_id"]
        # Fetch all segments text
        try:
            import sqlite3
            conn = sqlite3.connect(self.db.db_path, timeout=10)
            rows = conn.execute(
                "SELECT raw_text FROM transcript_segments WHERE conversation_id = ? ORDER BY started_at",
                (conv_id,),
            ).fetchall()
            conn.close()
            transcript_text = " ".join(row[0] for row in rows if row[0])
        except Exception as e:
            logger.warning("Failed to fetch transcript for summarization: %s", e)
            return

        if not transcript_text.strip():
            return

        summary, tags = await self.summarizer.summarize(transcript_text)

        if summary:
            self.db.update_conversation_summary(conv_id, summary, tags)
            self.sse_emit("enrichment.complete", {
                "type": "enrichment.complete",
                "conversation_id": conv_id,
                "summary": summary,
                "tags": tags,
            })

    async def _diarize_window(self, data: dict) -> None:
        """Run diarizer on buffered window, update segment speaker labels."""
        if not self.diarizer or not self.diarizer.is_loaded:
            return
        conv_id = data.get("conversation_id")

        segments = await asyncio.get_event_loop().run_in_executor(
            None, self.diarizer.run_window
        )
        if not segments:
            return

        import sqlite3, uuid, time
        try:
            conn = sqlite3.connect(self.db.db_path, timeout=10)
            conn.execute("PRAGMA journal_mode = WAL")
            now = int(time.time() * 1000)

            for seg in segments:
                # Find or create speaker_instance for this label in this conversation
                row = conn.execute(
                    "SELECT id FROM speaker_instances WHERE conversation_id = ? AND diarization_label = ?",
                    (conv_id, seg.speaker_label),
                ).fetchone()

                if row:
                    instance_id = row[0]
                else:
                    instance_id = str(uuid.uuid4())
                    conn.execute(
                        "INSERT INTO speaker_instances (id, conversation_id, diarization_label, created_at) VALUES (?, ?, ?, ?)",
                        (instance_id, conv_id, seg.speaker_label, now),
                    )

                # Update transcript_segments whose time range overlaps this diarization segment
                conn.execute(
                    """UPDATE transcript_segments
                       SET speaker_instance_id = ?
                       WHERE conversation_id = ?
                         AND speaker_instance_id IS NULL
                         AND started_at >= ? AND ended_at <= ?""",
                    (instance_id, conv_id, seg.start_ms_absolute, seg.end_ms_absolute),
                )

                self.sse_emit("transcript.speaker_update", {
                    "type": "transcript.speaker_update",
                    "conversation_id": conv_id,
                    "speaker_instance_id": instance_id,
                    "diarization_label": seg.speaker_label,
                    "start_ms": seg.start_ms_absolute,
                    "end_ms": seg.end_ms_absolute,
                })

            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning("Diarization DB update failed: %s", e)

    async def _match_speaker(self, data: dict) -> None:
        """Match a speech segment against known speaker profiles."""
        if not self.embedder or not self.embedder.is_loaded:
            return

        segment_id = data["segment_id"]
        conv_id = data["conversation_id"]
        audio = np.frombuffer(data["audio_data"], dtype=np.float32)

        embedding = await asyncio.get_event_loop().run_in_executor(
            None, self.embedder.embed, audio
        )
        if embedding is None:
            return

        # Load all speaker profile exemplars from DB
        import sqlite3, uuid, time, json
        try:
            conn = sqlite3.connect(self.db.db_path, timeout=10)
            profiles = conn.execute(
                "SELECT id, display_name FROM speaker_profiles"
            ).fetchall()

            best_profile_id = None
            best_score = 0.0
            best_display_name = None

            for profile_id, display_name in profiles:
                exemplars_rows = conn.execute(
                    "SELECT embedding FROM speaker_embeddings WHERE speaker_profile_id = ? LIMIT 20",
                    (profile_id,),
                ).fetchall()
                exemplars = [np.frombuffer(r[0], dtype=np.float32) for r in exemplars_rows]
                if not exemplars:
                    continue
                score = self.embedder.match_profile(embedding, exemplars)
                if score > best_score:
                    best_score = score
                    best_profile_id = profile_id
                    best_display_name = display_name

            classification = self.embedder.classify_match(best_score)
            now = int(time.time() * 1000)

            if classification == "auto" and best_profile_id:
                # Auto-link: update speaker_instance in DB
                conn.execute(
                    "UPDATE speaker_instances SET speaker_profile_id = ? WHERE id = (SELECT speaker_instance_id FROM transcript_segments WHERE id = ?)",
                    (best_profile_id, segment_id),
                )
                # Store this embedding as a new exemplar (cap at 20)
                count = conn.execute(
                    "SELECT COUNT(*) FROM speaker_embeddings WHERE speaker_profile_id = ?",
                    (best_profile_id,),
                ).fetchone()[0]
                if count < 20:
                    emb_id = str(uuid.uuid4())
                    conn.execute(
                        "INSERT INTO speaker_embeddings (id, speaker_profile_id, embedding, created_at) VALUES (?, ?, ?, ?)",
                        (emb_id, best_profile_id, embedding.tobytes(), now),
                    )
                conn.execute(
                    "UPDATE speaker_profiles SET updated_at = ? WHERE id = ?",
                    (now, best_profile_id),
                )
                self.sse_emit("speaker.identified", {
                    "type": "speaker.identified",
                    "segment_id": segment_id,
                    "speaker_profile_id": best_profile_id,
                    "display_name": best_display_name,
                    "confidence": best_score,
                })

            elif classification == "suggest" and best_profile_id:
                # Emit suggestion to frontend
                self.sse_emit("speaker.match_suggestion", {
                    "type": "speaker.match_suggestion",
                    "segment_id": segment_id,
                    "conversation_id": conv_id,
                    "speaker_profile_id": best_profile_id,
                    "display_name": best_display_name,
                    "confidence": best_score,
                })

            else:
                # New speaker — create profile
                profile_id = str(uuid.uuid4())
                conn.execute(
                    "INSERT INTO speaker_profiles (id, display_name, is_user, created_at, updated_at) VALUES (?, NULL, 0, ?, ?)",
                    (profile_id, now, now),
                )
                emb_id = str(uuid.uuid4())
                conn.execute(
                    "INSERT INTO speaker_embeddings (id, speaker_profile_id, embedding, created_at) VALUES (?, ?, ?, ?)",
                    (emb_id, profile_id, embedding.tobytes(), now),
                )
                self.sse_emit("speaker.new_profile", {
                    "type": "speaker.new_profile",
                    "speaker_profile_id": profile_id,
                    "segment_id": segment_id,
                })

            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning("Speaker matching failed: %s", e)

    async def _heartbeat_worker(self) -> None:
        """Emit pipeline status heartbeat every 5 seconds."""
        while True:
            await asyncio.sleep(STATUS_HEARTBEAT_INTERVAL)
            self.sse_emit("pipeline.status", {
                "type": "pipeline.status",
                "recording": self._recording,
                "paused": self._paused,
                "hot_queue_depth": self.speech_queue.qsize(),
                "cold_queue_depth": self.cold_queue.qsize(),
            })

    @property
    def status(self) -> dict:
        return {
            "recording": self._recording,
            "paused": self._paused,
            "current_conversation_id": self.segmenter.current_conversation_id,
            "hot_queue_depth": self.speech_queue.qsize(),
            "cold_queue_depth": self.cold_queue.qsize(),
            "models_ready": self._models_ready,
        }
