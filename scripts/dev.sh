#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="$ROOT/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  echo "ERROR: Project virtual environment not found at .venv/bin/python"
  echo "Create it and install the project's Python requirements before running npm run dev."
  exit 1
fi

if ! "$PYTHON" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
  echo "ERROR: FastAPI/Uvicorn are missing from .venv."
  echo "Install the project's backend requirements, then run npm run dev again."
  exit 1
fi

if [[ ! -d "$ROOT/node_modules" ]]; then
  echo "ERROR: node_modules is missing. Run npm install first."
  exit 1
fi

BACKEND_PID=""
cleanup() {
  echo
  echo "Stopping Coastal Erosion Platform..."
  if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "Starting FastAPI backend with project .venv on http://127.0.0.1:8000"
"$PYTHON" -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

echo "Starting Vite frontend on http://localhost:5173"
npm run dev:frontend -- --host 127.0.0.1
