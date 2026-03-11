# Conversation Memory App Build Brief

## Objective
Build a standalone macOS desktop app that runs whenever the user's Mac is open and the app is active in the background. The app should continuously capture microphone audio, transcribe speech locally, identify and separate speakers, organize conversations over time, and make them searchable through both keyword and semantic search.

This document is not the final build plan. It is the high-context product and engineering brief that an agent should use to generate a detailed implementation plan and then execute it.

---

## Product vision
The product is a local-first conversation memory system for macOS.

When the user's computer is open, the app should:
- continuously listen to microphone input
- detect when speech is happening
- transcribe speech locally in near real time
- split speech by speaker
- learn recurring speakers over time
- let the user assign real names to recurring speakers
- group transcript chunks into distinct conversations
- tag or summarize conversations by topic
- let the user search past conversations by keyword, topic, semantic meaning, time, and speaker

Example user flows:
- "When was I talking about pizza?"
- "Show my conversations with John from this week"
- "Find the conversation where we discussed AI agents and YC"
- "What did Sarah say about the budget last Tuesday?"

The app should feel like a searchable timeline of spoken life, with strong privacy guarantees and local processing by default.

---

## Non-negotiable requirements
- Must run on macOS as a standalone desktop app
- Must support long-running background operation while the machine is on
- Must process audio locally by default
- Must avoid sending microphone audio to cloud APIs in the default architecture
- Must support continuous transcription from microphone input
- Must support speaker diarization
- Must support recurring speaker recognition and user labeling
- Must store transcripts and metadata in a local database
- Must support both keyword search and semantic search
- Must have a clean, modern desktop UI
- Must be architected for later expansion into richer context capture and memory features

---

## Constraints and design principles
### 1. Local-first
Local processing is a core product principle, not an optional extra. The baseline architecture should assume no cloud dependency for transcription, diarization, storage, indexing, and search.

### 2. Reliability over novelty
A stable system that records, transcribes, and retrieves conversations well is more important than experimental features.

### 3. Efficiency matters
The app is intended to run for long periods on a laptop. CPU, memory, battery, disk usage, thermal impact, and idle behavior all matter.

### 4. Privacy matters
This product is inherently sensitive. The system must be designed with explicit consent flows, obvious recording state, strong local storage controls, and configurable retention.

### 5. Incremental buildability
The architecture should support phased delivery:
- phase 1: speech capture + transcription
- phase 2: diarization
- phase 3: speaker recognition
- phase 4: semantic indexing and search
- phase 5: polished timeline UI and settings

---

## Product requirements

### Continuous audio capture
The app should continuously capture microphone audio while enabled.

Requirements:
- start on app launch if enabled by user
- background-safe operation on macOS
- visible recording status in menu bar and app UI
- configurable pause/resume controls
- chunked audio buffering for downstream processing
- speech-aware processing so silence is not fully transcribed

Open question to clarify in final plan:
- whether to capture only the Mac microphone or also optionally system audio through loopback tools in a future version

### Real-time or near-real-time transcription
The app should convert microphone audio into text continuously.

Requirements:
- locally executed transcription
- low enough latency that the timeline feels near real time
- robust enough for multi-hour operation
- punctuated transcript output if possible
- timestamps on transcript segments
- preserve raw transcript chunks before any summarization

### Speaker diarization
The app should detect when multiple speakers are talking and assign transcript spans to speaker identities such as Speaker 1, Speaker 2, Speaker 3.

Requirements:
- segment transcript by speaker
- attach timestamps to speaker turns
- support imperfect diarization while enabling later correction
- display speaker-separated transcript in UI

### Speaker recognition and naming
The app should let the user assign a name to recurring speakers.

Requirements:
- generate reusable speaker embeddings from voice data
- compare new speaker segments against known embeddings
- surface confidence and possible matches
- let the user map recurring voices to names
- allow merge/split of incorrectly grouped speaker profiles
- keep the user's own voice distinguished from others if possible

### Conversation segmentation
The system should automatically group transcript segments into distinct conversations.

Requirements:
- split by large silence gaps
- split by speaker pattern changes if useful
- optionally split by topic shift if strong enough
- let UI present conversations as timeline entries

### Search and retrieval
The user should be able to retrieve conversations in multiple ways.

Requirements:
- keyword search over transcripts
- semantic search over embeddings
- filter by speaker, date range, and topic
- return exact transcript snippets with timestamps
- open the timeline directly to relevant moments

### Topic understanding and metadata
The app should understand broad subject matter of conversations.

Requirements:
- classify or tag transcript chunks or conversations
- generate lightweight summaries where useful
- make topics searchable
- avoid over-reliance on expensive large-model postprocessing

### Timeline and transcript UI
The app should give the user a clear way to browse their day.

Requirements:
- conversation timeline sorted by time
- expandable transcript view
- speaker-separated transcript styling
- topic tags
- search bar with fast results
- rename-speaker workflow
- settings for privacy, retention, model selection, and resource usage

---

## Recommended architecture

### Frontend
Use **Tauri + React + TypeScript** for the desktop app shell and UI.

Why:
- lighter than Electron for a long-running macOS utility
- good desktop integration
- React/TypeScript keeps UI development fast
- Rust backend in Tauri is useful for native performance-sensitive integration

Alternative:
- Electron if team prioritizes JS-only workflow over efficiency

Recommendation:
- choose Tauri unless there is a strong reason to stay fully web-stack only

### Backend orchestration
Use a **hybrid Rust + Python architecture**.

Suggested split:
- **Rust**: app shell integration, local services orchestration, lifecycle management, file/database coordination, system integration, menu bar hooks, performance-sensitive glue
- **Python**: ML/audio pipeline for transcription, diarization, speaker embeddings, summarization/classification

Why:
- best local ML tooling is still easiest in Python
- best native desktop performance and packaging on macOS is better with Rust/Tauri
- this separation reduces friction without forcing everything into Python or everything into Rust

Alternative simpler MVP:
- Python backend service + Tauri frontend, with backend launched as a local subprocess

### Audio capture
Primary recommendation:
- macOS-native audio capture via **CoreAudio / AVAudioEngine** if implemented in native layer

Practical MVP option:
- Python capture using **sounddevice** or a similar wrapper if it is stable enough for the first version

Important:
- downstream processing should operate on fixed-duration audio chunks, likely 2 to 5 seconds
- buffering and queueing should be explicit

### Voice Activity Detection
Use **Silero VAD**.

Why:
- strong open-source speech detection
- avoids wasting compute on silence
- crucial for 24/7 operation efficiency

Role in pipeline:
- microphone audio chunk
- VAD filters out silence/non-speech
- only speech segments go to transcription/diarization pipeline

### Transcription
Top recommendations:
1. **faster-whisper**
2. **whisper.cpp**

Recommended default:
- start with **faster-whisper** for the first serious build

Why:
- mature local Whisper implementation
- good performance and quality balance
- easy Python integration
- flexible model sizes

Model choice guidance:
- default practical model: `medium` or `distil-large-v3` depending on hardware tests
- higher-quality option: `large-v3` if hardware permits
- expose model choice in settings later

If optimizing aggressively for CPU-only laptops:
- evaluate `whisper.cpp` as an alternative or optional engine

### Speaker diarization
Use **pyannote.audio** for diarization.

Why:
- strongest open-source baseline for speaker diarization in practical usage
- well-suited for turn segmentation

Notes:
- diarization is often the hardest part to get reliably good
- overlapping speech remains difficult
- pipeline design should tolerate imperfect output

### Speaker identification
Use **Resemblyzer** or another speaker-embedding model for recurring voice identification.

Recommended approach:
- diarization first separates unknown speakers in a conversation
- generate speaker embeddings from representative segments
- compare against stored known speaker profiles via cosine similarity
- if confidence passes threshold, auto-suggest identity
- otherwise keep unlabeled until user names the speaker

Need in final plan:
- embedding update policy when a speaker gets more labeled data
- thresholds and confidence tuning
- handling false merges and false splits

### Topic understanding and semantic metadata
For lightweight topic classification and summaries, use a **small local LLM** through **Ollama** or a direct local inference path.

Possible models:
- Qwen family
- Mistral family
- Phi family

Recommendation:
- keep summarization/tagging as a postprocessing step on transcript segments or completed conversations
- do not put a large-model step in the hot path of real-time transcription

### Embeddings and search
Use a local embeddings model for semantic retrieval.

Recommended models to evaluate:
- `bge-small`
- `nomic-embed-text`

Recommended storage/indexing path:
- **SQLite** as core data store
- **sqlite-vss** if stable enough in target environment, or another local vector indexing option
- alternative: Chroma for faster iteration, though SQLite is simpler for a desktop product

Recommendation:
- favor SQLite-centric architecture if possible for operational simplicity

---

## End-to-end pipeline
The system should roughly operate as follows:

1. App launches and starts audio service
2. Audio is captured continuously from microphone
3. Audio is chunked into short windows
4. Voice activity detection filters non-speech
5. Speech segments are queued for transcription
6. Diarization runs on the relevant segment window
7. Transcript text and timestamps are produced
8. Transcript spans are assigned speaker labels
9. Speaker embeddings are generated or updated
10. Transcript chunks are grouped into conversations
11. Conversations or transcript chunks are tagged/summarized asynchronously
12. Embeddings are stored for semantic retrieval
13. UI timeline updates with new conversation data

This should be architected as a pipeline with explicit queues, workers, and persistence.

---

## Data model recommendations
Use SQLite with clear tables and indices.

### Tables

#### conversations
Fields:
- id
- started_at
- ended_at
- title or generated label
- summary
- topic_tags
- created_at
- updated_at

#### transcript_segments
Fields:
- id
- conversation_id
- started_at
- ended_at
- speaker_instance_id
- speaker_profile_id nullable
- raw_text
- normalized_text
- embedding reference or inline vector strategy
- confidence fields if useful
- created_at

#### speaker_profiles
Fields:
- id
- display_name nullable
- is_user boolean if supported
- canonical_embedding or embedding strategy
- notes optional
- created_at
- updated_at

#### speaker_instances
Fields:
- id
- conversation_id
- diarization_label
- linked_speaker_profile_id nullable
- segment_count
- confidence

#### topic_tags
Fields:
- id
- label

#### conversation_topic_links
Fields:
- conversation_id
- topic_tag_id

#### app_settings
Fields:
- key
- value

#### retention_policies or audit tables
Optional but recommended for privacy-sensitive lifecycle control.

---

## UI and UX recommendations

### Main surfaces
1. **Timeline view**
   - chronological list of conversations
   - each card shows time, likely topic, participants if known, short summary

2. **Conversation detail view**
   - full transcript
   - speaker-colored turns
   - speaker naming controls
   - search-in-conversation
   - timestamps for navigation

3. **Global search view**
   - keyword and semantic search
   - filters by date, speaker, topic
   - jump directly to transcript snippet

4. **Speakers view**
   - list of learned speakers
   - rename / merge / correct matches
   - mark user voice if desired

5. **Settings view**
   - model choice
   - recording controls
   - retention limits
   - battery/performance mode
   - storage usage
   - export/delete data
   - privacy notices and consent state

### UX principles
- recording state must always be obvious
- search must be fast
- speaker correction flow must be simple
- transcript readability matters more than flashy visual design
- timeline must feel like a memory browser, not a raw log viewer

---

## Performance and efficiency strategy
This product will fail if it is too heavy. The build plan should explicitly optimize for long-running laptop usage.

### Key efficiency strategies
- use VAD aggressively to reduce transcription workload
- batch transcription in sensible windows instead of ultra-fine granularity
- make heavy enrichment asynchronous
- avoid running speaker/topic/summary models on every millisecond of data
- use configurable model sizes
- throttle work when the machine is resource constrained
- allow lower-power mode in settings

### Example hot path vs cold path split
**Hot path**
- capture audio
- VAD
- transcription
- basic diarization
- persist transcript chunks

**Cold path**
- speaker identity refinement
- topic extraction
- summarization
- embedding generation for semantic search
- cleanup/retention jobs

This split is important.

---

## Privacy, consent, and risk considerations
This product has serious legal and ethical risk. The final plan must treat privacy and consent as first-class product requirements.

Must include:
- explicit onboarding consent and disclosure
- persistent visible recording status
- easy pause and disable
- clear local-storage explanation
- retention controls
- delete all data option
- export data option
- jurisdiction-aware warning about recording laws and consent requirements

Important product truth:
- some places require all-party consent for recording conversations
- the product can create significant user risk if this is ignored

The build plan should include a privacy and compliance section, not just engineering.

---

## Packaging and runtime considerations
The final plan should address:
- macOS permissions for microphone access
- app startup behavior
- background behavior and menu bar integration
- local model download/storage strategy
- log handling
- crash recovery
- database migrations
- packaging and signing strategy for macOS distribution

If shipping beyond a prototype, the plan should cover:
- notarization
- auto-update strategy
- migration strategy for model/index versions

---

## Suggested phased roadmap

### Phase 1: transcript pipeline MVP
Goal:
- microphone capture
- VAD
- local transcription
- store transcript chunks in SQLite
- basic transcript viewer

Success criteria:
- app can run for long periods
- user can browse raw transcript over time

### Phase 2: conversation timeline MVP
Goal:
- segment transcript into conversations
- show timeline cards
- support keyword search

Success criteria:
- user can find a conversation by time and words spoken

### Phase 3: diarization and speaker-separated transcript
Goal:
- assign speaker turns
- render speaker-separated transcript

Success criteria:
- conversations become readable between multiple participants

### Phase 4: recurring speaker recognition
Goal:
- generate speaker embeddings
- let user assign names
- auto-suggest future matches

Success criteria:
- repeated real-world contacts become recognizable in UI

### Phase 5: semantic retrieval and topic understanding
Goal:
- embeddings
- semantic search
- topic tags
- lightweight summaries

Success criteria:
- user can search by concept, not just exact words

### Phase 6: polish and hardening
Goal:
- resource tuning
- settings
- retention
- speaker correction UX
- packaging and distribution hardening

Success criteria:
- usable as an everyday background tool

---

## Major technical risks
The final plan should explicitly mitigate these.

### 1. Resource usage
Continuous audio + transcription can consume too much CPU/battery.

Mitigation:
- VAD
- configurable model size
- asynchronous enrichment
- power mode settings

### 2. Diarization quality
Multi-speaker and overlapping audio are difficult.

Mitigation:
- accept imperfect baseline
- expose correction tools
- separate diarization and identity layers

### 3. Speaker identity drift
Voice embedding matches may be wrong over time.

Mitigation:
- threshold tuning
- confidence display
- user correction loop
- careful profile update policy

### 4. Search quality
Semantic search can be noisy if chunking is bad.

Mitigation:
- test chunking strategies
- combine keyword + semantic search
- store exact timestamps/snippets

### 5. Privacy/compliance risk
The product itself can create legal exposure.

Mitigation:
- strong disclosures
- obvious controls
- consent guidance
- local-first defaults

---

## Build recommendations for the planning agent
The next agent should use this document to generate a larger execution plan.

That larger build plan should include:
- chosen architecture and why it was selected over alternatives
- exact repo structure
- exact components/services/modules
- interface contracts between frontend, backend, and ML workers
- data schemas
- queue/pipeline design
- detailed milestone plan
- package choices with rationale
- local development setup
- testing strategy
- model management strategy
- macOS permission and packaging details
- privacy and consent requirements
- performance tuning plan
- future extensibility ideas

The plan should not stay abstract. It should become implementation-ready.

---

## Strong default stack recommendation
If the planning agent must choose a default stack without over-exploring, use this:
- **Desktop shell:** Tauri
- **UI:** React + TypeScript
- **Native/backend orchestration:** Rust
- **ML worker:** Python
- **Audio capture:** CoreAudio/AVAudioEngine or stable wrapper
- **VAD:** Silero VAD
- **Transcription:** faster-whisper
- **Diarization:** pyannote.audio
- **Speaker embeddings:** Resemblyzer
- **Local LLM for summaries/tags:** Ollama with a small model
- **Database:** SQLite
- **Semantic retrieval:** SQLite + vector index path evaluated during implementation

This is the best default balance of practicality, performance, local-first operation, and build speed.

---

## Explicit questions the planning agent should resolve before coding
Because the user does not want assumptions, the generated build plan should surface and resolve these questions before implementation begins:
- Should the product capture only microphone input or eventually support system audio too?
- Is menu bar only support required, or full dock app + menu bar?
- Should audio be stored at all, or only transcripts and embeddings?
- What retention period should be default?
- Should the user's own speaker profile be enrolled during onboarding?
- What hardware target should be optimized first: Apple Silicon only, or Intel Macs too?
- What transcription latency target is acceptable?
- What minimum search quality bar defines success for MVP?

The agent should ask these before locking implementation choices where needed.

---

## Output instruction for the next agent
Generate a detailed `BUILD_PLAN.md` for this app.

That file should:
- be implementation-oriented
- include architecture, stack, repo structure, milestones, schemas, modules, interfaces, and test plan
- call out tradeoffs clearly
- ask clarifying questions wherever requirements are still underspecified
- optimize for local-first macOS development
- avoid unnecessary complexity
- be strong enough that a coding agent could execute it phase by phase

