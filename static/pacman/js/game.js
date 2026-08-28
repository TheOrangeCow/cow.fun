const socket = io();

const lobbyScreen = document.getElementById("lobby-screen");
const gameScreen = document.getElementById("game-screen");
const nameInput = document.getElementById("name-input");
const roomInput = document.getElementById("room-input");
const joinBtn = document.getElementById("join-btn");
const lobbyError = document.getElementById("lobby-error");
const roomPanel = document.getElementById("room-panel");
const roomCodeLabel = document.getElementById("room-code-label");
const rosterEl = document.getElementById("roster");
const startBtn = document.getElementById("start-btn");

const canvas = document.getElementById("game-canvas");
const ctx = canvas.getContext("2d");
const overlayMessage = document.getElementById("overlay-message");
const hudScore = document.getElementById("hud-score");
const cowscore = document.getElementById("score");
const hudHigh = document.getElementById("hud-highscore");
const hudDots = document.getElementById("hud-dots");
const playersPanel = document.getElementById("players-panel");

let TILE = 20, COLS = 28, ROWS = 31, MAZE = [];
let myId = null;
let myRoom = null;
let dots = new Map();
let players = [];
let ghosts = [];
let status = "lobby";
let pelletBlink = 0;
let mouthPhase = 0;

joinBtn.addEventListener("click", doJoin);
[nameInput, roomInput].forEach(el => el.addEventListener("keydown", e => {
    if (e.key === "Enter") doJoin();
}));

function doJoin() {
    const name = (nameInput.value || "PLAYER").trim().toUpperCase() || "PLAYER";
    const room = (roomInput.value || "").trim().toUpperCase();
    lobbyError.textContent = "";
    socket.emit("Pjoin", { name, room });
}

startBtn.addEventListener("click", () => socket.emit("Pstart_game"));

socket.on("Pjoined", data => {
    myId = data.you.id;
    myRoom = data.room;
    MAZE = data.maze;
    TILE = data.tile;
    COLS = data.cols;
    ROWS = data.rows;
    status = data.status;
    applyRoundStart(data);

    roomPanel.classList.remove("hidden");
    roomCodeLabel.textContent = myRoom;

    if (status !== "lobby") {
        showGameScreen();
    }
});

socket.on("Proster", data => {
    status = data.status;
    rosterEl.innerHTML = "";
    data.players.forEach(p => {
        const row = document.createElement("div");
        row.className = "roster-row";
        row.innerHTML = `<span><span class="roster-dot" style="background:${p.color}"></span>${p.name}</span><span>${p.alive ? "" : "spectating"}</span>`;
        rosterEl.appendChild(row);
    });
    startBtn.textContent = data.status === "lobby" ? "START GAME" : "GAME IN PROGRESS";
});

socket.on("Pround_start", data => {
    applyRoundStart(data);
    showGameScreen();
});

socket.on("Ptick", data => {
    status = data.status;
    players = data.players;
    ghosts = data.ghosts;
    hudScore.textContent = pad(players.reduce((s, p) => s + p.score, 0));
    cowscore.textContent = pad(players.reduce((s, p) => s + p.score, 0));
    hudHigh.textContent = pad(data.highScore);
    hudDots.textContent = data.dotsRemaining;
    (data.eaten || []).forEach(([c, r]) => dots.delete(c + "," + r));
    if (status === "round_end") {
        overlayMessage.textContent = data.message || "";
        overlayMessage.classList.remove("hidden");
    } else if (status === "playing") {
        overlayMessage.classList.add("hidden");
    }
    updatePlayersPanel();
});

function applyRoundStart(data) {
    dots = new Map(data.dots.map(([c, r, k]) => [c + "," + r, k]));
    players = data.players;
    ghosts = data.ghosts;
    status = data.status;
    hudHigh.textContent = pad(data.highScore || 0);
    hudDots.textContent = dots.size;
    flashReady(data.status, data.message);
    sizeCanvas();
}

function flashReady(roundStatus, message) {
    if (roundStatus === "playing") {
        overlayMessage.textContent = "READY!";
        overlayMessage.classList.remove("hidden");
        setTimeout(() => {
            if (status === "playing") overlayMessage.classList.add("hidden");
        }, 1500);
    } else if (roundStatus === "round_end") {
        overlayMessage.textContent = message || "";
        overlayMessage.classList.remove("hidden");
    } else {
        overlayMessage.classList.add("hidden");
    }
}

function updatePlayersPanel() {
    playersPanel.innerHTML = "";
    players.forEach(p => {
        const chip = document.createElement("div");
        chip.className = "player-chip" + (p.alive ? "" : " dead");
        const you = p.id === myId ? " (you)" : "";
        const state = p.alive ? "" : " spectating";
        chip.innerHTML = `<span class="swatch" style="background:${p.color}"></span>${p.name}${you}: ${p.score}${state}`;
        playersPanel.appendChild(chip);
    });
}

function pad(n) { return String(n).padStart(2, "0"); }

function showGameScreen() {
    lobbyScreen.classList.add("hidden");
    gameScreen.classList.remove("hidden");
    sizeCanvas();
}

function sizeCanvas() {
    canvas.width = COLS * TILE;
    canvas.height = ROWS * TILE;
}

const KEY_DIR = {
    ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right",
    w: "up", s: "down", a: "left", d: "right",
    W: "up", S: "down", A: "left", D: "right",
};
window.addEventListener("keydown", e => {
    const active = document.activeElement;
    if (active && (active.tagName === "INPUT" || active.tagName === "TEXTAREA")) {
        return;
    }
    const dir = KEY_DIR[e.key];
    if (dir) {
        e.preventDefault();
        socket.emit("Pdirection", { dir });
    }
});

let touchStart = null;
canvas.addEventListener("touchstart", e => {
    const t = e.changedTouches[0];
    touchStart = { x: t.clientX, y: t.clientY };
}, { passive: true });
canvas.addEventListener("touchend", e => {
    if (!touchStart) return;
    const t = e.changedTouches[0];
    const dx = t.clientX - touchStart.x;
    const dy = t.clientY - touchStart.y;
    let dir = null;
    if (Math.abs(dx) > Math.abs(dy)) {
        dir = dx > 0 ? "right" : "left";
    } else {
        dir = dy > 0 ? "down" : "up";
    }
    if (Math.abs(dx) > 15 || Math.abs(dy) > 15) socket.emit("Pdirection", { dir });
    touchStart = null;
}, { passive: true });

function isWall(col, row) {
    if (row < 0 || row >= ROWS) return true;
    if (col < 0 || col >= COLS) return true;
    return MAZE[row][col] === "#";
}

function drawMaze() {
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    if (!MAZE.length) return;

    ctx.strokeStyle = "#2121ff";
    ctx.lineWidth = TILE * 0.42;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.shadowColor = "#2121ffaa";
    ctx.shadowBlur = 4;

    ctx.beginPath();
    for (let row = 0; row < ROWS; row++) {
        for (let col = 0; col < COLS; col++) {
            if (!isWall(col, row)) continue;
            const cx = col * TILE + TILE / 2;
            const cy = row * TILE + TILE / 2;
            if (isWall(col + 1, row) || (col === COLS - 1 && row !== 15)) {
                const ncx = ((col + 1) % COLS) * TILE + TILE / 2;
                if (col < COLS - 1) {
                    ctx.moveTo(cx, cy);
                    ctx.lineTo(ncx, cy);
                }
            }
            if (isWall(col, row + 1)) {
                ctx.moveTo(cx, cy);
                ctx.lineTo(cx, cy + TILE);
            }
            if (!isWall(col + 1, row) && !isWall(col - 1, row) && !isWall(col, row + 1) && !isWall(col, row - 1)) {
                ctx.moveTo(cx - 1, cy);
                ctx.lineTo(cx + 1, cy);
            }
        }
    }
    ctx.stroke();
    ctx.shadowBlur = 0;

    ctx.strokeStyle = "#FFB8FF";
    ctx.lineWidth = 2;
    for (let row = 0; row < ROWS; row++) {
        for (let col = 0; col < COLS; col++) {
            if (MAZE[row][col] === "-") {
                ctx.beginPath();
                ctx.moveTo(col * TILE, row * TILE + TILE / 2);
                ctx.lineTo(col * TILE + TILE, row * TILE + TILE / 2);
                ctx.stroke();
            }
        }
    }
}

function drawDots() {
    pelletBlink += 1;
    const pelletVisible = Math.floor(pelletBlink / 12) % 2 === 0;
    dots.forEach((kind, key) => {
        const [col, row] = key.split(",").map(Number);
        const cx = col * TILE + TILE / 2;
        const cy = row * TILE + TILE / 2;
        if (kind === "dot") {
            ctx.fillStyle = "#FFD9A0";
            ctx.beginPath();
            ctx.arc(cx, cy, TILE * 0.08, 0, Math.PI * 2);
            ctx.fill();
        } else if (pelletVisible) {
            ctx.fillStyle = "#FFD9A0";
            ctx.beginPath();
            ctx.arc(cx, cy, TILE * 0.28, 0, Math.PI * 2);
            ctx.fill();
        }
    });
}

function dirAngle(dir) {
    switch (dir) {
        case "right": return 0;
        case "down": return Math.PI / 2;
        case "left": return Math.PI;
        case "up": return -Math.PI / 2;
        default: return 0;
    }
}

function drawPacman(p) {
    const cx = p.x + TILE / 2;
    const cy = p.y + TILE / 2;
    const r = TILE * 0.48;

    if (!p.alive) {
        return;
    }

    mouthPhase += 0.35;
    const mouthOpen = Math.abs(Math.sin(mouthPhase)) * 0.28 + 0.05;
    const angle = dirAngle(p.dir);

    ctx.fillStyle = p.color;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.arc(cx, cy, r, angle + mouthOpen * Math.PI, angle - mouthOpen * Math.PI + Math.PI * 2);
    ctx.closePath();
    ctx.fill();

    ctx.fillStyle = "#fff";
    ctx.font = "8px 'Press Start 2P'";
    ctx.textAlign = "center";
    ctx.fillText(p.name, cx, p.y - 4);
}

function drawGhost(g) {
    const cx = g.x + TILE / 2;
    const cy = g.y + TILE / 2;
    const r = TILE * 0.46;
    const bodyColor = g.frightened ? "#2121ff" : g.color;

    ctx.fillStyle = bodyColor;
    ctx.beginPath();
    ctx.arc(cx, cy - r * 0.15, r, Math.PI, 0, false);
    ctx.lineTo(cx + r, cy + r * 0.7);
    const bumps = 3;
    const step = (r * 2) / (bumps * 2);
    for (let i = 0; i < bumps * 2; i++) {
        const x = cx + r - step * (i + 1);
        const y = cy + r * 0.7 + (i % 2 === 0 ? r * 0.28 : 0);
        ctx.lineTo(x, y);
    }
    ctx.lineTo(cx - r, cy + r * 0.7);
    ctx.closePath();
    ctx.fill();

    if (g.frightened) {
        ctx.strokeStyle = "#fff";
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(cx - r * 0.4, cy - r * 0.1, r * 0.18, 0, Math.PI * 2);
        ctx.arc(cx + r * 0.4, cy - r * 0.1, r * 0.18, 0, Math.PI * 2);
        ctx.stroke();
    } else {
        const [ex, ey] = DIRS_VEC[g.dir] || [0, 0];
        ctx.fillStyle = "#fff";
        ctx.beginPath();
        ctx.arc(cx - r * 0.38, cy - r * 0.15, r * 0.24, 0, Math.PI * 2);
        ctx.arc(cx + r * 0.38, cy - r * 0.15, r * 0.24, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = "#00227a";
        ctx.beginPath();
        ctx.arc(cx - r * 0.38 + ex * r * 0.14, cy - r * 0.15 + ey * r * 0.14, r * 0.12, 0, Math.PI * 2);
        ctx.arc(cx + r * 0.38 + ex * r * 0.14, cy - r * 0.15 + ey * r * 0.14, r * 0.12, 0, Math.PI * 2);
        ctx.fill();
    }
}
const DIRS_VEC = { up: [0, -1], down: [0, 1], left: [-1, 0], right: [1, 0] };

function render() {
    drawMaze();
    drawDots();
    ghosts.forEach(drawGhost);
    players.forEach(drawPacman);
    requestAnimationFrame(render);
}
requestAnimationFrame(render);