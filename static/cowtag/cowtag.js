const socket = io();

const lobby = document.getElementById("lobby");
const game = document.getElementById("game");

const nameInput = document.getElementById("nameInput");
const roomInput = document.getElementById("roomInput");
const modeInput = document.getElementById("modeInput");

const roomArea = document.getElementById("roomArea");
const roomCodeEl = document.getElementById("roomCode");
const lobbyPlayers = document.getElementById("lobbyPlayers");
const startButton = document.getElementById("startButton");
const modeDisplay = document.getElementById("modeDisplay");

const errorEl = document.getElementById("error");

const world = document.getElementById("world");
const arena = document.getElementById("arena");

const timerEl = document.getElementById("timer");
const statusEl = document.getElementById("status");
const playerCountEl = document.getElementById("playerCount");
const modeInfoBox = document.getElementById("modeInfoBox");
const modeInfoEl = document.getElementById("modeInfo");

const mobileShootEl = document.getElementById("mobileShoot");

const countdownEl = document.getElementById("countdown");
const messageEl = document.getElementById("message");

const gameOverEl = document.getElementById("gameOver");
const winnerText = document.getElementById("winnerText");
const winnerSubtext = document.getElementById("winnerSubtext");

let roomCode = null;
let myId = null;
let myName = "";

let players = {};
let cows = {};

let keys = {};

let localX = 1600;
let localY = 900;

let cameraX = 1600;
let cameraY = 900;

let targetCameraX = 1600;
let targetCameraY = 900;

let lastFrame = performance.now();
let lastMoveSent = 0;

let worldObjectsCreated = false;
let pickupElements = {};
let bulletElements = {};
let canElement = null;

let lastServerX = 1600;
let lastServerY = 900;

let currentMode = "it";

let aimX = 1;
let aimY = 0;

let lastShotSent = 0;

const ARENA_WIDTH = 3200;
const ARENA_HEIGHT = 1800;

const SPEED = 430;
const BOOST_SPEED = 700;

const SEND_INTERVAL = 40;
const SHOOT_COOLDOWN_MS = 350;

const cameraSmoothness = 7;

const keyMap = {
    "arrowup": "arrowup",
    "arrowdown": "arrowdown",
    "arrowleft": "arrowleft",
    "arrowright": "arrowright",
    "w": "w",
    "a": "a",
    "s": "s",
    "d": "d"
};


function isTyping() {
    const element = document.activeElement;

    if (!element) {
        return false;
    }

    return (
        element.tagName === "INPUT" ||
        element.tagName === "TEXTAREA" ||
        element.tagName === "SELECT"
    );
}


document.addEventListener("keydown", event => {

    if (isTyping()) {
        return;
    }

    const key = keyMap[event.key.toLowerCase()];

    if (!key) {
        return;
    }

    event.preventDefault();

    keys[key] = true;
});


document.addEventListener("keyup", event => {

    const key = keyMap[event.key.toLowerCase()];

    if (!key) {
        return;
    }

    keys[key] = false;
});


arena.addEventListener("mousemove", event => {

    if (currentMode !== "gun") {
        return;
    }

    const rect = arena.getBoundingClientRect();

    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;

    const dx = event.clientX - centerX;
    const dy = event.clientY - centerY;

    const length = Math.sqrt(dx * dx + dy * dy);

    if (length > 5) {
        aimX = dx / length;
        aimY = dy / length;
    }
});


arena.addEventListener("mousedown", event => {

    if (currentMode !== "gun") {
        return;
    }

    event.preventDefault();

    fireShot();
});


document.addEventListener("keydown", event => {

    if (isTyping()) {
        return;
    }

    if (
        currentMode === "gun" &&
        event.key === " "
    ) {
        event.preventDefault();
        fireShot();
    }
});


function fireShot() {

    if (!roomCode) {
        return;
    }

    const now = performance.now();

    if (now - lastShotSent < SHOOT_COOLDOWN_MS) {
        return;
    }

    lastShotSent = now;

    socket.emit("cowtag_shoot", {
        code: roomCode,
        dx: aimX,
        dy: aimY
    });
}


function mobileShoot() {

    aimX = 1;
    aimY = 0;

    const me = players[myId];

    if (me) {

        if (keys["arrowleft"] || keys["a"]) {
            aimX = -1;
        }

        if (keys["arrowup"] || keys["w"]) {
            aimY = -1;
        }

        if (keys["arrowdown"] || keys["s"]) {
            aimY = 1;
        }
    }

    fireShot();
}


function getName() {

    const name = nameInput.value.trim();

    if (!name) {
        showError("Enter a cow name first.");
        return null;
    }

    return name.substring(0, 16);
}


function createRoom() {

    const name = getName();

    if (!name) {
        return;
    }

    myName = name;

    socket.emit("cowtag_create_room", {
        name: name,
        mode: modeInput.value
    });
}


function joinRoom() {

    const name = getName();

    if (!name) {
        return;
    }

    const code =
        roomInput.value.trim().toUpperCase();

    if (code.length !== 5) {
        showError(
            "Enter the 5 character room code."
        );

        return;
    }

    myName = name;

    socket.emit("cowtag_join_room", {
        code: code,
        name: name
    });
}


function startGame() {

    if (!roomCode) {
        return;
    }

    socket.emit("cowtag_start_game", {
        code: roomCode
    });
}


function restartGame() {

    socket.emit("cowtag_restart_game", {
        code: roomCode
    });

    gameOverEl.style.display = "none";
}


socket.on("cowtag_room_created", data => {

    roomCode = data.code;
    myId = data.player_id;

    showRoom();
});


socket.on("cowtag_room_joined", data => {

    roomCode = data.code;
    myId = data.player_id;

    showRoom();
});


socket.on("cowtag_error_message", data => {
    showError(data.message);
});


function showRoom() {

    errorEl.style.display = "none";

    roomArea.style.display = "block";

    roomCodeEl.textContent = roomCode;

    lobby.style.display = "block";
}


socket.on("cowtag_game_state", state => {

    roomCode = state.code;
    currentMode = state.mode;

    mobileShootEl.style.display =
        currentMode === "gun" ? "block" : "none";

    updateLobby(state);

    if (
        state.started ||
        state.countdown > 0
    ) {
        lobby.style.display = "none";
        game.style.display = "block";
    }

    if (state.countdown > 0) {

        countdownEl.style.display = "flex";

        countdownEl.textContent =
            state.countdown;

    } else {

        countdownEl.style.display = "none";
    }

    timerEl.textContent = state.time;

    playerCountEl.textContent =
        state.players.length +
        " player" +
        (state.players.length === 1
            ? ""
            : "s");

    players = {};

    state.players.forEach(player => {

        players[player.id] = player;

        if (player.id === myId) {

            lastServerX = player.x;
            lastServerY = player.y;

            if (!gameStartedLocally()) {
                localX = player.x;
                localY = player.y;
            }
        }

        updateCow(player);
    });

    removeMissingCows();

    createWorldObjects(state.objects);

    updatePickups(state.pickups);
    updateBullets(state.bullets || []);
    updateCan(state.can);

    const me = players[myId];

    if (me) {

        if (state.mode === "build_up") {

            if (me.it) {
                statusEl.textContent =
                    "YOU ARE IT - SPREAD IT!";
            } else {
                statusEl.textContent =
                    "RUN! DON'T GET TAGGED";
            }

        } else if (state.mode === "gun") {

            if (me.alive) {
                statusEl.textContent =
                    "AIM WITH MOUSE - CLICK OR SPACE TO SHOOT";
            } else {
                statusEl.textContent =
                    "YOU DIED - RESPAWNING...";
            }

        } else if (state.mode === "can") {

            if (me.id === (state.can && state.can.holder)) {
                statusEl.textContent =
                    "YOU HAVE THE CAN - SURVIVE!";
            } else {
                statusEl.textContent =
                    "STEAL THE CAN!";
            }

        } else {

            if (me.it) {
                statusEl.textContent =
                    "YOU ARE IT - TAG SOMEONE!";
            } else {
                statusEl.textContent =
                    "RUN! DON'T GET TAGGED";
            }
        }

        if (me.boosted) {
            statusEl.textContent += "  SPEED BOOST!";
        }

        if (state.mode === "gun") {

            modeInfoBox.style.display = "block";

            modeInfoEl.textContent =
                "kills: " + me.kills +
                "   deaths: " + me.deaths;

        } else if (state.mode === "can") {

            modeInfoBox.style.display = "block";

            modeInfoEl.textContent =
                "hold time: " +
                me.hold_time.toFixed(1) + "s";

        } else {

            modeInfoBox.style.display = "none";
        }
    }

    targetCameraX = localX;
    targetCameraY = localY;
});


function gameStartedLocally() {
    return game.style.display === "block";
}


function updateLobby(state) {

    lobbyPlayers.innerHTML = "";

    state.players.forEach(player => {

        const div =
            document.createElement("div");

        div.className = "lobby-player";

        div.innerHTML = `
            <span>
                ${escapeHtml(player.name)}
            </span>

            ${player.id === state.host
                ? '<span class="host">HOST</span>'
                : ''
            }
        `;

        lobbyPlayers.appendChild(div);
    });

    const modeNames = {
        it: "It",
        build_up: "Build Up It",
        gun: "Gun Fight",
        can: "Capture the Can"
    };

    modeDisplay.textContent =
        "Game mode: " +
        (modeNames[state.mode] || "It");

    if (state.host === myId) {
        startButton.style.display = "block";
    } else {
        startButton.style.display = "none";
    }

    if (state.started) {

        lobby.style.display = "none";
        game.style.display = "block";
    }
}


function updateCow(player) {

    let cow = cows[player.id];

    if (!cow) {

        cow =
            document.createElement("div");

        cow.className = "cow";

        cow.innerHTML = `
            <div class="it-ring"></div>
            <div class="boost-ring"></div>

            <div class="cow-dead-label">DEAD</div>

            <div class="cow-body">
                <div class="spot one"></div>
                <div class="spot two"></div>
            </div>

            <div class="cow-head">
                <div class="cow-eye left"></div>
                <div class="cow-eye right"></div>
                <div class="cow-nose"></div>
            </div>

            <div class="name"></div>
        `;

        world.appendChild(cow);

        cows[player.id] = cow;
    }

    const currentX =
        parseFloat(cow.dataset.x || player.x);

    const currentY =
        parseFloat(cow.dataset.y || player.y);

    let newX;
    let newY;

    if (player.id === myId) {

        newX = localX;
        newY = localY;

    } else {

        const interpolation = 0.35;

        newX =
            currentX +
            (player.x - currentX) *
            interpolation;

        newY =
            currentY +
            (player.y - currentY) *
            interpolation;
    }

    cow.dataset.x = newX;
    cow.dataset.y = newY;

    cow.style.left = newX + "px";
    cow.style.top = newY + "px";

    const name =
        cow.querySelector(".name");

    name.textContent = player.name;

    const ring =
        cow.querySelector(".it-ring");

    ring.style.display =
        player.it ? "block" : "none";

    const boostRing =
        cow.querySelector(".boost-ring");

    boostRing.style.display =
        player.boosted ? "block" : "none";

    const body =
        cow.querySelector(".cow-body");

    body.style.borderColor =
        player.colour;

    cow.style.zIndex =
        player.id === myId
            ? "10"
            : "5";

    cow.classList.toggle(
        "dead",
        player.alive === false
    );

    const deadLabel =
        cow.querySelector(".cow-dead-label");

    deadLabel.style.display =
        player.alive === false
            ? "block"
            : "none";
}


function removeMissingCows() {

    Object.keys(cows).forEach(id => {

        if (!players[id]) {

            cows[id].remove();

            delete cows[id];
        }
    });
}


function createWorldObjects(objects) {

    if (worldObjectsCreated) {
        return;
    }

    worldObjectsCreated = true;

    objects.forEach(object => {

        const element =
            document.createElement("div");

        element.className =
            "world-object " +
            object.type;

        element.style.left =
            object.x + "px";

        element.style.top =
            object.y + "px";

        if (object.type === "tree") {

            element.style.width =
                object.size * 1.4 + "px";

            element.style.height =
                object.size * 2 + "px";

            element.innerHTML = `
                <div class="tree-leaves"></div>
                <div class="tree-trunk"></div>
            `;
        }

        if (
            object.type === "rock" ||
            object.type === "bush"
        ) {

            element.style.width =
                object.size + "px";

            element.style.height =
                object.size * .75 + "px";
        }

        if (object.type === "building") {

            element.style.width =
                object.width + "px";

            element.style.height =
                object.height + "px";
        }

        if (object.type === "pond") {

            element.style.width =
                object.width + "px";

            element.style.height =
                object.height + "px";
        }

        if (object.type === "fence") {

            if (object.width > 0) {

                element.style.width =
                    object.width + "px";

                element.style.height =
                    "18px";

            } else {

                element.style.width =
                    "18px";

                element.style.height =
                    object.height + "px";
            }
        }

        if (object.type === "grass") {

            element.style.width =
                object.size + "px";

            element.style.height =
                object.size * .65 + "px";
        }

        world.appendChild(element);
    });
}


function updatePickups(pickups) {

    const activeIds = new Set();

    pickups.forEach(pickup => {

        activeIds.add(pickup.id);

        let element =
            pickupElements[pickup.id];

        if (!element) {

            element =
                document.createElement("div");

            element.className = "pickup";

            world.appendChild(element);

            pickupElements[pickup.id] =
                element;
        }

        element.style.left =
            pickup.x + "px";

        element.style.top =
            pickup.y + "px";

        element.style.display =
            pickup.active
                ? "block"
                : "none";
    });

    Object.keys(pickupElements)
        .forEach(id => {

            if (!activeIds.has(id)) {

                pickupElements[id].remove();

                delete pickupElements[id];
            }
        });
}


function updateBullets(bullets) {

    const activeIds = new Set();

    bullets.forEach(bullet => {

        activeIds.add(bullet.id);

        let element = bulletElements[bullet.id];

        if (!element) {

            element =
                document.createElement("div");

            element.className = "bullet";

            world.appendChild(element);

            bulletElements[bullet.id] = element;
        }

        element.style.left = bullet.x + "px";
        element.style.top = bullet.y + "px";
    });

    Object.keys(bulletElements)
        .forEach(id => {

            if (!activeIds.has(id)) {

                bulletElements[id].remove();

                delete bulletElements[id];
            }
        });
}


function updateCan(can) {

    if (!can) {

        if (canElement) {
            canElement.remove();
            canElement = null;
        }

        return;
    }

    if (!canElement) {

        canElement =
            document.createElement("div");

        canElement.className = "can";

        canElement.innerHTML = `
            <div class="can-top"></div>
            <div class="can-body"></div>
        `;

        world.appendChild(canElement);
    }

    canElement.style.left = can.x + "px";
    canElement.style.top = can.y + "px";

    canElement.classList.toggle(
        "held",
        !!can.holder
    );
}


socket.on("cowtag_kill", data => {

    showMessage(
        data.shooter +
        " shot " +
        data.target +
        "!"
    );
});


socket.on("cowtag_can_taken", data => {

    showMessage(
        data.player +
        " grabbed the can!"
    );
});


socket.on("cowtag_can_stolen", data => {

    showMessage(
        data.player +
        " stole the can from " +
        data.from +
        "!"
    );
});


socket.on("cowtag_tag", data => {

    if (data.mode === "build_up") {

        showMessage(
            data.tagger +
            " tagged " +
            data.target +
            " - another It!"
        );

    } else {

        showMessage(
            data.tagger +
            " tagged " +
            data.target +
            "!"
        );
    }
});


socket.on("cowtag_pickup", data => {

    showMessage(
        data.player +
        " got a speed boost!"
    );
});


socket.on("cowtag_game_over", data => {

    gameOverEl.style.display = "flex";

    winnerText.textContent =
        data.winner + " wins!";

    if (data.mode === "build_up") {

        winnerSubtext.textContent =
            "Build Up It ended with the fewest cows infected.";

    } else if (data.mode === "gun") {

        winnerSubtext.textContent =
            "Gun Fight ended with the most kills.";

    } else if (data.mode === "can") {

        winnerSubtext.textContent =
            "Capture the Can ended with the longest hold time.";

    } else {

        winnerSubtext.textContent =
            "The round ended before the tagger could catch everyone.";
    }
});


function updateCamera() {

    const arenaWidth =
        arena.clientWidth;

    const arenaHeight =
        arena.clientHeight;

    if (!arenaWidth || !arenaHeight) {
        return;
    }

    const scaleX =
        arenaWidth / 1050;

    const scaleY =
        arenaHeight / 700;

    const scale =
        Math.min(scaleX, scaleY);

    const visibleWorldWidth =
        arenaWidth / scale;

    const visibleWorldHeight =
        arenaHeight / scale;

    const maxCameraX =
        ARENA_WIDTH -
        visibleWorldWidth / 2;

    const minCameraX =
        visibleWorldWidth / 2;

    const maxCameraY =
        ARENA_HEIGHT -
        visibleWorldHeight / 2;

    const minCameraY =
        visibleWorldHeight / 2;

    targetCameraX =
        Math.max(
            minCameraX,
            Math.min(maxCameraX, targetCameraX)
        );

    targetCameraY =
        Math.max(
            minCameraY,
            Math.min(maxCameraY, targetCameraY)
        );

    cameraX +=
        (targetCameraX - cameraX) *
        Math.min(
            1,
            cameraSmoothness / 60
        );

    cameraY +=
        (targetCameraY - cameraY) *
        Math.min(
            1,
            cameraSmoothness / 60
        );

    const translateX =
        arenaWidth / 2 -
        cameraX * scale;

    const translateY =
        arenaHeight / 2 -
        cameraY * scale;

    world.style.transform =
        `translate(${translateX}px, ${translateY}px) scale(${scale})`;
}


window.addEventListener(
    "resize",
    updateCamera
);


function gameLoop(timestamp) {

    const delta =
        Math.min(
            (timestamp - lastFrame) / 1000,
            0.05
        );

    lastFrame = timestamp;

    const me = players[myId];

    if (
        me &&
        me.alive &&
        game.style.display === "block"
    ) {

        let dx = 0;
        let dy = 0;

        if (
            keys["arrowup"] ||
            keys["w"]
        ) {
            dy -= 1;
        }

        if (
            keys["arrowdown"] ||
            keys["s"]
        ) {
            dy += 1;
        }

        if (
            keys["arrowleft"] ||
            keys["a"]
        ) {
            dx -= 1;
        }

        if (
            keys["arrowright"] ||
            keys["d"]
        ) {
            dx += 1;
        }

        if (dx !== 0 || dy !== 0) {

            const length =
                Math.sqrt(
                    dx * dx +
                    dy * dy
                );

            dx /= length;
            dy /= length;

            const speed =
                me.boosted
                    ? BOOST_SPEED
                    : SPEED;

            localX +=
                dx * speed * delta;

            localY +=
                dy * speed * delta;

            localX =
                Math.max(
                    40,
                    Math.min(
                        ARENA_WIDTH - 40,
                        localX
                    )
                );

            localY =
                Math.max(
                    40,
                    Math.min(
                        ARENA_HEIGHT - 40,
                        localY
                    )
                );

            targetCameraX = localX;
            targetCameraY = localY;

            const now =
                performance.now();

            if (
                now - lastMoveSent >
                SEND_INTERVAL
            ) {

                socket.emit("cowtag_move", {
                    code: roomCode,
                    x: localX,
                    y: localY
                });

                lastMoveSent = now;
            }
        }

        const cow = cows[myId];

        if (cow) {

            cow.dataset.x = localX;
            cow.dataset.y = localY;

            cow.style.left =
                localX + "px";

            cow.style.top =
                localY + "px";
        }
    }

    updateCamera();

    requestAnimationFrame(gameLoop);
}


function pressKey(key) {

    const normal =
        key.toLowerCase();

    keys[normal] = true;

    setTimeout(() => {
        keys[normal] = false;
    }, 150);
}


function showMessage(text) {

    messageEl.textContent = text;

    messageEl.style.display =
        "block";

    clearTimeout(
        showMessage.timeout
    );

    showMessage.timeout =
        setTimeout(() => {

            messageEl.style.display =
                "none";

        }, 2500);
}


function showError(text) {

    errorEl.textContent = text;

    errorEl.style.display =
        "block";
}


function escapeHtml(text) {

    const div =
        document.createElement("div");

    div.textContent = text;

    return div.innerHTML;
}


modeInput.addEventListener(
    "change",
    () => {

        if (!roomCode) {
            return;
        }

        socket.emit("cowtag_change_mode", {
            code: roomCode,
            mode: modeInput.value
        });
    }
);


updateCamera();

requestAnimationFrame(gameLoop);