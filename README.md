# Jarvis Home Assistant Local Add-on

Jarvis is a Python FastAPI chatbot exposed in the Home Assistant sidebar through Supervisor ingress.

Important paths:

- Add-on files: `/addons/local/jarvis`
- Editable live Python program: `/config/jarvis/main.py`
- Add-on options: Home Assistant add-on Configuration tab, stored by Supervisor in `/data/options.json` inside the container

The add-on copies `default_main.py` to `/config/jarvis/main.py` only if that file does not already exist. After that, your editable file is preserved.

## Edit the App
main.py is placed at /config/jarvis/main.py and can be edited and customised according to requirement.

## Model selection

The model is selected from the **Models** browser in the Jarvis chat, not from the Home Assistant add-on Configuration tab. The selection is stored in the add-on data folder and survives page and add-on restarts.

The fallback used before a model is selected is the `DEFAULT_MODEL` constant in `default_main.py`.

For an existing installation, enable **Reset editable program on next start** once and restart the add-on to install the updated UI. Jarvis backs up the existing `/config/jarvis/main.py` before replacing it and automatically turns the reset option off again.

## V1 scope

This version chats only. Entity control can be added later by editing `/config/jarvis/main.py` to call Home Assistant services through `http://supervisor/core/api/services/<domain>/<service>`.
