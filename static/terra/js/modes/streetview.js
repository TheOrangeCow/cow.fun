const StreetView = {
    STEP_M: 3,
    TURN_DEG: 10,

    MOVE_REPEAT_MS: 90,
    TURN_REPEAT_MS: 60,


    ROAD_BUFFER_M: 80,


    TILE_URL_TEMPLATE: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    TILE_SUBDOMAINS: ["a", "b", "c"],
    TILE_SIZE: 256,

    SAMPLE_ZOOM: 19,


    ROAD_COLORS: [
        [142, 142, 142],
        [121, 121, 123],
        [136, 137, 123],
        [113, 98, 93],
        [98, 81, 84],
        [118, 118, 106]
    ],


    COLOR_TOLERANCE: 40,

    PREFETCH_MARGIN_TILES: 1,

    hud: null,
    heldKeys: new Set(),
    moveTimer: null,
    turnTimer: null,

    tileCache: new Map(),
    tilesLoadingCount: 0,
    didInitialSnap: false,

    init() {
        const enterBtn = document.getElementById("btn-enter-streetview");
        if (enterBtn) {
            enterBtn.onclick = () => {
                const hudEl = document.getElementById('walk-mode-hud');
                if (hudEl) hudEl.style.display = 'flex';

            };
        }

        const closeBtn = document.getElementById("sv-close");
        const forwardBtn = document.getElementById("sv-forward");
        const backBtn = document.getElementById("sv-back");
        const leftBtn = document.getElementById("sv-turn-left");
        const rightBtn = document.getElementById("sv-turn-right");

        if (closeBtn) closeBtn.onclick = () => this.close();
        if (forwardBtn) forwardBtn.onclick = () => this.walk(1);
        if (backBtn) backBtn.onclick = () => this.walk(-1);
        if (leftBtn) leftBtn.onclick = () => this.turn(-this.TURN_DEG);
        if (rightBtn) rightBtn.onclick = () => this.turn(this.TURN_DEG);

        window.addEventListener("keydown", (e) => this.onKeyDown(e));
        window.addEventListener("keyup", (e) => this.onKeyUp(e));
        window.addEventListener("blur", () => this.clearHeldKeys());

        this.createHud();
        this.hideOldStreetViewOverlay();
    },

    createHud() {
        if (this.hud) return;

        const hud = document.createElement("div");
        hud.id = "walk-mode-hud";
        hud.hidden = true;

        hud.style.position = "fixed";
        hud.style.left = "50%";
        hud.style.bottom = "18px";
        hud.style.transform = "translateX(-50%)";
        hud.style.zIndex = "9999";
        hud.style.display = "flex";
        hud.style.flexDirection = "column";
        hud.style.alignItems = "center";
        hud.style.gap = "8px";
        hud.style.padding = "12px";
        hud.style.borderRadius = "16px";
        hud.style.background = "rgba(0,0,0,0.78)";
        hud.style.color = "#fff";
        hud.style.fontFamily = "Arial, sans-serif";
        hud.style.boxShadow = "0 6px 24px rgba(0,0,0,0.4)";
        hud.style.userSelect = "none";
        hud.style.touchAction = "none";
        hud.style.display = "none"

        hud.innerHTML = `
            <div id="walk-mode-status" style="font-weight:bold;font-size:14px;text-align:center;">
                Walk mode
            </div>

            <div id="walk-facing-wrap" style="
                width:72px;
                height:72px;
                border-radius:50%;
                border:2px solid rgba(255,255,255,0.75);
                display:flex;
                align-items:center;
                justify-content:center;
                position:relative;
                background:rgba(255,255,255,0.08);
            ">
                <div style="
                    position:absolute;
                    top:5px;
                    font-size:10px;
                    opacity:0.8;
                    font-weight:bold;
                ">N</div>

                <div id="walk-facing-arrow" style="
                    width:0;
                    height:0;
                    border-left:10px solid transparent;
                    border-right:10px solid transparent;
                    border-bottom:30px solid #42d9ff;
                    transform-origin:50% 70%;
                    filter:drop-shadow(0 0 5px rgba(66,217,255,0.8));
                "></div>
            </div>

            <div id="walk-facing-text" style="font-size:13px;font-weight:bold;">
                Facing N
            </div>

            <button id="walk-forward" class="walk-btn" style="
                min-width:96px;
                padding:10px 14px;
                border-radius:12px;
                border:0;
                font-size:18px;
                font-weight:bold;
            ">
                ↑
            </button>

            <div style="display:flex;gap:8px;align-items:center;">
                <button id="walk-left" class="walk-btn" style="
                    width:58px;
                    padding:10px 12px;
                    border-radius:12px;
                    border:0;
                    font-size:18px;
                    font-weight:bold;
                ">
                    ←
                </button>

                <button id="walk-back" class="walk-btn" style="
                    width:58px;
                    padding:10px 12px;
                    border-radius:12px;
                    border:0;
                    font-size:18px;
                    font-weight:bold;
                ">
                    ↓
                </button>

                <button id="walk-right" class="walk-btn" style="
                    width:58px;
                    padding:10px 12px;
                    border-radius:12px;
                    border:0;
                    font-size:18px;
                    font-weight:bold;
                ">
                    →
                </button>
            </div>

            <button id="walk-close" style="
                padding:7px 14px;
                border-radius:12px;
                border:0;
                background:#ff5555;
                color:white;
                font-weight:bold;
            ">
                Exit walk mode
            </button>

            <div style="font-size:12px;opacity:0.8;text-align:center;">
                Mobile: arrows. Desktop: WASD or arrow keys.
            </div>
        `;

        document.body.appendChild(hud);
        this.hud = hud;

        this.bindHoldButton("walk-forward", () => this.walk(1), this.MOVE_REPEAT_MS);
        this.bindHoldButton("walk-back", () => this.walk(-1), this.MOVE_REPEAT_MS);
        this.bindHoldButton("walk-left", () => this.turn(-this.TURN_DEG), this.TURN_REPEAT_MS);
        this.bindHoldButton("walk-right", () => this.turn(this.TURN_DEG), this.TURN_REPEAT_MS);

        document.getElementById('walk-close').onclick = () => {
            document.getElementById('walk-mode-hud').style.display = 'none';
        };


    },

    bindHoldButton(id, action, repeatMs) {
        const btn = document.getElementById(id);
        if (!btn) return;

        let timer = null;

        const start = (e) => {
            e.preventDefault();

            action();

            if (timer) clearInterval(timer);
            timer = setInterval(action, repeatMs);
        };

        const stop = (e) => {
            if (e) e.preventDefault();

            if (timer) {
                clearInterval(timer);
                timer = null;
            }
        };

        btn.addEventListener("mousedown", start);
        btn.addEventListener("touchstart", start, { passive: false });

        btn.addEventListener("mouseup", stop);
        btn.addEventListener("mouseleave", stop);
        btn.addEventListener("touchend", stop);
        btn.addEventListener("touchcancel", stop);
    },

    hideOldStreetViewOverlay() {
        const overlay = document.getElementById("streetview-overlay");
        if (overlay) {
            overlay.hidden = true;
            overlay.style.display = "none";
        }
    },

    onKeyDown(e) {
        if (!STATE.streetViewOpen) return;

        const key = e.key.toLowerCase();

        if (
            key === "arrowup" ||
            key === "arrowdown" ||
            key === "arrowleft" ||
            key === "arrowright" ||
            key === "w" ||
            key === "a" ||
            key === "s" ||
            key === "d"
        ) {
            e.preventDefault();
            this.heldKeys.add(key);
            this.startKeyboardLoops();
        } else if (key === "escape") {
            e.preventDefault();
            this.close();
        }
    },

    onKeyUp(e) {
        const key = e.key.toLowerCase();
        this.heldKeys.delete(key);

        if (this.heldKeys.size === 0) {
            this.stopKeyboardLoops();
        }
    },

    clearHeldKeys() {
        this.heldKeys.clear();
        this.stopKeyboardLoops();
    },

    startKeyboardLoops() {
        if (!this.moveTimer) {
            this.handleKeyboardMove();
            this.moveTimer = setInterval(
                () => this.handleKeyboardMove(),
                this.MOVE_REPEAT_MS
            );
        }

        if (!this.turnTimer) {
            this.handleKeyboardTurn();
            this.turnTimer = setInterval(
                () => this.handleKeyboardTurn(),
                this.TURN_REPEAT_MS
            );
        }
    },

    stopKeyboardLoops() {
        if (this.moveTimer) {
            clearInterval(this.moveTimer);
            this.moveTimer = null;
        }

        if (this.turnTimer) {
            clearInterval(this.turnTimer);
            this.turnTimer = null;
        }
    },

    handleKeyboardMove() {
        if (!STATE.streetViewOpen) return;

        const forward =
            this.heldKeys.has("w") ||
            this.heldKeys.has("arrowup");

        const back =
            this.heldKeys.has("s") ||
            this.heldKeys.has("arrowdown");

        if (forward && !back) {
            this.walk(1);
        } else if (back && !forward) {
            this.walk(-1);
        }
    },

    handleKeyboardTurn() {
        if (!STATE.streetViewOpen) return;

        const left =
            this.heldKeys.has("a") ||
            this.heldKeys.has("arrowleft");

        const right =
            this.heldKeys.has("d") ||
            this.heldKeys.has("arrowright");

        if (left && !right) {
            this.turn(-this.TURN_DEG);
        } else if (right && !left) {
            this.turn(this.TURN_DEG);
        }
    },

    open() {
        if (!STATE.selfLatLng) {
            return toast("Waiting for your location before you can walk...");
        }

        this.createHud();
        this.hideOldStreetViewOverlay();

        STATE.streetViewOpen = true;
        STATE.manualWalking = true;

        if (!STATE.heading && STATE.heading !== 0) {
            STATE.heading = 0;
        }

        this.didInitialSnap = false;

        this.ensureTilesLoaded(STATE.selfLatLng.lat, STATE.selfLatLng.lng);
        this.snapIntoBoundsIfNeeded();

        this.hud.hidden = false;
        this.renderHud();
    },

    close() {
        STATE.streetViewOpen = false;
        STATE.manualWalking = false;

        this.clearHeldKeys();

        if (this.hud) {
            this.hud.hidden = true;
        }

        this.hideOldStreetViewOverlay();
    },

    async snapIntoBoundsIfNeeded() {
        if (this.didInitialSnap) return;
        if (!STATE.selfLatLng) return;

        this.didInitialSnap = true;

        const lat = STATE.selfLatLng.lat;
        const lng = STATE.selfLatLng.lng;

        await this.ensureTilesLoaded(lat, lng, 2);

        if (!this.canStandAt(lat, lng)) {
            const snapped = this.nearestRoadLatLng(lat, lng);

            if (snapped) {
                updateSelfPosition(snapped.lat, snapped.lng);

                if (STATE.map) {
                    STATE.map.panTo([snapped.lat, snapped.lng], {
                        animate: false
                    });
                }

                toast("Moved you onto the nearest road.");
            } else {
                toast("Couldn't find a nearby road — try moving the map first.");
            }
        }

        this.renderHud();
    },

    turn(deltaDeg) {
        if (!STATE.heading && STATE.heading !== 0) {
            STATE.heading = 0;
        }

        STATE.heading = ((STATE.heading + deltaDeg) % 360 + 360) % 360;

        this.renderHud();
    },

    walk(dir) {
        if (!STATE.selfLatLng) return;

        STATE.manualWalking = true;

        const heading = STATE.heading || 0;
        const bearing = dir > 0 ? heading : (heading + 180) % 360;

        const dest = destinationPoint(
            STATE.selfLatLng.lat,
            STATE.selfLatLng.lng,
            bearing,
            this.STEP_M
        );

        this.ensureTilesLoaded(dest.lat, dest.lng);

        if (!this.canStandAt(dest.lat, dest.lng)) {
            toast("You can't leave the roads unless you're inside your own territory.");
            this.flashBlocked();
            return;
        }

        updateSelfPosition(dest.lat, dest.lng);

        if (STATE.map) {
            STATE.map.panTo([dest.lat, dest.lng], {
                animate: false
            });
        }

        this.renderHud();
    },

    canStandAt(lat, lng) {
        const onRoad = this.isNearRoadColor(lat, lng, this.ROAD_BUFFER_M);

        if (onRoad === null || onRoad === true) return true;

        return this.isOwnTerritoryAt(lat, lng);
    },

    isOwnTerritoryAt(lat, lng) {
        if (!STATE.player || !STATE.territories) return false;

        return Object.values(STATE.territories).some((t) => {
            if (!t.data) return false;

            const ownedByMe = t.data.owner_id === STATE.player.id;
            if (!ownedByMe) return false;

            const distance = haversineMeters(
                lat,
                lng,
                t.data.lat,
                t.data.lng
            );

            return distance <= t.data.radius_m;
        });
    },

    metersPerPixel(lat, zoom) {
        return (156543.03392 * Math.cos((lat * Math.PI) / 180)) / Math.pow(2, zoom);
    },

    latLngToGlobalPixel(lat, lng, zoom) {
        const n = Math.pow(2, zoom) * this.TILE_SIZE;
        const latRad = (lat * Math.PI) / 180;

        const x = ((lng + 180) / 360) * n;
        const y =
            ((1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2) * n;

        return { x, y };
    },

    globalPixelToLatLng(px, py, zoom) {
        const n = Math.pow(2, zoom) * this.TILE_SIZE;

        const lng = (px / n) * 360 - 180;
        const yFrac = py / n;
        const latRad = Math.atan(Math.sinh(Math.PI * (1 - 2 * yFrac)));
        const lat = (latRad * 180) / Math.PI;

        return { lat, lng };
    },

    tileKey(zoom, tileX, tileY) {
        return `${zoom}_${tileX}_${tileY}`;
    },

    loadTile(tileX, tileY, zoom) {
        const key = this.tileKey(zoom, tileX, tileY);
        const existing = this.tileCache.get(key);
        if (existing) return existing.promise;

        const n = Math.pow(2, zoom);
        const wrappedX = ((tileX % n) + n) % n;

        const sub = this.TILE_SUBDOMAINS[
            Math.abs(tileX + tileY) % this.TILE_SUBDOMAINS.length
        ];

        const url = this.TILE_URL_TEMPLATE
            .replace("{s}", sub)
            .replace("{z}", zoom)
            .replace("{x}", wrappedX)
            .replace("{y}", tileY);

        const entry = { status: "loading", imageData: null };

        entry.promise = new Promise((resolve) => {
            const img = new Image();
            img.crossOrigin = "anonymous";

            img.onload = () => {
                try {
                    const canvas = document.createElement("canvas");
                    canvas.width = this.TILE_SIZE;
                    canvas.height = this.TILE_SIZE;

                    const ctx = canvas.getContext("2d");
                    ctx.drawImage(img, 0, 0, this.TILE_SIZE, this.TILE_SIZE);

                    entry.imageData = ctx.getImageData(0, 0, this.TILE_SIZE, this.TILE_SIZE);
                    entry.status = "ready";
                } catch (err) {
                    console.error("Couldn't read map tile pixels (CORS?)", err);
                    entry.status = "error";
                }

                this.tilesLoadingCount--;
                this.renderHud();
                resolve(entry);
            };

            img.onerror = () => {
                entry.status = "error";
                this.tilesLoadingCount--;
                this.renderHud();
                resolve(entry);
            };

            img.src = url;
        });

        this.tileCache.set(key, entry);
        this.tilesLoadingCount++;
        this.renderHud();

        return entry.promise;
    },

    ensureTilesLoaded(lat, lng, marginTiles = null) {
        const zoom = this.SAMPLE_ZOOM;
        const margin = marginTiles == null ? this.PREFETCH_MARGIN_TILES : marginTiles;

        const { x, y } = this.latLngToGlobalPixel(lat, lng, zoom);
        const centerTileX = Math.floor(x / this.TILE_SIZE);
        const centerTileY = Math.floor(y / this.TILE_SIZE);

        const promises = [];

        for (let dx = -margin; dx <= margin; dx++) {
            for (let dy = -margin; dy <= margin; dy++) {
                promises.push(this.loadTile(centerTileX + dx, centerTileY + dy, zoom));
            }
        }

        return Promise.all(promises);
    },

    globalPixelColor(px, py, zoom) {
        const tileX = Math.floor(px / this.TILE_SIZE);
        const tileY = Math.floor(py / this.TILE_SIZE);

        const entry = this.tileCache.get(this.tileKey(zoom, tileX, tileY));
        if (!entry || entry.status !== "ready") return null;

        const localX = Math.floor(px) - tileX * this.TILE_SIZE;
        const localY = Math.floor(py) - tileY * this.TILE_SIZE;

        const idx = (localY * this.TILE_SIZE + localX) * 4;
        const d = entry.imageData.data;

        return { r: d[idx], g: d[idx + 1], b: d[idx + 2], a: d[idx + 3] };
    },

    isRoadColor(color) {
        for (const [r, g, b] of this.ROAD_COLORS) {
            const diff = Math.max(
                Math.abs(color.r - r),
                Math.abs(color.g - g),
                Math.abs(color.b - b)
            );

            if (diff <= this.COLOR_TOLERANCE) return true;
        }

        return false;
    },

    isNearRoadColor(lat, lng, bufferM) {
        const zoom = this.SAMPLE_ZOOM;
        const mpp = this.metersPerPixel(lat, zoom);
        const bufferPx = Math.max(1, Math.round(bufferM / mpp));

        const center = this.latLngToGlobalPixel(lat, lng, zoom);

        const offsets = [[0, 0]];
        const ringFractions = [1, 0.66, 0.33];
        const angleStepsDeg = [0, 45, 90, 135, 180, 225, 270, 315];

        for (const frac of ringFractions) {
            const r = bufferPx * frac;

            for (const deg of angleStepsDeg) {
                const rad = (deg * Math.PI) / 180;
                offsets.push([r * Math.cos(rad), r * Math.sin(rad)]);
            }
        }

        let sawUnknown = false;

        for (const [ox, oy] of offsets) {
            const color = this.globalPixelColor(center.x + ox, center.y + oy, zoom);

            if (color === null) {
                sawUnknown = true;
                continue;
            }

            if (this.isRoadColor(color)) return true;
        }

        return sawUnknown ? null : false;
    },

    isRoadLatLng(lat, lng) {
        return this.isNearRoadColor(lat, lng, this.ROAD_BUFFER_M) === true;
    },

    nearestRoadLatLng(lat, lng, maxSearchM = 120) {
        const zoom = this.SAMPLE_ZOOM;
        const mpp = this.metersPerPixel(lat, zoom);
        const maxRadiusPx = Math.max(1, Math.round(maxSearchM / mpp));

        const center = this.latLngToGlobalPixel(lat, lng, zoom);

        let best = null;
        let bestDistSq = Infinity;

        for (let r = 1; r <= maxRadiusPx; r += 1) {
            for (let dx = -r; dx <= r; dx++) {
                for (let dy = -r; dy <= r; dy++) {
                    if (Math.max(Math.abs(dx), Math.abs(dy)) !== r) continue;

                    const px = center.x + dx;
                    const py = center.y + dy;

                    const color = this.globalPixelColor(px, py, zoom);
                    if (!color || !this.isRoadColor(color)) continue;

                    const distSq = dx * dx + dy * dy;
                    if (distSq < bestDistSq) {
                        bestDistSq = distSq;
                        best = { x: px, y: py };
                    }
                }
            }

            if (best) break;
        }

        if (!best) return null;

        return this.globalPixelToLatLng(best.x, best.y, zoom);
    },

    compassLabel(heading) {
        const dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
        return dirs[Math.round(heading / 45) % 8];
    },

    renderHud() {
        const status = document.getElementById("walk-mode-status");
        const facingArrow = document.getElementById("walk-facing-arrow");
        const facingText = document.getElementById("walk-facing-text");

        if (!status || !STATE.selfLatLng) return;

        const lat = STATE.selfLatLng.lat;
        const lng = STATE.selfLatLng.lng;
        const heading = STATE.heading || 0;

        const onRoad = this.isNearRoadColor(lat, lng, this.ROAD_BUFFER_M);
        const ownTerritory = this.isOwnTerritoryAt(lat, lng);

        let place;

        if (onRoad === null && this.tilesLoadingCount > 0) {
            place = "Reading the map…";
        } else if (onRoad === true) {
            place = "On road";
        } else if (ownTerritory) {
            place = "In your territory";
        } else {
            place = "Off-road blocked";
        }

        const direction = this.compassLabel(heading);

        status.textContent = `Walk mode · ${place}`;

        if (facingArrow) {
            facingArrow.style.transform = `rotate(${heading}deg)`;
        }

        if (facingText) {
            facingText.textContent = `Facing ${direction} (${Math.round(heading)}°)`;
        }
    },

    flashBlocked() {
        if (!this.hud) return;

        const oldBg = this.hud.style.background;
        this.hud.style.background = "rgba(160,0,0,0.88)";

        setTimeout(() => {
            if (this.hud) {
                this.hud.style.background = oldBg;
            }
        }, 180);
    }
};