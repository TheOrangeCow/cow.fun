import re

from flask import Flask, jsonify, render_template, request

from routes.wikiemoji.database import init_db, lookup_word, save_word
from routes.wikiemoji.gemini_client import ask_gemini_for_emojis


from flask import Blueprint, jsonify, request

wikiemoji = Blueprint("wikiemoji", __name__)


init_db()

FALLBACK_POOL = ["✨"]

_CLEAN_RE = re.compile(r"[^a-z0-9']")


def hash_str(s: str) -> int:
    h = 0
    for ch in s:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h


def clean_word(word: str) -> str:
    return _CLEAN_RE.sub("", word.lower())


@wikiemoji.route("/api/translate", methods=["POST"])
def translate():
    payload = request.get_json(silent=True) or {}
    text = payload.get("text", "")

    if not isinstance(text, str) or not text.strip():
        return jsonify({"error": "field 'text' is required"}), 400

    cleaned_words = [clean_word(w) for w in text.split()]
    cleaned_words = [w for w in cleaned_words if w]

    db_hits = {}
    unknown_words = []
    seen_unknown = set()

    for word in cleaned_words:
        emoji = lookup_word(word)
        if emoji is not None:
            db_hits[word] = emoji
        elif word not in seen_unknown:
            unknown_words.append(word)
            seen_unknown.add(word)

    gemini_hits = ask_gemini_for_emojis(unknown_words) if unknown_words else {}

    coined_by_gemini = []
    fallback_map = {}

    for word in unknown_words:
        emoji = gemini_hits.get(word)
        if emoji:
            save_word(word, emoji, source="gemini")
            coined_by_gemini.append(word)
        else:
            fallback_map[word] = FALLBACK_POOL[hash_str(word) % len(FALLBACK_POOL)]

    results = []
    for word in cleaned_words:
        if word in db_hits:
            emoji, source = db_hits[word], "db"
        elif word in gemini_hits:
            emoji, source = gemini_hits[word], "gemini"
        else:
            emoji, source = fallback_map[word], "fallback"
        results.append({"word": word, "emoji": emoji, "source": source})

    return jsonify(
        {
            "emoji_text": " ".join(r["emoji"] for r in results),
            "words": results,
            "coined_by_gemini": coined_by_gemini,
        }
    )
