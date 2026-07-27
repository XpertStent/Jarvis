# Changelog

All notable changes to the Jarvis Home Assistant add-on will be documented in this file.

## 2.0.1

### Added

- Added split editable runtime files:
  - `/config/jarvis/backend.py`
  - `/config/jarvis/frontend.html`
- Added packaged templates:
  - `default_backend.py`
  - `default_frontend.html`
- Added startup creation of missing backend and frontend files from templates.
- Added reset-to-default support for both backend and frontend files.
- Added backup creation for both editable files before reset.
- Added legacy `main.py` detection with safe warning logs.
- Added documentation for the new split-file layout.

### Changed

- Updated add-on version to `2.0.1`.
- Changed the Uvicorn entrypoint from `main:app` to `backend:app`.
- Changed Dockerfile to copy backend and frontend templates instead of `default_main.py`.
- Kept Python dependency installation in the Docker build for faster restarts.
- Kept the existing Jarvis UI, OpenAI model selection, streaming chat, and Home Assistant ingress behaviour.

### Fixed

- Avoided editing a huge single Python file for frontend changes.
- Reduced the chance of frontend quote/newline mistakes breaking the backend Python file.
- Preserved old `/config/jarvis/main.py` instead of deleting it during migration.

### Notes

- Updating to this version will not automatically delete or migrate old `/config/jarvis/main.py`.
- Jarvis now runs from `/config/jarvis/backend.py` and serves `/config/jarvis/frontend.html`.
- To install the new default split files on an existing setup, enable `reset_main_to_default_on_start` once and restart Jarvis.

---

## 2.0.0

### Added

- Added improved startup logging with coloured output.
- Added reset-to-default support for the editable Python app file.
- Added automatic backup before resetting `/config/jarvis/main.py`.
- Added one-time reset behaviour so the reset option turns itself back off after use.
- Added persistent editable app location at `/config/jarvis/main.py`.

### Changed

- Moved Python dependency installation into the Docker build process for faster add-on restarts.
- Improved startup flow for cleaner logs and easier troubleshooting.
- Improved sidebar launch behaviour through Home Assistant ingress.

### Fixed

- Fixed issue where `uvicorn` could be missing after moving dependency installation out of `run.sh`.
- Fixed repeated reset behaviour that could wipe `main.py` on every restart.

---

## 1.2.0

### Added

- Added configurable reset option for restoring the default Jarvis app file.
- Added backup creation before overwriting the editable Python file.
- Added improved add-on configuration options.
- Added persistent notification option when Jarvis starts.

---

## 1.0.0

### Added

- Initial Jarvis Home Assistant add-on release.
- Added Python FastAPI web app.
- Added editable app file at `/config/jarvis/main.py`.
- Added default app template through `default_main.py`.
- Added local Home Assistant sidebar panel.
- Added basic chatbot interface.
- Added OpenAI integration.
