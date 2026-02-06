#!/usr/bin/env bash
#
# CosyVoice Daemon Management
#
# Usage:
#   ./cosyvoice-daemon.sh start   - Start the daemon
#   ./cosyvoice-daemon.sh stop    - Stop the daemon
#   ./cosyvoice-daemon.sh status  - Check daemon status
#   ./cosyvoice-daemon.sh restart - Restart the daemon
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COSYVOICE_DIR="$SCRIPT_DIR/../speech/cosyvoice"
VENV_DIR="$COSYVOICE_DIR/.venv"
PID_FILE="$COSYVOICE_DIR/.daemon.pid"
LOG_FILE="$COSYVOICE_DIR/.daemon.log"

PORT="${COSYVOICE_PORT:-8765}"
HOST="${COSYVOICE_HOST:-127.0.0.1}"
IDLE_TIMEOUT="${COSYVOICE_IDLE_TIMEOUT:-30}"

check_venv() {
    if [[ ! -d "$VENV_DIR" ]]; then
        echo "ERROR: CosyVoice venv not found. Run: make cosyvoice-setup"
        exit 1
    fi
}

is_running() {
    if [[ -f "$PID_FILE" ]]; then
        local pid
        pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
        # Stale PID file
        rm -f "$PID_FILE"
    fi
    return 1
}

get_pid() {
    if [[ -f "$PID_FILE" ]]; then
        cat "$PID_FILE"
    fi
}

wait_for_ready() {
    local max_wait=120  # 2 minutes for model loading
    local waited=0
    echo -n "Waiting for model to load"
    while [[ $waited -lt $max_wait ]]; do
        if curl -s "http://$HOST:$PORT/health" >/dev/null 2>&1; then
            echo " ready!"
            return 0
        fi
        echo -n "."
        sleep 2
        waited=$((waited + 2))
    done
    echo " timeout!"
    return 1
}

cmd_start() {
    check_venv

    if is_running; then
        echo "Daemon already running (PID $(get_pid))"
        exit 0
    fi

    echo "Starting CosyVoice daemon..."
    echo "  Port: $PORT"
    echo "  Idle timeout: $IDLE_TIMEOUT minutes"

    # Install FastAPI/uvicorn if needed
    if ! "$VENV_DIR/bin/python" -c "import fastapi, uvicorn" 2>/dev/null; then
        echo "Installing FastAPI and uvicorn..."
        "$VENV_DIR/bin/pip" install -q fastapi uvicorn
    fi

    # Start daemon in background
    COSYVOICE_PORT="$PORT" \
    COSYVOICE_HOST="$HOST" \
    COSYVOICE_IDLE_TIMEOUT="$IDLE_TIMEOUT" \
    nohup "$VENV_DIR/bin/python" "$SCRIPT_DIR/cosyvoice-daemon.py" \
        > "$LOG_FILE" 2>&1 &

    local pid=$!
    echo "$pid" > "$PID_FILE"
    echo "Daemon started (PID $pid)"

    # Wait for it to be ready
    if wait_for_ready; then
        echo "CosyVoice daemon is ready at http://$HOST:$PORT"
    else
        echo "WARNING: Daemon may still be loading. Check: $0 status"
    fi
}

cmd_stop() {
    if ! is_running; then
        echo "Daemon not running"
        rm -f "$PID_FILE"
        exit 0
    fi

    local pid
    pid=$(get_pid)
    echo "Stopping daemon (PID $pid)..."

    # Try graceful shutdown first
    curl -s -X POST "http://$HOST:$PORT/shutdown" >/dev/null 2>&1 || true
    sleep 1

    # Force kill if still running
    if kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
        sleep 1
    fi

    # Really force kill
    if kill -0 "$pid" 2>/dev/null; then
        kill -9 "$pid" 2>/dev/null || true
    fi

    rm -f "$PID_FILE"
    echo "Daemon stopped"
}

cmd_status() {
    if ! is_running; then
        echo "Daemon not running"
        exit 1
    fi

    local pid
    pid=$(get_pid)
    echo "Daemon running (PID $pid)"

    # Get health info
    local health
    if health=$(curl -s "http://$HOST:$PORT/health" 2>/dev/null); then
        echo "Health: $health"
    else
        echo "Health: not responding (may still be loading)"
    fi
}

cmd_restart() {
    cmd_stop
    sleep 1
    cmd_start
}

cmd_logs() {
    if [[ -f "$LOG_FILE" ]]; then
        tail -f "$LOG_FILE"
    else
        echo "No log file found"
    fi
}

# Main
case "${1:-}" in
    start)   cmd_start ;;
    stop)    cmd_stop ;;
    status)  cmd_status ;;
    restart) cmd_restart ;;
    logs)    cmd_logs ;;
    *)
        echo "Usage: $0 {start|stop|status|restart|logs}"
        exit 1
        ;;
esac
