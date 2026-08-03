const RARITY_EMOJI = { common: "📦", uncommon: "🎁", rare: "💎", legendary: "👑" };

const Hunter = {
    async init() {
        await this.loadToday();
        await this.refreshLeaderboard();
    },

    async loadToday() {
        const { chests } = await api("/terra/api/chests/today");
        document.getElementById("chest-count").textContent = chests.filter((c) => !c.claimed_by).length;
        chests.forEach((c) => this.renderChest(c));
    },

    renderChest(c) {
        const existing = STATE.chests[c.id];
        const claimed = !!c.claimed_by;
        if (existing) {
            existing.data = c;
            existing.marker.setIcon(this.iconFor(c, claimed));
            return;
        }
        const marker = L.marker([c.lat, c.lng], { icon: this.iconFor(c, claimed) }).addTo(STATE.map);
        marker.on("click", () => this.select(c.id));
        STATE.chests[c.id] = { marker, data: c };
    },

    iconFor(c, claimed) {
        return L.divIcon({
            className: "",
            html: `<div class="chest-marker ${claimed ? "claimed" : ""}">${RARITY_EMOJI[c.rarity] || "📦"}</div>`,
            iconSize: [24, 24],
            iconAnchor: [12, 12],
        });
    },

    select(chestId) {
        const entry = STATE.chests[chestId];
        if (!entry || entry.data.claimed_by) return;
        STATE.pendingChest = entry.data;
        const box = document.getElementById("chest-selected");
        box.hidden = false;
        const dist = STATE.selfLatLng
            ? Math.round(haversineMeters(STATE.selfLatLng.lat, STATE.selfLatLng.lng, entry.data.lat, entry.data.lng))
            : "?";
        box.innerHTML = `
      <div><b>${RARITY_EMOJI[entry.data.rarity]} ${entry.data.rarity} chest</b> — ${dist}m away</div>
      ${entry.data.requires_puzzle ? `<div style="margin:6px 0"><i>Riddle:</i> ${entry.data.puzzle_question}<br>
        <input id="puzzle-answer" placeholder="your answer" style="width:100%;margin-top:4px;padding:6px;background:#12171c;border:1px solid var(--line);color:var(--text)"></div>` : ""}
      <button id="btn-open-chest" style="margin-top:8px;width:100%">Open chest</button>
    `;
        document.getElementById("btn-open-chest").onclick = () => this.claim(chestId);
    },

    async claim(chestId) {
        if (!STATE.selfLatLng) return toast("Waiting for your location...");
        const answerEl = document.getElementById("puzzle-answer");
        try {
            const result = await api("/terra/api/chests/claim", "POST", {
                chest_id: chestId,
                player_id: STATE.player.id,
                lat: STATE.selfLatLng.lat,
                lng: STATE.selfLatLng.lng,
                answer: answerEl ? answerEl.value : "",
            });
            toast(`${RARITY_EMOJI[result.rarity]} +${result.loot} resources!`);
            document.getElementById("chest-selected").hidden = true;
            STATE.pendingChest = null;
            await refreshPlayerStats();
            this.refreshLeaderboard();
        } catch (e) {
            toast(e.message);
        }
    },

    onMapClick() {
        
    },

    onSocketClaimed(data) {
        const entry = STATE.chests[data.chest_id];
        if (entry) {
            entry.data.claimed_by = data.player_id;
            this.renderChest(entry.data);
            document.getElementById("chest-count").textContent =
                Object.values(STATE.chests).filter((e) => !e.data.claimed_by).length;
        }
    },

    async refreshLeaderboard() {
        if (STATE.currentMode !== "hunter") return;
        const { leaderboard } = await api("/terra/api/chests/leaderboard");
        const list = document.getElementById("leaderboard-list");
        document.getElementById("leaderboard-title").textContent = "Today's Hunters";
        list.innerHTML = leaderboard
            .map((row) => `<li><span>${row.username}</span><span>${row.chests_found} chests</span></li>`)
            .join("") || "<li>No chests opened yet today</li>";
    },
};
