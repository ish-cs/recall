"""SQLite writer for the Python ml-worker side."""

import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Optional


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def now_ms(self) -> int:
        return int(time.time() * 1000)

    def insert_conversation(
        self,
        conversation_id: str,
        started_at: int,
        audio_path: Optional[str] = None,
    ) -> str:
        now = self.now_ms()
        with self.connection() as conn:
            conn.execute(
                """INSERT INTO conversations
                   (id, started_at, ended_at, title, summary, topic_tags, audio_path, created_at, updated_at)
                   VALUES (?, ?, NULL, NULL, NULL, '[]', ?, ?, ?)""",
                (conversation_id, started_at, audio_path, now, now),
            )
        return conversation_id

    def close_conversation(self, conversation_id: str, ended_at: int) -> None:
        now = self.now_ms()
        with self.connection() as conn:
            conn.execute(
                "UPDATE conversations SET ended_at = ?, updated_at = ? WHERE id = ?",
                (ended_at, now, conversation_id),
            )

    def update_conversation_audio_path(self, conversation_id: str, audio_path: str) -> None:
        now = self.now_ms()
        with self.connection() as conn:
            conn.execute(
                "UPDATE conversations SET audio_path = ?, updated_at = ? WHERE id = ?",
                (audio_path, now, conversation_id),
            )

    def insert_segment(
        self,
        conversation_id: str,
        started_at: int,
        ended_at: int,
        raw_text: str,
        normalized_text: Optional[str] = None,
        confidence: Optional[float] = None,
        speaker_instance_id: Optional[str] = None,
    ) -> str:
        segment_id = str(uuid.uuid4())
        now = self.now_ms()
        with self.connection() as conn:
            conn.execute(
                """INSERT INTO transcript_segments
                   (id, conversation_id, speaker_instance_id, started_at, ended_at,
                    raw_text, normalized_text, confidence, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    segment_id,
                    conversation_id,
                    speaker_instance_id,
                    started_at,
                    ended_at,
                    raw_text,
                    normalized_text,
                    confidence,
                    now,
                ),
            )
        return segment_id

    def update_segment_speaker(
        self, segment_id: str, speaker_instance_id: str
    ) -> None:
        with self.connection() as conn:
            conn.execute(
                "UPDATE transcript_segments SET speaker_instance_id = ? WHERE id = ?",
                (speaker_instance_id, segment_id),
            )

    def insert_speaker_instance(
        self,
        conversation_id: str,
        diarization_label: str,
        speaker_profile_id: Optional[str] = None,
        confidence: Optional[float] = None,
    ) -> str:
        instance_id = str(uuid.uuid4())
        now = self.now_ms()
        with self.connection() as conn:
            conn.execute(
                """INSERT INTO speaker_instances
                   (id, conversation_id, diarization_label, speaker_profile_id,
                    confidence, segment_count, created_at)
                   VALUES (?, ?, ?, ?, ?, 0, ?)""",
                (instance_id, conversation_id, diarization_label, speaker_profile_id, confidence, now),
            )
        return instance_id

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT value FROM app_settings WHERE key = ?", (key,)
            ).fetchone()
            return row["value"] if row else default

    def update_conversation_summary(
        self, conversation_id: str, summary: str, tags: list[str]
    ) -> None:
        import json
        now = self.now_ms()
        with self.connection() as conn:
            conn.execute(
                "UPDATE conversations SET summary = ?, topic_tags = ?, updated_at = ? WHERE id = ?",
                (summary, json.dumps(tags), now, conversation_id),
            )
