async function refreshPlayerStats() {
    const { player } = await api("/terra/api/me");
    if (!player) return;
    STATE.player = player;
    document.getElementById("player-resources").textContent = STATE.player.resources;
    document.getElementById("player-xp").textContent = STATE.player.xp;
}

function setMode(mode) {
    STATE.currentMode = mode;
    document.querySelectorAll(".dock-btn").forEach((b) => b.classList.toggle("active", b.dataset.mode === mode));
    ["territory", "hunter", "graffiti", "social"].forEach((m) => {
        document.getElementById(`panel-${m}`).hidden = m !== mode;
    });
    if (mode === "territory") { Territory.refreshLeaderboard(); Alliance.refresh(); }
    if (mode === "hunter") Hunter.refreshLeaderboard();
}

function wireDock() {
    document.querySelectorAll(".dock-btn").forEach((btn) => {
        btn.addEventListener("click", () => setMode(btn.dataset.mode));
    });
}

function wireHudButtons() {
    document.getElementById("leaderboard-toggle").onclick = () => {
        const panel = document.getElementById("hud-leaderboard");
        panel.hidden = !panel.hidden;
        if (!panel.hidden) {
            if (STATE.currentMode === "hunter") Hunter.refreshLeaderboard();
            else Territory.refreshLeaderboard();
        }
    };
    document.getElementById("leaderboard-close").onclick = () => {
        document.getElementById("hud-leaderboard").hidden = true;
    };
    document.querySelectorAll(".panel-close").forEach((btn) => {
        btn.onclick = () => { document.getElementById(btn.dataset.panel).hidden = true; };
    });
    document.getElementById("btn-claim-territory").onclick = () => Territory.claimAtSelf();
    document.getElementById("btn-place-graffiti").onclick = () => Graffiti.place();
    document.getElementById("btn-create-alliance").onclick = () => Alliance.create();
}

const Alliance = {
    async refresh() {
        const { alliances } = await api("/terra/api/alliances/list");
        const box = document.getElementById("alliance-current");
        if (STATE.player.alliance_id) {
            const mine = alliances.find((a) => a.id === STATE.player.alliance_id);
            box.innerHTML = mine
                ? `In <b>${mine.name}</b> (${mine.member_count} members) — <a href="#" id="leave-alliance">leave</a>`
                : "You're not in an alliance.";
            const leaveLink = document.getElementById("leave-alliance");
            if (leaveLink) leaveLink.onclick = async (e) => { e.preventDefault(); await api("/terra/api/alliances/leave", "POST"); await refreshPlayerStats(); this.refresh(); };
        } else {
            box.textContent = "You're not in an alliance.";
        }
        const list = document.getElementById("alliance-list");
        list.innerHTML = alliances
            .filter((a) => a.id !== STATE.player.alliance_id)
            .map((a) => `<li><span>${a.name} (${a.member_count})</span><button data-join="${a.id}">Join</button></li>`)
            .join("") || "<li>No alliances yet — start one</li>";
        list.querySelectorAll("[data-join]").forEach((btn) => {
            btn.onclick = async () => {
                await api("/terra/api/alliances/join", "POST", { alliance_id: btn.dataset.join });
                await refreshPlayerStats();
                this.refresh();
            };
        });
    },

    async create() {
        const input = document.getElementById("alliance-name-input");
        const name = input.value.trim();
        if (!name) return;
        try {
            await api("/terra/api/alliances/create", "POST", { name });
            input.value = "";
            await refreshPlayerStats();
            this.refresh();
            toast(`Alliance "${name}" created`);
        } catch (e) {
            toast(e.message);
        }
    },
};

function buildRegisterColorRow() {
    const row = document.getElementById("color-row");
    row.innerHTML = STATE.colors
        .map((c, i) => `<div class="swatch ${i === 0 ? "selected" : ""}" style="background:${c}" data-color="${c}"></div>`)
        .join("");
    let chosen = STATE.colors[0];
    row.querySelectorAll(".swatch").forEach((sw) => {
        sw.onclick = () => {
            row.querySelectorAll(".swatch").forEach((s) => s.classList.remove("selected"));
            sw.classList.add("selected");
            chosen = sw.dataset.color;
        };
    });
    return () => chosen;
}

function enterWorld(player) {
    STATE.player = player;
    document.getElementById("boot-screen").remove();
    document.getElementById("player-name").textContent = player.username;
    document.getElementById("player-dot").style.background = player.color;
    document.getElementById("player-resources").textContent = player.resources;
    document.getElementById("player-xp").textContent = player.xp;

    initMap();
    initSocket();
    setTimeout(() => {

        if (STATE.selfLatLng) {

            updateSelfPosition(
                STATE.selfLatLng.lat,
                STATE.selfLatLng.lng
            );

        }

    }, 500);
    wireDock();
    wireHudButtons();
    Territory.init();
    Hunter.init();
    Graffiti.init();
    Social.init();
    StreetView.init();
    setMode("territory");

    setInterval(refreshPlayerStats, 20000);
}

function wireAuthTabs() {
    document.querySelectorAll(".auth-tab").forEach((tab) => {
        tab.onclick = () => {
            document.querySelectorAll(".auth-tab").forEach((t) => t.classList.remove("active"));
            tab.classList.add("active");
            const log = document.getElementById("login-form");
            const from = document.getElementById("register-form")
            if (tab.dataset.tab == "login") {
                log.style = "display:unset;"
                from.style = "display:none;"
            } else if (tab.dataset.tab == "register") {
                log.style = "display:none;"
                from.style = "display:unset;"
            }
        };
    });
}

function showAuthError(elId, message) {
    const el = document.getElementById(elId);
    el.textContent = message;
    el.hidden = false;
}

async function boot() {
    wireAuthTabs();
    const getChosenColor = buildRegisterColorRow();

    try {
        const { player } = await api("/terra/api/me");
        if (player) {
            enterWorld(player);
            return;
        }
    } catch (e) {  }

    document.getElementById("login-form").addEventListener("submit", async (e) => {
        e.preventDefault();
        document.getElementById("login-error").hidden = true;
        const username = document.getElementById("login-username").value.trim();
        const password = document.getElementById("login-password").value;
        try {
            const { player } = await api("/terra/api/login", "POST", { username, password });
            enterWorld(player);
        } catch (err) {
            showAuthError("login-error", err.message);
        }
    });

    document.getElementById("register-form").addEventListener("submit", async (e) => {
        e.preventDefault();
        document.getElementById("register-error").hidden = true;
        const username = document.getElementById("register-username").value.trim();
        const password = document.getElementById("register-password").value;
        const color = getChosenColor();
        try {
            const { player } = await api("/terra/api/register", "POST", { username, password, color });
            enterWorld(player);
        } catch (err) {
            showAuthError("register-error", err.message);
        }
    });
}

boot();
