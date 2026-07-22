import json
import os
from pathlib import Path
from time import time
from typing import Any

import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from openai import AsyncOpenAI
from pydantic import BaseModel

OPTIONS_FILE = Path("/data/options.json")
PROGRAM_FILE = Path("/config/jarvis/main.py")

DEFAULT_OPTIONS = {
    "enabled": True,
    "openai_api_key": "",
    "model": "gpt-5.6-luna",
    "create_persistent_notification_on_online": True,
    "system_prompt": (
        "You are Jarvis, a concise Home Assistant chatbot. "
        "Help the user clearly and safely. In v1, do not claim to control devices "
        "unless code for that is added later."
    ),
}

app = FastAPI(title="Jarvis")


class ChatRequest(BaseModel):
    message: str
    history: list[dict[str, str]] | None = None


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


@app.on_event("startup")
async def startup_event() -> None:
    await create_online_notification()


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "name": "Jarvis", "time": int(time())}


@app.get("/api/status")
def status() -> dict[str, Any]:
    options = load_options()
    return {
        "ok": True,
        "enabled": bool(options.get("enabled", True)),
        "model": options.get("model", ""),
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
        return JSONResponse({"ok": True, "models": ids})
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
        model = str(options.get("model") or DEFAULT_OPTIONS["model"]).strip()
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
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Jarvis</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #111315;
      --card: #1e2024;
      --card2: #272a2f;
      --text: #f4f7fb;
      --muted: #aeb6c2;
      --border: #343941;
      --good: #3fb950;
      --bad: #ff6b6b;
      --warn: #f5c542;
      --accent: #03a9f4;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
    }
    .wrap { max-width: 1000px; margin: 0 auto; padding: 18px; }
    .top { display: flex; gap: 14px; align-items: center; justify-content: space-between; flex-wrap: wrap; }
    h1 { margin: 0; font-size: 28px; letter-spacing: .2px; }
    .badge { border: 1px solid var(--border); background: var(--card); padding: 8px 12px; border-radius: 999px; color: var(--muted); }
    .card { background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 16px; margin-top: 16px; }
    .row { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
    button {
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 10px 14px;
      color: var(--text);
      background: var(--card2);
      cursor: pointer;
      font-weight: 650;
    }
    button.primary { background: var(--accent); border-color: var(--accent); color: #00131f; }
    button:hover { filter: brightness(1.12); }
    button:disabled { opacity: .55; cursor: not-allowed; }
    #chatlog { display: flex; flex-direction: column; gap: 12px; min-height: 350px; max-height: 62vh; overflow: auto; padding-right: 4px; }
    .msg { border: 1px solid var(--border); border-radius: 14px; padding: 12px 14px; line-height: 1.45; white-space: pre-wrap; }
    .user { background: #123247; align-self: flex-end; max-width: 82%; }
    .assistant { background: var(--card2); align-self: flex-start; max-width: 88%; }
    .system { background: #272417; color: var(--muted); max-width: 100%; }
    textarea {
      flex: 1 1 520px;
      min-height: 80px;
      resize: vertical;
      background: #0f1114;
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 12px;
      color: var(--text);
      font: inherit;
    }
    pre { overflow: auto; background: #0f1114; border: 1px solid var(--border); border-radius: 12px; padding: 12px; color: var(--muted); }
    .ok { color: var(--good); }
    .bad { color: var(--bad); }
    .warn { color: var(--warn); }
    .small { color: var(--muted); font-size: 13px; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      <h1>🤖 Jarvis</h1>
      <div class="badge" id="status">Checking status...</div>
    </div>

    <div class="card">
      <div class="row">
        <button onclick="refreshStatus()">Refresh status</button>
        <button onclick="testKey()">Test API key</button>
        <button onclick="fetchModels()">Fetch models</button>
        <button onclick="clearChat()">Clear chat</button>
      </div>
      <p class="small" id="configLine">Loading config...</p>
      <pre id="modelsBox" style="display:none"></pre>
    </div>

    <div class="card">
      <div id="chatlog"></div>
    </div>

    <div class="card">
      <div class="row">
        <textarea id="message" placeholder="Ask Jarvis something... Example: Explain what I need to add next to control Home Assistant entities."></textarea>
        <button class="primary" id="sendBtn" onclick="sendMessage()">Send</button>
      </div>
      <p class="small">The editable Python file is <code>/config/jarvis/main.py</code>. Saving that file reloads this app automatically.</p>
    </div>
  </div>

<script>
let historyItems = [];

function addMsg(role, text) {
  const log = document.getElementById("chatlog");
  const div = document.createElement("div");
  div.className = "msg " + role;
  div.textContent = text;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

function setStatus(text, cls) {
  const el = document.getElementById("status");
  el.textContent = text;
  el.className = "badge " + (cls || "");
}

async function refreshStatus() {
  try {
    const r = await fetch("api/status");
    const data = await r.json();
    if (!data.enabled) setStatus("Disabled", "warn");
    else if (!data.has_openai_api_key) setStatus("Missing API key", "warn");
    else setStatus("Online", "ok");
    document.getElementById("configLine").textContent = `Enabled: ${data.enabled} | Model: ${data.model || "blank"} | API key set: ${data.has_openai_api_key} | Program: ${data.program_file}`;
  } catch (e) {
    setStatus("Offline", "bad");
    document.getElementById("configLine").textContent = String(e);
  }
}

async function testKey() {
  addMsg("system", "Testing OpenAI API key...");
  try {
    const r = await fetch("api/test-openai", { method: "POST" });
    const data = await r.json();
    addMsg("system", data.ok ? data.message : `Error: ${data.error}`);
  } catch (e) {
    addMsg("system", `Error: ${e}`);
  }
}

async function fetchModels() {
  const box = document.getElementById("modelsBox");
  box.style.display = "block";
  box.textContent = "Fetching models...";
  try {
    const r = await fetch("api/models");
    const data = await r.json();
    if (!data.ok) {
      box.textContent = `Error: ${data.error}`;
      return;
    }
    box.textContent = data.models.join("\n");
  } catch (e) {
    box.textContent = String(e);
  }
}

async function sendMessage() {
  const input = document.getElementById("message");
  const button = document.getElementById("sendBtn");
  const text = input.value.trim();
  if (!text) return;

  input.value = "";
  addMsg("user", text);
  button.disabled = true;

  try {
    const r = await fetch("api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, history: historyItems.slice(-10) })
    });
    const data = await r.json();
    if (!data.ok) {
      addMsg("system", `Error: ${data.error}`);
      return;
    }
    addMsg("assistant", data.answer);
    historyItems.push({ role: "user", content: text });
    historyItems.push({ role: "assistant", content: data.answer });
  } catch (e) {
    addMsg("system", `Error: ${e}`);
  } finally {
    button.disabled = false;
    input.focus();
  }
}

function clearChat() {
  historyItems = [];
  document.getElementById("chatlog").innerHTML = "";
  addMsg("system", "Chat cleared.");
}

document.getElementById("message").addEventListener("keydown", function(e) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

refreshStatus();
addMsg("system", "Jarvis v1 loaded. Configure the API key and model in the add-on Configuration tab, then test the key.");
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return HTML
