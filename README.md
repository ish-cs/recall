# Recall

Your personal conversation memory for macOS

## Overview

Recall is a local-first desktop application that continuously captures microphone audio, transcribes speech locally, identifies speakers, and makes your conversations searchable. All processing happens on your device—your audio never leaves your computer.

## Features

- **Continuous Audio Capture** — Records microphone input with voice activity detection to skip silence
- **Local Transcription** — On-device speech-to-text using Whisper
- **Speaker Diarization** — Automatically detects and separates multiple speakers
- **Speaker Recognition** — Learns recurring speakers over time; assign custom names
- **Conversation Timeline** — Browse past conversations chronologically
- **Search** — Find conversations by keywords or semantic meaning
- **Privacy-First** — All data stored locally; no cloud processing

## Tech Stack

- **Desktop Shell**: Tauri 2.x (Rust)
- **Frontend**: React 19 + TypeScript + Tailwind CSS
- **Backend**: Rust (Tauri core) + Python ML pipeline
- **Database**: SQLite
- **ML Models**: faster-whisper (transcription), pyannote.audio (diarization)

## Requirements

- macOS 13.0+ (Apple Silicon recommended)
- Python 3.12+
- Node.js 20+
- pnpm

## Development Setup

### 1. Clone the repository

```bash
git clone https://github.com/ish-cs/recall.git
cd recall
```

### 2. Install frontend dependencies

```bash
pnpm install
```

### 3. Set up Python environment

The ML worker requires Python 3.12+. Create a virtual environment:

```bash
cd ml-worker
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Or with uv (faster):

```bash
cd ml-worker
uv venv
source .venv/bin/activate
uv pip install -e .
```

### 4. Configure Tauri

Copy the example env file and configure:

```bash
cp src-tauri/.env.example src-tauri/.env
```

Edit `src-tauri/.env` with your settings (database path, etc.).

### 5. Run development server

```bash
# Start the React dev server
pnpm dev

# In another terminal, run Tauri
pnpm tauri dev
```

Or run both together:

```bash
pnpm tauri dev
```

The app will launch with hot-reload enabled.

## Building

### Build the frontend

```bash
pnpm build
```

### Build the Tauri app

```bash
pnpm tauri build
```

The built app will be in `src-tauri/target/release/bundle/dmg/` (macOS).

## Project Structure

```
recall/
├── src/                    # React frontend
│   ├── components/         # UI components
│   ├── routes/             # Page routes
│   └── stores/             # Zustand state
├── src-tauri/              # Rust backend
│   ├── src/
│   │   ├── commands/       # Tauri command handlers
│   │   ├── db/             # Database operations
│   │   ├── audio/          # Audio file management
│   │   └── worker/         # ML worker process management
│   └── migrations/         # SQLite migrations
├── ml-worker/              # Python ML pipeline
│   ├── pipeline/           # Audio processing stages
│   ├── models/             # Model management
│   └── storage/            # Data persistence
└── migrations/             # Shared migration files
```

## Architecture

The app uses a hybrid architecture:

1. **Tauri (Rust)** handles native macOS integration, database operations, file management, and process orchestration
2. **React (TypeScript)** provides the responsive UI with timeline, search, and settings views
3. **Python ML Worker** runs the audio pipeline: capture → VAD → transcription → diarization → embedding

Communication between Rust and Python happens via stdin/stdout IPC with JSON messages.

## Privacy

Recall is designed with privacy as a core principle:

- All audio processing happens locally on your machine
- No audio is sent to external services
- Data is stored in a local SQLite database
- You can delete all data at any time from Settings

**Note:** Be aware of recording consent laws in your jurisdiction. Ensure you have consent from all parties before recording conversations.

## Credits

Built with:

- [Tauri](https://tauri.app/) — Desktop framework
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — Local transcription
- [pyannote.audio](https://github.com/pyannote/pyannote-audio) — Speaker diarization
- [React](https://react.dev/) — UI framework
- [TanStack Router](https://tanstack.com/router) — Routing

## License

MIT
