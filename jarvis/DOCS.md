# Jarvis Documentation

Jarvis is a Python-based AI chatbot add-on for Home Assistant.

It runs as a Home Assistant sidebar app using Supervisor ingress and keeps the live editable program files in your Home Assistant config folder.

## Version 2.0.1 file layout

Jarvis now uses two editable runtime files:

```text
/config/jarvis/backend.py
/config/jarvis/frontend.html
```

The packaged template files in the GitHub repository are:

```text
jarvis/default_backend.py
jarvis/default_frontend.html
```

On startup, `run.sh` creates `/config/jarvis` and copies each template only if the matching editable file is missing.

## What each file does

### `backend.py`

Contains the FastAPI app, OpenAI client logic, Home Assistant persistent notification logic, model listing, model selection, status endpoints, and streaming chat endpoint.

### `frontend.html`

Contains the Jarvis web UI, CSS, and JavaScript. It calls the backend API endpoints through Home Assistant ingress.

## Configuration

Configuration is managed from the Jarvis add-on Configuration tab.

```yaml
enabled: true
openai_api_key: ""
create_persistent_notification_on_online: true
system_prompt: "You are Jarvis, a concise Home Assistant chatbot..."
reset_main_to_default_on_start: false
```

### `enabled`

Turns Jarvis functionality on or off.

### `openai_api_key`

Your OpenAI API key. Do not commit real keys to GitHub.

### `create_persistent_notification_on_online`

Creates a Home Assistant persistent notification when Jarvis starts.

### `system_prompt`

The main behaviour instruction sent to Jarvis before each response.

### `reset_main_to_default_on_start`

One-time reset option. When enabled and the add-on restarts, Jarvis:

1. Backs up `/config/jarvis/backend.py` if it exists.
2. Backs up `/config/jarvis/frontend.html` if it exists.
3. Copies the packaged default backend and frontend into `/config/jarvis`.
4. Sets `reset_main_to_default_on_start` back to `false`.

Backups are saved next to the files, for example:

```text
/config/jarvis/backend.py.backup.20260727-153000
/config/jarvis/frontend.html.backup.20260727-153000
```

## Legacy `main.py`

Older Jarvis builds used:

```text
/config/jarvis/main.py
```

Version 2.0.1 does not delete that file. If it exists, Jarvis logs a warning and leaves it untouched. The active app now runs from `backend.py` and reads the UI from `frontend.html`.

## Updating Jarvis

Home Assistant checks the version in:

```text
jarvis/config.yaml
```

For this release:

```yaml
version: "2.0.1"
```

After pushing to GitHub, use:

```text
Settings > Add-ons > Add-on Store > three dots > Check for updates
```

## Rebuilding

If you change any of these files, rebuild the add-on:

```text
Dockerfile
requirements.txt
run.sh
default_backend.py
default_frontend.html
```

From Home Assistant Terminal:

```sh
ha addons rebuild 6886fdbf_jarvis
```

Your installed slug may differ. Check the add-on URL or run `ha addons` to confirm.

## Troubleshooting

### UI stuck on Connecting

Check the add-on logs for JavaScript or backend errors. Also verify that `backend.py` can read:

```text
/config/jarvis/frontend.html
```

### No module named uvicorn

Rebuild the add-on. Dependencies are installed by the Dockerfile, not by `run.sh`.

### Streaming looks delayed

Some models think before sending the first visible token. Jarvis keeps the Thinking indicator visible until the first streamed text chunk arrives.

### Reset did not turn itself off

Turn `reset_main_to_default_on_start` off manually in the Configuration tab before restarting again.
