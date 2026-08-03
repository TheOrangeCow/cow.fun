const Territory = {
    selectedLatLng: null,

    async init() {
        await this.loadAll();
        setInterval(() => this.loadAll(), 15000);
    },

    async loadAll() {
        try {
            const { territories } = await api("/terra/api/territory/list");
            const seen = new Set();
            territories.forEach((t) => {
                seen.add(t.id);
                this.renderTerritory(t);
            });
            Object.keys(STATE.territories).forEach((id) => {
                if (!seen.has(id)) this.removeTerritory(id);
            });
        } catch (e) {
            console.warn(e);
        }
    },

    renderTerritory(t) {
        const existing = STATE.territories[t.id];
        if (existing) {
            existing.layer.setStyle({ color: t.owner_color });
            existing.data = t;
            return;
        }
        const isMine = STATE.player && t.owner_id === STATE.player.id;
        const circle = L.circle([t.lat, t.lng], {
            radius: t.radius_m,
            color: t.owner_color || "#3df5c0",
            weight: 2,
            fillOpacity: isMine ? 0.18 : 0.1,
        }).addTo(STATE.map);

        circle.bindPopup(() => this.popupHtml(STATE.territories[t.id].data));
        circle.on("popupopen", () => this.wirePopup(t.id));
        STATE.territories[t.id] = { layer: circle, data: t };
    },

    removeTerritory(id) {
        const entry = STATE.territories[id];
        if (entry) {
            STATE.map.removeLayer(entry.layer);
            delete STATE.territories[id];
        }
    },

    popupHtml(t) {
        const isMine = STATE.player && t.owner_id === STATE.player.id;
        const invested = Math.max(0, t.defense - 10);
        const maxedOut = invested >= 100;
        return `
      <div style="min-width:160px">
        <b>${t.owner_name}'s territory</b><br>
        Health: ${t.health}/100 <span style="opacity:.7">(+1/30s)</span><br>
        Defense: ${t.defense} <span style="opacity:.7">(invested ${invested}/100)</span><br>
        ${isMine
                ? `<button data-action="collect" data-id="${t.id}">Collect resources</button>
             ${maxedOut
                    ? `<div style="opacity:.7">Investment maxed out</div>`
                    : `<button data-action="invest" data-id="${t.id}">Invest 5 resources</button>`}`
                : `<button class="popup-danger" data-action="attack" data-id="${t.id}">Attack (-10 resources, 30s cooldown)</button>`}
      </div>`;
    },

    wirePopup(tid) {
        setTimeout(() => {
            document.querySelectorAll('[data-action="attack"]').forEach((btn) => {
                btn.onclick = () => this.attack(btn.dataset.id);
            });
            document.querySelectorAll('[data-action="collect"]').forEach((btn) => {
                btn.onclick = () => this.collect(btn.dataset.id);
            });
            document.querySelectorAll('[data-action="invest"]').forEach((btn) => {
                btn.onclick = () => this.invest(btn.dataset.id);
            });
        }, 0);
    },

    onMapClick(lat, lng) {
        this.selectedLatLng = { lat, lng };
        const box = document.getElementById("territory-selected");
        box.hidden = false;
        box.innerHTML = `Selected point: ${lat.toFixed(5)}, ${lng.toFixed(5)}`;
    },

    async claimAtSelf() {
        if (!STATE.selfLatLng) return toast("Waiting for your location...");
        const { lat, lng } = this.selectedLatLng || STATE.selfLatLng;
        try {
            const { territory } = await api("/terra/api/territory/claim", "POST", {
                player_id: STATE.player.id, lat, lng,
            });
            toast("Territory claimed!");
            this.renderTerritory(territory);
            await refreshPlayerStats();
        } catch (e) {
            toast(e.message);
        }
    },

    async attack(tid) {

        const territory = STATE.territories[tid]?.data;

        if (!territory || !STATE.selfLatLng) {
            toast("Waiting for your location...");
            return;
        }

        const distance = STATE.map.distance(
            [STATE.selfLatLng.lat, STATE.selfLatLng.lng],
            [territory.lat, territory.lng]
        );

        if (distance > territory.radius_m) {
            toast("You must be inside this territory to attack.");
            return;
        }

        try {
            const result = await api("/terra/api/territory/attack", "POST", {
                territory_id: tid, player_id: STATE.player.id,
            });
            toast(result.fell ? "You captured the territory!" : `Hit for ${result.damage} damage`);
            STATE.map.closePopup();
            if (result.fell) this.removeTerritory(tid);
            else this.renderTerritory(result.territory);
            await refreshPlayerStats();
            Territory.refreshLeaderboard();
        } catch (e) {
            toast(e.message);
        }
    },

    async invest(tid) {

        const territory = STATE.territories[tid]?.data;

        if (!territory || !STATE.selfLatLng) {
            toast("Waiting for your location...");
            return;
        }

        const distance = STATE.map.distance(
            [STATE.selfLatLng.lat, STATE.selfLatLng.lng],
            [territory.lat, territory.lng]
        );

        if (distance > territory.radius_m) {
            toast("You must be inside your territory to invest.");
            return;
        }

        try {
            const { territory } = await api("/terra/api/territory/invest", "POST", {
                territory_id: tid, amount: 5,
            });
            toast("Invested 5 resources in defense");
            STATE.map.closePopup();
            this.renderTerritory(territory);
            await refreshPlayerStats();
        } catch (e) {
            toast(e.message);
        }
    },

    async collect(tid) {
        try {
            const { earned } = await api("/terra/api/territory/collect", "POST", { territory_id: tid });
            toast(earned > 0 ? `Collected ${earned} resources` : "Nothing to collect yet");
            STATE.map.closePopup();
            await refreshPlayerStats();
        } catch (e) {
            toast(e.message);
        }
    },

    async refreshLeaderboard() {
        const { leaderboard } = await api("/terra/api/territory/leaderboard");
        const list = document.getElementById("leaderboard-list");
        document.getElementById("leaderboard-title").textContent = "Territory Leaders";
        list.innerHTML = leaderboard
            .map((row) => `<li><span>${row.username}</span><span>${row.count} plots</span></li>`)
            .join("") || "<li>No territories claimed yet</li>";
    },

    onSocketUpdate(data) {
        if (data.type === "claimed") this.renderTerritory(data.territory);
        if (data.type === "attacked") this.renderTerritory(data.territory);
        if (data.type === "captured") this.removeTerritory(data.territory_id);
    },
};