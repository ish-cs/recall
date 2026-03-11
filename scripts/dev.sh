#!/usr/bin/env bash
# dev.sh — start Recall in development mode
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$PROJECT_ROOT/ml-worker/.venv"

# Activate Python venv if not already active
if [[ -z "${VIRTUAL_ENV:-}" ]]; then
  if [[ -d "$VENV_DIR" ]]; then
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
  else
    echo "WARNING: Python venv not found at $VENV_DIR. Run scripts/setup.sh first."
  fi
fi

echo "==> Starting Recall (dev)"
echo "    RECALL_DB_PATH  : ${RECALL_DB_PATH:-<default app support>}"
echo "    RECALL_AUDIO_PATH: ${RECALL_AUDIO_PATH:-<default app support>}"

cd "$PROJECT_ROOT"
exec pnpm tauri dev
