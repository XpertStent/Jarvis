# Changelog

All notable changes to the Jarvis Home Assistant add-on will be documented in this file.

## 2.0.0

### Added

- Added official Home Assistant add-on repository update support.
- Added version bump to `2.0.0` for Home Assistant update detection.
- Added improved startup logging with coloured output.
- Added witty Jarvis-style boot messages because boring logs are for printers.
- Added reset-to-default support for the editable Python app file.
- Added automatic backup before resetting `/config/jarvis/main.py`.
- Added one-time reset behaviour so `reset_main_to_default_on_start` turns itself back off after use.
- Added safer handling of existing user-edited files.
- Added persistent editable app location at `/config/jarvis/main.py`.

### Changed

- Moved Python dependency installation into the Docker build process for faster add-on restarts.
- Updated Dockerfile to use a lightweight Python-based image.
- Improved `run.sh` so restarts do not reinstall all Python packages.
- Improved startup flow for cleaner logs and easier troubleshooting.
- Updated repository metadata to point to the Jarvis GitHub repository.
- Updated add-on configuration fields for better Home Assistant compatibility.
- Improved sidebar launch behaviour through Home Assistant ingress.

### Fixed

- Fixed issue where `uvicorn` could be missing after moving dependency installation out of `run.sh`.
- Fixed repeated reset behaviour that could wipe `main.py` on every restart.
- Fixed confusing startup logs by making each major step clearer.
- Fixed add-on file preservation logic so user-edited `/config/jarvis/main.py` is not replaced unless requested.
- Fixed Docker label version mismatch.

### Notes

- Updating to this version will not automatically replace your existing `/config/jarvis/main.py`.
- To load the latest default app code, enable `reset_main_to_default_on_start`, restart Jarvis once, then let Jarvis turn the setting back off automatically.
- A backup will be saved in `/config/jarvis/` before any reset is performed.

---

## 1.2.0

### Added

- Added configurable reset option for restoring the default Jarvis app file.
- Added backup creation before overwriting the editable Python file.
- Added improved add-on configuration options.
- Added persistent notification option when Jarvis starts.

### Changed

- Improved handling of `/config/jarvis/main.py`.
- Improved installer behaviour so existing editable files are not overwritten.
- Improved add-on startup messages.

### Fixed

- Fixed issue where reinstalling the add-on could risk replacing user-edited files.
- Fixed missing checks around the editable app directory.

---

## 1.1.0

### Added

- Added sidebar support using Home Assistant ingress.
- Added OpenAI API key configuration.
- Added model configuration option.
- Added optional API test button in the Jarvis web interface.
- Added basic model fetch support.

### Changed

- Improved default Jarvis web UI.
- Improved configuration loading from `/data/options.json`.
- Improved app startup handling.

### Fixed

- Fixed early issues with add-on startup paths.
- Fixed missing folder creation for `/config/jarvis`.

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
- Added install script for local deployment.
- Added support for preserving user edits across restarts and reinstalls.

### Notes

- First experimental version.
- Jarvis has entered the sidebar. The house may now have opinions.
