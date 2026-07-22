import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from time import time
from typing import Any

import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from openai import AsyncOpenAI
from pydantic import BaseModel

OPTIONS_FILE = Path("/data/options.json")
STATE_FILE = Path("/data/jarvis_state.json")
PROGRAM_FILE = Path("/config/jarvis/main.py")
DEFAULT_MODEL = "gpt-5.6-luna"

DEFAULT_OPTIONS = {
    "enabled": True,
    "openai_api_key": "",
    "create_persistent_notification_on_online": True,
    "system_prompt": (
        "You are Jarvis, a concise Home Assistant chatbot. "
        "Help the user clearly and safely. In v1, do not claim to control devices "
        "unless code for that is added later."
    ),
}

class ChatRequest(BaseModel):
    message: str
    history: list[dict[str, str]] | None = None


class ModelRequest(BaseModel):
    model: str


def load_options() -> dict[str, Any]:
    options = DEFAULT_OPTIONS.copy()
    if OPTIONS_FILE.exists():
        try:
            loaded = json.loads(OPTIONS_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                options.update(loaded)
        except Exception as exc:
            print(f"Jarvis: failed to read options: {exc}")
    return options


def get_api_key(options: dict[str, Any]) -> str:
    return (options.get("openai_api_key") or os.environ.get("OPENAI_API_KEY") or "").strip()


def get_openai_client(options: dict[str, Any]) -> AsyncOpenAI:
    api_key = get_api_key(options)
    if not api_key:
        raise RuntimeError("OpenAI API key is blank. Add it in the Jarvis add-on Configuration tab.")
    return AsyncOpenAI(api_key=api_key)


def get_selected_model() -> str:
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(state, dict):
                selected = str(state.get("selected_model") or "").strip()
                if selected:
                    return selected
        except Exception as exc:
            print(f"Jarvis: failed to read UI state: {exc}")
    return DEFAULT_MODEL


def save_selected_model(model: str) -> None:
    state: dict[str, Any] = {}
    if STATE_FILE.exists():
        try:
            loaded = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                state.update(loaded)
        except Exception as exc:
            print(f"Jarvis: replacing unreadable UI state: {exc}")

    state["selected_model"] = model
    temporary_file = STATE_FILE.with_suffix(".tmp")
    temporary_file.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    temporary_file.replace(STATE_FILE)


async def create_online_notification() -> None:
    options = load_options()
    if not options.get("enabled", True):
        return
    if not options.get("create_persistent_notification_on_online", False):
        return

    token = os.environ.get("SUPERVISOR_TOKEN", "")
    if not token:
        print("Jarvis: SUPERVISOR_TOKEN missing; skipping persistent notification")
        return

    url = "http://supervisor/core/api/services/persistent_notification/create"
    payload = {
        "title": "Jarvis online",
        "message": "Jarvis chatbot add-on is running.",
        "notification_id": "jarvis_online",
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code >= 300:
                print(f"Jarvis: persistent notification failed: {response.status_code} {response.text}")
    except Exception as exc:
        print(f"Jarvis: persistent notification error: {exc}")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await create_online_notification()
    yield


app = FastAPI(title="Jarvis", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "name": "Jarvis", "time": int(time())}


@app.get("/api/status")
def status() -> dict[str, Any]:
    options = load_options()
    return {
        "ok": True,
        "enabled": bool(options.get("enabled", True)),
        "model": get_selected_model(),
        "has_openai_api_key": bool(get_api_key(options)),
        "program_file": str(PROGRAM_FILE),
        "time": int(time()),
    }


@app.post("/api/test-openai")
async def test_openai() -> JSONResponse:
    options = load_options()
    if not options.get("enabled", True):
        return JSONResponse({"ok": False, "error": "Jarvis is disabled in add-on options."}, status_code=403)

    try:
        client = get_openai_client(options)
        models = await client.models.list()
        return JSONResponse({"ok": True, "message": f"API key works. Models visible: {len(models.data)}"})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@app.get("/api/models")
async def models() -> JSONResponse:
    options = load_options()
    if not options.get("enabled", True):
        return JSONResponse({"ok": False, "error": "Jarvis is disabled in add-on options."}, status_code=403)

    try:
        client = get_openai_client(options)
        model_list = await client.models.list()
        ids = sorted({item.id for item in model_list.data})
        return JSONResponse({"ok": True, "models": ids, "selected_model": get_selected_model()})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@app.post("/api/model")
async def select_model(payload: ModelRequest) -> JSONResponse:
    options = load_options()
    if not options.get("enabled", True):
        return JSONResponse({"ok": False, "error": "Jarvis is disabled in add-on options."}, status_code=403)

    selected = payload.model.strip()
    if not selected or len(selected) > 200:
        return JSONResponse({"ok": False, "error": "Choose a valid model."}, status_code=400)

    try:
        client = get_openai_client(options)
        model_list = await client.models.list()
        available = {item.id for item in model_list.data}
        if selected not in available:
            return JSONResponse(
                {"ok": False, "error": "That model is not available to this API key."},
                status_code=400,
            )
        save_selected_model(selected)
        return JSONResponse({"ok": True, "model": selected})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


@app.post("/api/chat")
async def chat(payload: ChatRequest) -> JSONResponse:
    options = load_options()
    if not options.get("enabled", True):
        return JSONResponse({"ok": False, "error": "Jarvis is disabled in add-on options."}, status_code=403)

    user_message = payload.message.strip()
    if not user_message:
        return JSONResponse({"ok": False, "error": "Message is blank."}, status_code=400)

    try:
        client = get_openai_client(options)
        model = get_selected_model()
        system_prompt = str(options.get("system_prompt") or DEFAULT_OPTIONS["system_prompt"]).strip()

        input_items: list[dict[str, str]] = []
        for item in (payload.history or [])[-10:]:
            role = item.get("role", "user")
            content = item.get("content", "")
            if role in {"user", "assistant"} and content:
                input_items.append({"role": role, "content": content})
        input_items.append({"role": "user", "content": user_message})

        response = await client.responses.create(
            model=model,
            instructions=system_prompt,
            input=input_items,
        )
        answer = response.output_text or "Jarvis did not return text."
        return JSONResponse({"ok": True, "answer": answer, "model": model})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


HTML = r"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <meta name="theme-color" content="#0a0e10" />
  <title>Jarvis</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0a0e10;
      --surface: #101619;
      --surface-solid: #12181c;
      --surface-raised: #182126;
      --surface-hover: #1d2a2f;
      --text: #eef5f4;
      --muted: #879592;
      --muted-strong: #bcc8c5;
      --border: #253135;
      --border-strong: #334247;
      --accent: #54d6c4;
      --accent-strong: #36bdaa;
      --accent-soft: #142c2a;
      --accent-text: #07110f;
      --user: #16443e;
      --good: #62d795;
      --warn: #e7b957;
      --bad: #f17883;
      --shadow: 0 24px 80px rgba(0, 0, 0, .38);
      --radius: 22px;
    }

    * { box-sizing: border-box; }
    html, body { height: 100%; }
    body {
      margin: 0;
      overflow: hidden;
      font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
      -webkit-font-smoothing: antialiased;
    }

    button, textarea, input { font: inherit; }
    button { -webkit-tap-highlight-color: transparent; }
    button:focus-visible, textarea:focus-visible, input:focus-visible {
      outline: 2px solid var(--accent);
      outline-offset: 2px;
    }

    .app-shell {
      width: min(1120px, 100%);
      height: 100dvh;
      min-height: 520px;
      margin: 0 auto;
      position: relative;
      isolation: isolate;
      padding: max(16px, env(safe-area-inset-top)) 18px max(16px, env(safe-area-inset-bottom));
      display: grid;
      grid-template-rows: auto auto minmax(0, 1fr);
      gap: 12px;
    }

    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      min-height: 52px;
    }

    .brand { display: flex; align-items: center; gap: 12px; min-width: 0; }
    .brand-mark {
      width: 42px;
      height: 42px;
      flex: 0 0 auto;
      display: grid;
      place-items: center;
      border: 1px solid #2a655e;
      border-radius: 14px;
      background: var(--accent-soft);
      box-shadow: 0 10px 30px rgba(0, 0, 0, .18);
      color: var(--accent);
      font-size: 18px;
      font-weight: 800;
      letter-spacing: -.04em;
    }
    .brand h1 { margin: 0; font-size: 18px; line-height: 1.1; letter-spacing: -.02em; }
    .brand p { margin: 4px 0 0; color: var(--muted); font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

    .top-actions { display: flex; align-items: center; gap: 8px; }
    .status-pill, .icon-btn, .action-btn {
      min-height: 38px;
      border: 1px solid var(--border);
      border-radius: 12px;
      background: var(--surface);
      color: var(--muted-strong);
    }
    .status-pill {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 0 12px;
      cursor: pointer;
    }
    .status-pill:hover, .icon-btn:hover, .action-btn:hover { background: var(--surface-hover); border-color: var(--border-strong); }
    .status-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--muted); box-shadow: 0 0 0 4px rgba(147, 155, 170, .09); }
    .status-pill.ok .status-dot { background: var(--good); box-shadow: 0 0 0 4px rgba(98, 215, 149, .12); }
    .status-pill.warn .status-dot { background: var(--warn); box-shadow: 0 0 0 4px rgba(231, 185, 87, .12); }
    .status-pill.bad .status-dot { background: var(--bad); box-shadow: 0 0 0 4px rgba(241, 120, 131, .12); }
    .status-text { font-size: 12px; font-weight: 700; }
    .icon-btn { width: 38px; padding: 0; display: grid; place-items: center; cursor: pointer; font-size: 16px; }

    .toolbar {
      position: relative;
      z-index: 20;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 9px;
      border: 1px solid var(--border);
      border-radius: 16px;
      background: var(--surface);
      box-shadow: 0 12px 44px rgba(0, 0, 0, .12);
    }
    .tool-group { display: flex; align-items: center; gap: 6px; min-width: 0; }
    .action-btn {
      padding: 0 11px;
      display: inline-flex;
      align-items: center;
      gap: 7px;
      white-space: nowrap;
      cursor: pointer;
      font-size: 12px;
      font-weight: 700;
    }
    .action-btn:disabled { cursor: wait; opacity: .65; }
    .action-symbol { color: var(--accent); font-size: 15px; line-height: 1; }
    .count-badge { min-width: 19px; padding: 2px 6px; border-radius: 999px; background: var(--accent-soft); color: var(--accent); font-size: 10px; text-align: center; }
    .model-selector-btn { min-width: 220px; justify-content: flex-start; padding: 5px 10px; }
    .model-button-copy { min-width: 0; display: grid; gap: 1px; text-align: left; }
    .model-button-label { color: var(--muted); font-size: 9px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
    .model-button-name { max-width: 190px; overflow: hidden; color: var(--text); font-size: 12px; text-overflow: ellipsis; }
    .selector-chevron { margin-left: auto; color: var(--muted); font-size: 13px; }

    .details-popover {
      position: absolute;
      z-index: 100;
      top: calc(100% + 8px);
      right: 0;
      width: min(390px, calc(100vw - 36px));
      padding: 14px;
      border: 1px solid var(--border-strong);
      border-radius: 16px;
      background: var(--surface-solid);
      box-shadow: var(--shadow);
      transform-origin: top right;
      animation: pop-in .16s ease-out;
    }
    .details-popover[hidden] { display: none; }
    .details-title { margin: 0 0 10px; font-size: 13px; }
    .detail-grid { display: grid; grid-template-columns: auto 1fr; gap: 8px 14px; margin: 0; font-size: 12px; }
    .detail-grid dt { color: var(--muted); }
    .detail-grid dd { margin: 0; color: var(--muted-strong); word-break: break-word; text-align: right; }

    .chat-panel {
      position: relative;
      z-index: 1;
      min-height: 0;
      overflow: hidden;
      display: grid;
      grid-template-rows: minmax(0, 1fr) auto;
      border: 1px solid var(--border);
      border-radius: var(--radius);
      background: var(--surface);
      box-shadow: var(--shadow);
    }

    #chatlog {
      min-height: 0;
      overflow-y: auto;
      overscroll-behavior: contain;
      scroll-behavior: smooth;
      scrollbar-gutter: stable;
      padding: 26px clamp(16px, 4vw, 46px) 18px;
    }
    #chatlog::-webkit-scrollbar, .model-list::-webkit-scrollbar, textarea::-webkit-scrollbar { width: 8px; }
    #chatlog::-webkit-scrollbar-track, .model-list::-webkit-scrollbar-track, textarea::-webkit-scrollbar-track { background: transparent; }
    #chatlog::-webkit-scrollbar-thumb, .model-list::-webkit-scrollbar-thumb, textarea::-webkit-scrollbar-thumb { background: var(--border-strong); border: 2px solid transparent; background-clip: padding-box; border-radius: 999px; }

    .welcome {
      min-height: 100%;
      display: grid;
      place-content: center;
      justify-items: center;
      text-align: center;
      padding: 20px;
      animation: fade-up .35s ease-out;
    }
    .welcome-mark { width: 64px; height: 64px; display: grid; place-items: center; margin-bottom: 18px; border-radius: 22px; background: var(--accent-soft); color: var(--accent); font-size: 25px; font-weight: 800; box-shadow: inset 0 0 0 1px rgba(110, 231, 216, .18); }
    .welcome h2 { margin: 0; font-size: clamp(22px, 4vw, 32px); letter-spacing: -.04em; }
    .welcome p { max-width: 500px; margin: 10px 0 20px; color: var(--muted); line-height: 1.6; font-size: 14px; }
    .suggestions { display: flex; justify-content: center; flex-wrap: wrap; gap: 8px; }
    .suggestion {
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 9px 13px;
      background: var(--surface-raised);
      color: var(--muted-strong);
      cursor: pointer;
      font-size: 12px;
      transition: transform .15s ease, border-color .15s ease, background .15s ease;
    }
    .suggestion:hover { transform: translateY(-1px); border-color: rgba(110, 231, 216, .35); background: var(--accent-soft); }

    .message-row { display: flex; gap: 10px; margin: 0 0 18px; animation: fade-up .2s ease-out; }
    .message-row.user { justify-content: flex-end; }
    .message-stack { max-width: min(82%, 720px); min-width: 0; }
    .message-row.assistant .message-stack { max-width: min(88%, 760px); }
    .message-label { margin: 0 4px 6px; color: var(--muted); font-size: 10px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; }
    .message-row.user .message-label { text-align: right; }
    .message-bubble {
      padding: 12px 15px;
      border: 1px solid var(--border);
      border-radius: 6px 17px 17px 17px;
      background: var(--surface-raised);
      color: var(--text);
      line-height: 1.55;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      font-size: 14px;
    }
    .message-row.user .message-bubble { border-color: rgba(102, 181, 216, .18); border-radius: 17px 6px 17px 17px; background: var(--user); color: #fff; }
    .message-time { display: block; margin: 6px 4px 0; color: var(--muted); font-size: 9px; }
    .message-row.user .message-time { text-align: right; }

    .notice {
      width: fit-content;
      max-width: min(92%, 700px);
      margin: 12px auto 18px;
      padding: 9px 12px;
      border: 1px solid var(--border);
      border-radius: 12px;
      background: var(--accent-soft);
      color: var(--muted-strong);
      text-align: center;
      line-height: 1.45;
      font-size: 11px;
      animation: fade-up .2s ease-out;
    }
    .notice.error { background: #2b171b; color: var(--bad); }

    .typing-bubble { display: flex; align-items: center; gap: 10px; min-width: 116px; }
    .typing-dots { display: inline-flex; align-items: center; gap: 4px; height: 20px; }
    .typing-dots i { width: 6px; height: 6px; border-radius: 50%; background: var(--accent); animation: typing 1.15s infinite ease-in-out; }
    .typing-dots i:nth-child(2) { animation-delay: .14s; }
    .typing-dots i:nth-child(3) { animation-delay: .28s; }
    .thinking-text { color: var(--muted); font-size: 12px; }

    .composer-wrap { padding: 12px; border-top: 1px solid var(--border); background: var(--surface-solid); }
    .composer {
      display: flex;
      align-items: flex-end;
      gap: 10px;
      padding: 7px 7px 7px 14px;
      border: 1px solid var(--border-strong);
      border-radius: 17px;
      background: var(--bg);
      transition: border-color .18s ease, box-shadow .18s ease;
    }
    .composer:focus-within { border-color: var(--accent-strong); box-shadow: 0 0 0 4px var(--accent-soft); }
    textarea {
      width: 100%;
      min-height: 38px;
      max-height: 150px;
      padding: 9px 0 7px;
      overflow-y: auto;
      resize: none;
      border: 0;
      outline: 0 !important;
      background: transparent;
      color: var(--text);
      line-height: 1.45;
      font-size: 14px;
    }
    textarea::placeholder { color: var(--muted); }
    .send-btn {
      width: 42px;
      height: 42px;
      flex: 0 0 auto;
      display: grid;
      place-items: center;
      border: 0;
      border-radius: 13px;
      background: var(--accent);
      color: var(--accent-text);
      cursor: pointer;
      font-size: 18px;
      font-weight: 900;
      transition: transform .15s ease, filter .15s ease;
    }
    .send-btn:hover { transform: translateY(-1px); filter: brightness(1.06); }
    .send-btn:disabled { opacity: .45; cursor: default; transform: none; }
    .send-btn.stop { background: var(--surface-hover); color: var(--bad); border: 1px solid var(--border-strong); }
    .composer-meta { display: flex; justify-content: space-between; gap: 12px; min-height: 15px; padding: 7px 4px 0; color: var(--muted); font-size: 10px; }
    #charCount { font-variant-numeric: tabular-nums; }

    .modal-backdrop {
      position: fixed;
      z-index: 30;
      inset: 0;
      display: grid;
      place-items: center;
      padding: 20px;
      background: rgba(2, 5, 10, .64);
      animation: fade-in .16s ease-out;
    }
    .modal-backdrop[hidden] { display: none; }
    .model-modal {
      width: min(620px, 100%);
      max-height: min(670px, 86dvh);
      overflow: hidden;
      display: grid;
      grid-template-rows: auto auto minmax(0, 1fr) auto;
      border: 1px solid var(--border-strong);
      border-radius: 22px;
      background: var(--surface-solid);
      box-shadow: 0 30px 100px rgba(0, 0, 0, .55);
      animation: modal-in .2s ease-out;
    }
    .modal-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 20px; padding: 20px 20px 14px; }
    .modal-head h2 { margin: 0; font-size: 17px; }
    .modal-head p { margin: 5px 0 0; color: var(--muted); font-size: 12px; }
    .modal-close { flex: 0 0 auto; }
    .search-wrap { padding: 0 20px 14px; }
    .search-wrap input { width: 100%; height: 42px; padding: 0 14px; border: 1px solid var(--border); border-radius: 12px; background: var(--bg); color: var(--text); font-size: 13px; }
    .model-list { min-height: 180px; overflow-y: auto; padding: 0 12px 12px; }
    .model-item { width: 100%; min-height: 52px; display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 12px; padding: 9px 11px; border: 1px solid transparent; border-bottom-color: var(--border); border-radius: 10px; background: transparent; color: var(--muted-strong); text-align: left; cursor: pointer; transition: background .15s ease, border-color .15s ease; }
    .model-item:last-child { border-bottom-color: transparent; }
    .model-item:last-child.active { border-bottom-color: #2a655e; }
    .model-item:hover { border-color: var(--border-strong); background: var(--surface-raised); }
    .model-item.active { border-color: #2a655e; background: var(--accent-soft); color: var(--accent); }
    .model-item:disabled { opacity: .55; cursor: wait; }
    .model-radio { width: 17px; height: 17px; display: grid; place-items: center; border: 1px solid var(--border-strong); border-radius: 50%; }
    .model-radio::after { width: 7px; height: 7px; border-radius: 50%; background: transparent; content: ""; }
    .model-item.active .model-radio { border-color: var(--accent); }
    .model-item.active .model-radio::after { background: var(--accent); }
    .model-name { min-width: 0; overflow: hidden; font: 12px ui-monospace, SFMono-Regular, Consolas, monospace; text-overflow: ellipsis; white-space: nowrap; }
    .model-state { color: var(--muted); font: 700 9px Inter, sans-serif; letter-spacing: .05em; text-transform: uppercase; }
    .model-item:hover .model-state { color: var(--accent); }
    .model-item.active .model-state { color: var(--accent); }
    .model-empty { display: grid; place-items: center; min-height: 180px; padding: 28px; color: var(--muted); text-align: center; font-size: 13px; }
    .skeleton { height: 42px; margin: 6px 8px; border-radius: 10px; background: var(--surface-raised); animation: pulse 1.1s infinite ease-in-out; }
    .modal-foot { padding: 12px 20px; border-top: 1px solid var(--border); color: var(--muted); font-size: 10px; }

    .toast-region { position: fixed; z-index: 50; right: 18px; bottom: 18px; display: grid; gap: 8px; pointer-events: none; }
    .toast { max-width: min(380px, calc(100vw - 36px)); padding: 11px 14px; border: 1px solid var(--border-strong); border-radius: 13px; background: var(--surface-solid); color: var(--muted-strong); box-shadow: var(--shadow); font-size: 12px; animation: toast-in .25s ease-out; }
    .toast.good { border-color: #347855; }
    .toast.error { border-color: #7c3c44; color: var(--bad); }

    @keyframes typing { 0%, 60%, 100% { transform: translateY(0); opacity: .35; } 30% { transform: translateY(-4px); opacity: 1; } }
    @keyframes pulse { 0%, 100% { opacity: .45; } 50% { opacity: 1; } }
    @keyframes fade-in { from { opacity: 0; } }
    @keyframes fade-up { from { opacity: 0; transform: translateY(7px); } }
    @keyframes pop-in { from { opacity: 0; transform: scale(.97) translateY(-4px); } }
    @keyframes modal-in { from { opacity: 0; transform: scale(.97) translateY(8px); } }
    @keyframes toast-in { from { opacity: 0; transform: translateY(8px); } }

    @media (max-width: 680px) {
      .app-shell { padding-left: 10px; padding-right: 10px; gap: 9px; }
      .brand p, .status-text { display: none; }
      .status-pill { width: 38px; padding: 0; justify-content: center; }
      .action-label { display: none; }
      .action-btn { width: 38px; padding: 0; justify-content: center; }
      .model-selector-btn { width: auto; min-width: 0; max-width: 48vw; padding: 5px 9px; }
      .model-button-label, .count-badge { display: none; }
      .model-button-name { max-width: 105px; }
      .toolbar { padding: 7px; }
      #chatlog { padding: 20px 12px 12px; }
      .message-stack, .message-row.assistant .message-stack { max-width: 90%; }
      .composer-wrap { padding: 9px; }
      .composer-meta span:first-child { display: none; }
      .modal-backdrop { padding: 10px; align-items: end; }
      .model-modal { width: 100%; max-height: 80dvh; border-radius: 22px 22px 14px 14px; }
    }

    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after { scroll-behavior: auto !important; animation-duration: .01ms !important; animation-iteration-count: 1 !important; }
    }
  </style>
</head>
<body>
  <main class="app-shell">
    <header class="topbar">
      <div class="brand">
        <div class="brand-mark" aria-hidden="true">J</div>
        <div>
          <h1>Jarvis</h1>
          <p>Your Home Assistant copilot</p>
        </div>
      </div>
      <div class="top-actions">
        <button class="status-pill" id="status" type="button" onclick="refreshStatus()" aria-label="Refresh connection status" title="Refresh status">
          <span class="status-dot"></span>
          <span class="status-text">Connecting</span>
        </button>
      </div>
    </header>

    <section class="toolbar" aria-label="Chat tools">
      <div class="tool-group">
        <button class="action-btn" id="testBtn" type="button" onclick="testKey()" title="Test API key">
          <span class="action-symbol" aria-hidden="true">✓</span><span class="action-label">Test key</span>
        </button>
        <button class="action-btn model-selector-btn" id="modelsBtn" type="button" onclick="openModels()" title="Choose the model Jarvis uses">
          <span class="action-symbol" aria-hidden="true">◎</span>
          <span class="model-button-copy">
            <span class="model-button-label">Model</span>
            <strong class="model-button-name" id="modelButtonName">Loading…</strong>
          </span>
          <span class="count-badge" id="modelCount">—</span>
          <span class="selector-chevron" aria-hidden="true">⌄</span>
        </button>
        <button class="action-btn" type="button" onclick="clearChat()" title="Clear conversation">
          <span class="action-symbol" aria-hidden="true">×</span><span class="action-label">Clear</span>
        </button>
      </div>
      <button class="icon-btn" type="button" onclick="toggleDetails(event)" aria-label="Show connection details" title="Connection details">⋯</button>

      <aside class="details-popover" id="detailsPopover" hidden>
        <h2 class="details-title">Connection details</h2>
        <dl class="detail-grid">
          <dt>Add-on</dt><dd id="detailEnabled">Checking…</dd>
          <dt>API key</dt><dd id="detailKey">Checking…</dd>
          <dt>Model</dt><dd id="detailModel">—</dd>
          <dt>Program</dt><dd id="detailProgram">—</dd>
        </dl>
      </aside>
    </section>

    <section class="chat-panel" aria-label="Jarvis conversation">
      <div id="chatlog" role="log" aria-live="polite" aria-relevant="additions">
        <div class="welcome" id="welcome">
          <div class="welcome-mark" aria-hidden="true">J</div>
          <h2>What can I help with?</h2>
          <p>Ask about your Home Assistant setup, troubleshoot an automation, or plan what to build next.</p>
          <div class="suggestions" aria-label="Suggested prompts">
            <button class="suggestion" type="button" onclick="useSuggestion(this)">Help me plan an automation</button>
            <button class="suggestion" type="button" onclick="useSuggestion(this)">Explain my next setup step</button>
            <button class="suggestion" type="button" onclick="useSuggestion(this)">Troubleshoot a device</button>
          </div>
        </div>
      </div>

      <div class="composer-wrap">
        <div class="composer">
          <textarea id="message" rows="1" maxlength="8000" aria-label="Message Jarvis" placeholder="Message Jarvis…"></textarea>
          <button class="send-btn" id="sendBtn" type="button" onclick="handleSendButton()" aria-label="Send message" title="Send message">↑</button>
        </div>
        <div class="composer-meta">
          <span>Enter to send · Shift + Enter for a new line</span>
          <span id="charCount">0 / 8,000</span>
        </div>
      </div>
    </section>
  </main>

  <div class="modal-backdrop" id="modelsModal" hidden role="presentation" onclick="backdropClose(event)">
    <section class="model-modal" role="dialog" aria-modal="true" aria-labelledby="modelsTitle">
      <div class="modal-head">
        <div>
          <h2 id="modelsTitle">Choose a model</h2>
          <p>Currently using <strong id="modalActiveModel">Loading…</strong></p>
        </div>
        <button class="icon-btn modal-close" type="button" onclick="closeModels()" aria-label="Close models">×</button>
      </div>
      <div class="search-wrap">
        <input id="modelSearch" type="search" placeholder="Filter models…" aria-label="Filter models" oninput="renderModels()" />
      </div>
      <div class="model-list" id="modelList"></div>
      <div class="modal-foot">Select any model in the list to switch immediately. Your choice is saved across restarts.</div>
    </section>
  </div>

  <div class="toast-region" id="toastRegion" aria-live="polite" aria-atomic="true"></div>

<script>
let historyItems = [];
let availableModels = [];
let activeModel = "";
let isSending = false;
let isSelectingModel = false;
let chatController = null;

const chatlog = document.getElementById("chatlog");
const input = document.getElementById("message");
const sendButton = document.getElementById("sendBtn");

function apiPath(path) {
  return "api/" + path;
}

function timeLabel() {
  return new Intl.DateTimeFormat([], { hour: "numeric", minute: "2-digit" }).format(new Date());
}

function scrollChat() {
  requestAnimationFrame(() => { chatlog.scrollTop = chatlog.scrollHeight; });
}

function removeWelcome() {
  document.getElementById("welcome")?.remove();
}

function addMsg(role, text) {
  removeWelcome();
  const row = document.createElement("article");
  row.className = "message-row " + role;

  const stack = document.createElement("div");
  stack.className = "message-stack";

  const label = document.createElement("div");
  label.className = "message-label";
  label.textContent = role === "user" ? "You" : "Jarvis";

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";
  bubble.textContent = text;

  const stamp = document.createElement("time");
  stamp.className = "message-time";
  stamp.textContent = timeLabel();

  stack.append(label, bubble, stamp);
  row.appendChild(stack);
  chatlog.appendChild(row);
  scrollChat();
  return row;
}

function addNotice(text, isError = false) {
  removeWelcome();
  const notice = document.createElement("div");
  notice.className = "notice" + (isError ? " error" : "");
  notice.textContent = text;
  chatlog.appendChild(notice);
  scrollChat();
}

function showTyping() {
  removeTyping();
  removeWelcome();
  const row = document.createElement("article");
  row.className = "message-row assistant";
  row.id = "typingIndicator";
  row.setAttribute("aria-label", "Jarvis is thinking");

  const stack = document.createElement("div");
  stack.className = "message-stack";
  const label = document.createElement("div");
  label.className = "message-label";
  label.textContent = "Jarvis";
  const bubble = document.createElement("div");
  bubble.className = "message-bubble typing-bubble";
  const dots = document.createElement("span");
  dots.className = "typing-dots";
  dots.setAttribute("aria-hidden", "true");
  dots.append(document.createElement("i"), document.createElement("i"), document.createElement("i"));
  const text = document.createElement("span");
  text.className = "thinking-text";
  text.textContent = "Thinking";
  bubble.append(dots, text);
  stack.append(label, bubble);
  row.appendChild(stack);
  chatlog.appendChild(row);
  scrollChat();
}

function removeTyping() {
  document.getElementById("typingIndicator")?.remove();
}

function toast(message, type = "") {
  const el = document.createElement("div");
  el.className = "toast " + type;
  el.textContent = message;
  document.getElementById("toastRegion").appendChild(el);
  window.setTimeout(() => el.remove(), 3600);
}

function setStatus(text, cls) {
  const el = document.getElementById("status");
  el.className = "status-pill " + (cls || "");
  el.querySelector(".status-text").textContent = text;
  el.title = text + " · click to refresh";
}

function updateActiveModelUi() {
  const displayName = activeModel || "Choose a model";
  document.getElementById("modelButtonName").textContent = displayName;
  document.getElementById("modalActiveModel").textContent = displayName;
  document.getElementById("detailModel").textContent = displayName;
  document.getElementById("modelsBtn").title = "Current model: " + displayName + " · click to change";
}

async function refreshStatus(showConfirmation = false) {
  setStatus("Checking", "");
  try {
    const response = await fetch(apiPath("status"));
    const data = await response.json();
    activeModel = data.model || "Not configured";
    updateActiveModelUi();

    if (!data.enabled) setStatus("Disabled", "warn");
    else if (!data.has_openai_api_key) setStatus("Key needed", "warn");
    else setStatus("Online", "ok");

    document.getElementById("detailEnabled").textContent = data.enabled ? "Enabled" : "Disabled";
    document.getElementById("detailKey").textContent = data.has_openai_api_key ? "Configured" : "Missing";
    document.getElementById("detailProgram").textContent = data.program_file;
    if (showConfirmation) toast("Status refreshed", "good");
  } catch (error) {
    setStatus("Offline", "bad");
    document.getElementById("modelButtonName").textContent = "Unavailable";
    if (showConfirmation) toast("Jarvis is currently unreachable", "error");
  }
}

async function testKey() {
  const button = document.getElementById("testBtn");
  button.disabled = true;
  const oldLabel = button.querySelector(".action-label")?.textContent;
  if (button.querySelector(".action-label")) button.querySelector(".action-label").textContent = "Testing…";
  try {
    const response = await fetch(apiPath("test-openai"), { method: "POST" });
    const data = await response.json();
    if (!data.ok) throw new Error(data.error || "The API key test failed.");
    toast(data.message, "good");
  } catch (error) {
    toast("API key test failed: " + error.message, "error");
  } finally {
    button.disabled = false;
    if (button.querySelector(".action-label")) button.querySelector(".action-label").textContent = oldLabel;
    refreshStatus();
  }
}

function openModels() {
  const modal = document.getElementById("modelsModal");
  modal.hidden = false;
  document.body.dataset.modalOpen = "true";
  document.getElementById("modelSearch").value = "";
  if (availableModels.length) {
    renderModels();
    document.getElementById("modelSearch").focus();
  } else {
    fetchModels();
  }
}

function closeModels() {
  document.getElementById("modelsModal").hidden = true;
  delete document.body.dataset.modalOpen;
  document.getElementById("modelsBtn").focus();
}

function backdropClose(event) {
  if (event.target.id === "modelsModal") closeModels();
}

async function fetchModels() {
  const list = document.getElementById("modelList");
  list.replaceChildren();
  for (let i = 0; i < 6; i += 1) {
    const skeleton = document.createElement("div");
    skeleton.className = "skeleton";
    list.appendChild(skeleton);
  }

  try {
    const response = await fetch(apiPath("models"));
    const data = await response.json();
    if (!data.ok) throw new Error(data.error || "Could not fetch models.");
    availableModels = data.models || [];
    activeModel = data.selected_model || activeModel;
    updateActiveModelUi();
    document.getElementById("modelCount").textContent = availableModels.length;
    renderModels();
    document.getElementById("modelSearch").focus();
  } catch (error) {
    list.replaceChildren();
    const empty = document.createElement("div");
    empty.className = "model-empty";
    empty.textContent = "Could not load models. " + error.message;
    list.appendChild(empty);
    document.getElementById("modelCount").textContent = "!";
  }
}

function renderModels() {
  const query = document.getElementById("modelSearch").value.trim().toLowerCase();
  const filtered = availableModels.filter(model => model.toLowerCase().includes(query));
  const list = document.getElementById("modelList");
  list.replaceChildren();

  if (!filtered.length) {
    const empty = document.createElement("div");
    empty.className = "model-empty";
    empty.textContent = query ? "No models match your search." : "No models were returned.";
    list.appendChild(empty);
    return;
  }

  const fragment = document.createDocumentFragment();
  filtered.forEach(model => {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "model-item" + (model === activeModel ? " active" : "");
    row.disabled = isSelectingModel;
    row.setAttribute("aria-label", model === activeModel ? model + ", currently active" : "Use " + model);
    const radio = document.createElement("span");
    radio.className = "model-radio";
    radio.setAttribute("aria-hidden", "true");
    const name = document.createElement("span");
    name.className = "model-name";
    name.textContent = model;
    const state = document.createElement("span");
    state.className = "model-state";
    state.textContent = model === activeModel ? "Active" : "Select";
    row.append(radio, name, state);
    row.addEventListener("click", () => selectModel(model));
    fragment.appendChild(row);
  });
  list.appendChild(fragment);
}

async function selectModel(model) {
  if (isSelectingModel) return;
  if (model === activeModel) {
    closeModels();
    return;
  }

  isSelectingModel = true;
  renderModels();
  try {
    const response = await fetch(apiPath("model"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model })
    });
    const data = await response.json();
    if (!data.ok) throw new Error(data.error || "Could not change models.");

    activeModel = data.model;
    updateActiveModelUi();
    if (historyItems.length) addNotice("Now using " + activeModel + ".");
    toast("Model switched to " + activeModel, "good");
    closeModels();
  } catch (error) {
    toast("Could not switch model: " + error.message, "error");
  } finally {
    isSelectingModel = false;
    renderModels();
  }
}

function autoSizeInput() {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 150) + "px";
  document.getElementById("charCount").textContent = input.value.length.toLocaleString() + " / 8,000";
  if (!isSending) sendButton.disabled = !input.value.trim();
}

function setSendingState(sending) {
  isSending = sending;
  sendButton.classList.toggle("stop", sending);
  sendButton.textContent = sending ? "■" : "↑";
  sendButton.setAttribute("aria-label", sending ? "Stop response" : "Send message");
  sendButton.title = sending ? "Stop response" : "Send message";
  sendButton.disabled = sending ? false : !input.value.trim();
}

function handleSendButton() {
  if (isSending) {
    chatController?.abort();
  } else {
    sendMessage();
  }
}

async function sendMessage() {
  const text = input.value.trim();
  if (!text || isSending) return;

  const previousHistory = historyItems.slice(-10);
  input.value = "";
  autoSizeInput();
  addMsg("user", text);
  showTyping();
  setSendingState(true);
  chatController = new AbortController();

  try {
    const response = await fetch(apiPath("chat"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, history: previousHistory }),
      signal: chatController.signal
    });
    const data = await response.json();
    if (!data.ok) throw new Error(data.error || "Jarvis could not answer.");
    removeTyping();
    addMsg("assistant", data.answer);
    historyItems.push({ role: "user", content: text });
    historyItems.push({ role: "assistant", content: data.answer });
    if (data.model && data.model !== activeModel) {
      activeModel = data.model;
      document.getElementById("detailModel").textContent = activeModel;
    }
  } catch (error) {
    removeTyping();
    if (error.name === "AbortError") {
      addNotice("Response stopped.");
    } else {
      addNotice("Something went wrong: " + error.message, true);
    }
  } finally {
    chatController = null;
    setSendingState(false);
    input.focus();
  }
}

function clearChat() {
  chatController?.abort();
  historyItems = [];
  chatlog.replaceChildren();

  const welcome = document.createElement("div");
  welcome.className = "welcome";
  welcome.id = "welcome";
  const mark = document.createElement("div");
  mark.className = "welcome-mark";
  mark.setAttribute("aria-hidden", "true");
  mark.textContent = "J";
  const title = document.createElement("h2");
  title.textContent = "Fresh conversation";
  const copy = document.createElement("p");
  copy.textContent = "Your chat history has been cleared. What would you like to work on?";
  welcome.append(mark, title, copy);
  chatlog.appendChild(welcome);
  toast("Conversation cleared");
  input.focus();
}

function useSuggestion(button) {
  input.value = button.textContent;
  autoSizeInput();
  input.focus();
}

function toggleDetails(event) {
  event.stopPropagation();
  const popover = document.getElementById("detailsPopover");
  popover.hidden = !popover.hidden;
}

input.addEventListener("input", autoSizeInput);
input.addEventListener("keydown", event => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    if (!isSending) sendMessage();
  }
});

document.addEventListener("click", event => {
  const popover = document.getElementById("detailsPopover");
  if (!popover.hidden && !popover.contains(event.target)) popover.hidden = true;
});

document.addEventListener("keydown", event => {
  if (event.key === "Escape") {
    if (!document.getElementById("modelsModal").hidden) closeModels();
    document.getElementById("detailsPopover").hidden = true;
  }
});

autoSizeInput();
refreshStatus();
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return HTML
