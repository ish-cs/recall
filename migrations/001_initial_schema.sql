PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE conversations (
  id          TEXT PRIMARY KEY,
  started_at  INTEGER NOT NULL,
  ended_at    INTEGER,
  title       TEXT,
  summary     TEXT,
  topic_tags  TEXT DEFAULT '[]',
  audio_path  TEXT,
  created_at  INTEGER NOT NULL,
  updated_at  INTEGER NOT NULL
);

CREATE INDEX idx_conversations_started_at ON conversations(started_at DESC);

CREATE TABLE speaker_profiles (
  id               TEXT PRIMARY KEY,
  display_name     TEXT,
  is_user          INTEGER NOT NULL DEFAULT 0,
  embedding        BLOB,
  embedding_count  INTEGER NOT NULL DEFAULT 0,
  notes            TEXT,
  created_at       INTEGER NOT NULL,
  updated_at       INTEGER NOT NULL
);

CREATE TABLE speaker_embeddings (
  id                TEXT PRIMARY KEY,
  speaker_profile_id TEXT NOT NULL REFERENCES speaker_profiles(id) ON DELETE CASCADE,
  embedding         BLOB NOT NULL,
  segment_id        TEXT,
  created_at        INTEGER NOT NULL
);

CREATE INDEX idx_speaker_embeddings_profile ON speaker_embeddings(speaker_profile_id);

CREATE TABLE speaker_instances (
  id                    TEXT PRIMARY KEY,
  conversation_id       TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  diarization_label     TEXT NOT NULL,
  speaker_profile_id    TEXT REFERENCES speaker_profiles(id),
  confidence            REAL,
  segment_count         INTEGER NOT NULL DEFAULT 0,
  created_at            INTEGER NOT NULL
);

CREATE INDEX idx_speaker_instances_conversation ON speaker_instances(conversation_id);
CREATE INDEX idx_speaker_instances_profile ON speaker_instances(speaker_profile_id);

CREATE TABLE transcript_segments (
  id                  TEXT PRIMARY KEY,
  conversation_id     TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  speaker_instance_id TEXT REFERENCES speaker_instances(id),
  started_at          INTEGER NOT NULL,
  ended_at            INTEGER NOT NULL,
  raw_text            TEXT NOT NULL,
  normalized_text     TEXT,
  confidence          REAL,
  created_at          INTEGER NOT NULL
);

CREATE INDEX idx_segments_conversation ON transcript_segments(conversation_id);
CREATE INDEX idx_segments_speaker_instance ON transcript_segments(speaker_instance_id);
CREATE INDEX idx_segments_started_at ON transcript_segments(started_at DESC);

CREATE TABLE topic_tags (
  id    TEXT PRIMARY KEY,
  label TEXT NOT NULL UNIQUE
);

CREATE TABLE conversation_topic_links (
  conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  topic_tag_id    TEXT NOT NULL REFERENCES topic_tags(id) ON DELETE CASCADE,
  PRIMARY KEY (conversation_id, topic_tag_id)
);

CREATE TABLE app_settings (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

INSERT INTO app_settings VALUES ('recording_enabled', 'false');
INSERT INTO app_settings VALUES ('model_size', 'distil-large-v3');
INSERT INTO app_settings VALUES ('power_mode', 'balanced');
INSERT INTO app_settings VALUES ('vad_threshold', '0.5');
INSERT INTO app_settings VALUES ('conversation_gap_seconds', '60');
INSERT INTO app_settings VALUES ('onboarding_complete', 'false');
INSERT INTO app_settings VALUES ('hf_token_stored', 'false');
