import math
import random
import datetime
import threading
import time
import functools

from flask import Blueprint, request, jsonify, session
from flask_socketio import emit, join_room, leave_room

from routes.extensions import socketio
import routes.terra.database_terra as db

terra_bp = Blueprint("terra", __name__)


DAILY_CHEST_COUNT = 300

ATTACK_COST = 10
ATTACK_COOLDOWN_SECONDS = 30

INVESTMENT_LOT = 5
MAX_INVESTMENT = 100

HEAL_INTERVAL_SECONDS = 30
HEAL_AMOUNT = 1


CONTINENT_BOXES = [
    ("North America", 25, -125, 49, -70, 1.0),
    ("Central America", 8, -105, 23, -80, 0.3),
    ("South America", -35, -75, 5, -45, 0.7),
    ("Western Europe", 40, -9, 58, 15, 1.0),
    ("Eastern Europe", 45, 15, 58, 40, 0.6),
    ("UK & Ireland", 50, -8, 59, 2, 0.5),
    ("Africa North", 15, -15, 35, 35, 0.5),
    ("Africa South", -33, 12, -5, 40, 0.5),
    ("Middle East", 20, 35, 40, 55, 0.4),
    ("South Asia", 8, 68, 30, 88, 0.9),
    ("East Asia", 25, 100, 45, 145, 1.0),
    ("Southeast Asia", -8, 95, 20, 140, 0.6),
    ("Australia East", -38, 140, -20, 153, 0.4),
    ("Japan", 31, 130, 43, 142, 0.4),
]

RARITY_TABLE = [
    ("common", 0.70, (5, 20)),
    ("uncommon", 0.20, (20, 60)),
    ("rare", 0.08, (60, 150)),
    ("legendary", 0.02, (150, 500)),
]

PUZZLES = [
    ("What is 7 x 8?", "56"),
    ("How many sides does a hexagon have?", "6"),
    ("Capital of France?", "paris"),
]

CELL_DEG = 0.05
SHOUT_RADIUS_M = 300

sid_to_player = {}
player_to_sid = {}
sid_to_cell = {}


def haversine_m(lat1, lng1, lat2, lng2):
    R = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * R * math.asin(math.sqrt(a))


def cell_for(lat, lng):
    return f"{math.floor(lat / CELL_DEG)}_{math.floor(lng / CELL_DEG)}"


def neighbour_cells(lat, lng):
    cx, cy = math.floor(lat / CELL_DEG), math.floor(lng / CELL_DEG)
    return [f"cell_{cx+dx}_{cy+dy}" for dx in (-1, 0, 1) for dy in (-1, 0, 1)]


def pick_rarity():
    roll = random.random()
    acc = 0
    for name, prob, loot_range in RARITY_TABLE:
        acc += prob
        if roll <= acc:
            return name, loot_range
    return RARITY_TABLE[0][0], RARITY_TABLE[0][2]


def random_point_in_box(box):
    _, min_lat, min_lng, max_lat, max_lng, _ = box
    return random.uniform(min_lat, max_lat), random.uniform(min_lng, max_lng)


def pick_weighted_box():
    total = sum(b[5] for b in CONTINENT_BOXES)
    roll = random.uniform(0, total)
    acc = 0
    for box in CONTINENT_BOXES:
        acc += box[5]
        if roll <= acc:
            return box
    return CONTINENT_BOXES[0]


def ensure_todays_chests():
    today = datetime.date.today().isoformat()
    if db.count_todays_chests(today) > 0:
        return
    for i in range(DAILY_CHEST_COUNT):
        box = pick_weighted_box()
        lat, lng = random_point_in_box(box)
        rarity, loot_range = pick_rarity()
        loot = random.randint(*loot_range)
        puzzle_q = puzzle_a = None
        if random.random() < 0.15:
            puzzle_q, puzzle_a = random.choice(PUZZLES)
        db.spawn_chest(lat, lng, rarity, loot, today, puzzle_q, puzzle_a)


def background_ticker():
    while True:
        time.sleep(60)
        try:
            db.decay_graffiti()
            ensure_todays_chests()
        except Exception as e:
            print("ticker error:", e)


def territory_heal_ticker():
    while True:
        time.sleep(HEAL_INTERVAL_SECONDS)
        try:
            db.heal_territories()
        except Exception as e:
            print("heal ticker error:", e)


def parse_bbox_from_request():
    keys = ("min_lat", "min_lng", "max_lat", "max_lng")
    if not all(k in request.args for k in keys):
        return None
    try:
        return (
            float(request.args["min_lat"]),
            float(request.args["min_lng"]),
            float(request.args["max_lat"]),
            float(request.args["max_lng"]),
        )
    except ValueError:
        return None


def login_required(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("player_id"):
            return jsonify({"error": "not logged in"}), 401
        return fn(*args, **kwargs)

    return wrapper


def current_player():
    pid = session.get("player_id")
    return db.get_player(pid) if pid else None


def public_player(player):
    if not player:
        return None
    p = dict(player)
    p.pop("password_hash", None)
    return p

@terra_bp.route("/api/register", methods=["POST"])
def api_register():
    data = request.get_json(force=True)
    username = (data.get("username") or "").strip()[:20]
    password = data.get("password") or ""
    if len(username) < 3 or len(password) < 4:
        return jsonify({"error": "Username needs 3+ chars, password 4+ chars"}), 400
    player = db.register_player(username, password, data.get("color"))
    if not player:
        return jsonify({"error": "That username is already taken"}), 400
    session["player_id"] = player["id"]
    return jsonify({"player": public_player(player)})


@terra_bp.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(force=True)
    player = db.authenticate_player(
        (data.get("username") or "").strip(), data.get("password") or ""
    )
    if not player:
        return jsonify({"error": "Wrong username or password"}), 401
    session["player_id"] = player["id"]
    db.touch_player(player["id"])
    return jsonify({"player": public_player(player)})


@terra_bp.route("/api/logout", methods=["POST"])
def api_logout():
    session.pop("player_id", None)
    return jsonify({"ok": True})


@terra_bp.route("/api/me")
def api_me():
    player = current_player()
    if not player:
        return jsonify({"player": None})
    return jsonify({"player": public_player(player)})

@terra_bp.route("/api/players/online")
def api_players_online():
    return jsonify({"players": db.list_online_players()})

@terra_bp.route("/api/territory/list")
def api_territory_list():
    return jsonify({"territories": db.list_territories(parse_bbox_from_request())})

@terra_bp.route("/api/territory/claim", methods=["POST"])
@login_required
def api_territory_claim():
    data = request.get_json(force=True)
    player_id = session["player_id"]
    lat, lng = float(data["lat"]), float(data["lng"])
    player = db.get_player(player_id)

    for t in db.list_territories():
        if haversine_m(lat, lng, t["lat"], t["lng"]) < (t["radius_m"] + 60):
            return jsonify({"error": "Too close to an existing territory"}), 400

    cost = 50
    if player["resources"] < cost:
        return jsonify({"error": f"Need {cost} resources to claim land"}), 400

    tid = db.create_territory(player_id, lat, lng)
    db.add_resources(player_id, -cost)
    db.add_xp(player_id, 20)
    territory = db.get_territory(tid)
    socketio.emit("territory_update", {"type": "claimed", "territory": territory})
    return jsonify({"territory": territory})

@terra_bp.route("/api/territory/attack", methods=["POST"])
@login_required
def api_territory_attack():
    data = request.get_json(force=True)
    player_id = session["player_id"]
    tid = data["territory_id"]
    t = db.get_territory(tid)
    player = db.get_player(player_id)

    distance = haversine_m(player["lat"], player["lng"], t["lat"], t["lng"])

    if distance > t["radius_m"]:
        return jsonify({"error": "You must be inside the territory to attack."}), 400
    if not t:
        return jsonify({"error": "no such territory"}), 404
    if t["owner_id"] == player_id:
        return jsonify({"error": "cannot attack your own territory"}), 400
    if db.are_allies(player_id, t["owner_id"]):
        return jsonify({"error": "You can't attack an ally's territory"}), 400

    player = db.get_player(player_id)
    now = time.time()
    remaining = ATTACK_COOLDOWN_SECONDS - (now - (player["last_attack_ts"] or 0))
    if remaining > 0:
        return jsonify({"error": f"Attack on cooldown: wait {remaining:.0f}s"}), 400
    if player["resources"] < ATTACK_COST:
        return jsonify({"error": f"Need {ATTACK_COST} resources to attack"}), 400

    db.add_resources(player_id, -ATTACK_COST)
    db.record_attack(player_id)

    raw_damage = random.randint(8, 20)
    invested = max(0, t["defense"] - db.BASE_DEFENSE)
    reduction_pct = min(0.5, invested / (db.MAX_INVESTMENT * 2))
    damage = max(1, round(raw_damage * (1 - reduction_pct)))

    updated = db.attack_territory(tid, damage)
    fell = False
    if updated["health"] <= 0:
        db.delete_territory(tid)
        db.add_xp(player_id, 50)
        fell = True
    socketio.emit(
        "territory_update",
        {
            "type": "captured" if fell else "attacked",
            "territory_id": tid,
            "territory": None if fell else updated,
            "damage": damage,
        },
    )
    return jsonify(
        {
            "damage": damage,
            "fell": fell,
            "territory": None if fell else updated,
            "resources_spent": ATTACK_COST,
        }
    )

@terra_bp.route("/api/territory/invest", methods=["POST"])
@login_required
def api_territory_invest():
    data = request.get_json(force=True)
    player_id = session["player_id"]
    tid = data["territory_id"]
    amount = int(data.get("amount", INVESTMENT_LOT))

    if amount <= 0 or amount % INVESTMENT_LOT != 0:
        return (
            jsonify({"error": f"Investment must be in lots of {INVESTMENT_LOT}"}),
            400,
        )

    t = db.get_territory(tid)
    player = db.get_player(player_id)

    distance = haversine_m(player["lat"], player["lng"], t["lat"], t["lng"])

    if distance > t["radius_m"]:
        return jsonify({"error": "You must be inside your territory to invest."}), 400
    if not t:
        return jsonify({"error": "no such territory"}), 404
    if t["owner_id"] != player_id:
        return jsonify({"error": "You can only invest in your own territory"}), 400

    player = db.get_player(player_id)
    if player["resources"] < amount:
        return jsonify({"error": f"Need {amount} resources to invest"}), 400

    updated = db.invest_in_territory(tid, amount)
    if updated is None:
        invested_so_far = t["defense"] - db.BASE_DEFENSE
        return (
            jsonify(
                {
                    "error": f"Max investment reached ({invested_so_far}/{MAX_INVESTMENT})"
                }
            ),
            400,
        )

    db.add_resources(player_id, -amount)
    socketio.emit(
        "territory_update",
        {"type": "attacked", "territory_id": tid, "territory": updated},
    )
    return jsonify({"territory": updated})

@terra_bp.route("/api/territory/collect", methods=["POST"])
@login_required
def api_territory_collect():
    data = request.get_json(force=True)
    tid = data["territory_id"]
    earned = db.collect_territory_resources(tid)
    return jsonify({"earned": earned})

@terra_bp.route("/api/territory/leaderboard")
def api_territory_leaderboard():
    return jsonify({"leaderboard": db.territory_leaderboard()})

@terra_bp.route("/api/chests/today")
def api_chests_today():
    ensure_todays_chests()
    today = datetime.date.today().isoformat()
    chests = db.get_todays_chests(today, parse_bbox_from_request())
    safe = []
    for c in chests:
        c = dict(c)
        c.pop("puzzle_answer", None)
        safe.append(c)
    return jsonify({"chests": safe})

@terra_bp.route("/api/chests/claim", methods=["POST"])
@login_required
def api_chests_claim():
    data = request.get_json(force=True)
    player_id = session["player_id"]
    chest_id = data["chest_id"]
    answer = (data.get("answer") or "").strip().lower()

    player = db.get_player(player_id)
    if not player or not player["last_move_ts"]:
        return jsonify({"error": "Share your location first (allow GPS access)"}), 400

    today = datetime.date.today().isoformat()
    chest = next((c for c in db.get_todays_chests(today) if c["id"] == chest_id), None)
    if not chest:
        return jsonify({"error": "chest not found"}), 404
    if chest["claimed_by"]:
        return jsonify({"error": "already claimed"}), 400

    dist = haversine_m(player["lat"], player["lng"], chest["lat"], chest["lng"])
    if dist > 40:
        return jsonify({"error": f"Too far away ({int(dist)}m). Get within 40m."}), 400

    if chest["requires_puzzle"] and answer != (chest["puzzle_answer"] or "").lower():
        return (
            jsonify({"error": "wrong_answer", "question": chest["puzzle_question"]}),
            400,
        )

    result = db.claim_chest(chest_id, player_id)
    if not result:
        return jsonify({"error": "already claimed"}), 400
    socketio.emit("chest_claimed", {"chest_id": chest_id, "player_id": player_id})
    return jsonify({"loot": result["loot_resources"], "rarity": result["rarity"]})


@terra_bp.route("/api/chests/leaderboard")
def api_chests_leaderboard():
    today = datetime.date.today().isoformat()
    return jsonify({"leaderboard": db.hunter_leaderboard(today)})

@terra_bp.route("/api/graffiti/list")
def api_graffiti_list():
    return jsonify({"graffiti": db.list_graffiti(parse_bbox_from_request())})

@terra_bp.route("/api/graffiti/create", methods=["POST"])
@login_required
def api_graffiti_create():
    data = request.get_json(force=True)
    artist_id = session["player_id"]
    lat, lng = float(data["lat"]), float(data["lng"])

    for t in db.list_territories():
        if (
            haversine_m(lat, lng, t["lat"], t["lng"]) < t["radius_m"]
            and not t["allow_graffiti"]
        ):
            return (
                jsonify(
                    {"error": "The owner of this territory has disabled graffiti here."}
                ),
                400,
            )

    gid = db.create_graffiti(
        artist_id,
        lat,
        lng,
        data.get("style", "tag"),
        data.get("color", "#FF3D8A"),
        data.get("message", "")[:60],
    )
    db.add_xp(artist_id, 5)
    piece = next((g for g in db.list_graffiti() if g["id"] == gid), None)
    socketio.emit("graffiti_update", {"type": "created", "graffiti": piece})
    return jsonify({"graffiti": piece})


@terra_bp.route("/api/graffiti/like", methods=["POST"])
@login_required
def api_graffiti_like():
    data = request.get_json(force=True)
    gid = data["graffiti_id"]
    player_id = session["player_id"]
    result = db.like_graffiti(gid, player_id)
    if not result:
        return jsonify({"error": "already liked"}), 400
    socketio.emit(
        "graffiti_update",
        {"type": "liked", "graffiti_id": gid, "likes": result["likes"]},
    )
    return jsonify({"likes": result["likes"]})


@terra_bp.route("/api/graffiti/trending")
def api_graffiti_trending():
    return jsonify({"trending": db.trending_graffiti()})

@terra_bp.route("/api/alliances/list")
def api_alliances_list():
    return jsonify({"alliances": db.list_alliances()})

@terra_bp.route("/api/alliances/create", methods=["POST"])
@login_required
def api_alliances_create():
    data = request.get_json(force=True)
    name = (data.get("name") or "").strip()[:24]
    if len(name) < 3:
        return jsonify({"error": "Alliance name needs 3+ characters"}), 400
    aid = db.create_alliance(name, session["player_id"])
    if not aid:
        return jsonify({"error": "That alliance name is taken"}), 400
    return jsonify({"alliance_id": aid})

@terra_bp.route("/api/alliances/join", methods=["POST"])
@login_required
def api_alliances_join():
    data = request.get_json(force=True)
    ok = db.join_alliance(data["alliance_id"], session["player_id"])
    if not ok:
        return jsonify({"error": "no such alliance"}), 404
    return jsonify({"ok": True})

@terra_bp.route("/api/alliances/leave", methods=["POST"])
@login_required
def api_alliances_leave():
    db.leave_alliance(session["player_id"])
    return jsonify({"ok": True})

@terra_bp.route("/api/alliances/members/<alliance_id>")
def api_alliances_members(alliance_id):
    return jsonify({"members": db.get_alliance_members(alliance_id)})

@terra_bp.route("/api/friends/request", methods=["POST"])
@login_required
def api_friends_request():
    data = request.get_json(force=True)
    from_id = session["player_id"]
    rid = db.send_friend_request(from_id, data["to_id"])
    if not rid:
        return jsonify({"error": "request already pending"}), 400
    socketio.emit(
        "friend_request",
        {"request_id": rid, "from_id": from_id, "to_id": data["to_id"]},
    )
    return jsonify({"request_id": rid})


@terra_bp.route("/api/friends/respond", methods=["POST"])
@login_required
def api_friends_respond():
    data = request.get_json(force=True)
    status = db.respond_friend_request(data["request_id"], data["accept"])
    return jsonify({"status": status})

@socketio.on("connect")
def on_connect():
    pid = session.get("player_id")
    if pid:
        sid_to_player[request.sid] = pid
        player_to_sid[pid] = request.sid
    emit("connected", {"ok": True, "player_id": pid})


@socketio.on("disconnect")
def on_disconnect():
    pid = sid_to_player.pop(request.sid, None)

    if pid:
        player_to_sid.pop(pid, None)

        socketio.emit("player_left", {"player_id": pid})

    sid_to_cell.pop(request.sid, None)


@socketio.on("player_move")
def on_player_move(data):
    player_id = session.get("player_id") or data.get("player_id")
    lat, lng = data.get("lat"), data.get("lng")
    if player_id is None or lat is None or lng is None:
        return

    accepted, reason = db.check_and_update_position(player_id, lat, lng)
    if not accepted:
        emit("move_rejected", {"reason": reason})
        return

    own_cell = f"cell_{math.floor(lat/CELL_DEG)}_{math.floor(lng/CELL_DEG)}"
    old_cell = sid_to_cell.get(request.sid)
    if old_cell != own_cell:
        if old_cell:
            leave_room(old_cell)
        join_room(own_cell)
        sid_to_cell[request.sid] = own_cell

    for room in neighbour_cells(lat, lng):
        emit(
            "player_moved",
            {
                "player_id": player_id,
                "lat": lat,
                "lng": lng,
                "username": data.get("username"),
                "color": data.get("color"),
            },
            room=room,
            include_self=False,
        )


@socketio.on("request_players")
def on_request_players():
    me = session.get("player_id")
    if not me:
        return

    players = []

    for p in db.list_online_players():
        if p["id"] == me:
            continue

        if p["lat"] is None or p["lng"] is None:
            continue

        players.append(
            {
                "player_id": p["id"],
                "lat": p["lat"],
                "lng": p["lng"],
                "username": p["username"],
                "color": p["color"],
            }
        )

    emit("players_snapshot", players)


@socketio.on("chat_message")
def on_chat_message(data):
    lat, lng = data.get("lat"), data.get("lng")
    payload = {
        "player_id": session.get("player_id") or data.get("player_id"),
        "username": data.get("username"),
        "message": (data.get("message") or "")[:280],
        "lat": lat,
        "lng": lng,
        "ts": time.time(),
    }
    if lat is None or lng is None:
        emit("chat_message", payload, broadcast=True)
        return
    for room in neighbour_cells(lat, lng):
        emit("chat_message", payload, room=room)


@socketio.on("voice_signal")
def on_voice_signal(data):
    target_id = data.get("target_id")
    target_sid = player_to_sid.get(target_id)
    if target_sid:
        emit("voice_signal", data, room=target_sid)


@socketio.on("emote")
def on_emote(data):
    lat, lng = data.get("lat"), data.get("lng")
    if lat is None or lng is None:
        emit("emote", data, broadcast=True, include_self=False)
        return
    for room in neighbour_cells(lat, lng):
        emit("emote", data, room=room, include_self=False)


def init_terra():
    db.init_db()
    ensure_todays_chests()
    threading.Thread(target=background_ticker, daemon=True).start()
    threading.Thread(target=territory_heal_ticker, daemon=True).start()
