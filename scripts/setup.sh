#!/usr/bin/env bash
# setup.sh — one-time dev environment setup for Recall
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "==> Recall dev environment setup"
echo "    Project root: $PROJECT_ROOT"

# ── Prerequisites check ────────────────────────────────────────
command -v rustup >/dev/null 2>&1 || { echo "ERROR: rustup not found. Install from https://rustup.rs"; exit 1; }
command -v node >/dev/null 2>&1  || { echo "ERROR: node not found. Install Node.js >= 18"; exit 1; }
command -v pnpm >/dev/null 2>&1  || { echo "ERROR: pnpm not found. Run: npm install -g pnpm"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 not found. Install Python >= 3.11"; exit 1; }

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
if [[ "$PYTHON_MAJOR" -lt 3 ]] || [[ "$PYTHON_MAJOR" -eq 3 && "$PYTHON_MINOR" -lt 11 ]]; then
  echo "ERROR: Python >= 3.11 required (found $PYTHON_VERSION)"
  exit 1
fi

echo "    Rust: $(rustc --version)"
echo "    Node: $(node --version)"
echo "    pnpm: $(pnpm --version)"
echo "    Python: $PYTHON_VERSION"

# ── Rust target ────────────────────────────────────────────────
echo "==> Ensuring Rust Apple Silicon target"
rustup target add aarch64-apple-darwin 2>/dev/null || true

# ── Node deps ──────────────────────────────────────────────────
echo "==> Installing Node dependencies"
cd "$PROJECT_ROOT"
pnpm install

# ── Python venv ────────────────────────────────────────────────
echo "==> Setting up Python virtual environment"
VENV_DIR="$PROJECT_ROOT/ml-worker/.venv"
if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

pip install --upgrade pip --quiet
pip install -r "$PROJECT_ROOT/ml-worker/requirements.txt" --quiet

echo "==> Python environment ready: $VENV_DIR"

# ── Verify Cargo build ─────────────────────────────────────────
echo "==> Checking Rust build"
cd "$PROJECT_ROOT/src-tauri"
cargo check --quiet

echo ""
echo "✓ Setup complete. Run 'scripts/dev.sh' to start the app."
