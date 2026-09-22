from flask import Blueprint, render_template, request
from flask_socketio import emit, join_room
from routes.extensions import socketio
import random
import string
import time

cowtag = Blueprint("cowtag", __name__)

rooms = {}

MAX_PLAYERS = 8
MIN_PLAYERS = 2
GAME_TIME = 120

ARENA_WIDTH = 3200
ARENA_HEIGHT = 1800

PLAYER_RADIUS = 32
TAG_DISTANCE = 75

SPEED = 430
BOOST_SPEED = 700
BOOST_TIME = 4

TAG_COOLDOWN = 1.0

MODES = ("it", "build_up", "gun", "can")

BULLET_SPEED = 1000
BULLET_RADIUS = 10
BULLET_LIFETIME = 1.1
GUN_COOLDOWN = 0.35
RESPAWN_TIME = 2.5

CAN_PICKUP_DISTANCE = 60
CAN_STEAL_DISTANCE = 65


COLOURS = [
    "#4AA9FF",
    "#FF6B6B",
    "#42B883",
    "#F0A52B",
    "#9B59B6",
    "#00A6A6",
    "#FF8C42",
    "#E84393"
]


def make_room_code():
    while True:
        code = "".join(
            random.choice(string.ascii_uppercase + string.digits)
            for _ in range(5)
        )

        if code not in rooms:
            return code


def random_position():
    return {
        "x": random.randint(150, ARENA_WIDTH - 150),
        "y": random.randint(150, ARENA_HEIGHT - 150)
    }


def create_world():
    random.seed(47291)

    objects = []

    for _ in range(90):
        objects.append({
            "type": "tree",
            "x": random.randint(80, ARENA_WIDTH - 80),
            "y": random.randint(80, ARENA_HEIGHT - 80),
            "size": random.randint(30, 55)
        })

    for _ in range(55):
        objects.append({
            "type": "rock",
            "x": random.randint(80, ARENA_WIDTH - 80),
            "y": random.randint(80, ARENA_HEIGHT - 80),
            "size": random.randint(20, 42)
        })

    for _ in range(65):
        objects.append({
            "type": "bush",
            "x": random.randint(80, ARENA_WIDTH - 80),
            "y": random.randint(80, ARENA_HEIGHT - 80),
            "size": random.randint(24, 42)
        })

    buildings = [
        (400, 300, 330, 220),
        (1400, 250, 380, 240),
        (2450, 350, 400, 260),
        (650, 1250, 420, 260),
        (2050, 1200, 390, 250)
    ]

    for x, y, width, height in buildings:
        objects.append({
            "type": "building",
            "x": x,
            "y": y,
            "width": width,
            "height": height
        })

    ponds = [
        (1000, 650, 280, 170),
        (2600, 1050, 360, 220),
        (1500, 1450, 300, 170)
    ]

    for x, y, width, height in ponds:
        objects.append({
            "type": "pond",
            "x": x,
            "y": y,
            "width": width,
            "height": height
        })

    fences = [
        (200, 800, 650, 0),
        (1800, 700, 700, 0),
        (850, 1100, 0, 500),
        (2800, 250, 0, 500)
    ]

    for x, y, width, height in fences:
        objects.append({
            "type": "fence",
            "x": x,
            "y": y,
            "width": width,
            "height": height
        })

    for _ in range(30):
        objects.append({
            "type": "grass",
            "x": random.randint(100, ARENA_WIDTH - 100),
            "y": random.randint(100, ARENA_HEIGHT - 100),
            "size": random.randint(40, 90)
        })

    pickups = []

    for _ in range(12):
        pos = random_position()

        pickups.append({
            "id": "".join(
                random.choice(string.ascii_lowercase + string.digits)
                for _ in range(8)
            ),
            "type": "speed",
            "x": pos["x"],
            "y": pos["y"],
            "active": True
        })

    return objects, pickups


WORLD_OBJECTS, WORLD_PICKUPS = create_world()


def room_state(room):
    return {
        "code": room["code"],
        "mode": room["mode"],
        "players": [
            {
                "id": player["id"],
                "name": player["name"],
                "x": player["x"],
                "y": player["y"],
                "it": player["it"],
                "alive": player["alive"],
                "colour": player["colour"],
                "boosted": player["boosted"],
                "kills": player["kills"],
                "deaths": player["deaths"],
                "hold_time": player["hold_time"]
            }
            for player in room["players"].values()
        ],
        "started": room["started"],
        "countdown": room["countdown"],
        "time": max(
            0,
            int(GAME_TIME - (time.time() - room["start_time"]))
        ) if room["started"] else GAME_TIME,
        "host": room["host"],
        "objects": room["objects"],
        "pickups": room["pickups"],
        "bullets": room["bullets"],
        "can": room["can"]
    }


def send_state(room_code):
    room = rooms.get(room_code)

    if room:
        socketio.emit(
            "cowtag_game_state",
            room_state(room),
            to=room_code
        )


@cowtag.route("/")
def index():
    return render_template("cowtag.html")


@cowtag.route("/cow-tag")
def cow_tag():
    return render_template("cowtag.html")


@socketio.on("cowtag_create_room")
def create_room(data):
    name = str(data.get("name", "Cow")).strip()[:16]

    if not name:
        name = "Cow"

    mode = str(data.get("mode", "it"))

    if mode not in MODES:
        mode = "it"

    code = make_room_code()

    room = {
        "code": code,
        "host": request.sid,
        "players": {},
        "started": False,
        "countdown": 0,
        "start_time": 0,
        "mode": mode,
        "objects": WORLD_OBJECTS,
        "pickups": [
            dict(pickup)
            for pickup in WORLD_PICKUPS
        ],
        "bullets": [],
        "can": None
    }

    room["players"][request.sid] = {
        "id": request.sid,
        "name": name,
        "x": ARENA_WIDTH // 2,
        "y": ARENA_HEIGHT // 2,
        "it": False,
        "alive": True,
        "colour": COLOURS[0],
        "boosted": False,
        "boost_until": 0,
        "last_tag": 0,
        "kills": 0,
        "deaths": 0,
        "last_shot": 0,
        "respawn_at": 0,
        "hold_time": 0.0
    }

    rooms[code] = room

    join_room(code)

    emit(
        "cowtag_room_created",
        {
            "code": code,
            "player_id": request.sid
        }
    )

    send_state(code)


@socketio.on("cowtag_join_room")
def join_game_room(data):
    code = str(data.get("code", "")).strip().upper()
    name = str(data.get("name", "Cow")).strip()[:16]

    if not name:
        name = "Cow"

    room = rooms.get(code)

    if not room:
        emit(
            "cowtag_error_message",
            {"message": "Room not found."}
        )
        return

    if room["started"]:
        emit(
            "cowtag_error_message",
            {"message": "That game has already started."}
        )
        return

    if len(room["players"]) >= MAX_PLAYERS:
        emit(
            "cowtag_error_message",
            {"message": "That room is full."}
        )
        return

    used_colours = {
        player["colour"]
        for player in room["players"].values()
    }

    colour = next(
        (
            c for c in COLOURS
            if c not in used_colours
        ),
        random.choice(COLOURS)
    )

    pos = random_position()

    room["players"][request.sid] = {
        "id": request.sid,
        "name": name,
        "x": pos["x"],
        "y": pos["y"],
        "it": False,
        "alive": True,
        "colour": colour,
        "boosted": False,
        "boost_until": 0,
        "last_tag": 0,
        "kills": 0,
        "deaths": 0,
        "last_shot": 0,
        "respawn_at": 0,
        "hold_time": 0.0
    }

    join_room(code)

    emit(
        "cowtag_room_joined",
        {
            "code": code,
            "player_id": request.sid
        }
    )

    send_state(code)


@socketio.on("cowtag_change_mode")
def change_mode(data):
    code = str(data.get("code", "")).strip().upper()
    mode = str(data.get("mode", "it"))

    room = rooms.get(code)

    if not room:
        return

    if request.sid != room["host"]:
        return

    if room["started"]:
        return

    if mode not in MODES:
        return

    room["mode"] = mode

    send_state(code)


@socketio.on("cowtag_start_game")
def start_game(data):
    code = str(data.get("code", "")).strip().upper()
    room = rooms.get(code)

    if not room:
        return

    if request.sid != room["host"]:
        emit(
            "cowtag_error_message",
            {
                "message":
                "Only the host can start the game."
            }
        )
        return

    if len(room["players"]) < MIN_PLAYERS:
        emit(
            "cowtag_error_message",
            {
                "message":
                f"You need at least {MIN_PLAYERS} players."
            }
        )
        return

    if room["started"]:
        return

    room["countdown"] = 3

    send_state(room["code"])

    socketio.start_background_task(
        countdown_game,
        room["code"]
    )


def countdown_game(code):
    room = rooms.get(code)

    if not room:
        return

    for number in [3, 2, 1]:
        room["countdown"] = number
        send_state(code)
        socketio.sleep(1)

    room = rooms.get(code)

    if not room:
        return

    players = list(room["players"].values())

    if len(players) < MIN_PLAYERS:
        room["countdown"] = 0
        send_state(code)
        return

    for player in players:
        pos = random_position()

        player["x"] = pos["x"]
        player["y"] = pos["y"]
        player["alive"] = True
        player["it"] = False
        player["boosted"] = False
        player["boost_until"] = 0
        player["kills"] = 0
        player["deaths"] = 0
        player["last_shot"] = 0
        player["respawn_at"] = 0
        player["hold_time"] = 0.0

    room["bullets"] = []

    if room["mode"] == "can":
        room["can"] = {
            "x": ARENA_WIDTH // 2,
            "y": ARENA_HEIGHT // 2,
            "holder": None
        }
    else:
        room["can"] = None

    if room["mode"] == "it" or room["mode"] == "build_up":
        random.choice(players)["it"] = True

    room["countdown"] = 0
    room["started"] = True
    room["start_time"] = time.time()

    send_state(code)

    socketio.start_background_task(
        game_timer,
        code
    )


def game_timer(code):
    last_tick = time.time()

    while True:
        socketio.sleep(0.05)

        room = rooms.get(code)

        if not room or not room["started"]:
            return

        now = time.time()

        delta = now - last_tick
        last_tick = now

        elapsed = now - room["start_time"]

        if elapsed >= GAME_TIME:
            finish_game(code)
            return

        for player in room["players"].values():
            if player["boosted"] and now >= player["boost_until"]:
                player["boosted"] = False
                player["boost_until"] = 0

            if (
                not player["alive"] and
                player["respawn_at"] and
                now >= player["respawn_at"]
            ):
                pos = random_position()

                player["x"] = pos["x"]
                player["y"] = pos["y"]
                player["alive"] = True
                player["respawn_at"] = 0

        if room["mode"] == "gun":
            update_bullets(room, delta, now)

        if room["mode"] == "can" and room["can"] and room["can"]["holder"]:
            holder = room["players"].get(room["can"]["holder"])

            if holder:
                holder["hold_time"] += delta

        send_state(code)


@socketio.on("cowtag_move")
def move_player(data):
    code = str(data.get("code", "")).strip().upper()
    room = rooms.get(code)

    if not room or not room["started"]:
        return

    player = room["players"].get(request.sid)

    if not player or not player["alive"]:
        return

    try:
        x = float(data.get("x", player["x"]))
        y = float(data.get("y", player["y"]))
    except (TypeError, ValueError):
        return

    max_step = 120

    dx = x - player["x"]
    dy = y - player["y"]

    distance = (dx * dx + dy * dy) ** 0.5

    if distance > max_step:
        if distance > 0:
            x = player["x"] + dx / distance * max_step
            y = player["y"] + dy / distance * max_step

    x = max(
        PLAYER_RADIUS,
        min(ARENA_WIDTH - PLAYER_RADIUS, x)
    )

    y = max(
        PLAYER_RADIUS,
        min(ARENA_HEIGHT - PLAYER_RADIUS, y)
    )

    player["x"] = x
    player["y"] = y

    check_pickups(room, player)
    check_tagging(room, player)

    if room["mode"] == "can":
        check_can(room, player)


@socketio.on("cowtag_shoot")
def shoot(data):
    code = str(data.get("code", "")).strip().upper()
    room = rooms.get(code)

    if not room or not room["started"]:
        return

    if room["mode"] != "gun":
        return

    player = room["players"].get(request.sid)

    if not player or not player["alive"]:
        return

    now = time.time()

    if now - player["last_shot"] < GUN_COOLDOWN:
        return

    try:
        dx = float(data.get("dx", 0))
        dy = float(data.get("dy", 0))
    except (TypeError, ValueError):
        return

    length = (dx * dx + dy * dy) ** 0.5

    if length == 0:
        return

    dx /= length
    dy /= length

    player["last_shot"] = now

    room["bullets"].append({
        "id": "".join(
            random.choice(string.ascii_lowercase + string.digits)
            for _ in range(8)
        ),
        "owner": player["id"],
        "x": player["x"],
        "y": player["y"],
        "dx": dx,
        "dy": dy,
        "spawned": now
    })

    send_state(code)


def point_segment_distance(px, py, x1, y1, x2, y2):
    dx = x2 - x1
    dy = y2 - y1

    if dx == 0 and dy == 0:
        return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5

    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0, min(1, t))

    closest_x = x1 + t * dx
    closest_y = y1 + t * dy

    return ((px - closest_x) ** 2 + (py - closest_y) ** 2) ** 0.5


def find_bullet_hit(room, bullet, x1, y1, x2, y2):
    for player in room["players"].values():

        if player["id"] == bullet["owner"]:
            continue

        if not player["alive"]:
            continue

        distance = point_segment_distance(
            player["x"], player["y"],
            x1, y1, x2, y2
        )

        if distance < PLAYER_RADIUS + BULLET_RADIUS:
            return player["id"]

    return None


def kill_player(room, shooter_id, target_id):
    shooter = room["players"].get(shooter_id)
    target = room["players"].get(target_id)

    if not target or not target["alive"]:
        return

    target["alive"] = False
    target["respawn_at"] = time.time() + RESPAWN_TIME
    target["deaths"] += 1

    if shooter and shooter["id"] != target["id"]:
        shooter["kills"] += 1

    socketio.emit(
        "cowtag_kill",
        {
            "shooter": shooter["name"] if shooter else "Someone",
            "target": target["name"]
        },
        to=room["code"]
    )


def update_bullets(room, delta, now):
    remaining = []

    for bullet in room["bullets"]:

        if now - bullet["spawned"] > BULLET_LIFETIME:
            continue

        old_x = bullet["x"]
        old_y = bullet["y"]

        new_x = old_x + bullet["dx"] * BULLET_SPEED * delta
        new_y = old_y + bullet["dy"] * BULLET_SPEED * delta

        if (
            new_x < 0 or new_x > ARENA_WIDTH or
            new_y < 0 or new_y > ARENA_HEIGHT
        ):
            continue

        hit = find_bullet_hit(room, bullet, old_x, old_y, new_x, new_y)

        if hit:
            kill_player(room, bullet["owner"], hit)
            continue

        bullet["x"] = new_x
        bullet["y"] = new_y

        remaining.append(bullet)

    room["bullets"] = remaining


def check_can(room, player):
    can = room.get("can")

    if not can:
        return

    if can["holder"] is None:

        dx = can["x"] - player["x"]
        dy = can["y"] - player["y"]

        distance = (dx * dx + dy * dy) ** 0.5

        if distance < CAN_PICKUP_DISTANCE:
            can["holder"] = player["id"]

            socketio.emit(
                "cowtag_can_taken",
                {"player": player["name"]},
                to=room["code"]
            )

    elif can["holder"] == player["id"]:

        can["x"] = player["x"]
        can["y"] = player["y"]

    else:

        holder = room["players"].get(can["holder"])

        if not holder:
            can["holder"] = player["id"]
            can["x"] = player["x"]
            can["y"] = player["y"]
            return

        dx = holder["x"] - player["x"]
        dy = holder["y"] - player["y"]

        distance = (dx * dx + dy * dy) ** 0.5

        if distance < CAN_STEAL_DISTANCE:
            can["holder"] = player["id"]

            socketio.emit(
                "cowtag_can_stolen",
                {
                    "player": player["name"],
                    "from": holder["name"]
                },
                to=room["code"]
            )


def check_pickups(room, player):
    for pickup in room["pickups"]:
        if not pickup["active"]:
            continue

        dx = pickup["x"] - player["x"]
        dy = pickup["y"] - player["y"]

        distance = (dx * dx + dy * dy) ** 0.5

        if distance < 55:
            pickup["active"] = False

            player["boosted"] = True
            player["boost_until"] = time.time() + BOOST_TIME

            socketio.emit(
                "cowtag_pickup",
                {
                    "player": player["name"],
                    "type": pickup["type"]
                },
                to=room["code"]
            )

            send_state(room["code"])

            socketio.start_background_task(
                respawn_pickup,
                room["code"],
                pickup["id"]
            )

            break


def respawn_pickup(code, pickup_id):
    socketio.sleep(8)

    room = rooms.get(code)

    if not room:
        return

    for pickup in room["pickups"]:
        if pickup["id"] == pickup_id:
            pos = random_position()

            pickup["x"] = pos["x"]
            pickup["y"] = pos["y"]
            pickup["active"] = True

            break

    send_state(code)


def check_tagging(room, tagger):
    if not tagger["it"]:
        return

    now = time.time()

    if now - tagger["last_tag"] < TAG_COOLDOWN:
        return

    for target in room["players"].values():

        if target["id"] == tagger["id"]:
            continue

        if not target["alive"]:
            continue

        dx = target["x"] - tagger["x"]
        dy = target["y"] - tagger["y"]

        distance = (dx * dx + dy * dy) ** 0.5

        if distance < TAG_DISTANCE:

            tagger["last_tag"] = now
            target["last_tag"] = now

            if room["mode"] == "it":
                tagger["it"] = False
                target["it"] = True

            elif room["mode"] == "build_up":
                target["it"] = True

            socketio.emit(
                "cowtag_tag",
                {
                    "tagger": tagger["name"],
                    "target": target["name"],
                    "mode": room["mode"]
                },
                to=room["code"]
            )

            send_state(room["code"])

            break


@socketio.on("cowtag_disconnect")
def disconnect():
    for code, room in list(rooms.items()):

        if request.sid not in room["players"]:
            continue

        del room["players"][request.sid]

        if room.get("can") and room["can"]["holder"] == request.sid:
            room["can"]["holder"] = None

        if not room["players"]:
            del rooms[code]
            return

        if room["host"] == request.sid:
            room["host"] = next(
                iter(room["players"])
            )

        if room["started"]:

            it_players = [
                p
                for p in room["players"].values()
                if p["it"]
            ]

            if not it_players:
                players = list(
                    room["players"].values()
                )

                if players:
                    random.choice(players)["it"] = True

        if (
            len(room["players"]) < MIN_PLAYERS
            and room["started"]
        ):
            room["started"] = False
            room["countdown"] = 0

        send_state(code)
        return


def finish_game(code):
    room = rooms.get(code)

    if not room:
        return

    room["started"] = False
    room["countdown"] = 0

    players = list(
        room["players"].values()
    )

    if not players:
        return

    if room["mode"] == "gun":

        winner = max(players, key=lambda p: p["kills"])

    elif room["mode"] == "can":

        winner = max(players, key=lambda p: p["hold_time"])

    else:

        non_it = [
            player
            for player in players
            if not player["it"]
        ]

        if non_it:
            winner = random.choice(non_it)
        else:
            winner = random.choice(players)

    socketio.emit(
        "cowtag_game_over",
        {
            "winner": winner["name"],
            "mode": room["mode"],
            "players": [
                {
                    "name": p["name"],
                    "it": p["it"],
                    "kills": p["kills"],
                    "deaths": p["deaths"],
                    "hold_time": round(p["hold_time"], 1)
                }
                for p in players
            ]
        },
        to=code
    )

    send_state(code)


@socketio.on("cowtag_restart_game")
def restart_game(data):
    code = str(data.get("code", "")).strip().upper()

    room = rooms.get(code)

    if not room:
        return

    if request.sid != room["host"]:
        return

    room["started"] = False
    room["countdown"] = 0
    room["bullets"] = []
    room["can"] = None

    for player in room["players"].values():
        player["it"] = False
        player["alive"] = True
        player["boosted"] = False
        player["boost_until"] = 0
        player["kills"] = 0
        player["deaths"] = 0
        player["last_shot"] = 0
        player["respawn_at"] = 0
        player["hold_time"] = 0.0

    send_state(code)
