import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "emoji.db"


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS emoji_dict (
            word       TEXT PRIMARY KEY,
            emoji      TEXT NOT NULL,
            source     TEXT NOT NULL DEFAULT 'seed',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """)
    conn.commit()
    conn.close()


def lookup_word(word: str) -> str | None:
    conn = get_db()
    row = conn.execute(
        "SELECT emoji FROM emoji_dict WHERE word = ?", (word,)
    ).fetchone()
    conn.close()
    return row["emoji"] if row else None


def save_word(word: str, emoji: str, source: str = "gemini") -> None:
    conn = get_db()
    conn.execute(
        """
        INSERT INTO emoji_dict (word, emoji, source)
        VALUES (?, ?, ?)
        ON CONFLICT(word) DO UPDATE SET emoji = excluded.emoji, source = excluded.source
        """,
        (word, emoji, source),
    )
    conn.commit()
    conn.close()


def word_count() -> int:
    conn = get_db()
    row = conn.execute("SELECT COUNT(*) AS c FROM emoji_dict").fetchone()
    conn.close()
    return row["c"]
