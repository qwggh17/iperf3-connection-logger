#!/usr/bin/env bash
set -u

LAUNCHER_VERSION="2026-06-16-WSL-TMP-PID-FINAL-v4"
MODE="${1:-}"
WSL_DEBUG="/tmp/connect_logger_gui_debug.log"

if [ "$MODE" = "start" ]; then
    SCRIPT="${2:-}"
    LOG="${3:-}"
    PID_PATH="${4:-}"
    IP="${5:-}"
    PORT="${6:-}"

    DIR="$(dirname "$SCRIPT")"

    {
        echo "===== GUI WSL PREFLIGHT ====="
        echo "LAUNCHER_VERSION=$LAUNCHER_VERSION"
        echo "DATE=$(date '+%Y-%m-%d %H:%M:%S')"
        echo "USER=$(whoami)"
        echo "ID=$(id)"
        echo "DIR=$DIR"
        echo "SCRIPT=$SCRIPT"
        echo "LOG=$LOG"
        echo "PID_PATH=$PID_PATH"
        echo "IP=$IP PORT=$PORT"
        echo "WSL_DEBUG=$WSL_DEBUG"
        echo "--- mount /mnt/c ---"
        mount | grep ' /mnt/c ' || true
        echo "--- ls dir ---"
        ls -ld "$DIR" || true
        echo "--- ls files before start ---"
        ls -l "$SCRIPT" "$LOG" 2>/dev/null || true
        echo "--- pid directory ---"
        ls -ld "$(dirname "$PID_PATH")" || true
    } | tee -a "$WSL_DEBUG"

    cd "$DIR" || {
        echo "ERROR: cannot cd to DIR: $DIR" | tee -a "$WSL_DEBUG"
        exit 10
    }

    if [ ! -f "$SCRIPT" ]; then
        echo "ERROR: script not found: $SCRIPT" | tee -a "$WSL_DEBUG"
        exit 14
    fi

    if [ ! -f "$LOG" ]; then
        echo "ERROR: LOG file does not exist. Windows GUI should create it first: $LOG" | tee -a "$WSL_DEBUG"
        exit 11
    fi

    if [ ! -w "$LOG" ]; then
        echo "ERROR: LOG file is not writable from WSL: $LOG" | tee -a "$WSL_DEBUG"
        ls -l "$LOG" | tee -a "$WSL_DEBUG" || true
        exit 11
    fi

    rm -f "$PID_PATH" 2>/dev/null || true

    touch "$PID_PATH" 2>/tmp/gui_touch_pid_error.txt || {
        echo "ERROR: cannot touch PID_PATH: $PID_PATH" | tee -a "$WSL_DEBUG"
        cat /tmp/gui_touch_pid_error.txt | tee -a "$WSL_DEBUG"
        ls -ld "$(dirname "$PID_PATH")" | tee -a "$WSL_DEBUG" || true
        exit 13
    }

    {
        echo ""
        echo "===== GUI START $(date '+%Y-%m-%d %H:%M:%S') ====="
        echo "LAUNCHER_VERSION=$LAUNCHER_VERSION"
        echo "DIR=$DIR"
        echo "SCRIPT=$SCRIPT"
        echo "LOG=$LOG"
        echo "PID_PATH=$PID_PATH"
        echo "IP=$IP PORT=$PORT"
        echo "whoami=$(whoami)"
        echo "pwd=$(pwd)"
        echo "bash=$(command -v bash || echo NOT_FOUND)"
        echo "iperf3=$(command -v iperf3 || echo NOT_FOUND)"
        echo "nc=$(command -v nc || echo NOT_FOUND)"
    } >> "$WSL_DEBUG" 2>&1

    chmod +x "$SCRIPT" 2>/dev/null || true
    rm -f "$PID_PATH"

    setsid bash "$SCRIPT" "$IP" "$PORT" >> "$WSL_DEBUG" 2>&1 < /dev/null &
    PID="$!"

    echo "$PID" > "$PID_PATH"

    sleep 1

    if kill -0 "$PID" 2>/dev/null; then
        echo "STARTED PID=$PID" | tee -a "$WSL_DEBUG"
        exit 0
    else
        echo "FAILED IMMEDIATELY PID=$PID" | tee -a "$WSL_DEBUG"
        exit 20
    fi

elif [ "$MODE" = "stop" ]; then
    PID_PATH="${2:-}"

    PID=""

    if [ -f "$PID_PATH" ]; then
        PID="$(cat "$PID_PATH" 2>/dev/null || true)"
    fi

    {
        echo ""
        echo "===== GUI STOP $(date '+%Y-%m-%d %H:%M:%S') PID=$PID ====="
        echo "LAUNCHER_VERSION=$LAUNCHER_VERSION"
        echo "PID_PATH=$PID_PATH"
    } >> "$WSL_DEBUG" 2>&1

    if [ -n "$PID" ]; then
        if kill -0 "$PID" 2>/dev/null; then
            kill -TERM "-$PID" 2>/dev/null || kill -TERM "$PID" 2>/dev/null || true
            sleep 1
            kill -KILL "-$PID" 2>/dev/null || kill -KILL "$PID" 2>/dev/null || true
        fi
    fi

    rm -f "$PID_PATH"
    echo "STOPPED" | tee -a "$WSL_DEBUG"
    exit 0

elif [ "$MODE" = "status" ]; then
    PID_PATH="${2:-}"

    if [ ! -f "$PID_PATH" ]; then
        echo "NO_PID_FILE"
        exit 3
    fi

    PID="$(cat "$PID_PATH" 2>/dev/null || true)"

    if [ -z "$PID" ]; then
        echo "EMPTY_PID"
        exit 4
    fi

    if kill -0 "$PID" 2>/dev/null; then
        echo "RUNNING PID=$PID"
        exit 0
    else
        echo "NOT_RUNNING PID=$PID"
        exit 5
    fi

elif [ "$MODE" = "debug" ]; then
    if [ -f "$WSL_DEBUG" ]; then
        tail -n 180 "$WSL_DEBUG"
    else
        echo "WSL debug file does not exist: $WSL_DEBUG"
    fi
    exit 0

elif [ "$MODE" = "clear-debug" ]; then
    rm -f "$WSL_DEBUG"
    echo "CLEARED"
    exit 0

else
    echo "Usage:"
    echo "  $0 start SCRIPT LOG PID_PATH IP PORT"
    echo "  $0 stop PID_PATH"
    echo "  $0 status PID_PATH"
    echo "  $0 debug"
    echo "  $0 clear-debug"
    exit 64
fi
