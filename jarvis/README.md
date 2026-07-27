# Jarvis

Jarvis is a Python FastAPI chatbot exposed in the Home Assistant sidebar through Supervisor ingress.

Version `2.0.1` splits the editable app into:

```text
/config/jarvis/backend.py
/config/jarvis/frontend.html
```

The add-on only creates those files if they do not already exist. Your edits survive restarts, rebuilds, reinstalls, and updates.

To reset both editable files to the packaged defaults, enable **Reset editable program on next start** in the add-on Configuration tab and restart once. Jarvis backs up the existing files and then turns the reset option off again.
