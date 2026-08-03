const STYLES = ["tag", "stencil", "mural", "scribble"];

const Graffiti = {
    selectedLatLng: null,
    selectedStyle: "tag",
    selectedColor: "#ff3d8a",

    init() {
        this.buildStyleRow();
        this.buildColorRow();
        this.loadAll();
        this.refreshTrending();
    },

    buildStyleRow() {
        const row = document.getElementById("graffiti-style-row");
        row.innerHTML = STYLES.map(
            (s, i) => `<div class="style-chip ${i === 0 ? "selected" : ""}" data-style="${s}">${s}</div>`
        ).join("");
        row.querySelectorAll(".style-chip").forEach((chip) => {
            chip.onclick = () => {
                row.querySelectorAll(".style-chip").forEach((c) => c.classList.remove("selected"));
                chip.classList.add("selected");
                this.selectedStyle = chip.dataset.style;
            };
        });
    },

    buildColorRow() {
        const row = document.getElementById("graffiti-color-row");
        row.innerHTML = STATE.colors
            .map((c, i) => `<div class="swatch ${i === 2 ? "selected" : ""}" style="background:${c}" data-color="${c}"></div>`)
            .join("");
        row.querySelectorAll(".swatch").forEach((sw) => {
            sw.onclick = () => {
                row.querySelectorAll(".swatch").forEach((s) => s.classList.remove("selected"));
                sw.classList.add("selected");
                this.selectedColor = sw.dataset.color;
            };
        });
    },

    async loadAll() {
        const { graffiti } = await api("/terra/api/graffiti/list");
        graffiti.forEach((g) => this.renderGraffiti(g));
    },

    renderGraffiti(g) {
        const existing = STATE.graffiti[g.id];
        const opacity = Math.max(0.15, Math.min(1, g.life / 100));
        if (existing) {
            existing.data = g;
            existing.marker.setOpacity(opacity);
            return;
        }
        const marker = L.marker([g.lat, g.lng], {
            icon: L.divIcon({
                className: "",
                html: `<div class="graffiti-marker" style="color:${g.color}">${this.emojiFor(g.style)}</div>`,
                iconSize: [20, 20],
                iconAnchor: [10, 10],
            }),
            opacity,
        }).addTo(STATE.map);
        marker.bindPopup(() => this.popupHtml(g));
        marker.on("popupopen", () => this.wirePopup(g.id));
        STATE.graffiti[g.id] = { marker, data: g };
    },

    emojiFor(style) {
        return { tag: "🖊️", stencil: "🔳", mural: "🖼️", scribble: "✏️" }[style] || "🎨";
    },

    popupHtml(g) {
        return `
      <div style="min-width:150px">
        <b>${g.artist_name}</b> — ${g.style}<br>
        ${g.message ? `<i>"${this.escapeHtml(g.message)}"</i><br>` : ""}
        ❤️ ${g.likes} likes<br>
        <button data-like="${g.id}">Like</button>
      </div>`;
    },

    escapeHtml(s) {
        const d = document.createElement("div");
        d.textContent = s;
        return d.innerHTML;
    },

    wirePopup(gid) {
        setTimeout(() => {
            document.querySelectorAll(`[data-like="${gid}"]`).forEach((btn) => {
                btn.onclick = () => this.like(gid);
            });
        }, 0);
    },

    onMapClick(lat, lng) {
        this.selectedLatLng = { lat, lng };
        toast("Spray point selected — press Spray here");
    },

    async place() {
        if (!this.selectedLatLng) return toast("Tap the map to choose a spot first");
        const message = document.getElementById("graffiti-message").value;
        try {
            const { graffiti } = await api("/terra/api/graffiti/create", "POST", {
                artist_id: STATE.player.id,
                lat: this.selectedLatLng.lat,
                lng: this.selectedLatLng.lng,
                style: this.selectedStyle,
                color: this.selectedColor,
                message,
            });
            this.renderGraffiti(graffiti);
            document.getElementById("graffiti-message").value = "";
            toast("Sprayed!");
            await refreshPlayerStats();
        } catch (e) {
            toast(e.message);
        }
    },

    async like(gid) {
        try {
            await api("/terra/api/graffiti/like", "POST", { graffiti_id: gid, player_id: STATE.player.id });
            STATE.map.closePopup();
            toast("Liked!");
            this.refreshTrending();
        } catch (e) {
            toast(e.message);
        }
    },

    async refreshTrending() {
        const { trending } = await api("/terra/api/graffiti/trending");
        const list = document.getElementById("graffiti-trending");
        list.innerHTML = trending
            .map((g) => `<li><span>${this.emojiFor(g.style)} ${g.artist_name}</span><span>❤️ ${g.likes}</span></li>`)
            .join("") || "<li>Nothing trending yet</li>";
    },

    onSocketUpdate(data) {
        if (data.type === "created") this.renderGraffiti(data.graffiti);
        if (data.type === "liked") {
            const entry = STATE.graffiti[data.graffiti_id];
            if (entry) {
                entry.data.likes = data.likes;
                this.refreshTrending();
            }
        }
    },
};
