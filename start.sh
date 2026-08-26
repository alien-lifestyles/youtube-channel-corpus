#!/usr/bin/env bash
# One-click local UI: install if needed, start Flask, open http://localhost:3000
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

PORT="${PORT:-3000}"
URL="http://127.0.0.1:${PORT}"

pick_python() {
  local cmd
  for cmd in python3.11 python3.10 python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
      echo "$cmd"
      return 0
    fi
  done
  echo "Python 3.10+ is required." >&2
  exit 1
}

port_open() {
  python -c "import socket; s=socket.socket(); s.settimeout(0.3); raise SystemExit(0 if s.connect_ex(('127.0.0.1', ${PORT}))==0 else 1)"
}

open_browser() {
  if [[ "${YT_SCRAPER_SKIP_BROWSER:-0}" == "1" ]]; then
    return 0
  fi
  if command -v open >/dev/null 2>&1; then
    open "$URL"
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$URL"
  fi
}

PYTHON="$(pick_python)"

if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  echo "Creating virtualenv with $PYTHON..."
  "$PYTHON" -m venv "$ROOT/.venv"
fi

# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"
python -m pip install --upgrade pip >/dev/null
python -m pip install -r "$ROOT/requirements.txt"

if port_open; then
  echo "Already running at $URL"
  open_browser
  exit 0
fi

(
  for _ in $(seq 1 60); do
    if port_open; then
      open_browser
      exit 0
    fi
    sleep 0.25
  done
) &

echo "Opening $URL  —  press Ctrl+C in this window to stop."
export PORT
export YT_SCRAPER_DEBUG="${YT_SCRAPER_DEBUG:-0}"
exec python "$ROOT/app.py"
