import os
import time
import sqlite3

from flask import Blueprint, request, jsonify

graveyard = Blueprint("graveyard", __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "graveyard.db")


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS graves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            created_at INTEGER NOT NULL
        )""")
    return conn


@graveyard.route("/api/graves", methods=["GET"])
def list_graves():
    conn = get_db()
    rows = conn.execute("SELECT * FROM graves ORDER BY created_at DESC").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@graveyard.route("/api/graves", methods=["POST"])
def add_grave():
    data = request.get_json(force=True, silent=True) or {}

    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()

    if not title:
        return jsonify({"error": "title required"}), 400

    title = title[:80]
    description = description[:500]

    now = int(time.time())

    conn = get_db()
    cur = conn.execute(
        "INSERT INTO graves (title, description, created_at) VALUES (?, ?, ?)",
        (title, description, now),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()

    return (
        jsonify(
            {
                "id": new_id,
                "title": title,
                "description": description,
                "created_at": now,
            }
        ),
        201,
    )


@graveyard.route("/api/graves/<int:grave_id>", methods=["DELETE"])
def delete_grave(grave_id):
    conn = get_db()
    conn.execute("DELETE FROM graves WHERE id = ?", (grave_id,))
    conn.commit()
    conn.close()
    return jsonify({"deleted": grave_id})
