import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from time import time
from typing import Any

import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from openai import AsyncOpenAI
from pydantic import BaseModel

OPTIONS_FILE = Path("/data/options.json")
STATE_FILE = Path("/data/jarvis_state.json")
BACKEND_FILE = Path("/config/jarvis/backend.py")
FRONTEND_FILE = Path("/config/jarvis/frontend.html")
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
        "program_file": str(BACKEND_FILE),
        "frontend_file": str(FRONTEND_FILE),
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
async def chat(payload: ChatRequest):
    options = load_options()

    if not options.get("enabled", True):
        return JSONResponse(
            {"ok": False, "error": "Jarvis is disabled in add-on options."},
            status_code=403,
        )

    user_message = payload.message.strip()

    if not user_message:
        return JSONResponse(
            {"ok": False, "error": "Message is blank."},
            status_code=400,
        )

    try:
        client = get_openai_client(options)
    except Exception as exc:
        return JSONResponse(
            {"ok": False, "error": str(exc)},
            status_code=500,
        )

    model = get_selected_model()
    system_prompt = str(
        options.get("system_prompt") or DEFAULT_OPTIONS["system_prompt"]
    ).strip()

    input_items: list[dict[str, str]] = []

    for item in (payload.history or [])[-10:]:
        role = item.get("role", "user")
        content = item.get("content", "")

        if role in {"user", "assistant"} and content:
            input_items.append(
                {
                    "role": role,
                    "content": content,
                }
            )

    input_items.append(
        {
            "role": "user",
            "content": user_message,
        }
    )

    def sse_packet(packet: dict[str, Any]) -> str:
        return f"data: {json.dumps(packet, ensure_ascii=False)}\n\n"

    async def stream_answer():
        try:
            yield sse_packet({"type": "start"})

            stream = await client.responses.create(
                model=model,
                instructions=system_prompt,
                input=input_items,
                stream=True,
            )

            async for event in stream:
                event_type = getattr(event, "type", "")

                if event_type == "response.output_text.delta":
                    delta = getattr(event, "delta", "")

                    if delta:
                        # Split chunks slightly so the UI visibly types out,
                        # even if OpenAI or the HA ingress proxy sends larger chunks.
                        chunk_size = 8

                        for index in range(0, len(delta), chunk_size):
                            small_chunk = delta[index:index + chunk_size]

                            yield sse_packet(
                                {
                                    "type": "delta",
                                    "text": small_chunk,
                                }
                            )

                            await asyncio.sleep(0.01)

                elif event_type == "error":
                    message = getattr(event, "message", "Unknown streaming error")

                    yield sse_packet(
                        {
                            "type": "error",
                            "text": f"Jarvis stream error: {message}",
                        }
                    )

            yield sse_packet({"type": "done"})

        except Exception as exc:
            yield sse_packet(
                {
                    "type": "error",
                    "text": f"Jarvis error: {exc}",
                }
            )

    return StreamingResponse(
        stream_answer(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Jarvis-Model": model,
        },
    )



@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    try:
        return HTMLResponse(FRONTEND_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        return HTMLResponse(
            f"""
            <!doctype html>
            <html lang="en">
              <head>
                <meta charset="utf-8" />
                <meta name="viewport" content="width=device-width, initial-scale=1" />
                <title>Jarvis frontend missing</title>
              </head>
              <body style="background:#0a0e10;color:#eef5f4;font-family:Arial,sans-serif;padding:24px;">
                <h1>Jarvis frontend missing</h1>
                <p>Could not read the frontend file:</p>
                <code>{FRONTEND_FILE}</code>
                <pre style="white-space:pre-wrap;color:#f17883;">{exc}</pre>
              </body>
            </html>
            """,
            status_code=500,
        )
