#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${PYTHO_ARENA_PYTHON:-$REPO_DIR/.venv/bin/python}"
HOST="${PYTHO_ARENA_HOST:-127.0.0.1}"
PORT="${PYTHO_ARENA_PORT:-8096}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python environment not found at $PYTHON_BIN" >&2
  echo "Run: python3.12 -m venv .venv && .venv/bin/pip install -e '.[dev]'" >&2
  exit 1
fi

if ! "$PYTHON_BIN" -c "import importlib.util; raise SystemExit(0 if all(importlib.util.find_spec(name) for name in ('fastapi', 'torch', 'uvicorn')) else 1)" >/dev/null 2>&1; then
  echo "The environment is missing FastAPI, PyTorch, or Uvicorn." >&2
  echo "Run: .venv/bin/pip install -e '.[dev]'" >&2
  exit 1
fi

cd "$REPO_DIR"
export PYTHONPATH="$REPO_DIR/src${PYTHONPATH:+:$PYTHONPATH}"
exec "$PYTHON_BIN" -m uvicorn pytho_arena.server.app:app --host "$HOST" --port "$PORT"
