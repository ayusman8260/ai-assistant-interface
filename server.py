"""AI chat server. Serves the UI and exposes POST /api/chat.

With ANTHROPIC_API_KEY set, messages go to the Anthropic Messages API.
Without it, the built-in offline assistant answers. The key stays on the server.

Run:  python server.py     then open http://127.0.0.1:5001
"""
import json
import os
import urllib.error
import urllib.request

from flask import Flask, jsonify, request, send_from_directory

import assistant

API_URL = "https://api.anthropic.com/v1/messages"
MAX_MESSAGES, MAX_CHARS = 40, 8000
SYSTEM_PROMPT = "You are a concise, friendly assistant. Use Markdown for lists and code."


def call_anthropic(messages, key, model):
    body = json.dumps({"model": model, "max_tokens": 1024, "system": SYSTEM_PROMPT,
                       "messages": messages}).encode()
    req = urllib.request.Request(API_URL, data=body, method="POST", headers={
        "content-type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=60) as res:
        data = json.load(res)
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


def clean(messages):
    """Validate the client's message list and return (messages, error)."""
    if not isinstance(messages, list) or not messages:
        return None, "Send at least one message."
    out = []
    for m in messages[-MAX_MESSAGES:]:
        if not isinstance(m, dict) or m.get("role") not in ("user", "assistant") \
                or not isinstance(m.get("content"), str):
            return None, "Each message needs a role (user or assistant) and text content."
        out.append({"role": m["role"], "content": m["content"][:MAX_CHARS]})
    if out[-1]["role"] != "user" or not out[-1]["content"].strip():
        return None, "The last message must be from the user."
    return out, None


def create_app():
    app = Flask(__name__, static_folder="static", static_url_path="")

    @app.get("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.get("/api/status")
    def status():
        return jsonify(mode="api" if os.environ.get("ANTHROPIC_API_KEY") else "offline")

    @app.post("/api/chat")
    def chat():
        messages, err = clean((request.get_json(silent=True) or {}).get("messages"))
        if err:
            return jsonify(error=err), 400
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            return jsonify(reply=assistant.reply(messages[-1]["content"]), mode="offline")
        try:
            model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
            return jsonify(reply=call_anthropic(messages, key, model), mode="api")
        except urllib.error.HTTPError as e:
            return jsonify(error=f"The AI service returned an error ({e.code}). Check your API key and model name."), 502
        except Exception:
            return jsonify(error="Could not reach the AI service. Check your internet connection."), 502

    return app


if __name__ == "__main__":
    create_app().run(port=5001, debug=True)
