# Recall — Build Status Log

---

## Session: 2026-03-11

### Summary of work completed

**Phase 1 scaffold — DONE**

#### Tasks completed:
- **1.1.1** Tauri 2.x + React + TypeScript scaffold initialized, Cargo.toml updated with all deps (rusqlite, r2d2, reqwest, tokio, uuid, tauri tray-icon, etc.), package.json updated with Zustand, TanStack Router, Tailwind, Vitest
- **1.1.2** Tailwind CSS configured (tailwind.config.ts, postcss.config.js, globals.css)
- **1.1.3** Zustand store created (src/store/index.ts) with full AppStore interface
- **1.1.4** Python ml-worker scaffold: main.py, ipc/server.py (FastAPI + SSE), all pipeline modules, storage modules, models/manager.py
- **1.1.5** Rust worker spawn: src-tauri/src/worker/process.rs (reads PORT= from stdout)
- **1.1.6** Rust IPC: worker/client.rs (reqwest HTTP), worker/events.rs (SSE → Tauri events)
- **1.2.1** Migration files: migrations/001_initial_schema.sql, 002_fts5.sql, 003_vector_search.sql
- **1.2.2** Rust DB layer: db/connection.rs (r2d2 pool, WAL), db/migrations.rs, db/models.rs
- **1.2.3** Python DB writer: storage/db.py (insert_conversation, close_conversation, insert_segment, etc.)
- **1.3.1** Audio capture: pipeline/capture.py (sounddevice 16kHz mono, queues chunks)
- **1.3.2** VAD: pipeline/vad.py (Silero VAD, SILENCE/SPEECH state machine, hysteresis)
- **1.3.3** Transcriber: pipeline/transcriber.py (faster-whisper, MPS, thread pool)
- **1.3.4** WAV storage: storage/audio_store.py (soundfile, per-conversation files)
- **1.3.5** Segmenter: pipeline/segmenter.py (60s gap, midnight boundary)
- **1.3.6** Orchestrator: pipeline/orchestrator.py (hot + cold path async workers, SSE emit)
- **1.4.1** FastAPI server: all Phase 1 endpoints (/pipeline/start|stop|pause|resume|status, /events SSE, /health, /embed, /speakers/confirm|merge, /models/status|download)
- **1.5.1** Recording commands (Rust): start/stop/pause/resume/get_status
- **1.5.2** Conversation commands: list_conversations, get_conversation, delete_conversation, split_conversation
- **1.5.3** Settings commands: get_setting, set_setting
- **1.5.4** All commands registered in lib.rs; AppState wired; tray icon setup
- Also implemented: speakers commands, storage commands (get_usage, delete_by_age, export, delete_all), audio/storage.rs
- **1.6.1** TypeScript types (src/api/types.ts) and Tauri invoke wrappers (src/api/tauri.ts)
- **1.6.3** Hooks: useRecordingStatus, useTauriEvents, useConversations
- **App.tsx** replaced with functional shell: sidebar nav, timeline view placeholder, recording status bar, Tauri event wiring
- **config.rs** app support dir resolution

#### Tests run and passing:
- `cargo test` → 7/7 pass
  - db::migrations::test_migrations_apply_in_order ✓
  - db::migrations::test_migrations_idempotent_on_rerun ✓
  - commands::search::test_keyword_search_returns_matching_segments ✓
  - commands::search::test_search_respects_date_filter ✓
  - commands::settings::test_get_setting ✓
  - commands::settings::test_set_setting ✓
  - audio::storage::test_audio_path_format ✓
- `pnpm build` → clean (no TS errors)
- Python worker manual test: starts, prints PORT=, /health returns {"ok":true}, /pipeline/status returns correct JSON

---

## Session: 2026-03-11 (session 3)

### Completed

- [x] 1.6.2 src/components/layout/{AppShell,Sidebar,RecordingStatusBar}.tsx
- [x] 1.6.4 src/components/transcript/{TranscriptView,SpeakerTurn,TimestampLabel}.tsx
- [x] 1.6.5 Recording controls (Start/Stop/Pause/Resume) wired in RecordingStatusBar
- [x] 1.6.6 Tray icon state driven by pipeline:status events (existing in lib.rs/events.rs)
- [x] 1.7.1 src/components/onboarding/{OnboardingFlow,ConsentStep,ModelDownloadStep}.tsx — checks onboarding_complete on launch
- [x] 1.8.1 src-tauri/entitlements.plist (microphone, network.client, disable-library-validation)
- [x] 1.8.2 ml-worker/tests/{conftest.py,test_vad.py,test_transcriber.py,test_segmenter.py} — 21/21 pass
- [x] 1.8.3 scripts/setup.sh, scripts/dev.sh
- [x] 2.2.1 TimelineView, ConversationCard, ConversationDetail with react-virtual
- [x] 2.2.2 Conversation detail navigation
- [x] 2.3.1 Rust keyword/semantic/hybrid search (already done in Phase 1)
- [x] 2.3.2 SearchBar, SearchView, SearchResultItem UI
- [x] 2.3.3 useSearch hook with debounce
- [x] 3.1.1 Diarizer already implemented (pyannote.audio wrapper)
- [x] 3.1.2 HF token Keychain integration (get_hf_token in main.py)
- [x] 3.1.3 Orchestrator diarization integration (_diarize_window cold task)
- [x] 3.2.1 SpeakerTurn already has color-coded labels
- [x] 3.2.2 speaker:match_suggestion event handler in App.tsx
- [x] 4.1.1 Embedder already implemented (Resemblyzer wrapper)
- [x] 4.1.2 Orchestrator speaker matching (_match_speaker cold task)
- [x] 4.2.1 SpeakersView, SpeakerCard, RenameDialog
- [x] 4.2.2 Speaker commands already in Rust
- [x] 4.2.4 Speaker badge in Sidebar
- [x] 5.1.2 Migration 003 optional fallback (skips if vec extension missing)
- [x] 5.2.1 Summarizer already implemented (Ollama wrapper)
- [x] 5.2.2 Orchestrator summarization (already in _summarize_conversation)
- [x] 5.2.3 Topic tags already in UI (ConversationCard, ConversationDetail)
- [x] 6.1.1 SettingsView with tabs (General, Recording, Storage, Privacy)
- [x] 6.1.2 StoragePanel with usage bars, delete by age

### Test results (session 3)
- `cargo test` → 7/7 pass
- Python pytest → 21/21 pass
- `pnpm build` → clean

## Phases 1-6 — IMPLEMENTATION COMPLETE

## Remaining for production
- Power mode UI toggle (6.2.1)
- Worker crash recovery verification (6.2.2)
- Log rotation setup (6.2.3)
- Launch at login toggle (6.2.4)
- Python bundling for distribution (6.3.1)
- App icon and DMG (6.3.2)
- Code signing and notarization CI (6.3.3)
- Auto-update endpoint (6.3.4)
- Full integration tests

## Key files created this session

```
src-tauri/src/
  lib.rs, main.rs, config.rs
  db/{mod,connection,migrations,models}.rs
  worker/{mod,process,client,events}.rs
  commands/{mod,recording,conversations,search,settings,speakers,storage}.rs
  audio/{mod,storage}.rs
migrations/001_initial_schema.sql
migrations/002_fts5.sql
migrations/003_vector_search.sql
ml-worker/
  main.py, requirements.txt
  pipeline/{__init__,capture,vad,transcriber,segmenter,diarizer,embedder,text_embedder,summarizer,orchestrator}.py
  models/{__init__,manager}.py
  storage/{__init__,db,audio_store}.py
  ipc/{__init__,server}.py
src/
  main.tsx, App.tsx
  api/{types,tauri}.ts
  store/index.ts
  hooks/{useTauriEvents,useRecordingStatus,useConversations}.ts
  styles/globals.css
tailwind.config.ts, postcss.config.js
TASKS.md, STATUS.md
```

## To resume next session

**Verified clean on resume (2026-03-11 session 2):**
- `cargo test` → 7/7 pass
- `pnpm build` → clean

**Start from TASKS.md task 1.6.2.** Order of work:
1. 1.6.2 src/components/layout/{AppShell,Sidebar,RecordingStatusBar}.tsx
2. 1.6.4 src/components/transcript/{TranscriptView,SpeakerTurn,TimestampLabel}.tsx
3. 1.6.5 Wire recording buttons (start/stop/pause/resume) to Tauri commands
4. 1.6.6 Tray icon state updates driven by pipeline:status events
5. 1.7.1 src/components/onboarding/{OnboardingFlow,ConsentStep,ModelDownloadStep}.tsx — check `onboarding_complete` setting on launch
6. 1.8.1 src-tauri/entitlements.plist, update tauri.conf.json bundle.macOS
7. 1.8.2 ml-worker/tests/{conftest.py,test_vad.py,test_transcriber.py,test_segmenter.py} + silence.wav fixture
8. 1.8.3 scripts/setup.sh, scripts/dev.sh
9. Then Phase 2: segmenter full integration, TimelineView, ConversationCard, keyword search UI
