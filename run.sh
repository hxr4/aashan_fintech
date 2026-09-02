#!/usr/bin/env bash
# Boot Aashan locally. Creates the virtualenv and installs dependencies the
# first time, so a fresh clone needs nothing but Python.
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
VENV=".venv"
PORT="${PORT:-8000}"

version_ok() {
  "$1" - <<'PY' 2>/dev/null
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
}

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "python3 not found. Install Python 3.10 or newer." >&2
  exit 1
fi

# An existing venv built on an older interpreter is the usual cause of
# 'uvicorn: command not found'. Move it aside rather than deleting it.
if [ -d "$VENV" ] && ! version_ok "$VENV/bin/python"; then
  STAMP="$(date +%Y%m%d-%H%M%S)"
  echo "Existing $VENV uses an unsupported Python; moving it to $VENV.old-$STAMP"
  mv "$VENV" "$VENV.old-$STAMP"
fi

if [ ! -d "$VENV" ]; then
  if ! version_ok "$PYTHON"; then
    echo "Aashan needs Python 3.10+. Found: $("$PYTHON" --version)" >&2
    echo "Try:  PYTHON=python3.12 ./run.sh" >&2
    exit 1
  fi
  echo "Creating $VENV ..."
  "$PYTHON" -m venv "$VENV"
fi

VPY="$VENV/bin/python"

if ! "$VPY" -c "import uvicorn, fastapi" >/dev/null 2>&1; then
  echo "Installing dependencies (first run only) ..."
  "$VPY" -m pip install --quiet --upgrade pip
  "$VPY" -m pip install --quiet -r requirements-api.txt
fi

[ -f .env ] || { [ -f .env.example ] && cp .env.example .env && echo "Created .env from .env.example"; }

echo
echo "  API      http://localhost:${PORT}"
echo "  Docs     http://localhost:${PORT}/docs"
echo "  Verify   http://localhost:${PORT}/dev"
echo
exec "$VPY" -m uvicorn app.main:app --reload --port "$PORT"
