import random
import string

from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room as sio_join_room, emit

from game import GameRoom, TICK_DT

from flask import Blueprint
from routes.extensions import socketio
pacman_bp = Blueprint("pacman_bp", __name__)

rooms = {}
sid_room = {}
room_loops_running = set()


def make_room_code():
    while True:
        code = "".join(random.choices(string.ascii_uppercase, k=4))
        if code not in rooms:
            return code


def get_or_create_room(code):
    code = (code or "").strip().upper()[:4]
    if not code:
        code = make_room_code()
    if code not in rooms:
        rooms[code] = GameRoom(code)
    return rooms[code]


def room_loop(code):
    room_loops_running.add(code)
    prev_status = None
    try:
        while True:
            room = rooms.get(code)
            if room is None:
                break
            if not room.players:
                break
            room.tick()
            if prev_status == "round_end" and room.status == "playing":
                socketio.emit("Pround_start", room.serialize_round_start(), room=code)
            elif room.status in ("playing", "round_end"):
                socketio.emit("Ptick", room.serialize_tick(), room=code)
            prev_status = room.status
            socketio.sleep(TICK_DT)
    finally:
        room_loops_running.discard(code)
        if code in rooms and not rooms[code].players:
            del rooms[code]


@pacman_bp.route("/")
def index():
    return render_template("index.html")


@socketio.on("Pconnect")
def on_connect():
    pass


@socketio.on("Pdisconnect")
def on_disconnect():
    code = sid_room.pop(request.sid, None)
    if code and code in rooms:
        rooms[code].remove_player(request.sid)
        socketio.emit("Proster", roster_payload(rooms[code]), room=code)


@socketio.on("Pjoin")
def on_join(data):
    name = (data or {}).get("name", "PLAYER")
    code = (data or {}).get("room", "")
    room = get_or_create_room(code)
    sio_join_room(room.code)
    sid_room[request.sid] = room.code
    player = room.add_player(request.sid, name)

    emit(
        "Pjoined",
        {
            "you": player.to_dict(),
            "room": room.code,
            **room.serialize_maze(),
            **room.serialize_round_start(),
        },
    )
    socketio.emit("Proster", roster_payload(room), room=room.code)

    if room.code not in room_loops_running:
        socketio.start_background_task(room_loop, room.code)


@socketio.on("Pstart_game")
def on_start_game():
    code = sid_room.get(request.sid)
    room = rooms.get(code)
    if not room:
        return
    if room.status == "lobby" and room.players:
        room.start_or_restart()
        socketio.emit("Pround_start", room.serialize_round_start(), room=room.code)


@socketio.on("Pdirection")
def on_direction(data):
    code = sid_room.get(request.sid)
    room = rooms.get(code)
    if not room:
        return
    player = room.players.get(request.sid)
    d = (data or {}).get("dir")
    if player and d in ("up", "down", "left", "right"):
        player.next_direction = d


def roster_payload(room):
    return {
        "status": room.status,
        "players": [
            {"name": p.name, "color": p.color, "alive": p.alive, "score": p.score}
            for p in room.players.values()
        ],
    }
