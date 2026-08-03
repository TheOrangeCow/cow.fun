const FALLBACK_CENTER = [50.89880, -1.39196];

function initMap() {
    STATE.map = L.map("map", { zoomControl: false, attributionControl: true }).setView(FALLBACK_CENTER, 16);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: "&copy; OpenStreetMap contributors",
    }).addTo(STATE.map);

    L.control.zoom({ position: "bottomright" }).addTo(STATE.map);

    STATE.map.on("click", (e) => {
        onMapClick(e.latlng.lat, e.latlng.lng);
    });

    startGeolocation();
}

function onMapClick(lat, lng) {
    if (STATE.currentMode === "territory") Territory.onMapClick(lat, lng);
    else if (STATE.currentMode === "graffiti") Graffiti.onMapClick(lat, lng);
    else if (STATE.currentMode === "hunter") Hunter.onMapClick(lat, lng);
}

function makeSelfIcon() {
    return L.divIcon({
        className: "",
        html: `<div class="self-marker" style="background:${STATE.player.color}"></div>`,
        iconSize: [22, 22],
        iconAnchor: [11, 11],
    });
}

function updateSelfPosition(lat, lng) {
    STATE.selfLatLng = { lat, lng };
    if (!STATE.selfMarker) {
        STATE.selfMarker = L.marker([lat, lng], { icon: makeSelfIcon(), zIndexOffset: 1000 }).addTo(STATE.map);
    } else {
        STATE.selfMarker.setLatLng([lat, lng]);
    }
    if (STATE.socket && STATE.socket.connected && STATE.player) {
        STATE.socket.emit("player_move", {
            player_id: STATE.player.id, lat, lng,
            username: STATE.player.username, color: STATE.player.color,
        });
    }
    Social.onSelfMove(lat, lng);
}

function startGeolocation() {
    if (!("geolocation" in navigator)) {
        toast("Geolocation not available — using a fallback position.");
        updateSelfPosition(FALLBACK_CENTER[0], FALLBACK_CENTER[1]);
        return;
    }
    navigator.geolocation.watchPosition(
        (pos) => {
            if (STATE.manualWalking) return;
            const { latitude, longitude } = pos.coords;
            updateSelfPosition(latitude, longitude);
            if (!STATE.hasCentered) {
                STATE.map.setView([latitude, longitude], 17);
                STATE.hasCentered = true;
            }
        },
        (err) => {
            console.warn("geolocation error", err);
            if (!STATE.selfLatLng) {
                toast("Location unavailable — drop a pin by clicking the map instead.");
                const c = STATE.map.getCenter();
                updateSelfPosition(c.lat, c.lng);
            }
        },
        { enableHighAccuracy: true, maximumAge: 5000, timeout: 10000 }
    );
}

function upsertOtherPlayerMarker(id, lat, lng, username, color) {
    if (id === STATE.player?.id) return;
    let entry = STATE.otherPlayers[id];
    if (!entry) {
        const icon = L.divIcon({
            className: "",
            html: `<div class="player-marker" style="background:${color || "#4d9fff"}" title="${username}"></div>`,
            iconSize: [16, 16],
            iconAnchor: [8, 8],
        });
        const marker = L.marker([lat, lng], { icon }).addTo(STATE.map).bindTooltip(username || "Player");
        marker.bindPopup(
            `<div><b>${username || "Player"}</b><br>
       <button data-friend="${id}">Add friend</button></div>`
        );
        marker.on("popupopen", () => {
            setTimeout(() => {
                const btn = document.querySelector(`[data-friend="${id}"]`);
                if (btn) btn.onclick = () => Social.sendFriendRequest(id, username);
            }, 0);
        });
        entry = { marker, username, color, lat, lng };
        STATE.otherPlayers[id] = entry;
    } else {
        entry.marker.setLatLng([lat, lng]);
        entry.lat = lat;
        entry.lng = lng;
    }
}

function removeOtherPlayer(id) {

    const player = STATE.otherPlayers[id];

    if (!player) return;

    STATE.map.removeLayer(player.marker);

    delete STATE.otherPlayers[id];

}