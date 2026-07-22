#!/bin/sh
set -eu

RED="$(printf '\033[31m')"
GREEN="$(printf '\033[32m')"
YELLOW="$(printf '\033[33m')"
BLUE="$(printf '\033[34m')"
MAGENTA="$(printf '\033[35m')"
CYAN="$(printf '\033[36m')"
BOLD="$(printf '\033[1m')"
RESET="$(printf '\033[0m')"

log_info() {
  echo "${CYAN}Jarvis INFO:${RESET} $1"
}

log_ok() {
  echo "${GREEN}Jarvis OK:${RESET} $1"
}

log_warn() {
  echo "${YELLOW}Jarvis WARNING:${RESET} $1"
}

log_error() {
  echo "${RED}Jarvis ERROR:${RESET} $1"
}

log_fun() {
  echo "${MAGENTA}Jarvis:${RESET} $1"
}


REQ_FILE="/opt/jarvis/requirements.txt"

if [ ! -f "${REQ_FILE}" ]; then
  log_error "Missing requirements file: ${REQ_FILE}"
  exit 1
fi

log_info "Checking Python requirements"
log_fun "Counting Python packages. Tiny snakes, big responsibilities."

if ! python3 -c "import fastapi, uvicorn, openai" >/dev/null 2>&1; then
  log_warn "Python requirements missing"
  log_fun "Installing dependencies. The internet elves have been summoned."
  python3 -m pip install --no-cache-dir -r "${REQ_FILE}"
  log_ok "Python requirements installed"
else
  log_ok "Python requirements already installed"
  log_fun "Dependencies are behaving. Suspicious, but acceptable."
fi

APP_DIR="/config/jarvis"
MAIN_FILE="${APP_DIR}/main.py"
DEFAULT_FILE="/opt/jarvis/default_main.py"

if [ ! -f "${DEFAULT_FILE}" ]; then
  log_error "Missing default main file: ${DEFAULT_FILE}"
  exit 1
fi

mkdir -p "${APP_DIR}"

log_fun "Booting up. Polishing the arc reactor..."
log_info "Editable program folder: ${APP_DIR}"



RESET_MAIN="$(python3 - <<'PY'
import json
import os

path = "/data/options.json"

try:
    if not os.path.exists(path):
        print("false")
    else:
        with open(path, "r", encoding="utf-8") as f:
            opts = json.load(f)

        value = opts.get("reset_main_to_default_on_start", False)
        print("true" if value is True else "false")
except Exception:
    print("false")
PY
)"

if [ "${RESET_MAIN}" = "true" ]; then
  log_warn "Reset toggle is enabled"
  log_fun "Resetting main.py to factory again. I will save the current one first, because I am not a monster."

  if [ -f "${MAIN_FILE}" ]; then
    BACKUP_FILE="${MAIN_FILE}.backup.$(date +%Y%m%d-%H%M%S)"
    cp "${MAIN_FILE}" "${BACKUP_FILE}"
    log_ok "Backed up existing main.py to ${BACKUP_FILE}"
  else
    log_warn "No existing main.py found to back up"
  fi

  cp "${DEFAULT_FILE}" "${MAIN_FILE}"
  log_ok "main.py has been reset to default"
  log_fun "Fresh brain installed. Ego reboot pending."

  if python3 - <<'PY'
import json
import os
import sys

path = "/data/options.json"

try:
    opts = {}

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            opts = json.load(f)

    opts["reset_main_to_default_on_start"] = False

    tmp_path = path + ".tmp"

    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(opts, f, indent=2)
        f.write("\n")

    os.replace(tmp_path, path)
except Exception as e:
    print(e, file=sys.stderr)
    sys.exit(1)
PY
  then
    log_ok "reset_main_to_default_on_start has been set back to false"
    log_fun "Next restart will not wipe main.py again. Hopefully."
  else
    log_error "main.py was reset, but failed to set reset_main_to_default_on_start back to false"
    log_warn "Turn the reset toggle off manually before restarting"
  fi

else
  if [ ! -f "${MAIN_FILE}" ]; then
    cp "${DEFAULT_FILE}" "${MAIN_FILE}"
    log_ok "Created editable main program at ${MAIN_FILE}"
    log_fun "New python file created. It knows almost nothing, which is still more than most printers."
  else
    log_ok "Using existing editable main program at ${MAIN_FILE}"
    log_fun "Your custom python file is being used. I did not touch it. Very professional."
  fi
fi

cd "${APP_DIR}"

log_info "Starting web UI on internal port 8099"
log_fun "Launching Jarvis. Please keep hands and YAML inside the vehicle."

exec python3 -m uvicorn main:app --host 0.0.0.0 --port 8099 --reload --reload-dir "${APP_DIR}"