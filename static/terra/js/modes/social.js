const Social = {
    voiceEnabled: false,
    localStream: null,
    peers: {},

    init() {
        document.getElementById("chat-form").addEventListener("submit", (e) => {
            e.preventDefault();
            this.sendChat();
        });
        setInterval(() => this.refreshNearby(), 4000);
    },

    onSelfMove(lat, lng) {

    },

    sendChat() {
        const input = document.getElementById("chat-input");
        const message = input.value.trim();
        if (!message || !STATE.selfLatLng) return;
        STATE.socket.emit("chat_message", {
            player_id: STATE.player.id,
            username: STATE.player.username,
            message,
            lat: STATE.selfLatLng.lat,
            lng: STATE.selfLatLng.lng,
        });
        input.value = "";
    },

    onChatMessage(data) {
        const log = document.getElementById("chat-log");
        let far = false;
        if (STATE.selfLatLng && data.lat != null) {
            const dist = haversineMeters(STATE.selfLatLng.lat, STATE.selfLatLng.lng, data.lat, data.lng);
            far = dist > SHOUT_RADIUS_M;
        }
        const row = document.createElement("div");
        row.className = "msg" + (far ? " far" : "");
        row.innerHTML = `<span class="who">${data.username || "?"}</span>: ${this.escapeHtml(data.message)}`;
        log.appendChild(row);
        log.scrollTop = log.scrollHeight;
    },

    escapeHtml(s) {
        const d = document.createElement("div");
        d.textContent = s;
        return d.innerHTML;
    },

    async refreshNearby() {
        if (!STATE.selfLatLng) return;
        try {
            const { players } = await api("/terra/api/players/online");
            const list = document.getElementById("nearby-players");
            const nearby = players
                .filter((p) => p.id !== STATE.player?.id)
                .map((p) => ({
                    ...p,
                    dist: haversineMeters(STATE.selfLatLng.lat, STATE.selfLatLng.lng, p.lat, p.lng),
                }))
                .sort((a, b) => a.dist - b.dist);
            list.innerHTML = nearby
                .map((p) => `<li><span>${p.username}</span><span>${Math.round(p.dist)}m</span></li>`)
                .join("") || "<li>No one else online right now</li>";
        } catch (e) {
            console.warn(e);
        }
    },

    sendFriendRequest(toId, username) {
        api("/terra/api/friends/request", "POST", { from_id: STATE.player.id, to_id: toId })
            .then(() => toast(`Friend request sent to ${username}`))
            .catch((e) => toast(e.message));
    },

    onFriendRequest(data) {
        if (data.to_id !== STATE.player?.id) return;
        toast("You received a friend request!");
    },
    sendEmote(emoji) {
        if (!STATE.selfLatLng) return;
        STATE.socket.emit("emote", {
            player_id: STATE.player.id, username: STATE.player.username,
            emoji, lat: STATE.selfLatLng.lat, lng: STATE.selfLatLng.lng,
        });
    },

    onEmote(data) {
        const entry = STATE.otherPlayers[data.player_id];
        if (!entry) return;
        entry.marker.bindTooltip(`${data.emoji} ${data.username}`, { permanent: false }).openTooltip();
        setTimeout(() => entry.marker.bindTooltip(data.username), 2000);
    },

    async toggleVoice() {
        if (this.voiceEnabled) {
            this.voiceEnabled = false;
            if (this.localStream) this.localStream.getTracks().forEach((t) => t.stop());
            Object.values(this.peers).forEach((pc) => pc.close());
            this.peers = {};
            toast("Voice chat off");
            return;
        }
        try {
            this.localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.voiceEnabled = true;
            toast("Mic captured. Wire up RTCPeerConnections in social.js to finish proximity voice.");
        } catch (e) {
            toast("Microphone permission denied");
        }
    },
};
