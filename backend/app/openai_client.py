from typing import Any
import json
from urllib import request, error

from .config import settings


def _extract_text_from_chat_response(data: Any) -> str | None:
    if not isinstance(data, dict):
        return None

    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        choice = choices[0] or {}
        if isinstance(choice, dict):
            message = choice.get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()
            text = choice.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()

    for key in ["output_text", "text", "content"]:
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    return None


def openai_explain_mn(prompt_mn: str) -> str:
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OpenAI API key not configured (OPENAI_API_KEY).")

    base = settings.OPENAI_BASE_URL.rstrip("/")
    raw_path = settings.OPENAI_CHAT_PATH.strip()
    if not raw_path.startswith("/"):
        raw_path = "/" + raw_path

    path_candidates = [
        raw_path,
        "/chat/completions",
        "/v1/chat/completions",
    ]

    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.OPENAI_MODEL,
        "messages": [{"role": "user", "content": prompt_mn}],
        "temperature": 0.7,
    }
    body = json.dumps(payload).encode("utf-8")

    last_error: Exception | None = None
    for path in path_candidates:
        url = f"{base}{path}"
        req = request.Request(url, data=body, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                data = json.loads(raw)
                text = _extract_text_from_chat_response(data)
                if text:
                    return text
                return str(data)
        except error.HTTPError as e:
            code = int(getattr(e, "code", 0) or 0)
            resp_text = ""
            try:
                resp_text = e.read().decode("utf-8", errors="replace")
            except Exception:
                resp_text = str(e)

            if code == 429:
                return "AI tailbar tur bolomjgui baina (OpenAI rate limit or quota). Daraa dahin oroldono uu."
            if code in (401, 403):
                return "AI tailbar bolomjgui baina (OpenAI auth error)."

            last_error = RuntimeError(f"OpenAI API error: {code} {resp_text}")
            continue
        except Exception as e:
            last_error = e
            continue

    raise RuntimeError(f"OpenAI API request failed: {last_error}")
