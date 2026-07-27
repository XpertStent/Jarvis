# Jarvis Home Assistant Add-on

Jarvis is a Python FastAPI chatbot exposed in the Home Assistant sidebar through Supervisor ingress.

## Version 2.0.1

This release splits the editable live app into two files:

```text
/config/jarvis/backend.py
/config/jarvis/frontend.html
```

The add-on package stores the templates as:

```text
jarvis/default_backend.py
jarvis/default_frontend.html
```

On start, `run.sh` creates `/config/jarvis` and copies those templates into the config folder only when the editable files are missing. Existing editable files are preserved.

## Repository install

Add this repository in Home Assistant:

```text
https://github.com/XpertStent/Jarvis
```

Then install **Jarvis** from the Add-on Store.
