# Jarvis Home Assistant Local Add-on

Jarvis is a Python FastAPI chatbot exposed in the Home Assistant sidebar through Supervisor ingress.

Important paths:

- Add-on files: `/addons/local/jarvis`
- Editable live Python program: `/config/jarvis/main.py`
- Add-on options: Home Assistant add-on Configuration tab, stored by Supervisor in `/data/options.json` inside the container

The add-on copies `default_main.py` to `/config/jarvis/main.py` only if that file does not already exist. After that, your editable file is preserved.

## Install

1. Copy this folder to your Home Assistant machine.
2. Run `bash install.sh`, or manually copy the `jarvis` folder to `/addons/local/jarvis`.
3. In Home Assistant, open Settings > Add-ons > Add-on Store.
4. Use the three-dot menu and choose Check for updates.
5. Install Jarvis.
6. Add your OpenAI API key and model in the Configuration tab.
7. Start the add-on.
8. Open Jarvis from the sidebar.

## V1 scope

This version chats only. Entity control can be added later by expanding `/config/jarvis/main.py` to call Home Assistant services through `http://supervisor/core/api/services/<domain>/<service>`.
