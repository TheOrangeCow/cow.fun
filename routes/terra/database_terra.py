import sqlite3
import time
import random
import string
import os
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), "game.db")

MAX_PLAUSIBLE_SPEED_MS = 95


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.executescript("""
    CREATE TABLE IF NOT EXISTS players (
        id TEXT PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT,
        lat REAL DEFAULT 0,
        lng REAL DEFAULT 0,
        last_move_ts REAL DEFAULT 0,
        flagged_count INTEGER DEFAULT 0,
        resources INTEGER DEFAULT 100,
        xp INTEGER DEFAULT 0,
        alliance_id TEXT,
        color TEXT DEFAULT '#3DF5C0',
        created_at REAL,
        last_seen REAL
    );

    CREATE TABLE IF NOT EXISTS alliances (
        id TEXT PRIMARY KEY,
        name TEXT UNIQUE NOT NULL,
        owner_id TEXT,
        created_at REAL
    );

    CREATE TABLE IF NOT EXISTS territories (
        id TEXT PRIMARY KEY,
        owner_id TEXT NOT NULL,
        lat REAL NOT NULL,
        lng REAL NOT NULL,
        radius_m REAL DEFAULT 60,
        health INTEGER DEFAULT 100,
        defense INTEGER DEFAULT 10,
        resource_rate INTEGER DEFAULT 5,
        resources_banked INTEGER DEFAULT 0,
        allow_graffiti INTEGER DEFAULT 1,
        created_at REAL,
        last_collected REAL,
        FOREIGN KEY (owner_id) REFERENCES players(id)
    );

    CREATE TABLE IF NOT EXISTS chests (
        id TEXT PRIMARY KEY,
        lat REAL NOT NULL,
        lng REAL NOT NULL,
        rarity TEXT NOT NULL,
        loot_resources INTEGER NOT NULL,
        requires_puzzle INTEGER DEFAULT 0,
        puzzle_question TEXT,
        puzzle_answer TEXT,
        spawn_date TEXT,
        claimed_by TEXT,
        claimed_at REAL
    );

    CREATE TABLE IF NOT EXISTS graffiti (
        id TEXT PRIMARY KEY,
        artist_id TEXT NOT NULL,
        lat REAL NOT NULL,
        lng REAL NOT NULL,
        style TEXT,
        color TEXT,
        message TEXT,
        likes INTEGER DEFAULT 0,
        life REAL DEFAULT 100,
        is_mural INTEGER DEFAULT 0,
        created_at REAL,
        FOREIGN KEY (artist_id) REFERENCES players(id)
    );

    CREATE TABLE IF NOT EXISTS graffiti_likes (
        graffiti_id TEXT,
        player_id TEXT,
        PRIMARY KEY (graffiti_id, player_id)
    );

    CREATE TABLE IF NOT EXISTS friend_requests (
        id TEXT PRIMARY KEY,
        from_id TEXT NOT NULL,
        to_id TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        created_at REAL
    );

    CREATE TABLE IF NOT EXISTS friends (
        player_id TEXT,
        friend_id TEXT,
        PRIMARY KEY (player_id, friend_id)
    );

    CREATE INDEX IF NOT EXISTS idx_territories_lat ON territories(lat);
    CREATE INDEX IF NOT EXISTS idx_territories_lng ON territories(lng);
    CREATE INDEX IF NOT EXISTS idx_chests_lat ON chests(lat);
    CREATE INDEX IF NOT EXISTS idx_chests_lng ON chests(lng);
    CREATE INDEX IF NOT EXISTS idx_graffiti_lat ON graffiti(lat);
    CREATE INDEX IF NOT EXISTS idx_graffiti_lng ON graffiti(lng);
    """)
    conn.commit()

    cols = [r["name"] for r in conn.execute("PRAGMA table_info(players)")]
    if "password_hash" not in cols:
        conn.execute("ALTER TABLE players ADD COLUMN password_hash TEXT")
        conn.commit()
    if "last_attack_ts" not in cols:
        conn.execute("ALTER TABLE players ADD COLUMN last_attack_ts REAL DEFAULT 0")
        conn.commit()
    conn.close()


def bbox_clause(min_lat, min_lng, max_lat, max_lng, alias=""):
    p = f"{alias}." if alias else ""
    if max_lng >= min_lng:
        return (f"{p}lat BETWEEN ? AND ? AND {p}lng BETWEEN ? AND ?",
                [min_lat, max_lat, min_lng, max_lng])
    return (f"{p}lat BETWEEN ? AND ? AND ({p}lng >= ? OR {p}lng <= ?)",
            [min_lat, max_lat, min_lng, max_lng])


def new_id(prefix=""):
    rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
    return f"{prefix}{int(time.time()*1000)}{rand}"

def register_player(username, password, color=None):
    conn = get_db()
    existing = conn.execute("SELECT id FROM players WHERE username=?", (username,)).fetchone()
    if existing:
        conn.close()
        return None
    pid = new_id("p_")
    now = time.time()
    conn.execute(
        "INSERT INTO players (id, username, password_hash, color, created_at, last_seen) "
        "VALUES (?,?,?,?,?,?)",
        (pid, username, generate_password_hash(password), color or "#3DF5C0", now, now),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM players WHERE id=?", (pid,)).fetchone()
    conn.close()
    return dict(row)


def authenticate_player(username, password):
    conn = get_db()
    row = conn.execute("SELECT * FROM players WHERE username=?", (username,)).fetchone()
    conn.close()
    if not row or not row["password_hash"]:
        return None
    if not check_password_hash(row["password_hash"], password):
        return None
    return dict(row)

def touch_player(player_id):
    conn = get_db()
    conn.execute("UPDATE players SET last_seen=? WHERE id=?", (time.time(), player_id))
    conn.commit()
    conn.close()


def check_and_update_position(player_id, lat, lng):
    conn = get_db()
    row = conn.execute("SELECT lat, lng, last_move_ts FROM players WHERE id=?", (player_id,)).fetchone()
    now = time.time()
    if row and row["last_move_ts"]:
        dt = max(now - row["last_move_ts"], 0.001)
        dist = _haversine(row["lat"], row["lng"], lat, lng)
        speed = dist / dt
        if dt > 0.5 and speed > MAX_PLAUSIBLE_SPEED_MS:
            conn.execute("UPDATE players SET flagged_count = flagged_count + 1 WHERE id=?", (player_id,))
            conn.commit()
            conn.close()
            return False, f"Movement rejected: implied speed {speed:.0f} m/s is implausible"
    conn.execute("UPDATE players SET lat=?, lng=?, last_move_ts=?, last_seen=? WHERE id=?",
                 (lat, lng, now, now, player_id))
    conn.commit()
    conn.close()
    return True, None


def _haversine(lat1, lng1, lat2, lng2):
    import math
    R = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def get_player(player_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM players WHERE id=?", (player_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_resources(player_id, amount):
    conn = get_db()
    conn.execute("UPDATE players SET resources = resources + ? WHERE id=?", (amount, player_id))
    conn.commit()
    conn.close()


def add_xp(player_id, amount):
    conn = get_db()
    conn.execute("UPDATE players SET xp = xp + ? WHERE id=?", (amount, player_id))
    conn.commit()
    conn.close()


def record_attack(player_id):
    conn = get_db()
    conn.execute("UPDATE players SET last_attack_ts=? WHERE id=?", (time.time(), player_id))
    conn.commit()
    conn.close()


def create_territory(owner_id, lat, lng, radius_m=60):
    conn = get_db()
    tid = new_id("t_")
    conn.execute(
        "INSERT INTO territories (id, owner_id, lat, lng, radius_m, created_at, last_collected) "
        "VALUES (?,?,?,?,?,?,?)",
        (tid, owner_id, lat, lng, radius_m, time.time(), time.time()),
    )
    conn.commit()
    conn.close()
    return tid


def list_territories(bbox=None):
    conn = get_db()
    sql = """
        SELECT territories.*, players.username as owner_name, players.color as owner_color
        FROM territories JOIN players ON territories.owner_id = players.id
    """
    params = []
    if bbox:
        clause, params = bbox_clause(bbox[0], bbox[1], bbox[2], bbox[3], alias="territories")
        sql += " WHERE " + clause
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_territory(tid):
    conn = get_db()
    row = conn.execute("SELECT * FROM territories WHERE id=?", (tid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def attack_territory(tid, damage):
    conn = get_db()
    conn.execute("UPDATE territories SET health = MAX(0, health - ?) WHERE id=?", (damage, tid))
    conn.commit()
    row = conn.execute("SELECT * FROM territories WHERE id=?", (tid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_territory(tid):
    conn = get_db()
    conn.execute("DELETE FROM territories WHERE id=?", (tid,))
    conn.commit()
    conn.close()

BASE_DEFENSE = 10
MAX_INVESTMENT = 100


def invest_in_territory(tid, amount):
    t = get_territory(tid)
    if not t:
        return None
    invested_so_far = t["defense"] - BASE_DEFENSE
    if invested_so_far + amount > MAX_INVESTMENT:
        return None
    conn = get_db()
    conn.execute("UPDATE territories SET defense = defense + ? WHERE id=?", (amount, tid))
    conn.commit()
    row = conn.execute("SELECT * FROM territories WHERE id=?", (tid,)).fetchone()
    conn.close()
    return dict(row)


def heal_territories():
    conn = get_db()
    conn.execute("UPDATE territories SET health = MIN(100, health + 1) WHERE health < 100")
    conn.commit()
    conn.close()


def collect_territory_resources(tid):
    t = get_territory(tid)
    if not t:
        return 0
    now = time.time()
    elapsed_hours = (now - t["last_collected"]) / 3600.0
    earned = int(elapsed_hours * t["resource_rate"] * 10)
    if earned > 0:
        conn = get_db()
        conn.execute("UPDATE territories SET last_collected=? WHERE id=?", (now, tid))
        conn.commit()
        conn.close()
        add_resources(t["owner_id"], earned)
    return earned


def territory_leaderboard():
    conn = get_db()
    rows = conn.execute("""
        SELECT players.username, players.id, COUNT(territories.id) as count
        FROM territories JOIN players ON territories.owner_id = players.id
        GROUP BY players.id ORDER BY count DESC LIMIT 20
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_todays_chests(today_str, bbox=None):
    conn = get_db()
    sql = "SELECT * FROM chests WHERE spawn_date=?"
    params = [today_str]
    if bbox:
        clause, bparams = bbox_clause(bbox[0], bbox[1], bbox[2], bbox[3])
        sql += " AND " + clause
        params += bparams
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def count_todays_chests(today_str):
    conn = get_db()
    row = conn.execute("SELECT COUNT(*) as n FROM chests WHERE spawn_date=?", (today_str,)).fetchone()
    conn.close()
    return row["n"]


def spawn_chest(lat, lng, rarity, loot, today_str, puzzle_q=None, puzzle_a=None):
    conn = get_db()
    cid = new_id("c_")
    conn.execute(
        "INSERT INTO chests (id, lat, lng, rarity, loot_resources, requires_puzzle, "
        "puzzle_question, puzzle_answer, spawn_date) VALUES (?,?,?,?,?,?,?,?,?)",
        (cid, lat, lng, rarity, loot, 1 if puzzle_q else 0, puzzle_q, puzzle_a, today_str),
    )
    conn.commit()
    conn.close()
    return cid


def claim_chest(chest_id, player_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM chests WHERE id=?", (chest_id,)).fetchone()
    if not row or row["claimed_by"]:
        conn.close()
        return None
    conn.execute("UPDATE chests SET claimed_by=?, claimed_at=? WHERE id=?",
                 (player_id, time.time(), chest_id))
    conn.commit()
    conn.close()
    add_resources(player_id, row["loot_resources"])
    add_xp(player_id, 10 if row["rarity"] == "common" else 30)
    return dict(row)


def hunter_leaderboard(today_str):
    conn = get_db()
    rows = conn.execute("""
        SELECT players.username, players.id, COUNT(chests.id) as chests_found,
               COALESCE(SUM(chests.loot_resources),0) as loot
        FROM chests JOIN players ON chests.claimed_by = players.id
        WHERE chests.spawn_date=?
        GROUP BY players.id ORDER BY loot DESC LIMIT 20
    """, (today_str,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_graffiti(artist_id, lat, lng, style, color, message):
    conn = get_db()
    gid = new_id("g_")
    conn.execute(
        "INSERT INTO graffiti (id, artist_id, lat, lng, style, color, message, created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (gid, artist_id, lat, lng, style, color, message, time.time()),
    )
    conn.commit()
    conn.close()
    return gid


def list_graffiti(bbox=None):
    conn = get_db()
    sql = """
        SELECT graffiti.*, players.username as artist_name
        FROM graffiti JOIN players ON graffiti.artist_id = players.id
        WHERE graffiti.life > 0
    """
    params = []
    if bbox:
        clause, params = bbox_clause(bbox[0], bbox[1], bbox[2], bbox[3], alias="graffiti")
        sql += " AND " + clause
    sql += " ORDER BY graffiti.created_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def like_graffiti(gid, player_id):
    conn = get_db()
    already = conn.execute(
        "SELECT * FROM graffiti_likes WHERE graffiti_id=? AND player_id=?", (gid, player_id)
    ).fetchone()
    if already:
        conn.close()
        return None
    conn.execute("INSERT INTO graffiti_likes (graffiti_id, player_id) VALUES (?,?)", (gid, player_id))
    conn.execute("UPDATE graffiti SET likes = likes + 1, life = MIN(200, life + 15) WHERE id=?", (gid,))
    conn.commit()
    row = conn.execute("SELECT * FROM graffiti WHERE id=?", (gid,)).fetchone()
    conn.close()
    return dict(row)


def decay_graffiti():
    conn = get_db()
    conn.execute("UPDATE graffiti SET life = life - 1 WHERE life > 0")
    conn.commit()
    conn.close()


def trending_graffiti(limit=10):
    conn = get_db()
    rows = conn.execute("""
        SELECT graffiti.*, players.username as artist_name
        FROM graffiti JOIN players ON graffiti.artist_id = players.id
        WHERE graffiti.life > 0
        ORDER BY graffiti.likes DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create_alliance(name, owner_id):
    conn = get_db()
    existing = conn.execute("SELECT id FROM alliances WHERE name=?", (name,)).fetchone()
    if existing:
        conn.close()
        return None
    aid = new_id("a_")
    conn.execute("INSERT INTO alliances (id, name, owner_id, created_at) VALUES (?,?,?,?)",
                 (aid, name, owner_id, time.time()))
    conn.execute("UPDATE players SET alliance_id=? WHERE id=?", (aid, owner_id))
    conn.commit()
    conn.close()
    return aid


def join_alliance(alliance_id, player_id):
    conn = get_db()
    alliance = conn.execute("SELECT * FROM alliances WHERE id=?", (alliance_id,)).fetchone()
    if not alliance:
        conn.close()
        return False
    conn.execute("UPDATE players SET alliance_id=? WHERE id=?", (alliance_id, player_id))
    conn.commit()
    conn.close()
    return True


def leave_alliance(player_id):
    conn = get_db()
    conn.execute("UPDATE players SET alliance_id=NULL WHERE id=?", (player_id,))
    conn.commit()
    conn.close()


def list_alliances():
    conn = get_db()
    rows = conn.execute("""
        SELECT alliances.*, COUNT(players.id) as member_count
        FROM alliances LEFT JOIN players ON players.alliance_id = alliances.id
        GROUP BY alliances.id ORDER BY member_count DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_alliance_members(alliance_id):
    conn = get_db()
    rows = conn.execute("SELECT id, username, color FROM players WHERE alliance_id=?", (alliance_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def are_allies(player_id_a, player_id_b):
    conn = get_db()
    a = conn.execute("SELECT alliance_id FROM players WHERE id=?", (player_id_a,)).fetchone()
    b = conn.execute("SELECT alliance_id FROM players WHERE id=?", (player_id_b,)).fetchone()
    conn.close()
    if not a or not b or not a["alliance_id"] or not b["alliance_id"]:
        return False
    return a["alliance_id"] == b["alliance_id"]


def send_friend_request(from_id, to_id):
    conn = get_db()
    existing = conn.execute(
        "SELECT * FROM friend_requests WHERE from_id=? AND to_id=? AND status='pending'",
        (from_id, to_id)
    ).fetchone()
    if existing:
        conn.close()
        return None
    rid = new_id("fr_")
    conn.execute(
        "INSERT INTO friend_requests (id, from_id, to_id, status, created_at) VALUES (?,?,?,?,?)",
        (rid, from_id, to_id, "pending", time.time()),
    )
    conn.commit()
    conn.close()
    return rid


def respond_friend_request(request_id, accept):
    conn = get_db()
    req = conn.execute("SELECT * FROM friend_requests WHERE id=?", (request_id,)).fetchone()
    if not req:
        conn.close()
        return None
    status = "accepted" if accept else "declined"
    conn.execute("UPDATE friend_requests SET status=? WHERE id=?", (status, request_id))
    if accept:
        conn.execute("INSERT OR IGNORE INTO friends (player_id, friend_id) VALUES (?,?)",
                     (req["from_id"], req["to_id"]))
        conn.execute("INSERT OR IGNORE INTO friends (player_id, friend_id) VALUES (?,?)",
                     (req["to_id"], req["from_id"]))
    conn.commit()
    conn.close()
    return status


def list_online_players(active_seconds=120):
    conn = get_db()
    cutoff = time.time() - active_seconds
    rows = conn.execute(
        "SELECT id, username, lat, lng, resources, xp, alliance_id, color, last_seen "
        "FROM players WHERE last_seen > ?", (cutoff,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]