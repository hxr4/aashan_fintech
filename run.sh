#!/usr/bin/env bash
# Boot Aashan locally. Creates the virtualenv and installs dependencies the
# first time, so a fresh clone needs nothing but a Python 3.10 or newer.
set -euo pipefail
cd "$(dirname "$0")"

VENV=".venv"
PORT="${PORT:-8000}"

version_ok() {
  [ -x "$1" ] || command -v "$1" >/dev/null 2>&1 || return 1
  "$1" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
}

# FastAPI, Starlette, uvicorn, psycopg and numpy all require >= 3.10, so an
# older interpreter cannot install the dependency set at all. macOS still ships
# 3.9 as `python3`, so look for a newer one rather than stopping at the default.
find_python() {
  if [ -n "${PYTHON:-}" ]; then
    version_ok "$PYTHON" && { echo "$PYTHON"; return 0; }
    echo "PYTHON=$PYTHON is not 3.10 or newer." >&2
    return 1
  fi
  local candidate
  for candidate in \
      python3.14 python3.13 python3.12 python3.11 python3.10 \
      /opt/homebrew/bin/python3.14 /opt/homebrew/bin/python3.13 \
      /opt/homebrew/bin/python3.12 /opt/homebrew/bin/python3.11 \
      /opt/homebrew/bin/python3.10 /opt/homebrew/bin/python3 \
      /usr/local/bin/python3.13 /usr/local/bin/python3.12 \
      /usr/local/bin/python3.11 /usr/local/bin/python3.10 /usr/local/bin/python3 \
      /Library/Frameworks/Python.framework/Versions/Current/bin/python3 \
      python3; do
    if version_ok "$candidate"; then
      command -v "$candidate" 2>/dev/null || echo "$candidate"
      return 0
    fi
  done
  return 1
}

# A venv built on an older interpreter is the usual cause of
# 'no such file or directory: .venv/bin/python'. Move it aside, never delete it.
if [ -d "$VENV" ] && ! version_ok "$VENV/bin/python"; then
  STAMP="$(date +%Y%m%d-%H%M%S)"
  echo "Existing $VENV uses an unsupported Python; moving it to $VENV.old-$STAMP"
  mv "$VENV" "$VENV.old-$STAMP"
fi

if [ ! -d "$VENV" ]; then
  if ! PY="$(find_python)"; then
    cat >&2 <<'MSG'

  Aashan needs Python 3.10 or newer, and none was found.

  macOS ships 3.9 as `python3`, which cannot install FastAPI or psycopg.

    brew install python@3.12       # then re-run ./run.sh

  No Homebrew? Install from https://www.python.org/downloads/macos/
  Already have one somewhere else?

    PYTHON=/full/path/to/python3.12 ./run.sh

MSG
    exit 1
  fi
  echo "Using $("$PY" --version 2>&1) at $PY"
  echo "Creating $VENV ..."
  "$PY" -m venv "$VENV"
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
