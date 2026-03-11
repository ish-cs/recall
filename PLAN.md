# Recall — Implementation Plan

## Resolved Design Decisions

Before the plan, the following open questions from the brief are resolved:

| Question | Decision |
|---|---|
| Audio scope | Microphone only in v1; architecture must allow system audio (loopback) as a future addition without structural changes |
| App presence | Full Dock app + menu bar item |
| Audio storage | Store both raw audio (WAV per conversation) and transcripts/embeddings |
| Retention | Infinite by default; user-initiated selective deletion by age (14d/30d/90d/all) × scope (audio/transcripts/both) |
| Speaker enrollment | Passive learning only in v1; onboarding enrollment left as a future addition |
| Hardware target | Apple Silicon only (M1+); no Intel Mac support, enables Metal/MPS acceleration throughout |
| Transcription latency | Target under 10 seconds end-to-end; quality over speed |
| Search scope | Semantic search is in-scope for the complete build (Phase 5) |

---

## 1. System Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│  macOS App (Tauri 2.x)                                           │
│                                                                  │
│  ┌─────────────────────┐   ┌──────────────────────────────────┐  │
│  │  React + TypeScript │   │  Rust (Tauri Core)               │  │
│  │  UI / Frontend      │◄──│  - Command handlers              │  │
│  │                     │──►│  - DB queries (rusqlite)         │  │
│  │  Views:             │   │  - Worker process management     │  │
│  │  - Timeline         │   │  - SSE → Tauri event bridge      │  │
│  │  - Search           │   │  - Audio file management         │  │
│  │  - Speakers         │   │  - Menu bar integration          │  │
│  │  - Settings         │   │  - macOS permissions             │  │
│  └─────────────────────┘   └──────────────┬───────────────────┘  │
└─────────────────────────────────────────────────────────────────-┘
                                             │ HTTP + SSE
                                             │ (localhost, random port)
                              ┌──────────────▼───────────────────┐
                              │  Python ML Worker (sidecar)      │
                              │                                  │
                              │  FastAPI server                  │
                              │                                  │
                              │  HOT PATH:                       │
                              │  Audio Capture (sounddevice)     │
                              │  → VAD (Silero)                  │
                              │  → Transcription (faster-whisper)│
                              │  → Persist segment               │
                              │  → Emit SSE event                │
                              │                                  │
                              │  COLD PATH (async workers):      │
                              │  → Diarization (pyannote)        │
                              │  → Speaker matching (Resemblyzer)│
                              │  → Text embedding (nomic-embed)  │
                              │  → Summarize/tag (Ollama)        │
                              └──────────────┬───────────────────┘
                                             │
                              ┌──────────────▼───────────────────┐
                              │  SQLite (WAL mode)               │
                              │  - recall.db                     │
                              │  - FTS5 (keyword search)         │
                              │  - sqlite-vec (semantic search)  │
                              │                                  │
                              │  ~/Library/Application Support   │
                              │  /Recall/                        │
                              │  ├── recall.db                   │
                              │  ├── audio/YYYY/MM/DD/*.wav      │
                              │  ├── models/                     │
                              │  └── logs/                       │
                              └──────────────────────────────────┘
```

The Tauri Rust core spawns the Python ML worker as a sidecar process at startup. The Python worker starts a FastAPI server on a random localhost port and communicates that port back to Rust via stdout. Rust forwards commands from the frontend to the worker and subscribes to the SSE event stream, relaying events to the React frontend via Tauri's built-in event system.

Both Rust and Python read/write the same SQLite database. WAL mode allows concurrent access safely. Python is the primary writer for transcript and audio data; Rust writes app settings and handles search queries.

---

## 2. Stack Decisions

| Layer | Technology | Rationale |
|---|---|---|
| Desktop shell | Tauri 2.x | Lighter than Electron; native macOS integration; Rust backend |
| UI framework | React 18 + TypeScript | Fast development; strong ecosystem |
| UI build | Vite | Fast HMR; Tauri's preferred bundler |
| Styling | Tailwind CSS | Utility-first; consistent with minimal custom CSS |
| State management | Zustand | Minimal boilerplate; works well with Tauri events |
| Rust HTTP client | reqwest | Async HTTP to Python worker |
| Rust DB | rusqlite + sqlite-vec | Direct SQLite access with vector extension |
| Python server | FastAPI + uvicorn | Async; SSE support; typed API |
| Audio capture | sounddevice (PortAudio → CoreAudio) | Simple Python API; CoreAudio quality underneath |
| VAD | Silero VAD v5 | Best open-source VAD; ONNX runtime, fast |
| Transcription | faster-whisper (distil-large-v3) | CTranslate2 with Metal backend; quality + speed balance |
| Diarization | pyannote.audio 3.1 | Best open-source diarization baseline |
| Speaker embeddings | Resemblyzer | 256-d embeddings; cosine similarity matching |
| Text embeddings | nomic-embed-text via sentence-transformers | 768-d; strong retrieval quality; runs locally |
| Semantic index | sqlite-vec | SQLite extension; no separate service needed |
| Summarization | Ollama (qwen2.5:7b or phi3.5:3.8b) | Cold path only; local inference; optional |
| DB migrations | SQL files + Rust runner | Forward-only; versioned |
| Testing (Rust) | cargo test + criterion | Unit + benchmarks |
| Testing (Python) | pytest + pytest-asyncio | Unit + integration |
| Testing (UI) | Vitest + Testing Library | Component tests |
| Testing (E2E) | Playwright (Tauri WebDriver) | Full workflow tests |

**Apple Silicon optimizations enabled throughout:**
- faster-whisper: CTranslate2 Metal backend (`device="mps"`)
- pyannote: PyTorch MPS backend
- sentence-transformers: MPS backend
- Ollama: Metal GPU inference (built-in)
- Resemblyzer: CPU (fast enough at 256-d; MPS not needed)

---

## 3. Repository Structure

```
recall/
├── .github/
│   └── workflows/
│       ├── ci.yml                    # test on push
│       └── build.yml                 # notarized build on tag
│
├── src-tauri/                        # Rust / Tauri backend
│   ├── src/
│   │   ├── main.rs                   # entry point
│   │   ├── lib.rs                    # Tauri builder + plugin registration
│   │   ├── commands/
│   │   │   ├── mod.rs
│   │   │   ├── recording.rs          # start/stop/pause/resume/status
│   │   │   ├── conversations.rs      # list/get/delete/split
│   │   │   ├── search.rs             # keyword + semantic + hybrid
│   │   │   ├── speakers.rs           # profiles CRUD
│   │   │   └── settings.rs           # app_settings read/write
│   │   ├── db/
│   │   │   ├── mod.rs
│   │   │   ├── connection.rs         # r2d2 connection pool, WAL setup
│   │   │   ├── migrations.rs         # reads migrations/ dir, runs pending
│   │   │   └── models.rs             # Rust structs (Conversation, Segment, etc.)
│   │   ├── worker/
│   │   │   ├── mod.rs
│   │   │   ├── process.rs            # spawn Python sidecar, read port from stdout
│   │   │   ├── client.rs             # reqwest HTTP client for worker API
│   │   │   └── events.rs             # SSE listener → emit Tauri events
│   │   ├── audio/
│   │   │   ├── mod.rs
│   │   │   └── storage.rs            # compute audio file paths, delete by age
│   │   └── config.rs                 # app support dir, model dir, log dir paths
│   ├── capabilities/
│   │   └── default.json              # Tauri 2 capability config
│   ├── icons/                        # app icons (generated)
│   ├── Cargo.toml
│   └── tauri.conf.json
│
├── src/                              # React frontend
│   ├── main.tsx
│   ├── App.tsx
│   ├── routes.tsx                    # TanStack Router routes
│   ├── components/
│   │   ├── layout/
│   │   │   ├── AppShell.tsx          # sidebar + main content layout
│   │   │   ├── Sidebar.tsx           # nav links + recording indicator
│   │   │   └── RecordingStatusBar.tsx # always-visible status strip
│   │   ├── timeline/
│   │   │   ├── TimelineView.tsx      # paginated conversation list
│   │   │   ├── ConversationCard.tsx  # card: time, speakers, summary, tags
│   │   │   └── ConversationDetail.tsx # full transcript + speaker controls
│   │   ├── transcript/
│   │   │   ├── TranscriptView.tsx    # scrollable transcript container
│   │   │   ├── SpeakerTurn.tsx       # one speaker turn (colored label + text)
│   │   │   └── TimestampLabel.tsx    # formatted HH:MM:SS link
│   │   ├── search/
│   │   │   ├── SearchView.tsx        # search layout
│   │   │   ├── SearchBar.tsx         # input + mode toggle (keyword/semantic/hybrid)
│   │   │   ├── SearchFilters.tsx     # date range, speaker, topic dropdowns
│   │   │   └── SearchResultItem.tsx  # snippet + context + jump link
│   │   ├── speakers/
│   │   │   ├── SpeakersView.tsx      # grid of speaker profile cards
│   │   │   ├── SpeakerCard.tsx       # name, segment count, last seen, merge btn
│   │   │   └── RenameDialog.tsx      # modal to set display name
│   │   ├── settings/
│   │   │   ├── SettingsView.tsx      # tab layout
│   │   │   ├── ModelPanel.tsx        # model status, download progress
│   │   │   ├── StoragePanel.tsx      # usage display + selective delete UI
│   │   │   ├── PerformancePanel.tsx  # power mode, model size selection
│   │   │   └── PrivacyPanel.tsx      # consent info, data export, delete all
│   │   └── onboarding/
│   │       ├── OnboardingFlow.tsx    # multi-step wizard
│   │       ├── ConsentStep.tsx       # privacy disclosure + checkbox
│   │       └── ModelDownloadStep.tsx # download progress
│   ├── hooks/
│   │   ├── useRecordingStatus.ts     # subscribe to pipeline.status events
│   │   ├── useConversations.ts       # load + update conversation list
│   │   ├── useSearch.ts              # debounced search invoker
│   │   ├── useTauriEvents.ts         # generic Tauri event listener
│   │   └── useStorageUsage.ts        # storage stats poller
│   ├── store/
│   │   ├── index.ts                  # Zustand store root
│   │   ├── recording.slice.ts
│   │   ├── conversations.slice.ts
│   │   └── search.slice.ts
│   ├── api/
│   │   ├── tauri.ts                  # typed invoke() wrappers for all commands
│   │   └── types.ts                  # shared TypeScript types
│   └── styles/
│       └── globals.css
│
├── ml-worker/                        # Python ML service
│   ├── main.py                       # startup: init models, start FastAPI
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── capture.py                # sounddevice stream, chunked callback
│   │   ├── vad.py                    # Silero VAD ONNX wrapper
│   │   ├── transcriber.py            # faster-whisper wrapper
│   │   ├── diarizer.py               # pyannote.audio pipeline wrapper
│   │   ├── embedder.py               # Resemblyzer speaker embedding
│   │   ├── text_embedder.py          # nomic-embed-text / sentence-transformers
│   │   ├── segmenter.py              # conversation boundary detection
│   │   ├── summarizer.py             # Ollama HTTP calls
│   │   └── orchestrator.py           # async pipeline coordination
│   ├── models/
│   │   ├── __init__.py
│   │   └── manager.py                # download, verify checksums, cache
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── db.py                     # SQLite writes from Python side
│   │   └── audio_store.py            # WAV file write per conversation
│   ├── ipc/
│   │   ├── __init__.py
│   │   └── server.py                 # FastAPI routes + SSE endpoint
│   └── tests/
│       ├── conftest.py
│       ├── fixtures/                 # sample audio WAV files
│       ├── test_vad.py
│       ├── test_transcriber.py
│       ├── test_diarizer.py
│       ├── test_embedder.py
│       └── test_segmenter.py
│
├── migrations/
│   ├── 001_initial_schema.sql
│   ├── 002_fts5.sql
│   └── 003_vector_search.sql
│
├── tests/
│   ├── integration/
│   │   └── pipeline_test.rs          # Rust integration tests
│   └── e2e/
│       └── search_flow.spec.ts       # Playwright E2E
│
├── scripts/
│   ├── setup.sh                      # one-time dev environment setup
│   ├── download-models.py            # model download with progress
│   └── dev.sh                        # start all services for development
│
├── package.json
├── pnpm-lock.yaml
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.ts
├── BRIEF.md
├── PLAN.md
└── CLAUDE.md
```

---

## 4. Database Schema

SQLite with WAL mode, FTS5, and sqlite-vec extension.

### 4.1 Migration 001 — Core Schema

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE schema_versions (
  version INTEGER PRIMARY KEY,
  applied_at INTEGER NOT NULL
);

CREATE TABLE conversations (
  id          TEXT PRIMARY KEY,           -- UUIDv4
  started_at  INTEGER NOT NULL,           -- Unix ms
  ended_at    INTEGER,                    -- NULL while in progress
  title       TEXT,                       -- user-set or generated
  summary     TEXT,                       -- LLM summary
  topic_tags  TEXT DEFAULT '[]',          -- JSON array of strings
  audio_path  TEXT,                       -- abs path to WAV file
  created_at  INTEGER NOT NULL,
  updated_at  INTEGER NOT NULL
);

CREATE INDEX idx_conversations_started_at ON conversations(started_at DESC);

CREATE TABLE speaker_profiles (
  id               TEXT PRIMARY KEY,
  display_name     TEXT,
  is_user          INTEGER NOT NULL DEFAULT 0,  -- boolean
  embedding        BLOB,                         -- averaged 256-d float32 array
  embedding_count  INTEGER NOT NULL DEFAULT 0,
  notes            TEXT,
  created_at       INTEGER NOT NULL,
  updated_at       INTEGER NOT NULL
);

CREATE TABLE speaker_embeddings (
  id                TEXT PRIMARY KEY,
  speaker_profile_id TEXT NOT NULL REFERENCES speaker_profiles(id) ON DELETE CASCADE,
  embedding         BLOB NOT NULL,   -- 256-d float32 exemplar
  segment_id        TEXT,            -- source segment (nullable, set later)
  created_at        INTEGER NOT NULL
);

CREATE INDEX idx_speaker_embeddings_profile ON speaker_embeddings(speaker_profile_id);

CREATE TABLE speaker_instances (
  id                    TEXT PRIMARY KEY,
  conversation_id       TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  diarization_label     TEXT NOT NULL,    -- SPEAKER_00, SPEAKER_01, ...
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
  started_at          INTEGER NOT NULL,   -- Unix ms, absolute
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

-- Default settings
INSERT INTO app_settings VALUES ('recording_enabled', 'false');
INSERT INTO app_settings VALUES ('model_size', 'distil-large-v3');
INSERT INTO app_settings VALUES ('power_mode', 'balanced');   -- balanced | performance | low_power
INSERT INTO app_settings VALUES ('vad_threshold', '0.5');
INSERT INTO app_settings VALUES ('conversation_gap_seconds', '60');
INSERT INTO app_settings VALUES ('onboarding_complete', 'false');
INSERT INTO app_settings VALUES ('hf_token_stored', 'false');  -- actual token in Keychain
```

### 4.2 Migration 002 — FTS5 Keyword Search

```sql
CREATE VIRTUAL TABLE transcript_fts USING fts5(
  text,
  segment_id UNINDEXED,
  conversation_id UNINDEXED,
  content='transcript_segments',
  content_rowid='rowid',
  tokenize='porter unicode61'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER trig_fts_insert AFTER INSERT ON transcript_segments BEGIN
  INSERT INTO transcript_fts(rowid, text, segment_id, conversation_id)
  VALUES (new.rowid, new.raw_text, new.id, new.conversation_id);
END;

CREATE TRIGGER trig_fts_delete AFTER DELETE ON transcript_segments BEGIN
  INSERT INTO transcript_fts(transcript_fts, rowid, text, segment_id, conversation_id)
  VALUES ('delete', old.rowid, old.raw_text, old.id, old.conversation_id);
END;

CREATE TRIGGER trig_fts_update AFTER UPDATE ON transcript_segments BEGIN
  INSERT INTO transcript_fts(transcript_fts, rowid, text, segment_id, conversation_id)
  VALUES ('delete', old.rowid, old.raw_text, old.id, old.conversation_id);
  INSERT INTO transcript_fts(rowid, text, segment_id, conversation_id)
  VALUES (new.rowid, new.raw_text, new.id, new.conversation_id);
END;
```

### 4.3 Migration 003 — Vector Search

```sql
-- Requires sqlite-vec extension loaded at connection time
CREATE VIRTUAL TABLE segment_embeddings USING vec0(
  segment_id TEXT PRIMARY KEY,
  embedding   FLOAT[768]
);
```

### Schema Notes

- All IDs are UUIDv4 strings (generated in application layer)
- All timestamps are Unix milliseconds stored as INTEGER
- Embeddings are stored as BLOB (serialized float32 numpy arrays, little-endian)
- `topic_tags` on conversations is a JSON array string for read performance; canonical tags live in `topic_tags` table
- The `speaker_profiles.embedding` column holds an averaged embedding for fast first-pass matching; `speaker_embeddings` holds up to 20 exemplars for refined matching
- Audio is stored outside SQLite as WAV files; `conversations.audio_path` is the absolute path

---

## 5. Audio Processing Pipeline

### 5.1 Audio Capture (`ml-worker/pipeline/capture.py`)

```
sounddevice.InputStream
  sample_rate: 16000 Hz
  channels: 1 (mono)
  dtype: float32
  blocksize: 48000  (3-second chunks)
  callback: on_audio_chunk(indata, frames, time, status)
```

- `on_audio_chunk` is called every 3 seconds with a numpy array
- Chunk is put onto an asyncio queue (`raw_audio_queue`)
- Audio is simultaneously written to the current conversation's WAV file via `soundfile`
- WAV file is opened when a new conversation starts; closed when conversation ends

**Microphone input scope note:** The capture module uses `sounddevice.default.device` which is the system default input. Future system audio support would require a separate loopback device (e.g., via BlackHole or Rogue Amoeba Loopback). The capture module must be designed with a `device_id` parameter so future versions can pass any input device without structural changes.

### 5.2 Voice Activity Detection (`ml-worker/pipeline/vad.py`)

```
Model: silero-vad v5 (ONNX format)
Input: 3-second audio chunk (float32, 16kHz)
Output: speech_probability float [0.0, 1.0]
Threshold: 0.5 (configurable via app_settings.vad_threshold)
```

VAD state machine:
```
SILENCE → (speech_prob > threshold) → SPEECH
SPEECH  → (speech_prob < threshold for > 2s) → SILENCE

On SILENCE → SPEECH transition: mark speech start, push to transcription queue
On SPEECH → SILENCE transition: mark speech end
Track cumulative silence duration for conversation boundary detection
```

The VAD module accumulates short speech segments to form longer windows for transcription. It does not emit every 3-second chunk to the transcription queue; instead it buffers until a natural pause and emits the accumulated speech segment (typically 5–30 seconds).

**Silence tracking for conversation segmentation:**
- VAD tracks total silence duration since last speech
- If silence > `conversation_gap_seconds` (default 60s): signal `segmenter.py` to close conversation
- If current time crosses midnight: always close conversation

### 5.3 Transcription (`ml-worker/pipeline/transcriber.py`)

```
Model: faster-whisper distil-large-v3
Device: mps (Apple Silicon Metal)
Compute type: float16
Beam size: 5
Word timestamps: True
Language: en (default; configurable)
```

Input: numpy float32 array (speech segment, variable length 2–30s)
Output:
```python
@dataclass
class TranscriptChunk:
    text: str
    words: list[WordTimestamp]  # (word, start_sec, end_sec, prob)
    start_sec: float
    end_sec: float
    language: str
    avg_log_prob: float
```

Times in `start_sec`/`end_sec` are relative to the start of the speech segment. The transcriber module converts these to absolute Unix milliseconds before returning, using the segment's wall-clock start time (captured from `time.time()` when audio was captured).

The transcriber runs in a dedicated thread (not asyncio) to avoid blocking the event loop during inference.

### 5.4 Diarization (`ml-worker/pipeline/diarizer.py`)

```
Model: pyannote/speaker-diarization-3.1
Device: mps
Requires: HuggingFace token (stored in macOS Keychain)
```

**Windowed diarization approach:**

Diarization runs on 30-second audio windows, not in real-time with each 3-second chunk. The diarizer maintains a rolling buffer:

```
diarization_buffer: deque of audio chunks
Target window: 30 seconds of audio
Overlap: 5 seconds (to handle speaker turns at window boundaries)
```

When a 30-second window is ready (or a conversation ends), diarization runs on that window and produces:
```python
@dataclass
class DiarizationSegment:
    speaker_label: str   # SPEAKER_00, SPEAKER_01, ...
    start_sec: float     # relative to window start
    end_sec: float
```

**Merging diarization with transcript:**

After diarization, the orchestrator merges diarization segments with transcript word timestamps:
1. For each transcript word, find the diarization segment whose time range contains it
2. Group consecutive words assigned to the same speaker into a `TranscriptSegment`
3. Update already-persisted segments with speaker_instance_id

This means segments are initially stored without speaker labels and updated asynchronously. The frontend handles the case where `speaker_instance_id` is null.

### 5.5 Speaker Embeddings (`ml-worker/pipeline/embedder.py`)

```
Model: Resemblyzer (GE2E model)
Output: 256-d float32 embedding
```

For each diarized speaker segment (minimum 2 seconds of speech):
1. Extract audio for that speaker from the recorded WAV
2. Generate embedding via `encoder.embed_utterance(wav)`
3. Compare against all stored speaker profiles:
   - Load up to 20 exemplar embeddings per profile
   - Compute cosine similarity against each exemplar
   - Take maximum similarity as the profile score
4. Matching thresholds:
   - score > 0.85: auto-link to profile (no user confirmation required)
   - score 0.70–0.85: suggest to user as "possible match"
   - score < 0.70: create new unknown speaker

**Profile update policy:**
- When a speaker is confirmed (auto or user-confirmed): add new embedding to `speaker_embeddings` table (keep max 20 exemplars; drop oldest if exceeded)
- Recompute `speaker_profiles.embedding` as the mean of all exemplars
- Do not update profile from auto-linked segments where score < 0.80 to prevent drift

### 5.6 Text Embeddings (`ml-worker/pipeline/text_embedder.py`)

```
Model: nomic-ai/nomic-embed-text-v1.5
Backend: sentence-transformers with MPS
Output: 768-d float32 embedding
```

Embedding is run on each transcript segment's `raw_text`, prefixed with `"search_document: "` (nomic-embed-text requires task prefix).

Embeddings are written to the `segment_embeddings` sqlite-vec table immediately after a segment is persisted. This runs on a cold-path worker with a bounded queue (max 50 pending embeddings).

### 5.7 Conversation Segmentation (`ml-worker/pipeline/segmenter.py`)

Conditions for closing the current conversation and opening a new one:
1. Silence gap exceeds `conversation_gap_seconds` (default 60s)
2. Clock crosses midnight (day boundary)
3. User manually triggers split via UI

When a conversation closes:
1. Set `conversations.ended_at`
2. Close and finalize WAV file
3. Enqueue conversation for summarization/tagging (cold path)

When a new conversation opens:
1. Insert new `conversations` row
2. Open new WAV file at `audio/YYYY/MM/DD/{conversation_id}.wav`
3. Emit `conversation.started` SSE event

### 5.8 Summarization (`ml-worker/pipeline/summarizer.py`)

Triggered when a conversation ends. Runs entirely on the cold path.

```
API: Ollama HTTP (localhost:11434)
Model: qwen2.5:7b (default); phi3.5:3.8b (low-power mode)
```

Prompt:
```
Given this conversation transcript, extract:
1. A one-sentence summary (max 25 words)
2. Up to 5 topic tags (single words or short phrases)

Transcript:
{transcript_text}

Respond in JSON: {"summary": "...", "tags": ["...", "..."]}
```

If Ollama is not running or times out (30s), the conversation is stored without summary/tags. The user can trigger re-summarization manually later. This dependency is optional; the app works fully without Ollama.

---

## 6. IPC Design

### 6.1 Python Worker API (FastAPI)

The Python worker starts on a random available port and prints `PORT={port}` to stdout. Rust reads this line and stores the port for all subsequent requests.

**Endpoints:**

```
POST /pipeline/start
     → Start audio capture and processing
     → Body: {}
     → Response: { "ok": true }

POST /pipeline/pause
     → Pause audio capture (VAD and transcription stop; file closed)
     → Response: { "ok": true }

POST /pipeline/resume
     → Resume from pause
     → Response: { "ok": true }

GET /pipeline/status
     → Response: {
         "recording": bool,
         "paused": bool,
         "current_conversation_id": str | null,
         "hot_queue_depth": int,
         "cold_queue_depth": int,
         "models_ready": bool
       }

GET /events
     → Server-Sent Events stream
     → Content-Type: text/event-stream
     → Events (see 6.2 below)

GET /models/status
     → Response: {
         "models": [
           { "name": str, "status": "ready"|"downloading"|"missing", "size_mb": int }
         ]
       }

POST /models/download
     → Trigger async model download
     → Progress reported via /events stream

POST /speakers/confirm
     → Link speaker instance to profile (or create new profile)
     → Body: { "speaker_instance_id": str, "speaker_profile_id": str | null, "display_name": str | null }
     → Response: { "speaker_profile_id": str }

POST /speakers/merge
     → Merge speaker_profile_from into speaker_profile_to
     → Body: { "from_profile_id": str, "to_profile_id": str }
     → Response: { "ok": true }
```

### 6.2 SSE Events

All events are JSON objects with a `type` field.

```
transcript.segment
  { type, segment_id, conversation_id, text, started_at, ended_at }
  Emitted immediately after a segment is persisted (before speaker labels)

transcript.speaker_update
  { type, segment_id, speaker_instance_id, speaker_profile_id, display_name }
  Emitted after diarization assigns speaker labels to existing segments

conversation.started
  { type, conversation_id, started_at }

conversation.ended
  { type, conversation_id, ended_at }

speaker.identified
  { type, speaker_instance_id, speaker_profile_id, confidence, display_name }
  Emitted when auto-match confidence > 0.85

speaker.match_suggestion
  { type, speaker_instance_id, speaker_profile_id, confidence, display_name }
  Emitted when confidence 0.70–0.85; requires user confirmation

enrichment.complete
  { type, conversation_id, summary, tags }

pipeline.status
  { type, recording, paused, hot_queue_depth, cold_queue_depth }
  Emitted every 5 seconds as a heartbeat

model.download_progress
  { type, model_name, progress_pct, bytes_downloaded, total_bytes }
```

### 6.3 Rust Worker Management

`src-tauri/src/worker/process.rs`:
- Spawn Python sidecar via `tauri::process::Command`
- Read stdout line by line until `PORT={n}` is found
- Store port; start SSE listener task
- Monitor process health: if process exits unexpectedly, restart with exponential backoff (1s, 2s, 4s, max 30s)
- On app quit: send SIGTERM to worker; wait 5s; SIGKILL if needed

`src-tauri/src/worker/events.rs`:
- Maintain persistent SSE connection to `GET /events`
- On each event: deserialize JSON, emit corresponding Tauri event to frontend
- If connection drops: reconnect after 2s
- Tauri event names mirror SSE event types: `transcript:segment`, `conversation:started`, etc.

---

## 7. Tauri Commands (Rust)

All commands are registered in `lib.rs` via `.invoke_handler(tauri::generate_handler![...])`.

### 7.1 Recording Commands

```rust
// src-tauri/src/commands/recording.rs

#[tauri::command]
async fn start_recording(state: State<'_, AppState>) -> Result<(), String>

#[tauri::command]
async fn stop_recording(state: State<'_, AppState>) -> Result<(), String>

#[tauri::command]
async fn pause_recording(state: State<'_, AppState>) -> Result<(), String>

#[tauri::command]
async fn resume_recording(state: State<'_, AppState>) -> Result<(), String>

#[tauri::command]
async fn get_recording_status(state: State<'_, AppState>) -> Result<RecordingStatus, String>
// RecordingStatus { recording: bool, paused: bool, current_conversation_id: Option<String> }
```

### 7.2 Conversation Commands

```rust
// src-tauri/src/commands/conversations.rs

#[tauri::command]
async fn list_conversations(
    db: State<'_, DbPool>,
    limit: i64,
    offset: i64,
    date_from: Option<i64>,  // Unix ms
    date_to: Option<i64>,
) -> Result<Vec<ConversationSummary>, String>

#[tauri::command]
async fn get_conversation(
    db: State<'_, DbPool>,
    id: String,
) -> Result<ConversationDetail, String>
// ConversationDetail includes Vec<TranscriptSegment> with speaker info joined

#[tauri::command]
async fn delete_conversation(
    db: State<'_, DbPool>,
    id: String,
    delete_audio: bool,
) -> Result<(), String>

#[tauri::command]
async fn split_conversation(
    db: State<'_, DbPool>,
    id: String,
    at_segment_id: String,
) -> Result<String, String>  // returns new conversation_id
```

### 7.3 Search Commands

```rust
// src-tauri/src/commands/search.rs

#[derive(Deserialize)]
struct SearchQuery {
    text: String,
    mode: SearchMode,  // Keyword | Semantic | Hybrid
    speaker_profile_id: Option<String>,
    date_from: Option<i64>,
    date_to: Option<i64>,
    topic_tag: Option<String>,
    limit: Option<i64>,
}

#[tauri::command]
async fn search(
    db: State<'_, DbPool>,
    query: SearchQuery,
) -> Result<Vec<SearchResult>, String>
```

**Search implementation:**

*Keyword:* FTS5 query with BM25 ranking. Filter by speaker/date/topic via JOIN after FTS match.

*Semantic:* Generate query embedding via Python worker endpoint, then:
```sql
SELECT s.id, s.raw_text, s.conversation_id, s.started_at, s.speaker_instance_id,
       vec_distance_cosine(se.embedding, ?) AS distance
FROM segment_embeddings se
JOIN transcript_segments s ON s.id = se.segment_id
WHERE distance < 0.4
ORDER BY distance
LIMIT 20
```

*Hybrid (RRF):* Run both keyword and semantic in parallel, combine results:
```
score(doc) = 1/(60 + keyword_rank) + 1/(60 + semantic_rank)
```
Merge lists, sort by combined score, deduplicate by segment_id.

Note: Query embedding for semantic search is generated by calling the Python worker's text embedder directly (a new lightweight endpoint `POST /embed` that accepts a string and returns a float array).

### 7.4 Speaker Commands

```rust
#[tauri::command]
async fn list_speaker_profiles(db: State<'_, DbPool>) -> Result<Vec<SpeakerProfile>, String>

#[tauri::command]
async fn rename_speaker_profile(
    db: State<'_, DbPool>,
    id: String,
    display_name: String,
) -> Result<(), String>

#[tauri::command]
async fn merge_speaker_profiles(
    worker: State<'_, WorkerClient>,
    from_id: String,
    to_id: String,
) -> Result<(), String>

#[tauri::command]
async fn delete_speaker_profile(
    db: State<'_, DbPool>,
    id: String,
) -> Result<(), String>
```

### 7.5 Settings and Storage Commands

```rust
#[tauri::command]
async fn get_setting(db: State<'_, DbPool>, key: String) -> Result<String, String>

#[tauri::command]
async fn set_setting(db: State<'_, DbPool>, key: String, value: String) -> Result<(), String>

#[tauri::command]
async fn get_storage_usage(config: State<'_, AppConfig>) -> Result<StorageUsage, String>
// StorageUsage { audio_bytes: u64, transcript_db_bytes: u64, models_bytes: u64 }

#[tauri::command]
async fn delete_data_by_age(
    db: State<'_, DbPool>,
    config: State<'_, AppConfig>,
    older_than_days: u32,
    scope: DeleteScope,  // Audio | Transcripts | Both
) -> Result<DeletionSummary, String>

#[tauri::command]
async fn export_transcripts(
    db: State<'_, DbPool>,
    output_path: String,
) -> Result<(), String>

#[tauri::command]
async fn delete_all_data(
    db: State<'_, DbPool>,
    config: State<'_, AppConfig>,
) -> Result<(), String>
```

---

## 8. Frontend Architecture

### 8.1 TypeScript Types (`src/api/types.ts`)

```typescript
export interface ConversationSummary {
  id: string
  startedAt: number       // Unix ms
  endedAt: number | null
  title: string | null
  summary: string | null
  topicTags: string[]
  segmentCount: number
  speakerCount: number
}

export interface ConversationDetail extends ConversationSummary {
  segments: TranscriptSegment[]
  speakers: SpeakerInstance[]
}

export interface TranscriptSegment {
  id: string
  conversationId: string
  speakerInstanceId: string | null
  startedAt: number
  endedAt: number
  text: string
  confidence: number | null
}

export interface SpeakerInstance {
  id: string
  conversationId: string
  diarizationLabel: string
  speakerProfileId: string | null
  speakerDisplayName: string | null
  confidence: number | null
  segmentCount: number
}

export interface SpeakerProfile {
  id: string
  displayName: string | null
  isUser: boolean
  segmentCount: number
  conversationCount: number
  createdAt: number
  updatedAt: number
}

export interface SearchResult {
  segmentId: string
  conversationId: string
  conversationStartedAt: number
  text: string
  startedAt: number
  speakerDisplayName: string | null
  matchType: 'keyword' | 'semantic' | 'hybrid'
  score: number
}

export interface StorageUsage {
  audioBytes: number
  transcriptDbBytes: number
  modelsBytes: number
}

export type RecordingStatus = {
  recording: boolean
  paused: boolean
  currentConversationId: string | null
}
```

### 8.2 Zustand Store

```typescript
// src/store/index.ts
interface AppStore {
  // Recording state (kept in sync via Tauri events)
  recording: boolean
  paused: boolean
  currentConversationId: string | null

  // Conversations
  conversations: ConversationSummary[]
  selectedConversationId: string | null
  selectedConversationDetail: ConversationDetail | null

  // Search
  searchQuery: string
  searchMode: 'keyword' | 'semantic' | 'hybrid'
  searchFilters: SearchFilters
  searchResults: SearchResult[]
  searchLoading: boolean

  // Active view
  activeView: 'timeline' | 'search' | 'speakers' | 'settings'

  // Speaker match suggestions (from pipeline events)
  pendingSpeakerSuggestions: SpeakerMatchSuggestion[]
}
```

### 8.3 Real-time Event Handling

```typescript
// src/hooks/useTauriEvents.ts
// Sets up listeners for all pipeline SSE events forwarded by Tauri

listen('transcript:segment', (event) => {
  // Append new segment to selectedConversation if it's the active one
  // Increment segment count on conversation card
})

listen('transcript:speaker_update', (event) => {
  // Update existing segment's speaker info in state
})

listen('conversation:started', (event) => {
  // Add new conversation to top of timeline list
  // Update recording status with new conversation ID
})

listen('conversation:ended', (event) => {
  // Mark conversation as ended in list
})

listen('speaker:match_suggestion', (event) => {
  // Add to pendingSpeakerSuggestions → shows notification badge in Speakers tab
})

listen('enrichment:complete', (event) => {
  // Update conversation card with summary and tags
})
```

### 8.4 Views

**Timeline View:** Virtualized list (react-virtual) of `ConversationCard` components, sorted by `started_at` descending. Each card shows: date/time, duration, speaker icons (colored initials), topic tags, summary excerpt. Click → navigate to ConversationDetail.

**Conversation Detail:** Full transcript with speaker-colored turns. Each turn shows speaker label (display name or "Speaker N"), timestamp, text. Speaker label is clickable → opens rename/profile dialog. Timestamps are links that (future: play audio from that point).

**Search View:** Persistent search bar with mode selector (Keyword / Semantic / Hybrid). Filters panel (collapsible): date range pickers, speaker dropdown, topic tag multiselect. Results list shows snippet with matched text highlighted, conversation context, speaker, timestamp. Click → navigate to conversation at that segment.

**Speakers View:** Grid of speaker profile cards. Each card: initials avatar (color-coded), display name or "Unknown Speaker", segment count, last seen. Actions: Rename, Mark as me, Merge with..., Delete. Merge opens a dialog to select another profile.

**Settings View:** Tab navigation across:
- Recording: auto-start toggle, conversation gap slider
- Models: status of each required model, download buttons, model size selector
- Storage: bar chart of audio/transcripts/models usage; delete-by-age controls per scope
- Performance: power mode selector (Performance / Balanced / Low Power)
- Privacy: recording law notice, data location display, export button, "Delete All Data" (red, confirmation required)

---

## 9. Model Management

### 9.1 Required Models

| Model | Size (approx) | Required | Source |
|---|---|---|---|
| faster-whisper distil-large-v3 | 1.5 GB | Yes | HuggingFace |
| pyannote/speaker-diarization-3.1 | 250 MB | Phase 3+ | HuggingFace (token required) |
| pyannote/embedding | 100 MB | Phase 3+ | HuggingFace (token required) |
| Resemblyzer GE2E | 17 MB | Phase 4+ | bundled in package |
| nomic-embed-text-v1.5 | 270 MB | Phase 5+ | HuggingFace |
| Ollama qwen2.5:7b | 4.7 GB | Optional | Ollama pull |

Total required (Phases 1–4): ~2 GB
Total with semantic + summarization: ~7 GB

### 9.2 Storage Location

```
~/Library/Application Support/Recall/models/
├── faster-whisper/distil-large-v3/    # CTranslate2 format
├── pyannote/diarization-3.1/
├── pyannote/embedding/
├── resemblyzer/
└── nomic-embed-text/
```

Ollama models managed by Ollama itself (`~/.ollama/models/`).

### 9.3 Download Strategy

`ml-worker/models/manager.py` implements:
- `check_model(name) -> ModelStatus`
- `download_model(name, hf_token=None, progress_callback=fn)` — streams download, verifies SHA256 checksum post-download
- `load_model(name) -> model_object` — loads from disk into memory; caches in module-level dict

First launch (onboarding):
1. Check which models are present
2. Show model download step in onboarding wizard
3. Download required models with progress bar
4. HF token input field in onboarding (stored in macOS Keychain via `security` CLI)
5. pyannote models gated behind HF token acceptance of model license on HuggingFace.co

**HuggingFace Token Storage:**
```bash
# Store
security add-generic-password -a "recall-app" -s "huggingface-token" -w "{token}"
# Retrieve
security find-generic-password -a "recall-app" -s "huggingface-token" -w
```

Python worker calls `security` CLI at startup to retrieve the token.

---

## 10. macOS Integration

### 10.1 Tauri Configuration (`tauri.conf.json`)

```json
{
  "productName": "Recall",
  "identifier": "app.recall.desktop",
  "bundle": {
    "category": "Productivity",
    "icon": ["icons/icon.icns"],
    "macOS": {
      "minimumSystemVersion": "13.0",
      "entitlements": "entitlements.plist",
      "signingIdentity": "$APPLE_SIGNING_IDENTITY",
      "providerShortName": "$APPLE_TEAM_ID"
    }
  },
  "app": {
    "withGlobalTauri": true,
    "windows": [{
      "title": "Recall",
      "width": 1100,
      "height": 750,
      "minWidth": 800,
      "minHeight": 600
    }]
  }
}
```

### 10.2 Entitlements (`entitlements.plist`)

```xml
<key>com.apple.security.device.audio-input</key>
<true/>
<key>com.apple.security.network.client</key>
<true/>
<key>com.apple.security.files.user-selected.read-write</key>
<true/>
<key>com.apple.security.cs.allow-jit</key>
<false/>
```

### 10.3 Info.plist Additions

```xml
<key>NSMicrophoneUsageDescription</key>
<string>Recall listens to conversations to create a searchable transcript. Audio is processed locally and never sent to the cloud.</string>
<key>LSUIElement</key>
<false/>
```

### 10.4 Menu Bar Item

Tauri's `tray` plugin creates a menu bar item:
- Icon: circle (gray = off, red filled = recording, yellow = paused)
- Menu: "Open Recall", "Pause Recording" / "Resume Recording", "Stop Recording", separator, "Quit"

The menu bar icon state is driven by recording status events from the Python worker.

### 10.5 Launch at Login

Implemented via `tauri-plugin-autostart`. User can toggle in Settings. Uses `LoginItems` on macOS 13+.

### 10.6 Background Operation

The app is a regular Dock app. The main window can be closed (hidden) without quitting; recording continues. The menu bar item provides a way to reopen the window and check status. The app will not quit when all windows are closed (`prevent_default_on_close` in Tauri config), only when Quit is explicitly chosen from the menu bar or Dock menu.

---

## 11. Privacy and Consent Architecture

### 11.1 Onboarding Flow (first launch)

Step 1 — Welcome screen
- Brief product description
- "What Recall does" in plain language

Step 2 — Privacy disclosure (must scroll to bottom before continuing)
- Full explanation of what is captured
- Where data is stored (exact path shown)
- Confirmation that no audio or text leaves the device
- Link to privacy documentation

Step 3 — Legal acknowledgment
- Text: "Recording laws vary by location. In some places, recording conversations without all parties' consent is illegal. You are responsible for complying with local laws."
- Checkbox: "I understand and accept responsibility for complying with local recording laws"
- Checkbox: "I understand that Recall stores audio and transcripts on this device"
- Both must be checked to continue

Step 4 — Microphone permission
- "Click to grant microphone access" button
- Triggers macOS permission dialog
- If denied: show instructions to grant in System Settings > Privacy & Security > Microphone

Step 5 — Model download
- Show required models, sizes, total download
- Download button with progress
- App is functional for basic use after faster-whisper downloads

Step 6 — Done
- Recording starts immediately (or user can start manually)

### 11.2 Persistent Consent Indicators

- `RecordingStatusBar` component is always visible at the bottom of the app window
- Shows: red dot "Recording" / yellow "Paused" / gray "Off"
- One-click "Pause" button always accessible
- Menu bar icon always shows recording state

### 11.3 Data Controls (Settings > Privacy)

**Storage path display:** Shows actual path; "Open in Finder" button.

**Selective deletion UI:**
```
Delete data older than: [14 days ▼]
What to delete:         [○ Audio only  ○ Transcripts only  ● Both]
                        [Delete Now]
Estimated: 4.2 GB audio, 12 MB transcripts
```

After deletion: confirmation dialog showing exact counts. Operation is irreversible and clearly stated.

**Export:**
- "Export all transcripts as JSON" → saves to user-chosen location
- Format: `{ conversations: [...], segments: [...], speakers: [...] }`
- Does not export audio or embeddings

**Delete all data:**
- Red "Delete All Data" button
- Confirmation dialog with typed confirmation (`DELETE`)
- Deletes: all WAV files, recall.db, all embeddings
- App returns to onboarding state on next launch

---

## 12. Background Worker Design

### 12.1 Python Orchestrator (`ml-worker/pipeline/orchestrator.py`)

The orchestrator uses Python `asyncio` with a thread pool for blocking ML inference.

```python
# Queue architecture
raw_audio_queue: asyncio.Queue[AudioChunk]    # from capture callback → VAD
speech_segment_queue: asyncio.Queue[SpeechSegment]  # from VAD → transcriber
transcript_queue: asyncio.Queue[TranscriptChunk]    # from transcriber → persister
diarization_queue: asyncio.Queue[DiarizationWindow] # 30s windows → diarizer
cold_queue: asyncio.Queue[ColdTask]                 # embeddings, matching, summarization

# Workers (all async tasks)
capture_worker()        # reads raw_audio_queue, writes to WAV, puts on speech_segment_queue
vad_worker()            # reads speech_segment_queue, filters silence, accumulates speech windows
transcription_worker()  # reads from VAD output, runs faster-whisper in thread pool
persist_worker()        # inserts TranscriptChunk into DB, emits SSE event
diarization_worker()    # reads 30s windows, runs pyannote in thread pool
speaker_match_worker()  # cold path: Resemblyzer matching, emits suggestions
text_embed_worker()     # cold path: nomic-embed-text, writes to sqlite-vec
summarization_worker()  # cold path: Ollama API call when conversation ends
```

### 12.2 Power Mode Behavior

| Mode | Diarization | Speaker Match | Embeddings | Summarization |
|---|---|---|---|---|
| Performance | Always | Always | Always | Always |
| Balanced (default) | Always | Always | Throttled (queue max 20) | Yes |
| Low Power | Disabled | Disabled | Disabled | Disabled |

Low power mode: only hot path runs (capture → VAD → transcription → persist). Diarization and all enrichment can be re-run later via "Re-process conversation" (future feature, but the architecture must support it).

### 12.3 Resource Throttling

The `orchestrator.py` monitors system resources:
- If `psutil.cpu_percent(interval=5) > 80`: pause cold queue processing for 30s
- If `psutil.sensors_battery()` present and not charging: switch to Low Power mode unless user set Performance mode explicitly
- Cold queue has a max size of 100; if full, drop oldest tasks with a warning log

---

## 13. Performance Optimization

### 13.1 Audio Hot Path Targets

| Stage | Target Latency | Notes |
|---|---|---|
| Capture → VAD | < 100ms | VAD runs on CPU, ONNX, very fast |
| VAD → Transcription queue | ~3s | VAD buffers until natural pause |
| Transcription (5s speech) | 2–4s | faster-whisper Metal, distil-large-v3 |
| Persist to DB | < 50ms | SQLite WAL, simple INSERT |
| DB → SSE event | < 10ms | In-process, asyncio |
| SSE → Tauri event | < 50ms | Local TCP loopback |
| Tauri event → UI update | < 16ms | React re-render |
| **Total end-to-end** | **< 10s** | Target met |

### 13.2 Model Loading

All models are loaded once at worker startup and kept in memory:
- faster-whisper: ~2.5 GB VRAM (Metal unified memory on M-series)
- pyannote: ~400 MB
- Resemblyzer: ~50 MB
- nomic-embed-text: ~500 MB

Total ML memory: ~3.5 GB with all models loaded. On 8 GB M1 machines, this leaves ~4.5 GB for system + app. Tested target: M1 Pro with 16 GB.

For 8 GB machines (base M1), Low Power mode is recommended. The settings panel will detect available RAM and suggest appropriate defaults.

### 13.3 Database Performance

- WAL mode: allows concurrent reader (Rust) and writer (Python)
- Indexes on all frequently queried columns (see schema)
- Transcript segments table will grow large; keep per-conversation queries fast with `conversation_id` index
- FTS5 index is updated synchronously via triggers; acceptable latency (< 5ms per insert)
- sqlite-vec queries over large tables: ANN search, not exact; acceptable for semantic retrieval
- Periodic `PRAGMA optimize` (run weekly via background task)

---

## 14. Testing Strategy

### 14.1 Python Unit Tests (`ml-worker/tests/`)

```python
# test_vad.py
def test_vad_detects_speech_above_threshold()
def test_vad_returns_silence_for_quiet_audio()
def test_vad_hysteresis_does_not_cut_mid_word()

# test_transcriber.py
def test_transcriber_returns_text_with_timestamps()
def test_transcriber_handles_empty_audio()
def test_transcriber_word_timestamps_within_segment_bounds()

# test_diarizer.py
def test_diarizer_produces_non_overlapping_segments()
def test_diarizer_labels_two_speakers_in_fixture()

# test_embedder.py
def test_embedder_produces_256d_vector()
def test_embedder_same_speaker_high_cosine_similarity()
def test_embedder_different_speakers_low_cosine_similarity()

# test_segmenter.py
def test_segmenter_closes_conversation_on_60s_gap()
def test_segmenter_closes_on_midnight_boundary()
```

Test fixtures: 30-second audio samples (mono, 16kHz WAV) in `ml-worker/tests/fixtures/`:
- `speech_single.wav` (single speaker, known content)
- `speech_two_speakers.wav` (alternating speakers)
- `silence.wav` (pure silence)
- `speech_with_noise.wav` (speech + background noise)

### 14.2 Rust Unit Tests

```rust
// src-tauri/src/db/migrations.rs tests
#[test] fn test_migrations_apply_in_order()
#[test] fn test_migrations_idempotent_on_rerun()

// src-tauri/src/commands/search.rs tests
#[test] fn test_keyword_search_returns_matching_segments()
#[test] fn test_search_respects_date_filter()
#[test] fn test_hybrid_search_combines_scores()
```

### 14.3 Integration Tests

`tests/integration/pipeline_test.rs`:
- Start Python worker as subprocess
- Feed known audio file via mock capture
- Wait for SSE events: `transcript.segment`, `conversation.ended`
- Assert DB contains expected text and timestamps

### 14.4 E2E Tests (`tests/e2e/`)

Using Playwright with Tauri WebDriver:
```typescript
test('record, stop, search finds spoken word', async ({ page }) => {
  // Trigger recording with test audio injection
  // Wait for transcript to appear in timeline
  // Search for known word in transcript
  // Assert result appears with correct conversation
})

test('speaker rename flow', async ({ page }) => {
  // Open conversation with two speakers
  // Click speaker label → rename dialog
  // Set name → confirm
  // Assert label updates in transcript
  // Assert speaker profile list updated
})
```

### 14.5 Performance Benchmarks

`criterion` benchmarks in Rust:
- DB insert throughput (segments/second)
- FTS5 search latency at 100k / 1M segments
- sqlite-vec ANN search latency at 100k vectors

Python benchmarks:
- Transcription throughput (seconds of audio per second of processing)
- VAD throughput (chunks per second)
- Embedding generation (embeddings per second)

---

## 15. Packaging and Distribution

### 15.1 Python Bundling

The Python worker is bundled as a Tauri sidecar:

1. Use `python-build-standalone` to get a self-contained Python 3.11 interpreter for `aarch64-apple-darwin`
2. Create a venv inside the interpreter's directory
3. Install all requirements into the venv
4. The sidecar binary is a shell script that sets `PYTHONHOME`/`PYTHONPATH` and runs `python ml-worker/main.py`
5. This entire bundle (~500 MB with all pure Python deps) is placed in `src-tauri/binaries/`

Models are NOT bundled (too large). They are downloaded on first launch as described in Section 9.

### 15.2 Build Process

```bash
# Production build
pnpm tauri build

# This produces:
# src-tauri/target/release/bundle/macos/Recall.app
# src-tauri/target/release/bundle/dmg/Recall_x.y.z_aarch64.dmg
```

### 15.3 Code Signing and Notarization

```bash
# Sign
codesign --force --options runtime \
  --entitlements entitlements.plist \
  --sign "Developer ID Application: {name} ({team_id})" \
  "Recall.app"

# Notarize
xcrun notarytool submit Recall_x.y.z_aarch64.dmg \
  --apple-id "$APPLE_ID" \
  --password "$APPLE_APP_PASSWORD" \
  --team-id "$APPLE_TEAM_ID" \
  --wait

# Staple
xcrun stapler staple Recall_x.y.z_aarch64.dmg
```

Signing identity and credentials are stored as GitHub Actions secrets.

### 15.4 Auto-Update

Tauri's built-in updater plugin:
- Update endpoint: GitHub Releases (JSON format Tauri expects)
- Check frequency: on app launch + every 24h
- Show update dialog with changelog
- Download and apply in background; prompt to restart
- Update JSON format:
  ```json
  {
    "version": "0.2.0",
    "notes": "Changelog text",
    "pub_date": "2025-01-01T00:00:00Z",
    "platforms": {
      "darwin-aarch64": {
        "url": "https://...",
        "signature": "..."
      }
    }
  }
  ```

### 15.5 Database Migration Strategy

On startup, `migrations.rs`:
1. Check `schema_versions` table (create if missing)
2. Read all `.sql` files from `migrations/` dir, sorted by filename
3. For each migration not in `schema_versions`: run in a transaction, record version on success
4. If migration fails: rollback, show error dialog, refuse to start (prevents data corruption)

Before any migration, back up the database:
```
recall.db → recall.db.backup.{version}.{timestamp}
```

---

## 16. Local Development Setup

### 16.1 Prerequisites

```bash
# Xcode Command Line Tools
xcode-select --install

# Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
rustup target add aarch64-apple-darwin

# Node.js + pnpm
brew install node
npm install -g pnpm

# Python 3.11
brew install pyenv
pyenv install 3.11.9
pyenv local 3.11.9

# Ollama (optional)
brew install ollama
ollama pull qwen2.5:7b
```

### 16.2 First-Time Setup

```bash
# Clone and setup
cd recall

# Python environment
cd ml-worker
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ..

# Node dependencies
pnpm install

# Download ML models (interactive, will ask for HF token)
python scripts/download-models.py

# Start development
pnpm tauri dev
```

`pnpm tauri dev` starts the Vite dev server and the Tauri app. The Tauri app spawns the Python worker automatically. Hot reload is available for the React frontend; Rust changes require a full Tauri rebuild.

### 16.3 Environment Variables (Development Only)

```bash
RECALL_WORKER_LOG_LEVEL=debug
RECALL_WORKER_PORT=8765    # fix port in dev (override random port)
RECALL_DB_PATH=/tmp/recall-dev.db   # use separate dev DB
RECALL_AUDIO_PATH=/tmp/recall-audio # use separate dev audio dir
```

---

## 17. Phased Roadmap

### Phase 1 — Transcript Pipeline MVP

**Goal:** Working app that captures mic audio, transcribes locally, stores chunks, shows raw transcript.

**Deliverables:**
- Tauri + React + Python worker scaffold
- IPC: worker spawn, port discovery, SSE connection
- Audio capture via sounddevice (3s chunks)
- Silero VAD (speech/silence filtering)
- faster-whisper transcription (distil-large-v3)
- SQLite with migrations 001 (core schema without diarization usage)
- WAV file storage per session
- Basic transcript viewer: chronological list of segments, raw text, timestamps
- Recording status bar (red dot, pause button)
- Menu bar item (gray/red icon)
- Microphone permission request
- Onboarding: consent + microphone + model download steps

**Success criteria:**
- App runs for 2+ hours without crash
- Transcription latency under 10 seconds
- User can read transcript of what was said in the last hour

**Key packages (Python):**
```
faster-whisper==1.1.0
silero-vad==5.1.2
sounddevice==0.5.0
soundfile==0.12.1
fastapi==0.115.0
uvicorn==0.32.0
numpy==2.1.0
onnxruntime==1.20.0
```

**Key packages (Rust):**
```toml
tauri = { version = "2", features = ["tray-icon"] }
rusqlite = { version = "0.31", features = ["bundled", "load_extension"] }
reqwest = { version = "0.12", features = ["json", "stream"] }
tokio = { version = "1", features = ["full"] }
serde = { version = "1", features = ["derive"] }
uuid = { version = "1", features = ["v4"] }
```

---

### Phase 2 — Conversation Timeline and Keyword Search

**Goal:** Segment transcript into conversations, show timeline cards, enable keyword search.

**Deliverables:**
- `segmenter.py`: conversation boundary detection (60s silence gap)
- `conversations` table fully utilized; segmentation writes `ended_at`
- Timeline view: chronological list of `ConversationCard` components
- Conversation detail view: full transcript (no speaker separation yet)
- FTS5 migration (002) and search implementation
- `search` command (keyword mode only)
- Search view with keyword input and results
- Date range filter in search
- "Jump to conversation" from search result

**Success criteria:**
- User can find a conversation by approximate time
- User can search for a spoken word and see the conversation containing it
- Conversations are clearly separated in timeline

---

### Phase 3 — Diarization and Speaker-Separated Transcript

**Goal:** Attribute transcript segments to speaker turns, render speaker-separated transcript.

**Deliverables:**
- `diarizer.py`: pyannote.audio integration with 30s window buffering
- HuggingFace token input + Keychain storage
- `speaker_instances` table populated from diarization output
- Diarization-to-transcript merge logic in orchestrator
- Async speaker label update (segments updated after diarization completes)
- `SpeakerTurn` component in transcript view (colored labels: Speaker 1, Speaker 2...)
- Speaker turn update via `transcript:speaker_update` Tauri event
- Speaker instances visible in conversation detail

**Success criteria:**
- Two-person conversation transcript shows distinct speaker turns
- Speaker labels update within ~30 seconds of speech

---

### Phase 4 — Recurring Speaker Recognition

**Goal:** Generate speaker embeddings, match recurring voices across conversations, let user assign names.

**Deliverables:**
- `embedder.py`: Resemblyzer integration
- `speaker_embeddings` + `speaker_profiles` tables active
- Auto-matching logic (thresholds: 0.85 auto-link, 0.70–0.85 suggest)
- `speaker.identified` and `speaker.match_suggestion` SSE events
- Speakers view: grid of profiles
- Rename dialog component
- Merge profiles workflow
- Speaker filter in search results
- Speaker name displayed in transcript (overrides "Speaker N" label)
- Notification badge when new speaker suggestions are pending

**Success criteria:**
- Recognizable recurring speakers are suggested across multiple conversations
- User can assign a name and have it persist across all conversations
- Speaker filter in search narrows results correctly

---

### Phase 5 — Semantic Retrieval and Topic Understanding

**Goal:** Full semantic search, topic tags, conversation summaries, hybrid search.

**Deliverables:**
- `text_embedder.py`: nomic-embed-text integration
- sqlite-vec migration (003) and vector table
- Semantic search implementation (embedding query, cosine distance ranking)
- Hybrid search with RRF
- Search mode toggle (Keyword / Semantic / Hybrid) in UI
- `summarizer.py`: Ollama integration (optional dependency)
- Topic tag extraction + storage
- Topic tags displayed on conversation cards
- Topic filter in search
- Ollama status indicator in Settings > Models

**Success criteria:**
- User can search "when did we talk about machine learning" and find relevant conversations even without exact word matches
- Conversation cards show topic tags and summary
- Search quality improves noticeably over keyword-only

---

### Phase 6 — Polish, Storage Management, and Distribution

**Goal:** Production-ready, packaging, performance hardening, full settings, distribution.

**Deliverables:**
- Storage panel: usage display (audio, transcripts, models)
- Selective deletion UI (by age × scope)
- Data export (JSON)
- "Delete all data" with confirmation
- Performance panel: power mode selector
- Apple Silicon resource throttling implementation (CPU/battery monitoring)
- Low Power mode behavior (disable cold path)
- Settings persistence across restarts
- Launch at login toggle
- Crash recovery: worker restart with backoff
- Log rotation (`~/Library/Logs/Recall/`)
- Complete onboarding flow (all steps)
- App icon + DMG background design
- Code signing + notarization CI pipeline
- Auto-update endpoint setup
- README for end users

**Success criteria:**
- App runs 8+ hours on a MacBook without excessive thermal impact
- User can manage storage and delete specific data
- App can be distributed and installed by a non-developer user
- First-launch onboarding is clear and complete

---

## 18. Technical Risk Register

| Risk | Severity | Mitigation |
|---|---|---|
| pyannote license requirement (HF token) | High | Clear onboarding instructions; token stored securely in Keychain; diarization gracefully disabled if token absent |
| faster-whisper Metal backend stability | Medium | Pin CTranslate2 version; test on M1/M2/M3; fallback to CPU if Metal fails |
| sqlite-vec compatibility with rusqlite | Medium | Test early in Phase 5; keep Chroma as fallback option if sqlite-vec proves unstable |
| Python subprocess entitlement inheritance | Medium | Verify mic permission granted to parent app carries through to subprocess; test on clean macOS install |
| Memory pressure on 8 GB M1 | Medium | Detect RAM at startup; recommend Low Power mode; document minimum 16 GB for full feature set |
| Diarization quality on overlapping speech | Medium | Accept imperfect baseline; expose correction UI; design schema to support re-processing |
| Speaker identity drift over time | Low | Exponential moving average embedding update; confidence display; user correction always available |
| WAV files growing large (no compression) | Low | Document storage usage clearly; Phase 6 can add FLAC conversion as background job post-conversation |
| Ollama not installed | Low | Fully optional; app works without it; clear status indicator in settings |
| Conversation boundary mis-segmentation | Low | Expose manual split/merge in Phase 3+; 60s gap is conservative and works well in practice |

---

## 19. Future Extensibility Notes

The architecture is designed so these additions don't require structural changes:

- **System audio capture:** Add a `device_id` parameter to `capture.py`; add device selector to Settings; no pipeline changes needed
- **Re-processing conversations:** All raw audio is stored; any conversation can be re-run through diarization, speaker matching, or summarization with updated models
- **Multiple microphone profiles:** `app_settings` can store per-context device configurations
- **Cloud sync (opt-in):** Database and audio files are in a well-defined location; iCloud Drive opt-in is a folder move
- **iOS companion app:** All data in SQLite; could share DB via iCloud
- **Wearable audio source:** Any audio input device works with `device_id` abstraction
- **Custom summarization prompts:** Prompt templates stored in `app_settings`
- **Speaker enrollment during onboarding:** `speaker_profiles` table and `speaker_embeddings` already designed to support this; add a recording step to onboarding

---

## 20. File Locations at Runtime

```
~/Library/Application Support/Recall/
├── recall.db                   # main database (WAL mode)
├── recall.db-wal               # WAL journal
├── recall.db-shm               # WAL shared memory
├── audio/
│   └── 2025/
│       └── 01/
│           └── 15/
│               ├── {uuid}.wav  # one file per conversation
│               └── {uuid}.wav
├── models/
│   ├── faster-whisper/distil-large-v3/
│   ├── pyannote/diarization-3.1/
│   ├── pyannote/embedding/
│   └── nomic-embed-text/
└── logs/
    └── worker.log              # Python worker log (rotated daily, keep 7 days)

~/Library/Logs/Recall/
└── tauri.log                   # Tauri/Rust log
```
