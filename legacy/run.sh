#!/usr/bin/env bash
# ============================================================
# Espero-bot — one-command setup & launch (Linux / Steam Deck / macOS)
#
#   ./run.sh               # set up env if needed, run the robot
#   ./run.sh --test        # set up env if needed, run BLE link test
#   ./run.sh --setup-only  # just prepare the environment
#   ./run.sh --reinstall   # force reinstall of dependencies
#
# Safe on a fresh machine: finds Python 3.10–3.13, creates the venv,
# rebuilds a venv broken by moving/copying the project, installs deps
# only when requirements.txt changed.
# ============================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$ROOT/espero_env"
VENV_PY="$VENV/bin/python"
MARKER="$VENV/.requirements.sha256"

TEST=0; SETUP_ONLY=0; REINSTALL=0
for arg in "$@"; do
    case "$arg" in
        --test)       TEST=1 ;;
        --setup-only) SETUP_ONLY=1 ;;
        --reinstall)  REINSTALL=1 ;;
        *) echo "Unknown option: $arg"; exit 1 ;;
    esac
done

find_base_python() {
    # torch needs <= 3.13, pybricksdev needs >= 3.10
    for py in python3.13 python3.12 python3.11 python3.10 python3; do
        if command -v "$py" >/dev/null 2>&1; then
            if "$py" -c 'import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] <= (3,13) else 1)'; then
                command -v "$py"
                return 0
            fi
        fi
    done
    return 1
}

# ── 1. Validate the venv (catches the moved-project case) ──
venv_ok=0
if [ -x "$VENV_PY" ] && "$VENV_PY" -m pip --version >/dev/null 2>&1; then
    # venv scripts hardcode the absolute path; if the project moved, rebuild
    if grep -qs "command = .*$VENV" "$VENV/pyvenv.cfg" 2>/dev/null || \
       ! grep -qs "^command" "$VENV/pyvenv.cfg" 2>/dev/null; then
        venv_ok=1
    else
        echo "[setup] Venv was created for a different path - rebuilding..."
    fi
else
    [ -d "$VENV" ] && echo "[setup] Venv python/pip not working - rebuilding..."
fi

if [ "$venv_ok" -ne 1 ]; then
    rm -rf "$VENV"
    BASE="$(find_base_python)" || {
        echo "No Python 3.10-3.13 found. Install it (e.g. 'sudo pacman -S python' on Steam Deck) and re-run."
        exit 1
    }
    echo "[setup] Creating venv with $BASE ..."
    "$BASE" -m venv "$VENV"
    "$VENV_PY" -m pip install --upgrade pip --quiet
fi

# ── 2. Install dependencies only when requirements.txt changed ──
req_hash="$(sha256sum "$ROOT/requirements.txt" | cut -d' ' -f1)"
old_hash="$(cat "$MARKER" 2>/dev/null || true)"
if [ "$REINSTALL" -eq 1 ] || [ "$req_hash" != "$old_hash" ]; then
    echo "[setup] Installing dependencies (first time downloads ~2 GB for torch)..."
    "$VENV_PY" -m pip install -r "$ROOT/requirements.txt"
    echo "$req_hash" > "$MARKER"
else
    echo "[setup] Dependencies up to date."
fi

[ "$SETUP_ONLY" -eq 1 ] && { echo "[setup] Done."; exit 0; }

# ── 3. Launch ──
cd "$ROOT"
if [ "$TEST" -eq 1 ]; then
    exec "$VENV_PY" "$ROOT/tools/ble_link_test.py" --auto
else
    exec "$VENV_PY" "$ROOT/computer.py"
fi
