

TILE = 20

r0 = "#" * 28
r1 = "#" + "." * 12 + "##" + "." * 12 + "#"
r2 = "#" + "." + "####" + "." + "#####" + "." + "##" + "." + "#####" + "." + "####" + "." + "#"
r3 = "#o" + "####" + "." + "#####" + "." + "##" + "." + "#####" + "." + "####" + "o" + "#"
r4 = r2
r5 = "#" + "." * 26 + "#"
r6 = "#" + "." + "####" + "." + "##" + "." + "########" + "." + "##" + "." + "####" + "." + "#"
r7 = r6
r8 = "#" + "." * 6 + "##" + "." * 4 + "##" + "." * 4 + "##" + "." * 6 + "#"
r9 = "#" * 6 + "." + "#" * 5 + " " + "#" * 2 + " " + "#" * 5 + "." + "#" * 6
r10 = "#" + "#" * 4 + "#" + "." + "#" * 5 + " " + "#" * 2 + " " + "#" * 5 + "." + "#" + "#" * 4 + "#"
r11 = "#" + "#" * 4 + "#" + "." + " " * 14 + "." + "#" + "#" * 4 + "#"
r12 = "#" + "#" * 4 + "#" + "." + "  " + "#" * 4 + "--" + "#" * 4 + "  " + "." + "#" + "#" * 4 + "#"
r13 = r11
r14 = "#" + "#" * 4 + "#" + "." + "#" * 14 + "." + "#" + "#" * 4 + "#"
r15 = " " + "." * 26 + " "

MAZE = [r0, r1, r2, r3, r4, r5, r6, r7, r8, r9, r10, r11, r12, r13, r14, r15,
        r14, r13, r12, r11, r10, r9, r8, r7, r6, r5, r4, r3, r2, r1, r0]

ROWS = len(MAZE)
COLS = len(MAZE[0])
TUNNEL_ROW = 15

assert all(len(row) == COLS for row in MAZE)


def is_wall(col, row):
    if row < 0 or row >= ROWS:
        return True
    if col < 0 or col >= COLS:
        return row != TUNNEL_ROW
    return MAZE[row][col] == "#"


def wrap_col(col):
    if col < 0:
        return COLS - 1
    if col >= COLS:
        return 0
    return col


def dot_layout():
    dots = {}
    for row, line in enumerate(MAZE):
        for col, ch in enumerate(line):
            if ch == ".":
                dots[(col, row)] = "dot"
            elif ch == "o":
                dots[(col, row)] = "pellet"
    return dots

PLAYER_SPAWNS = [
    (9, 7), (18, 7), (9, 23), (18, 23),
    (5, 5), (22, 5), (5, 25), (22, 25),
]

GHOST_SPAWNS = [(12, 13), (13, 13), (14, 13), (15, 13)]

GHOST_HOUSE_EXIT = (13, 11)

GHOST_COLORS = ["#FF0000", "#FFB8FF", "#00FFFF", "#FFB852"]
GHOST_NAMES = ["Blinky", "Pinky", "Inky", "Clyde"]

PLAYER_COLORS = [
    "#FFFF00", "#39FF6A", "#DA70D6", "#1E90FF",
    "#FF8C00", "#F08080", "#ADFF2F", "#40E0D0",
]