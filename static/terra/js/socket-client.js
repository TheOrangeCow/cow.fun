function initSocket() {

    STATE.socket = io();

    STATE.socket.on("connect", () => {

        console.log("Connected");

        if (STATE.selfLatLng && STATE.player) {

            STATE.socket.emit("player_move", {
                player_id: STATE.player.id,
                lat: STATE.selfLatLng.lat,
                lng: STATE.selfLatLng.lng,
                username: STATE.player.username,
                color: STATE.player.color,
            });

        }

        setInterval(() => {

            STATE.socket.emit("request_players");

        }, 15000);

    });

    STATE.socket.on("players_snapshot", (players) => {

        players.forEach((p) => {

            upsertOtherPlayerMarker(
                p.player_id,
                p.lat,
                p.lng,
                p.username,
                p.color
            );

        });

    });

    STATE.socket.on("player_moved", (data) => {

        upsertOtherPlayerMarker(
            data.player_id,
            data.lat,
            data.lng,
            data.username,
            data.color
        );

    });

    STATE.socket.on("player_left", (data) => {

        removeOtherPlayer(data.player_id);

    });

    STATE.socket.on("move_rejected", (data) => {
        console.warn(data.reason);
    });

    STATE.socket.on("territory_update", Territory.onSocketUpdate);
    STATE.socket.on("chest_claimed", Hunter.onSocketClaimed);
    STATE.socket.on("graffiti_update", Graffiti.onSocketUpdate);
    STATE.socket.on("chat_message", Social.onChatMessage);
    STATE.socket.on("emote", Social.onEmote);
    STATE.socket.on("friend_request", Social.onFriendRequest);

}