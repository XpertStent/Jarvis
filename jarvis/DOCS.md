# Jarvis Documentation

Jarvis is a Python-based AI chatbot add-on for Home Assistant.

It runs as a Home Assistant sidebar app using Supervisor ingress and keeps the main editable Python program in your Home Assistant config folder:

```text
/config/jarvis/main.py
```

This lets you edit Jarvis live from Home Assistant without needing to rebuild or manually modify the add-on container every time.

---

## What Jarvis Does

Jarvis provides a simple local Home Assistant sidebar interface for chatting with an AI assistant.

Version 2.0.0 focuses on:

- Running a Python FastAPI web app inside Home Assistant
- Showing Jarvis in the Home Assistant sidebar
- Using OpenAI models through an API key
- Keeping the editable app code in `/config/jarvis/main.py`
- Preserving your custom edits across restarts, rebuilds, reinstalls, and updates
- Allowing a safe one-time reset back to the default app file
- Creating a backup before resetting your editable `main.py`

Future versions may add local Ollama support and direct Home Assistant entity control.

---

## Sidebar Access

After installing and starting the add-on, Jarvis appears in the Home Assistant sidebar as:

```text
Jarvis
```

The sidebar panel is powered by Home Assistant ingress, so you do not need to manually expose a port to access the web interface.

---

## File Locations

Jarvis uses two main locations.

### Add-on files

These are managed by Home Assistant and GitHub updates:

```text
/addons/local/jarvis
```

or internally by the Home Assistant add-on system.

These files include:

```text
config.yaml
Dockerfile
run.sh
requirements.txt
default_main.py
```

You normally should not edit these directly inside Home Assistant unless you are developing the add-on.

### Editable app file

This is the main file you can safely edit:

```text
/config/jarvis/main.py
```

Jarvis starts the web app from this file.

When the add-on starts:

- If `/config/jarvis/main.py` exists, Jarvis uses it.
- If it does not exist, Jarvis creates it from `default_main.py`.
- Jarvis will not overwrite your edited `main.py` unless you enable the reset option.

---

## Configuration Options

The add-on configuration is managed from the Home Assistant add-on Configuration tab.

Example options:

```yaml
enabled: true
openai_api_key: ""
model: "gpt-4.1-mini"
create_persistent_notification_on_online: true
reset_main_to_default_on_start: false
```

---

## Option Details

### `enabled`

Turns Jarvis on or off.

```yaml
enabled: true
```

When enabled, the Jarvis web interface starts normally.

When disabled, Jarvis may still start the container, but the app can be configured to block or ignore chat functionality depending on the current `main.py` logic.

---

### `openai_api_key`

Stores your OpenAI API key.

```yaml
openai_api_key: "your-api-key-here"
```

Keep this private.

Do not commit real API keys to GitHub.

---

### `model`

Controls which OpenAI model Jarvis uses.

```yaml
model: "gpt-4.1-mini"
```

You can change this to another model your API key has access to.

Examples:

```text
gpt-4.1-mini
gpt-4.1
gpt-4o-mini
```

Model availability depends on your OpenAI account and API access.

---

### `create_persistent_notification_on_online`

Creates a Home Assistant persistent notification when Jarvis starts.

```yaml
create_persistent_notification_on_online: true
```

This is useful for confirming that Jarvis came online successfully.

---

### `reset_main_to_default_on_start`

Safely resets the editable app file back to the packaged default.

```yaml
reset_main_to_default_on_start: false
```

When set to `true`, Jarvis will do this on next start:

1. Back up the existing file:

```text
/config/jarvis/main.py
```

2. Save the backup beside it:

```text
/config/jarvis/main.py.backup.YYYYMMDD-HHMMSS
```

3. Replace `main.py` with the packaged default:

```text
/opt/jarvis/default_main.py
```

4. Set `reset_main_to_default_on_start` back to `false`.

This makes the reset a one-time action so your file does not get wiped on every restart.

---

## Resetting Jarvis Back to Default

To reset the editable Jarvis program:

1. Go to the Jarvis add-on page.
2. Open the Configuration tab.
3. Set:

```yaml
reset_main_to_default_on_start: true
```

4. Save the configuration.
5. Restart the Jarvis add-on.

Jarvis will back up your current file and then replace it with the default version.

After the reset, Jarvis automatically changes the option back to:

```yaml
reset_main_to_default_on_start: false
```

You should see log messages confirming the reset and the backup location.

---

## Backup Location

Before resetting `main.py`, Jarvis saves a backup in:

```text
/config/jarvis/
```

Example backup file:

```text
/config/jarvis/main.py.backup.20260727-143012
```

To restore a backup manually:

```sh
cp /config/jarvis/main.py.backup.20260727-143012 /config/jarvis/main.py
```

Then restart the Jarvis add-on.

---

## Editing Jarvis

The file to edit is:

```text
/config/jarvis/main.py
```

You can edit it using:

- Home Assistant File Editor
- Studio Code Server add-on
- Samba share
- SSH terminal
- Any other method that can access the Home Assistant config folder

After editing the file, Jarvis should reload automatically because Uvicorn runs with reload enabled.

If changes do not appear, restart the add-on.

---

## Restart Behaviour

Restarting Jarvis will not delete your edited `main.py`.

Normal restart behaviour:

```text
/config/jarvis/main.py exists
Jarvis uses existing file
No overwrite happens
```

Only these actions can replace it:

- You manually delete `/config/jarvis/main.py`
- You enable `reset_main_to_default_on_start`
- You manually copy another file over it
- You wipe or restore your Home Assistant config folder

---

## Updating Jarvis

Jarvis can be updated from the Home Assistant add-on UI when installed through the GitHub repository.

To publish an update:

1. Change the version in:

```text
jarvis/config.yaml
```

Example:

```yaml
version: "2.0.0"
```

2. Commit and push the change to GitHub.
3. In Home Assistant, go to:

```text
Settings > Add-ons > Add-on Store
```

4. Open the three-dot menu.
5. Select:

```text
Check for updates
```

If Home Assistant sees a newer version in the GitHub repository, it should show an Update button.

---

## Important Update Note

Updating the add-on does not automatically replace:

```text
/config/jarvis/main.py
```

This is intentional.

It protects your custom edits.

To use the newest packaged default app after an update, enable:

```yaml
reset_main_to_default_on_start: true
```

Then restart Jarvis once.

---

## Rebuilding Jarvis

If you change files like:

```text
Dockerfile
requirements.txt
run.sh
default_main.py
```

you need to rebuild the add-on.

From Home Assistant Terminal:

```sh
ha addons rebuild local_jarvis
```

Or from the Home Assistant UI:

```text
Settings > Add-ons > Jarvis > three dots > Rebuild
```

A normal restart is not enough for Dockerfile or dependency changes.

---

## Python Dependencies

Python dependencies are installed during the Docker build process.

The dependency list is stored in:

```text
jarvis/requirements.txt
```

Example:

```text
fastapi
uvicorn
openai
requests
```

Installing dependencies during build is preferred because:

- Restarts are faster
- The add-on does not reinstall packages every start
- Jarvis can restart even if internet access is temporarily unavailable
- Startup logs stay cleaner

---

## Common Troubleshooting

### Jarvis says `No module named uvicorn`

This means Python dependencies were not installed into the Docker image.

Fix:

1. Make sure `requirements.txt` contains:

```text
uvicorn
fastapi
openai
requests
```

2. Make sure the Dockerfile installs requirements:

```dockerfile
RUN python3 -m pip install --no-cache-dir -r /opt/jarvis/requirements.txt
```

3. Rebuild the add-on.

---

### Jarvis does not show in the sidebar

Check `config.yaml` includes ingress settings:

```yaml
ingress: true
ingress_port: 8099
ingress_entry: /
panel_icon: mdi:robot
panel_title: Jarvis
```

Then restart the add-on.

---

### Jarvis update does not appear in Home Assistant

Check the version in:

```text
jarvis/config.yaml
```

The version must be higher than the currently installed version.

Example:

```yaml
version: "2.0.0"
```

Then in Home Assistant:

```text
Settings > Add-ons > Add-on Store > three dots > Check for updates
```

---

### My changes to `main.py` disappeared

Check whether you enabled:

```yaml
reset_main_to_default_on_start: true
```

If Jarvis reset your file, it should have created a backup in:

```text
/config/jarvis/
```

Look for files like:

```text
main.py.backup.20260727-143012
```

---

### Add-on starts but chat does not work

Check:

- Your API key is correct
- Your selected model exists
- Your OpenAI account has API access
- Home Assistant has internet access
- The add-on logs for Python errors

---

## Logs

Jarvis uses coloured logs where supported.

Example log types:

```text
Jarvis INFO
Jarvis OK
Jarvis WARNING
Jarvis ERROR
Jarvis
```

Some Home Assistant log views may not show colours, but the text labels should still be readable.

Jarvis may also print humorous startup messages.

This is normal.

Jarvis takes its job seriously. Mostly.

---

## Development Notes

The packaged default app lives at:

```text
jarvis/default_main.py
```

At runtime, Jarvis copies it to:

```text
/config/jarvis/main.py
```

only when `main.py` does not already exist.

This design allows you to:

- Keep the add-on managed by GitHub
- Keep your live Python logic editable from Home Assistant
- Update the add-on without losing your changes
- Reset back to the packaged default when needed

---

## Planned Future Ideas

Possible future features:

- Local Ollama support
- Model fetch dropdown
- API key test button improvements
- Home Assistant entity control
- Tool calling for lights, switches, scripts, scenes, and automations
- Conversation history
- System prompt editor
- Voice assistant support
- Better mobile layout
- More Jarvis personality
- Fewer printer insults, unless deserved

---

## Support

Project repository:

```text
https://github.com/XpertStent/Jarvis
```

When reporting an issue, include:

- Jarvis version
- Home Assistant version
- Add-on logs
- Whether you edited `/config/jarvis/main.py`
- Whether reset was enabled
- Any Python error messages shown in the logs
