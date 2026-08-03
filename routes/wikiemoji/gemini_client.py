import json
import os
import re

import requests

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)


CHUNK_SIZE = 40

_EMOJI_RE = re.compile(
    "["
    "\U0001f300-\U0001faff"
    "\U00002600-\U000027bf"
    "\U0001f1e6-\U0001f1ff"
    "\u2190-\u21ff"
    "\ufe0f"
    "\u200d"
    "]+"
)


def _ask_gemini_chunk(words: list[str]) -> dict[str, str]:
    if not GEMINI_API_KEY or not words:
        return {}

    word_list = "\n".join(f"- {w}" for w in words)
    prompt = (
        "For EACH of the following English words, pick a single emoji (or at most "
        "a short sequence of 2-3 emoji) that best represents it.\n\n"
        f"Words:\n{word_list}\n\n"
        "Respond with ONLY a JSON object mapping each word (exactly as given, "
        "lowercase) to its emoji string. Every single word listed above MUST "
        "appear as a key — do not skip or omit any of them. No markdown fences, "
        'no explanation, no extra keys. Example shape: {"cat": "🐱", "run": "🏃"}'
    )

    try:
        resp = requests.post(
            GEMINI_URL,
            params={"key": GEMINI_API_KEY},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "response_mime_type": "application/json",
                    "maxOutputTokens": 4096,
                },
            },
            timeout=30,
        )

        if not resp.ok:
            print(
                f"[gemini_client] {resp.status_code} error for batch of {len(words)} words: {resp.text}"
            )
            return {}

        data = resp.json()
        candidate = data["candidates"][0]
        finish_reason = candidate.get("finishReason")
        text = candidate["content"]["parts"][0]["text"].strip()

        if finish_reason == "MAX_TOKENS":
            print(
                f"[gemini_client] response for {len(words)} words was cut off "
                f"(MAX_TOKENS) — some words in this chunk may be missing"
            )

        try:
            raw_map = json.loads(text)
        except json.JSONDecodeError:
            print(f"[gemini_client] couldn't parse JSON from Gemini response: {text!r}")
            return {}

        result = {}
        for word, value in raw_map.items():
            if not isinstance(value, str):
                continue
            found = _EMOJI_RE.findall(value)
            if found:
                result[word.strip().lower()] = "".join(found)[:8]

        missing = set(words) - result.keys()
        if missing:
            print(
                f"[gemini_client] Gemini didn't return an emoji for: {sorted(missing)}"
            )

        return result

    except Exception as exc:
        print(f"[gemini_client] batch lookup failed for {len(words)} words: {exc}")
        return {}


def ask_gemini_for_emojis(words: list[str]) -> dict[str, str]:
    if not GEMINI_API_KEY or not words:
        return {}

    result = {}
    for i in range(0, len(words), CHUNK_SIZE):
        chunk = words[i : i + CHUNK_SIZE]
        result.update(_ask_gemini_chunk(chunk))

    return result
