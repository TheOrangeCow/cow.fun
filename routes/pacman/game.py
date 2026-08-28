import random
import time
import itertools

import routes.pacman.maze as M

TICK_HZ = 15
TICK_DT = 1.0 / TICK_HZ

PLAYER_SPEED = 4
GHOST_SPEED = 4
GHOST_SPEED_FRIGHT = 2
FRIGHTENED_SECONDS = 8
ROUND_END_PAUSE = 4.5

DIRS = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}
OPPOSITE = {"up": "down", "down": "up", "left": "right", "right": "left"}


def tile_of(px, py):
    return int(round(px / M.TILE)), int(round(py / M.TILE))


def aligned(px, py):
    return px % M.TILE == 0 and py % M.TILE == 0


def can_step(col, row, direction):
    dx, dy = DIRS[direction]
    ncol, nrow = col + dx, row + dy
    if row == M.TUNNEL_ROW and (ncol < 0 or ncol >= M.COLS):
        return True
    return not M.is_wall(ncol, nrow)


class Entity:
    def __init__(self, col, row):
        self.px = col * M.TILE
        self.py = row * M.TILE
        self.direction = None
        self.next_direction = None

    @property
    def col(self):
        return int(round(self.px / M.TILE))

    @property
    def row(self):
        return int(round(self.py / M.TILE))

    def move_step(self, speed):
        if aligned(self.px, self.py):
            col, row = self.col, self.row
            if self.next_direction and can_step(col, row, self.next_direction):
                self.direction = self.next_direction
            if self.direction and not can_step(col, row, self.direction):
                self.direction = None
        if self.direction:
            dx, dy = DIRS[self.direction]
            if dx:
                offset = self.px % M.TILE
                to_boundary = (M.TILE - offset) if dx > 0 else offset
                step = min(speed, to_boundary) if to_boundary else speed
            else:
                offset = self.py % M.TILE
                to_boundary = (M.TILE - offset) if dy > 0 else offset
                step = min(speed, to_boundary) if to_boundary else speed
            self.px += dx * step
            self.py += dy * step
            if self.row == M.TUNNEL_ROW:
                maxx = M.COLS * M.TILE
                if self.px < 0:
                    self.px = maxx - M.TILE
                elif self.px >= maxx:
                    self.px = 0


class Player(Entity):
    def __init__(self, sid, name, color, spawn):
        col, row = spawn
        super().__init__(col, row)
        self.sid = sid
        self.name = name[:12] if name else "PLAYER"
        self.color = color
        self.score = 0
        self.alive = True
        self.spawn = spawn

    def reset_round(self):
        col, row = self.spawn
        self.px = col * M.TILE
        self.py = row * M.TILE
        self.direction = None
        self.next_direction = None
        self.alive = True

    def to_dict(self):
        return {
            "id": self.sid,
            "name": self.name,
            "color": self.color,
            "x": self.px,
            "y": self.py,
            "dir": self.direction,
            "alive": self.alive,
            "score": self.score,
        }


class Ghost(Entity):
    def __init__(self, name, color, spawn):
        col, row = spawn
        super().__init__(col, row)
        self.name = name
        self.color = color
        self.spawn = spawn
        self.frightened = False
        self.released = False
        self.release_at = 0.0

    def reset_round(self, delay=0.0):
        col, row = self.spawn
        self.px = col * M.TILE
        self.py = row * M.TILE
        self.direction = None
        self.next_direction = None
        self.frightened = False
        self.released = False
        self.release_at = time.time() + delay

    def choose_direction(self, target_col, target_row, rng):
        col, row = self.col, self.row
        options = []
        for d in DIRS:
            if d == OPPOSITE.get(self.direction):
                continue
            if can_step(col, row, d):
                options.append(d)
        if not options:
            for d in DIRS:
                if can_step(col, row, d):
                    options.append(d)
        if not options:
            return self.direction

        if self.frightened:
            if rng.random() < 0.6:
                return rng.choice(options)
            target_col = col + (col - target_col)
            target_row = row + (row - target_row)

        if rng.random() < 0.15 and not self.frightened:
            return rng.choice(options)

        def dist(d):
            dx, dy = DIRS[d]
            ncol, nrow = col + dx, row + dy
            return (ncol - target_col) ** 2 + (nrow - target_row) ** 2

        options.sort(key=dist)
        return options[0]

    def to_dict(self):
        return {
            "name": self.name,
            "color": self.color,
            "x": self.px,
            "y": self.py,
            "dir": self.direction,
            "frightened": self.frightened,
        }


class GameRoom:
    def __init__(self, code):
        self.code = code
        self.players = {}
        self.ghosts = [
            Ghost(n, c, s)
            for n, c, s in zip(M.GHOST_NAMES, M.GHOST_COLORS, M.GHOST_SPAWNS)
        ]
        self.status = "lobby"
        self.message = ""
        self.dots = {}
        self.total_dots = 0
        self.frightened_until = 0
        self.round_end_at = 0
        self.rng = random.Random()
        self._spawn_cycle = itertools.cycle(M.PLAYER_SPAWNS)
        self.high_score = 0
        self.last_eaten = []

    def add_player(self, sid, name):
        color = M.PLAYER_COLORS[len(self.players) % len(M.PLAYER_COLORS)]
        spawn = next(self._spawn_cycle)
        p = Player(sid, name, color, spawn)
        if self.status != "lobby":
            p.alive = False
        self.players[sid] = p
        return p

    def remove_player(self, sid):
        self.players.pop(sid, None)

    def alive_players(self):
        return [p for p in self.players.values() if p.alive]

    def start_or_restart(self):
        self.dots = M.dot_layout()
        self.total_dots = len(self.dots)
        for p in self.players.values():
            p.reset_round()
        for i, g in enumerate(self.ghosts):
            g.reset_round(delay=i * 1.5)
        self.status = "playing"
        self.message = "READY!"
        self.frightened_until = 0

    def end_round(self, message, won):
        self.status = "round_end"
        self.message = message
        self.round_end_at = time.time() + ROUND_END_PAUSE
        team_score = sum(p.score for p in self.players.values())
        if team_score > self.high_score:
            self.high_score = team_score

    def tick(self):
        now = time.time()
        self.last_eaten = []

        if self.status == "round_end":
            if now >= self.round_end_at and self.players:
                self.start_or_restart()
            return

        if self.status != "playing":
            return

        for p in self.players.values():
            if not p.alive:
                continue
            p.move_step(PLAYER_SPEED)
            key = (p.col, p.row)
            if key in self.dots:
                kind = self.dots.pop(key)
                if kind == "dot":
                    p.score += 10
                else:
                    p.score += 50
                    self.frightened_until = now + FRIGHTENED_SECONDS
                self.last_eaten.append([key[0], key[1]])

        frightened_now = now < self.frightened_until
        for g in self.ghosts:
            g.frightened = frightened_now
            if not g.released:
                if now >= g.release_at:
                    g.released = True
                    g.next_direction = g.choose_direction(
                        M.GHOST_HOUSE_EXIT[0], M.GHOST_HOUSE_EXIT[1], self.rng
                    )
                else:
                    continue
            if aligned(g.px, g.py):
                targets = self.alive_players()
                if targets:
                    tgt = min(
                        targets,
                        key=lambda p: (p.col - g.col) ** 2 + (p.row - g.row) ** 2,
                    )
                    tcol, trow = tgt.col, tgt.row
                else:
                    tcol, trow = M.GHOST_HOUSE_EXIT
                g.next_direction = g.choose_direction(tcol, trow, self.rng)
            speed = GHOST_SPEED_FRIGHT if g.frightened else GHOST_SPEED
            g.move_step(speed)

        for p in self.players.values():
            if not p.alive:
                continue
            for g in self.ghosts:
                if not g.released:
                    continue
                if abs(p.px - g.px) < M.TILE * 0.6 and abs(p.py - g.py) < M.TILE * 0.6:
                    if g.frightened:
                        p.score += 200
                        g.reset_round(delay=1.0)
                    else:
                        p.alive = False

        if self.total_dots and not self.dots:
            self.end_round("CLEARED! GREAT TEAMWORK", won=True)
            return

        if self.players and not self.alive_players():
            self.end_round("GAME OVER", won=False)
            return

    def serialize_tick(self):
        return {
            "status": self.status,
            "message": self.message,
            "players": [p.to_dict() for p in self.players.values()],
            "ghosts": [g.to_dict() for g in self.ghosts],
            "eaten": self.last_eaten,
            "dotsRemaining": len(self.dots),
            "highScore": self.high_score,
        }

    def serialize_round_start(self):
        return {
            "dots": [[c, r, k] for (c, r), k in self.dots.items()],
            "players": [p.to_dict() for p in self.players.values()],
            "ghosts": [g.to_dict() for g in self.ghosts],
            "status": self.status,
            "message": self.message,
            "highScore": self.high_score,
        }

    def serialize_maze(self):
        return {"maze": M.MAZE, "tile": M.TILE, "cols": M.COLS, "rows": M.ROWS}
