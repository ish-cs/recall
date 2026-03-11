# Recall — Task Breakdown

> Auto-generated from PLAN.md. Organized by phase. Each task is concrete and implementation-ready.

---

## Legend
- [ ] = not started
- [x] = complete
- [~] = in progress
- [!] = blocked

---

## Phase 1 — Transcript Pipeline MVP

**Goal:** Working app that captures mic audio, transcribes locally, stores chunks, shows raw transcript.

### 1.1 Project Scaffold

- [x] **1.1.1** Initialize Tauri 2.x + React + TypeScript project
  - Files: `package.json`, `tsconfig.json`, `vite.config.ts`, `src/main.tsx`, `src/App.tsx`, `src-tauri/tauri.conf.json`, `src-tauri/Cargo.toml`
  - Command: `pnpm create tauri-app@latest recall --template react-ts --manager pnpm`
  - Verify: `pnpm tauri info` succeeds, `pnpm tauri dev` builds and opens window

- [x] **1.1.2** Configure Tailwind CSS
  - Files: `tailwind.config.ts`, `src/styles/globals.css`
  - Add Tailwind to PostCSS / Vite pipeline
  - Verify: div with `className="bg-red-500"` renders as red

- [x] **1.1.3** Add Zustand and TanStack Router
  - Files: `src/routes.tsx`, `src/store/index.ts`, `src/store/recording.slice.ts`, `src/store/conversations.slice.ts`, `src/store/search.slice.ts`
  - Verify: `pnpm build` succeeds with no TS errors

- [x] **1.1.4** Create Python ml-worker scaffold
  - Files: `ml-worker/main.py`, `ml-worker/requirements.txt`, `ml-worker/requirements-dev.txt`, `ml-worker/pipeline/__init__.py`, `ml-worker/ipc/__init__.py`, `ml-worker/ipc/server.py`, `ml-worker/storage/__init__.py`, `ml-worker/models/__init__.py`
  - `main.py` starts FastAPI on random port, prints `PORT={n}` to stdout, health check at GET /health
  - Verify: `python ml-worker/main.py` prints PORT line; `curl localhost:{port}/health` returns `{"ok": true}`

- [x] **1.1.5** Configure Tauri to spawn Python sidecar
  - Files: `src-tauri/src/config.rs`, `src-tauri/src/worker/mod.rs`, `src-tauri/src/worker/process.rs`
  - Spawns `ml-worker/main.py` via Python, reads stdout for PORT line
  - For dev: spawn Python directly (not bundled)
  - Verify: Tauri app starts, Rust log shows "Worker started on port N"

- [x] **1.1.6** IPC: Worker HTTP client + SSE bridge
  - Files: `src-tauri/src/worker/client.rs`, `src-tauri/src/worker/events.rs`
  - `client.rs`: reqwest client with base URL from discovered port
  - `events.rs`: connects to GET /events, relays SSE → Tauri events
  - Verify: dummy SSE event from Python worker appears in frontend console

### 1.2 Database

- [ ] **1.2.1** Create migration files
  - Files: `migrations/001_initial_schema.sql`, `migrations/002_fts5.sql`, `migrations/003_vector_search.sql`
  - Exact SQL from PLAN.md §4.1, §4.2, §4.3

- [ ] **1.2.2** Implement Rust DB layer
  - Files: `src-tauri/src/db/mod.rs`, `src-tauri/src/db/connection.rs`, `src-tauri/src/db/migrations.rs`, `src-tauri/src/db/models.rs`
  - `connection.rs`: opens SQLite with WAL mode, sets up r2d2 pool
  - `migrations.rs`: reads migrations/ dir, applies pending, records in schema_versions
  - `models.rs`: Rust structs for Conversation, Segment, SpeakerProfile, etc.
  - Verify: `cargo test db::migrations::tests` passes

- [ ] **1.2.3** Implement Python DB writer
  - Files: `ml-worker/storage/db.py`
  - Functions: `insert_conversation()`, `close_conversation()`, `insert_segment()`
  - Uses sqlite3 directly with WAL mode
  - Verify: unit test inserts a segment and reads it back

### 1.3 Audio Pipeline (Python)

- [ ] **1.3.1** Implement audio capture module
  - Files: `ml-worker/pipeline/capture.py`
  - sounddevice.InputStream: 16kHz, mono, float32, 3s chunks
  - Queues chunks to `raw_audio_queue`; writes to WAV file via soundfile
  - Accepts `device_id=None` parameter for future extensibility
  - Verify: test script records 5s and saves valid WAV

- [ ] **1.3.2** Implement Silero VAD module
  - Files: `ml-worker/pipeline/vad.py`
  - Loads silero-vad v5 ONNX model
  - Implements SILENCE/SPEECH state machine with hysteresis
  - Accumulates speech chunks until pause, emits to speech_segment_queue
  - Tracks silence duration for conversation boundary signaling
  - Verify: `pytest ml-worker/tests/test_vad.py` passes (speech/silence detection, hysteresis)

- [ ] **1.3.3** Implement faster-whisper transcription module
  - Files: `ml-worker/pipeline/transcriber.py`
  - Loads distil-large-v3 on MPS backend with float16
  - Runs in thread pool (not async)
  - Returns TranscriptChunk with absolute Unix ms timestamps
  - Verify: `pytest ml-worker/tests/test_transcriber.py` passes

- [ ] **1.3.4** Implement WAV audio storage
  - Files: `ml-worker/storage/audio_store.py`
  - Opens WAV at `audio/YYYY/MM/DD/{conversation_id}.wav` when conversation starts
  - Appends chunks; closes cleanly on conversation end
  - Verify: unit test creates a valid WAV file with correct format

- [ ] **1.3.5** Implement conversation segmenter (Phase 1 scope: silence-gap only)
  - Files: `ml-worker/pipeline/segmenter.py`
  - Watches silence duration from VAD; triggers conversation close/open when gap > 60s
  - Closes conversation on midnight boundary
  - Verify: `pytest ml-worker/tests/test_segmenter.py::test_segmenter_closes_conversation_on_60s_gap`

- [ ] **1.3.6** Implement pipeline orchestrator (hot path only)
  - Files: `ml-worker/pipeline/orchestrator.py`
  - Wires: capture → VAD → transcriber → persist → SSE emit
  - asyncio queue architecture; transcriber in thread pool
  - Emits `transcript.segment` SSE event after each persisted segment
  - Emits `conversation.started` / `conversation.ended` events
  - Emits `pipeline.status` heartbeat every 5s
  - Verify: manual test — start pipeline, speak, check SSE events

### 1.4 IPC Server

- [ ] **1.4.1** Implement FastAPI server with all Phase 1 endpoints
  - Files: `ml-worker/ipc/server.py`
  - Endpoints: POST /pipeline/start, POST /pipeline/pause, POST /pipeline/resume, GET /pipeline/status, GET /events, GET /health
  - SSE endpoint using async generator
  - Verify: `pytest ml-worker/tests/` — API endpoint tests

- [ ] **1.4.2** Implement model manager (Phase 1: faster-whisper only)
  - Files: `ml-worker/models/manager.py`
  - check_model(), download_model() with SHA256 verify, load_model()
  - GET /models/status endpoint, POST /models/download endpoint
  - Verify: status endpoint returns correct status for installed/missing model

### 1.5 Rust Commands

- [ ] **1.5.1** Implement recording commands
  - Files: `src-tauri/src/commands/mod.rs`, `src-tauri/src/commands/recording.rs`
  - start_recording, stop_recording, pause_recording, resume_recording, get_recording_status
  - Proxies to Python worker via HTTP client
  - Verify: `cargo test commands::recording` passes

- [ ] **1.5.2** Implement conversation commands (Phase 1: list + get)
  - Files: `src-tauri/src/commands/conversations.rs`
  - list_conversations (paginated), get_conversation (with segments)
  - Verify: `cargo test commands::conversations` passes

- [ ] **1.5.3** Implement settings commands
  - Files: `src-tauri/src/commands/settings.rs`
  - get_setting, set_setting
  - Verify: `cargo test commands::settings` passes

- [ ] **1.5.4** Register all commands and AppState in lib.rs
  - Files: `src-tauri/src/lib.rs`, `src-tauri/src/main.rs`
  - AppState: DbPool + WorkerClient + AppConfig
  - Register Tauri plugins: tray-icon
  - Verify: `cargo build` succeeds

### 1.6 Frontend — Phase 1 UI

- [ ] **1.6.1** Create TypeScript types and Tauri API wrappers
  - Files: `src/api/types.ts`, `src/api/tauri.ts`
  - All types from PLAN.md §8.1
  - Typed invoke() wrappers for all commands
  - Verify: `pnpm build` succeeds with no TS errors

- [ ] **1.6.2** Create AppShell layout
  - Files: `src/components/layout/AppShell.tsx`, `src/components/layout/Sidebar.tsx`, `src/components/layout/RecordingStatusBar.tsx`
  - Sidebar: nav links (Timeline, Search, Speakers, Settings) + recording indicator
  - RecordingStatusBar: always-visible bottom strip with status + pause button
  - Verify: renders in dev, nav links switch active state

- [ ] **1.6.3** Implement useRecordingStatus and useTauriEvents hooks
  - Files: `src/hooks/useRecordingStatus.ts`, `src/hooks/useTauriEvents.ts`, `src/hooks/useConversations.ts`
  - useRecordingStatus: subscribes to pipeline.status Tauri events
  - useTauriEvents: generic listener wrapper
  - useConversations: invokes list_conversations
  - Verify: hook unit tests pass (Vitest)

- [ ] **1.6.4** Implement basic transcript viewer (Phase 1 version)
  - Files: `src/components/transcript/TranscriptView.tsx`, `src/components/transcript/SpeakerTurn.tsx`, `src/components/transcript/TimestampLabel.tsx`
  - Shows raw text segments without speaker separation (Phase 1)
  - Scrollable; new segments append at bottom
  - Verify: renders segments from mock data

- [ ] **1.6.5** Implement recording controls in Sidebar/StatusBar
  - Wire start/stop/pause/resume buttons to Tauri commands
  - Show current recording state from Zustand store
  - Verify: clicking start/stop calls correct Tauri command

- [ ] **1.6.6** Implement menu bar tray icon
  - Files: Update `src-tauri/src/lib.rs` with tray setup
  - Gray circle = off, red = recording, yellow = paused
  - Menu: Open Recall, Pause/Resume, Stop, Quit
  - Verify: tray icon appears and changes state

### 1.7 Onboarding

- [ ] **1.7.1** Implement onboarding flow (Phase 1 steps)
  - Files: `src/components/onboarding/OnboardingFlow.tsx`, `src/components/onboarding/ConsentStep.tsx`, `src/components/onboarding/ModelDownloadStep.tsx`
  - Steps: Welcome → Privacy disclosure → Legal checkboxes → Microphone permission → Model download → Done
  - Gated by `onboarding_complete` setting; shown on first launch
  - Verify: onboarding shows on first launch, setting persists after completion

### 1.8 macOS Config

- [ ] **1.8.1** Configure Tauri for macOS (entitlements, Info.plist)
  - Files: `src-tauri/entitlements.plist`, update `src-tauri/tauri.conf.json`
  - Microphone permission description in Info.plist
  - Window config: 1100×750, min 800×600
  - Verify: mic permission dialog appears on first recording attempt

- [ ] **1.8.2** Create Python tests for Phase 1
  - Files: `ml-worker/tests/conftest.py`, `ml-worker/tests/fixtures/` (WAV files), `ml-worker/tests/test_vad.py`, `ml-worker/tests/test_transcriber.py`, `ml-worker/tests/test_segmenter.py`
  - Audio fixtures: silence.wav, speech_single.wav
  - Verify: `pytest ml-worker/tests/ -v` all pass

- [ ] **1.8.3** Create dev scripts
  - Files: `scripts/setup.sh`, `scripts/dev.sh`
  - `setup.sh`: install Python deps, node deps
  - `dev.sh`: start Python worker in dev mode
  - Verify: `./scripts/setup.sh` runs without error

---

## Phase 2 — Conversation Timeline and Keyword Search

### 2.1 Conversation Segmentation

- [ ] **2.1.1** Full segmenter integration (conversations table, WAV finalize)
  - Update `ml-worker/pipeline/segmenter.py` to write ended_at, close WAV
  - Conversation titles: auto-generate from date/time
  - Verify: 60s silence test creates two conversation records

### 2.2 Timeline View

- [ ] **2.2.1** Implement Timeline and ConversationCard
  - Files: `src/components/timeline/TimelineView.tsx`, `src/components/timeline/ConversationCard.tsx`, `src/components/timeline/ConversationDetail.tsx`
  - TimelineView: virtualized list (react-virtual), sorted by started_at DESC
  - ConversationCard: date/time, duration, segment count, summary excerpt, topic tags
  - Verify: renders with mock data, pagination loads more

- [ ] **2.2.2** Implement conversation detail navigation
  - Click ConversationCard → navigate to full transcript view
  - Load full conversation via get_conversation command
  - Verify: clicking card shows full transcript

### 2.3 Keyword Search

- [ ] **2.3.1** Implement search command (Rust, keyword mode)
  - Files: `src-tauri/src/commands/search.rs`
  - FTS5 query with BM25 ranking
  - Filters: date range, speaker (Phase 4), topic (Phase 5)
  - Verify: `cargo test commands::search::test_keyword_search_returns_matching_segments`

- [ ] **2.3.2** Implement Search UI (keyword mode)
  - Files: `src/components/search/SearchView.tsx`, `src/components/search/SearchBar.tsx`, `src/components/search/SearchFilters.tsx`, `src/components/search/SearchResultItem.tsx`
  - Debounced search hook; date range filter
  - SearchResultItem: snippet, conversation context, jump link
  - Verify: searching returns results with correct highlighting

- [ ] **2.3.3** Implement useSearch hook
  - Files: `src/hooks/useSearch.ts`
  - Debounced invoke to search command
  - Verify: unit test with mocked invoke

---

## Phase 3 — Diarization and Speaker-Separated Transcript

### 3.1 Diarization Pipeline

- [ ] **3.1.1** Implement diarizer.py (pyannote.audio)
  - Files: `ml-worker/pipeline/diarizer.py`
  - 30s windowed diarization with 5s overlap
  - MPS device; requires HF token
  - Verify: `pytest ml-worker/tests/test_diarizer.py` passes

- [ ] **3.1.2** HuggingFace token Keychain integration
  - Python: retrieve token via `security` CLI at startup
  - Onboarding: add HF token input step
  - Verify: token stored and retrieved correctly

- [ ] **3.1.3** Orchestrator: diarization integration
  - Merge diarization segments with transcript word timestamps
  - Update transcript_segments with speaker_instance_id
  - Emit `transcript.speaker_update` SSE events
  - Verify: integration test — speak, wait 30s, speaker labels appear in DB

### 3.2 Speaker Turn UI

- [ ] **3.2.1** Update SpeakerTurn component for diarized labels
  - Color-coded speaker labels (Speaker 1, Speaker 2...)
  - Handles null speaker_instance_id gracefully
  - Updates in real-time via Tauri events
  - Verify: transcript shows distinct colored speaker turns

- [ ] **3.2.2** Add transcript.speaker_update event handler
  - Files: Update `src/hooks/useTauriEvents.ts`
  - Updates existing segment's speaker info in Zustand store
  - Verify: speaker label appears on segment after diarization event

---

## Phase 4 — Recurring Speaker Recognition

### 4.1 Speaker Embeddings

- [ ] **4.1.1** Implement Resemblyzer embedder
  - Files: `ml-worker/pipeline/embedder.py`
  - extract embedding for each diarized speaker segment ≥ 2s
  - Compare against profiles (cosine similarity, max over exemplars)
  - Auto-link at 0.85, suggest at 0.70–0.85, create new below 0.70
  - Verify: `pytest ml-worker/tests/test_embedder.py` passes

- [ ] **4.1.2** Orchestrator: speaker matching integration
  - Cold-path speaker_match_worker
  - Emit speaker.identified / speaker.match_suggestion SSE events
  - Profile update: add exemplar to speaker_embeddings (max 20), recompute mean
  - Verify: integration test — two conversations, same voice matched

### 4.2 Speakers UI

- [ ] **4.2.1** Implement Speakers view
  - Files: `src/components/speakers/SpeakersView.tsx`, `src/components/speakers/SpeakerCard.tsx`, `src/components/speakers/RenameDialog.tsx`
  - Grid of profile cards: initials, name, segment count, last seen
  - Actions: Rename, Mark as me, Merge, Delete
  - Verify: renders speaker profiles, rename dialog works

- [ ] **4.2.2** Implement speaker commands (Rust)
  - list_speaker_profiles, rename_speaker_profile, merge_speaker_profiles, delete_speaker_profile
  - Verify: `cargo test commands::speakers` passes

- [ ] **4.2.3** Speaker filter in search
  - Add speaker_profile_id filter to search command and SearchFilters UI
  - Verify: searching with speaker filter returns correct results

- [ ] **4.2.4** Notification badge for pending speaker suggestions
  - Files: Update `src/components/layout/Sidebar.tsx`
  - Badge count from pendingSpeakerSuggestions in Zustand store
  - Verify: badge appears when suggestion event received

---

## Phase 5 — Semantic Retrieval and Topic Understanding

### 5.1 Text Embeddings + Vector Search

- [ ] **5.1.1** Implement text_embedder.py (nomic-embed-text)
  - Files: `ml-worker/pipeline/text_embedder.py`
  - sentence-transformers with MPS; "search_document: " prefix
  - Write to segment_embeddings sqlite-vec table
  - Bounded queue (max 50)
  - Verify: embedding generated, written to DB, correct 768-d

- [ ] **5.1.2** Apply migration 003 (vector search)
  - sqlite-vec extension loaded at connection time
  - segment_embeddings USING vec0(segment_id TEXT, embedding FLOAT[768])
  - Verify: table created; test insert + query

- [ ] **5.1.3** POST /embed endpoint in FastAPI
  - Accept text string, return float array
  - Verify: curl test returns 768-element array

- [ ] **5.1.4** Implement semantic and hybrid search (Rust)
  - Semantic: call /embed, then vec_distance_cosine query
  - Hybrid: RRF combination of keyword + semantic ranks
  - Verify: `cargo test commands::search::test_hybrid_search_combines_scores`

- [ ] **5.1.5** Search mode toggle in UI
  - Files: Update `src/components/search/SearchBar.tsx`
  - Keyword / Semantic / Hybrid toggle
  - Verify: mode switch changes search behavior

### 5.2 Summarization

- [ ] **5.2.1** Implement summarizer.py (Ollama)
  - Files: `ml-worker/pipeline/summarizer.py`
  - Ollama HTTP call, 30s timeout, graceful fallback if absent
  - Extracts summary + topic tags as JSON
  - Verify: test with running Ollama instance; and graceful failure test

- [ ] **5.2.2** Orchestrator: summarization on conversation end
  - Cold path: summarization_worker
  - Emits enrichment.complete SSE event
  - Writes summary + tags to conversations table
  - Verify: conversation card shows summary after recording stops

- [ ] **5.2.3** Topic tags UI
  - Display tags on ConversationCard and ConversationDetail
  - Topic filter in SearchFilters
  - Verify: tags render; filter narrows search correctly

---

## Phase 6 — Polish, Storage Management, Distribution

### 6.1 Settings Views

- [ ] **6.1.1** Implement full Settings view with tabs
  - Files: `src/components/settings/SettingsView.tsx`, `src/components/settings/ModelPanel.tsx`, `src/components/settings/StoragePanel.tsx`, `src/components/settings/PerformancePanel.tsx`, `src/components/settings/PrivacyPanel.tsx`
  - Verify: all tabs render, settings persist on restart

- [ ] **6.1.2** Storage panel + selective deletion
  - StoragePanel: audio/transcripts/models usage bars
  - delete_data_by_age command (Rust); delete scope × age
  - DeletionSummary response
  - Verify: delete_data_by_age removes correct files + DB records

- [ ] **6.1.3** Data export command
  - export_transcripts: JSON export to user-chosen path
  - Verify: exported JSON contains all conversations and segments

- [ ] **6.1.4** Delete all data with confirmation
  - delete_all_data command; typed "DELETE" confirmation in UI
  - App returns to onboarding on next launch
  - Verify: all data removed, onboarding_complete reset

### 6.2 Performance and Reliability

- [ ] **6.2.1** Power mode implementation
  - Low Power: disable cold queue workers
  - Performance: no throttling
  - Balanced: throttled embeddings (max 20 queue)
  - Auto-detect battery state (psutil)
  - Verify: power mode switch changes cold worker behavior

- [ ] **6.2.2** Worker crash recovery (Rust)
  - Exponential backoff restart: 1s, 2s, 4s, max 30s
  - Verify: kill Python worker, observe restart in log

- [ ] **6.2.3** Log rotation
  - Python: rotating file handler, daily rotation, 7-day retention
  - Tauri: log to ~/Library/Logs/Recall/
  - Verify: logs appear in correct location

- [ ] **6.2.4** Launch at login toggle
  - tauri-plugin-autostart integration
  - Toggle in Settings > Recording
  - Verify: toggle enables/disables login item in macOS

### 6.3 Distribution

- [ ] **6.3.1** Python sidecar bundling
  - python-build-standalone aarch64 interpreter
  - Bundle venv + requirements into src-tauri/binaries/
  - Tauri sidecar configuration in tauri.conf.json
  - Verify: pnpm tauri build produces working .app

- [ ] **6.3.2** App icon and DMG
  - Create app icon (1024×1024 PNG → icns via iconutil)
  - DMG background image
  - Verify: app shows icon in Dock and Finder

- [ ] **6.3.3** Code signing and notarization CI
  - Files: `.github/workflows/ci.yml`, `.github/workflows/build.yml`
  - ci.yml: tests on push
  - build.yml: sign + notarize on tag
  - Verify: CI pipeline runs, build.yml produces notarized DMG

- [ ] **6.3.4** Auto-update endpoint setup
  - tauri-plugin-updater configuration
  - GitHub Releases JSON format
  - Verify: update check works against test release

---

## Cross-Phase Infrastructure

- [ ] **X.1** CI configuration (tests on push)
  - `cargo test`, `pytest`, `pnpm vitest run`
  - Verify: CI passes on clean run

- [ ] **X.2** Integration test: full pipeline
  - Files: `tests/integration/pipeline_test.rs`
  - Start worker, feed audio, check SSE events + DB
  - Verify: test passes

- [ ] **X.3** E2E test scaffold
  - Files: `tests/e2e/search_flow.spec.ts`
  - Playwright + Tauri WebDriver setup
  - Verify: test runner launches app

---

## Notes

- Phase 1 must be completed in full before Phase 2 begins (IPC dependency)
- Phase 3 requires HuggingFace token for pyannote models
- Phase 5 requires sqlite-vec extension compatibility test early
- Ollama is optional throughout; app must work without it
- All Apple Silicon (aarch64) only; no Intel fallback
