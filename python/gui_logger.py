import os
import shlex
import shutil
import subprocess
import tkinter as tk
from datetime import datetime
from pathlib import Path, PureWindowsPath
from tkinter import messagebox


GUI_VERSION = "2026-06-16-WSL-TMP-PID-FINAL-v4"

SCRIPT_DIR = Path(__file__).resolve().parent
BASH_SCRIPT = SCRIPT_DIR / "connect_logger.sh"
LOG_FILE = SCRIPT_DIR / "connect_log.txt"
DEBUG_FILE = SCRIPT_DIR / "connect_logger_debug.txt"
LAUNCHER_FILE = SCRIPT_DIR / "connect_logger_launcher.sh"

DEFAULT_IP = "192.168.1.77"
DEFAULT_PORT = "4444"


WSL_DISTRO = ""

# PID хранится только внутри Linux/WSL.
# Здесь не должно быть Windows-пути и не должно быть PID-файла в рабочей папке.
WSL_PID_FILE = "/tmp/connect_logger_gui.pid"
WSL_DEBUG_PATH = "/tmp/connect_logger_gui_debug.log"

GUI_MESSAGES_MAX = 280
LOG_LINES_MAX = 180

gui_messages = []
log_cache = ""


def windows_path_to_wsl(path):
    windows_path = PureWindowsPath(str(Path(path).resolve()))
    drive = windows_path.drive.rstrip(":").lower()

    if not drive:
        raise RuntimeError(f"Не удалось определить диск Windows для пути: {path}")

    parts = windows_path.parts[1:]
    wsl_path = f"/mnt/{drive}"

    if parts:
        wsl_path += "/" + "/".join(parts)

    return wsl_path


def get_wsl_base_command():
    command = ["wsl.exe"]

    if WSL_DISTRO:
        command.extend(["-d", WSL_DISTRO])

    return command


def run_wsl(command, timeout=20):
    kwargs = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "timeout": timeout,
    }

    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    return subprocess.run(
        get_wsl_base_command() + ["bash", "-lc", command],
        **kwargs
    )


def append_debug(text):
    try:
        DEBUG_FILE.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open(DEBUG_FILE, "a", encoding="utf-8", errors="replace") as file:
            file.write(f"\n===== PYTHON GUI {timestamp} {GUI_VERSION} =====\n")
            file.write(str(text).rstrip() + "\n")

    except Exception:
        pass


def create_launcher_script():
    launcher_content = """#!/usr/bin/env bash
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
"""

    with open(LAUNCHER_FILE, "w", encoding="utf-8", newline="\n") as file:
        file.write(launcher_content)


def refresh_output():
    output_text.delete("1.0", tk.END)

    if gui_messages:
        output_text.insert(tk.END, "===== Сообщения GUI =====\n")
        output_text.insert(tk.END, "\n".join(gui_messages[-GUI_MESSAGES_MAX:]))
        output_text.insert(tk.END, "\n\n")

    output_text.insert(tk.END, "===== connect_log.txt =====\n")

    if log_cache.strip():
        output_text.insert(tk.END, log_cache)
    else:
        output_text.insert(tk.END, "Лог пока пустой.\n")

    output_text.see(tk.END)


def write_output(text):
    timestamp = datetime.now().strftime("%H:%M:%S")
    lines = str(text).splitlines()

    if not lines:
        lines = [""]

    for line in lines:
        gui_messages.append(f"[{timestamp}] {line}")

    while len(gui_messages) > GUI_MESSAGES_MAX:
        gui_messages.pop(0)

    refresh_output()


def get_ping_command(ip):
    if os.name == "nt":
        return ["ping", "-n", "1", "-w", "3000", ip]

    return ["ping", "-c", "1", "-W", "3", ip]


def check_wsl_available(show_error=True):
    if not shutil.which("wsl.exe"):
        if show_error:
            messagebox.showerror(
                "Ошибка",
                "Не найден wsl.exe.\n\n"
                "Убедитесь, что WSL установлен и доступен из Windows."
            )
        return False

    try:
        result = run_wsl("echo ok", timeout=10)

        if result.returncode != 0:
            append_debug(f"WSL availability check failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")

            if show_error:
                messagebox.showerror(
                    "Ошибка WSL",
                    "WSL найден, но команда внутри WSL не выполнилась.\n\n"
                    f"STDOUT:\n{result.stdout}\n\n"
                    f"STDERR:\n{result.stderr}"
                )
            return False

        return True

    except Exception as error:
        append_debug(f"WSL availability exception: {error}")

        if show_error:
            messagebox.showerror("Ошибка WSL", str(error))
        return False


def is_wsl_monitor_running():
    try:
        create_launcher_script()
        wsl_launcher = windows_path_to_wsl(LAUNCHER_FILE)

        command = (
            f"bash {shlex.quote(wsl_launcher)} "
            f"status {shlex.quote(WSL_PID_FILE)}"
        )

        result = run_wsl(command, timeout=8)
        return result.returncode == 0

    except Exception:
        return False


def read_wsl_debug_tail():
    try:
        create_launcher_script()
        wsl_launcher = windows_path_to_wsl(LAUNCHER_FILE)
        result = run_wsl(f"bash {shlex.quote(wsl_launcher)} debug", timeout=10)

        text = ""

        if result.stdout.strip():
            text += result.stdout.strip()

        if result.stderr.strip():
            if text:
                text += "\n\n"
            text += "STDERR:\n" + result.stderr.strip()

        return text.strip() or "WSL debug пустой."

    except Exception as error:
        return f"Ошибка чтения WSL debug: {error}"


def read_debug_tail(lines_count=180):
    parts = []

    if DEBUG_FILE.exists():
        try:
            lines = DEBUG_FILE.read_text(
                encoding="utf-8",
                errors="replace"
            ).splitlines()

            if lines:
                parts.append("===== Windows debug =====")
                parts.append("\n".join(lines[-lines_count:]))
            else:
                parts.append("===== Windows debug =====")
                parts.append("Windows debug создан, но пустой.")

        except Exception as error:
            parts.append(f"Ошибка чтения Windows debug: {error}")
    else:
        parts.append(f"Windows debug не создан:\n{DEBUG_FILE}")

    parts.append("")
    parts.append("===== WSL debug =====")
    parts.append(read_wsl_debug_tail())

    return "\n".join(parts)


def show_debug_tail():
    tail = read_debug_tail()
    messagebox.showinfo("Debug", tail)
    write_output("Открыт debug-лог.")


def format_log_lines(lines):
    result = []

    for line in lines[-LOG_LINES_MAX:]:
        clean = line.strip()

        if clean.startswith("Скорость:"):
            speed_line = clean.replace("Скорость:", "").strip()
            parts = speed_line.split()

            if len(parts) >= 3:
                speed = parts[-3] + " " + parts[-2]
                result.append(f"Скорость: {speed}\n")
            else:
                result.append(line)

        elif clean == "receiver":
            continue

        else:
            result.append(line)

    return "".join(result)


def update_log():
    global log_cache

    if LOG_FILE.exists():
        try:
            with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as file:
                lines = file.readlines()

            log_cache = format_log_lines(lines)

        except Exception as error:
            log_cache = f"Ошибка чтения connect_log.txt: {error}\n"

    refresh_output()
    root.after(2000, update_log)


def check_address():
    ip = ip_entry.get().strip()

    if not ip:
        messagebox.showerror("Ошибка", "Введите IP-адрес")
        return

    write_output(f"Проверка адреса {ip}...")

    try:
        result = subprocess.run(
            get_ping_command(ip),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15
        )

        if result.returncode == 0:
            status_label.config(text="Адрес доступен")
            write_output("Адрес доступен.")
        else:
            status_label.config(text="Адрес недоступен")
            write_output("Адрес недоступен.")

    except subprocess.TimeoutExpired:
        status_label.config(text="Таймаут проверки")
        write_output("Проверка адреса превысила таймаут.")

    except FileNotFoundError:
        status_label.config(text="Ошибка ping")
        write_output("Команда ping не найдена.")

    except Exception as error:
        status_label.config(text="Ошибка проверки")
        write_output(f"Ошибка проверки адреса: {error}")


def verify_monitor_started():
    if is_wsl_monitor_running():
        status_label.config(text="Мониторинг работает через WSL")
        write_output("Проверка PID: мониторинг работает.")
    else:
        status_label.config(text="Мониторинг не запустился")
        write_output("Мониторинг завершился сразу после запуска.")
        write_output("Последние строки debug-лога:")
        write_output(read_debug_tail())


def start_script():
    ip = ip_entry.get().strip()
    port = port_entry.get().strip()

    if not ip or not port:
        messagebox.showerror("Ошибка", "Введите IP-адрес и порт")
        return

    if not BASH_SCRIPT.exists():
        messagebox.showerror("Ошибка", f"Не найден скрипт:\n{BASH_SCRIPT}")
        return

    if is_wsl_monitor_running():
        messagebox.showinfo("Информация", "Мониторинг уже запущен")
        return

    if not check_wsl_available():
        return

    try:
        create_launcher_script()

        LOG_FILE.touch(exist_ok=True)
        DEBUG_FILE.touch(exist_ok=True)

        wsl_launcher = windows_path_to_wsl(LAUNCHER_FILE)
        wsl_script = windows_path_to_wsl(BASH_SCRIPT)
        wsl_log = windows_path_to_wsl(LOG_FILE)

        command = (
            f"bash {shlex.quote(wsl_launcher)} "
            f"start "
            f"{shlex.quote(wsl_script)} "
            f"{shlex.quote(wsl_log)} "
            f"{shlex.quote(WSL_PID_FILE)} "
            f"{shlex.quote(ip)} "
            f"{shlex.quote(port)}"
        )

        append_debug("START command:\n" + command)

        result = run_wsl(command, timeout=25)

        append_debug(
            "START result\n"
            f"returncode={result.returncode}\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

        if result.returncode != 0:
            status_label.config(text=f"Ошибка запуска WSL, код {result.returncode}")
            write_output(f"Ошибка запуска WSL. Код выхода: {result.returncode}")

            if result.stdout.strip():
                write_output("STDOUT:")
                write_output(result.stdout.strip())

            if result.stderr.strip():
                write_output("STDERR:")
                write_output(result.stderr.strip())

            write_output("Последние строки debug-лога:")
            write_output(read_debug_tail())
            return

        status_label.config(text="Мониторинг запущен через WSL")
        write_output(f"Запущен мониторинг через WSL: {ip}:{port}")
        write_output(f"PID-файл WSL: {WSL_PID_FILE}")
        write_output(f"Debug-лог Windows: {DEBUG_FILE}")
        write_output(f"Debug-лог WSL: {WSL_DEBUG_PATH}")

        if result.stdout.strip():
            write_output("WSL:")
            write_output(result.stdout.strip())

        if result.stderr.strip():
            write_output("WSL STDERR:")
            write_output(result.stderr.strip())

        root.after(1500, verify_monitor_started)

    except Exception as error:
        append_debug(f"START exception: {error}")
        status_label.config(text="Ошибка запуска")
        write_output(f"Ошибка запуска мониторинга: {error}")
        messagebox.showerror("Ошибка запуска", str(error))


def stop_script():
    if not check_wsl_available():
        return

    try:
        create_launcher_script()
        wsl_launcher = windows_path_to_wsl(LAUNCHER_FILE)

        command = (
            f"bash {shlex.quote(wsl_launcher)} "
            f"stop "
            f"{shlex.quote(WSL_PID_FILE)}"
        )

        append_debug("STOP command:\n" + command)

        result = run_wsl(command, timeout=15)

        append_debug(
            "STOP result\n"
            f"returncode={result.returncode}\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

        if result.returncode == 0:
            status_label.config(text="Мониторинг остановлен")
            write_output("Мониторинг остановлен.")

            if result.stdout.strip():
                write_output("WSL:")
                write_output(result.stdout.strip())

        else:
            status_label.config(text="Ошибка остановки")
            write_output(f"Ошибка остановки. Код выхода: {result.returncode}")

            if result.stdout.strip():
                write_output("STDOUT:")
                write_output(result.stdout.strip())

            if result.stderr.strip():
                write_output("STDERR:")
                write_output(result.stderr.strip())

            write_output("Последние строки debug-лога:")
            write_output(read_debug_tail())

    except Exception as error:
        append_debug(f"STOP exception: {error}")
        status_label.config(text="Ошибка остановки")
        write_output(f"Ошибка остановки мониторинга: {error}")


def clear_debug():
    try:
        DEBUG_FILE.unlink(missing_ok=True)
    except Exception:
        pass

    try:
        create_launcher_script()
        wsl_launcher = windows_path_to_wsl(LAUNCHER_FILE)
        run_wsl(f"bash {shlex.quote(wsl_launcher)} clear-debug", timeout=10)
    except Exception:
        pass

    write_output("Debug-логи очищены.")


def open_work_dir():
    try:
        if os.name == "nt":
            os.startfile(str(SCRIPT_DIR))
        else:
            subprocess.Popen(["xdg-open", str(SCRIPT_DIR)])
    except Exception as error:
        messagebox.showerror("Ошибка", str(error))


def close_app():
    try:
        if is_wsl_monitor_running():
            stop_script()
    finally:
        root.destroy()


root = tk.Tk()
root.title(f"Connection Monitor - {GUI_VERSION}")
root.geometry("1060x760")
root.minsize(840, 580)
root.protocol("WM_DELETE_WINDOW", close_app)

root.columnconfigure(0, weight=1)
root.rowconfigure(4, weight=1)

title_label = tk.Label(
    root,
    text="Connection Monitor",
    font=("Arial", 20, "bold")
)
title_label.grid(row=0, column=0, pady=(15, 4), sticky="n")

version_label = tk.Label(root, text=GUI_VERSION, font=("Arial", 9))
version_label.grid(row=0, column=0, pady=(45, 8), sticky="n")

input_frame = tk.Frame(root)
input_frame.grid(row=1, column=0, pady=5, sticky="n")

tk.Label(input_frame, text="IP-адрес:").grid(row=0, column=0, padx=5, pady=5, sticky="e")

ip_entry = tk.Entry(input_frame, width=28)
ip_entry.insert(0, DEFAULT_IP)
ip_entry.grid(row=0, column=1, padx=5, pady=5, sticky="we")

tk.Label(input_frame, text="Порт:").grid(row=1, column=0, padx=5, pady=5, sticky="e")

port_entry = tk.Entry(input_frame, width=28)
port_entry.insert(0, DEFAULT_PORT)
port_entry.grid(row=1, column=1, padx=5, pady=5, sticky="we")

button_frame = tk.Frame(root)
button_frame.grid(row=2, column=0, pady=10, sticky="n")

check_button = tk.Button(
    button_frame,
    text="Проверить адрес",
    width=18,
    command=check_address
)
check_button.grid(row=0, column=0, padx=5, pady=4, sticky="we")

start_button = tk.Button(
    button_frame,
    text="Запустить",
    width=18,
    command=start_script
)
start_button.grid(row=0, column=1, padx=5, pady=4, sticky="we")

stop_button = tk.Button(
    button_frame,
    text="Остановить",
    width=18,
    command=stop_script
)
stop_button.grid(row=0, column=2, padx=5, pady=4, sticky="we")

debug_button = tk.Button(
    button_frame,
    text="Показать debug",
    width=18,
    command=show_debug_tail
)
debug_button.grid(row=0, column=3, padx=5, pady=4, sticky="we")

clear_debug_button = tk.Button(
    button_frame,
    text="Очистить debug",
    width=18,
    command=clear_debug
)
clear_debug_button.grid(row=0, column=4, padx=5, pady=4, sticky="we")

folder_button = tk.Button(
    button_frame,
    text="Открыть папку",
    width=18,
    command=open_work_dir
)
folder_button.grid(row=0, column=5, padx=5, pady=4, sticky="we")

status_label = tk.Label(root, text="Ожидание действия", font=("Arial", 12))
status_label.grid(row=3, column=0, pady=(5, 0), sticky="n")

output_frame = tk.LabelFrame(root, text="Вывод GUI / connect_log.txt")
output_frame.grid(row=4, column=0, padx=20, pady=15, sticky="nsew")

output_frame.columnconfigure(0, weight=1)
output_frame.rowconfigure(0, weight=1)

output_text = tk.Text(output_frame, wrap="word")
output_text.grid(row=0, column=0, sticky="nsew")

scrollbar = tk.Scrollbar(output_frame, command=output_text.yview)
scrollbar.grid(row=0, column=1, sticky="ns")

output_text.config(yscrollcommand=scrollbar.set)

write_output(f"Версия GUI: {GUI_VERSION}")
write_output(f"Рабочая папка: {SCRIPT_DIR}")
write_output(f"Bash-скрипт: {BASH_SCRIPT}")
write_output(f"Лог: {LOG_FILE}")
write_output(f"PID-файл WSL: {WSL_PID_FILE}")
write_output(f"Debug-лог Windows: {DEBUG_FILE}")
write_output(f"Debug-лог WSL: {WSL_DEBUG_PATH}")
write_output(f"Launcher: {LAUNCHER_FILE}")

update_log()

root.mainloop()
