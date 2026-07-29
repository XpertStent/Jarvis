#!/bin/sh
set -eu

RED="$(printf '\033[31m')"
GREEN="$(printf '\033[32m')"
YELLOW="$(printf '\033[33m')"
MAGENTA="$(printf '\033[35m')"
CYAN="$(printf '\033[36m')"
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

APP_DIR="/config/jarvis"
BACKEND_FILE="${APP_DIR}/backend.py"
FRONTEND_FILE="${APP_DIR}/frontend.html"
LEGACY_MAIN_FILE="${APP_DIR}/main.py"

DEFAULT_BACKEND_FILE="/opt/jarvis/default_backend.py"
DEFAULT_FRONTEND_FILE="/opt/jarvis/default_frontend.html"

SHOW_FOR_NON_ADMINS="$(bashio::config 'show_in_sidebar_for_non_admin_users')"

log_fun "Booting up. Polishing the arc reactor..."
log_info "Editable program folder: ${APP_DIR}"

if [ ! -f "${DEFAULT_BACKEND_FILE}" ]; then
  log_error "Missing default backend template: ${DEFAULT_BACKEND_FILE}"
  exit 1
fi

if [ ! -f "${DEFAULT_FRONTEND_FILE}" ]; then
  log_error "Missing default frontend template: ${DEFAULT_FRONTEND_FILE}"
  exit 1
fi

log_info "Checking Python requirements"
log_fun "Counting Python packages. Tiny snakes, big responsibilities."

if ! python3 -c "import fastapi, uvicorn, openai, httpx" >/dev/null 2>&1; then
  log_error "Python requirements are missing from the image. Rebuild the add-on so Dockerfile can install requirements.txt."
  exit 1
fi

log_ok "Python requirements already installed"
log_fun "Dependencies are behaving. Suspicious, but acceptable."

mkdir -p "${APP_DIR}"

if [ -f "${LEGACY_MAIN_FILE}" ]; then
  log_warn "Legacy combined file found at ${LEGACY_MAIN_FILE}"
  log_fun "Jarvis now uses backend.py and frontend.html. I will not delete your old main.py. I am dramatic, not reckless."
fi

OPTIONS_MIGRATION="$(python3 - <<'PY'
import json
import os
import urllib.request

path = "/data/options.json"
try:
    with open(path, "r", encoding="utf-8") as file:
        options = json.load(file)
except Exception as exc:
    print(f"warning:could not read options: {exc}")
    raise SystemExit(0)

changed = False

if "model" in options:
    options.pop("model", None)
    changed = True

legacy_reset = options.pop("reset_main.py_to_default_on_start", None)
if legacy_reset is not None:
    if legacy_reset is True:
        options["reset_main_to_default_on_start"] = True
    changed = True

if not changed:
    print("none")
    raise SystemExit(0)

token = os.environ.get("SUPERVISOR_TOKEN", "")
if token:
    try:
        request = urllib.request.Request(
            "http://supervisor/addons/self/options",
            data=json.dumps({"options": options}).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status < 300:
                print("updated")
                raise SystemExit(0)
    except SystemExit:
        raise
    except Exception:
        pass

try:
    temporary_path = path + ".tmp"
    with open(temporary_path, "w", encoding="utf-8") as file:
        json.dump(options, file, indent=2)
        file.write("\n")
    os.replace(temporary_path, path)
    print("updated-locally")
except Exception as exc:
    print(f"warning:could not remove legacy options: {exc}")
PY
)"

case "${OPTIONS_MIGRATION}" in
  updated)
    log_ok "Removed retired configuration options"
    ;;
  updated-locally)
    log_warn "Removed retired options locally; Supervisor API was unavailable"
    ;;
  warning:*)
    log_warn "${OPTIONS_MIGRATION#warning:}"
    ;;
esac

RESET_MAIN="$(python3 - <<'PY'
import json
import os

path = "/data/options.json"
try:
    if not os.path.exists(path):
        print("false")
    else:
        with open(path, "r", encoding="utf-8") as file:
            options = json.load(file)
        print("true" if options.get("reset_main_to_default_on_start", False) is True else "false")
except Exception:
    print("false")
PY
)"

backup_file_if_exists() {
  source_file="$1"
  label="$2"

  if [ -f "${source_file}" ]; then
    backup_file="${source_file}.backup.$(date +%Y%m%d-%H%M%S)"
    cp "${source_file}" "${backup_file}"
    log_ok "Backed up ${label} to ${backup_file}"
  else
    log_warn "No existing ${label} found to back up"
  fi
}

set_reset_toggle_false() {
  python3 - <<'PY'
import json
import os
import sys
import urllib.request

path = "/data/options.json"

try:
    options = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as file:
            options = json.load(file)

    options["reset_main_to_default_on_start"] = False

    token = os.environ.get("SUPERVISOR_TOKEN", "")
    if token:
        try:
            request = urllib.request.Request(
                "http://supervisor/addons/self/options",
                data=json.dumps({"options": options}).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                if response.status < 300:
                    raise SystemExit(0)
        except SystemExit:
            raise
        except Exception:
            pass

    temporary_path = path + ".tmp"
    with open(temporary_path, "w", encoding="utf-8") as file:
        json.dump(options, file, indent=2)
        file.write("\n")
    os.replace(temporary_path, path)
except Exception as exc:
    print(exc, file=sys.stderr)
    raise SystemExit(1)
PY
}

if [ "${RESET_MAIN}" = "true" ]; then
  log_warn "Reset toggle is enabled"
  log_fun "Resetting editable Jarvis files to factory defaults. I will save backups first, because I am not a monster."

  backup_file_if_exists "${BACKEND_FILE}" "backend.py"
  backup_file_if_exists "${FRONTEND_FILE}" "frontend.html"

  cp "${DEFAULT_BACKEND_FILE}" "${BACKEND_FILE}"
  cp "${DEFAULT_FRONTEND_FILE}" "${FRONTEND_FILE}"

  log_ok "backend.py has been reset to default"
  log_ok "frontend.html has been reset to default"
  log_fun "Fresh split brain installed. Backend and frontend are now speaking again. Probably."

  if set_reset_toggle_false; then
    log_ok "reset_main_to_default_on_start has been set back to false"
    log_fun "Next restart will not reset Jarvis again. Self-control achieved."
  else
    log_error "Jarvis was reset, but failed to set reset_main_to_default_on_start back to false"
    log_warn "Turn the reset toggle off manually before restarting"
  fi
else
  if [ ! -f "${BACKEND_FILE}" ]; then
    cp "${DEFAULT_BACKEND_FILE}" "${BACKEND_FILE}"
    log_ok "Created editable backend at ${BACKEND_FILE}"
    log_fun "Backend brain created. It has opinions now."
  else
    log_ok "Using existing editable backend at ${BACKEND_FILE}"
  fi

  if [ ! -f "${FRONTEND_FILE}" ]; then
    cp "${DEFAULT_FRONTEND_FILE}" "${FRONTEND_FILE}"
    log_ok "Created editable frontend at ${FRONTEND_FILE}"
    log_fun "Frontend face created. Looking stylish, feeling dangerous."
  else
    log_ok "Using existing editable frontend at ${FRONTEND_FILE}"
  fi

  log_fun "Your custom files survived. I did not touch them. Very professional."
fi

cd "${APP_DIR}"

log_info "Starting web UI on internal port 8099"
log_fun "Launching Jarvis. Please keep hands and YAML inside the vehicle."

exec python3 -m uvicorn backend:app --host 0.0.0.0 --port 8099 --reload --reload-dir "${APP_DIR}"
