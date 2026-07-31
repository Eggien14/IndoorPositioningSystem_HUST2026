/* Realtime page for Algorithm 5 (Trilateration: Tightly-coupled EKF).
 * Exact clone of the Algorithm 3 page — only the positioning backend differs
 * (UWB ranging straight into one EKF), so there is no model/campaign picker and the
 * API prefix is /api/training-alg5/. Receive side = uwb_ranging + uwb_id (backend);
 * transmit side (user_pos / fire_data) is identical to Algorithm 3.
 * Phase A: live positioning/heading/spray. Fire simulation + scoring = Phase B. */

let runData = null;
let mapData = null;
let mapCells = [];
let selectedDevices = [];      // [{device_id, device_name, device_hex_id}]
let pollTimer = null;
let activeTimer = null;
let countdownTimer = null;
let trainingStarted = false;
let countdownInProgress = false;
let elapsedSeconds = 0;
let assemblyPoint = null;       // {x, y} cell bottom-left coord
let deviceColors = {};          // hex(lower) -> colour (each device chosen independently)
let deviceOrder = [];           // canonical hex(lower) list -> stable colour index
let devicePanelBuilt = false;
let devicePanelKey = '';        // signature of the built card set (rebuild when it changes)
let collapsedCards = new Set(); // hex of device sub-cards the user collapsed (per-card)
let lastState = { tags: [] };
let runValid = true;            // false after a run finishes -> next Start re-prepares

const CELL_SIZE = 40;
const CELL_GAP = 1;
const CELL_STEP = CELL_SIZE + CELL_GAP;   // pixels per 1 metre (1 cell = 1 m)
const PALETTE = ['#00c853', '#d500f9', '#00bfa5', '#7c4dff', '#1de9b6', '#651fff', '#00e5ff', '#64dd17'];

// Spray cone geometry (spec): spread = 60° / max 1.5 m ; jet = 30° / max 3.0 m.
// Hình học cung phun — giá trị DỰ PHÒNG; sẽ được nạp đè từ backend (extinguish.SPRAY)
// qua fetchSprayConfig() khi vào trang để luôn khớp vùng dập thật.
let SPRAY = {
    spread: { halfAngle: 30, maxRadiusM: 1.5 },
    jet:    { halfAngle: 15, maxRadiusM: 3.0 },
};
const SPRAY_FILL = 'rgba(255, 138, 0, 0.22)';
const SPRAY_STROKE = 'rgba(255, 111, 0, 0.85)';

// Fire visuals: colour + size scale by level (1..5). Level 5 ≈ full cell, level 1 ≈ 1/3.
const FIRE_COLORS = { 1: '#ffd54f', 2: '#ffb300', 3: '#fb8c00', 4: '#f4511e', 5: '#d32f2f' };
let firePanelBuilt = false;
let endedHandled = false;

// --- Virtual ADMIN device (hex 0xad, controlled directly on the server screen) ---
const ADMIN_HEX = '0xad';
const ADMIN_SPEED_CELLS_PER_SEC = 2.5;   // WASD movement speed
let adminEnabled = false;
let adminState = { x: 0, y: 0, yaw_map: 0, valve_open: 0, valve_mode: 0, visible: true };
let adminControlMode = false;
let adminKeys = {};            // currently-held WASD keys
let adminRafId = null;
let adminRafLast = 0;
let adminPushTimer = null;

// ---------------------------------------------------------------- helpers
function readRunData() {
    const raw = sessionStorage.getItem('trainingRun');
    if (!raw) return null;
    try { return JSON.parse(raw); } catch (e) { return null; }
}

function formatHexId(value) {
    if (!value) return '--';
    const text = String(value).trim();
    if (text.toLowerCase().startsWith('0x')) return `0x${text.slice(2).toUpperCase()}`;
    return text.toUpperCase();
}

function normHex(value) {
    let v = String(value || '').trim().toLowerCase();
    if (v && !v.startsWith('0x')) v = `0x${v}`;
    return v;
}

// Dung tích bình nước của 1 thiết bị: ưu tiên state (đang chạy), rồi /api/devices (lúc vào
// trang). ADMIN ảo = vô hạn (-1). Trả null nếu chưa biết.
function waterCapacityForHex(hex, live) {
    if (live && live.water_capacity != null) return live.water_capacity;
    if (normHex(hex) === ADMIN_HEX) return -1;
    const dev = selectedDevices.find((d) => normHex(d.device_hex_id) === normHex(hex));
    return (dev && dev.water_capacity != null) ? dev.water_capacity : null;
}

// Hiển thị nước "còn / dung tích" (∞ nếu vô hạn). -1 (vô hạn) ở remaining/capacity => ∞.
function formatWater(hex, live) {
    const cap = waterCapacityForHex(hex, live);
    if (cap === -1) return '∞';
    const rem = (live && live.water_remaining != null && live.water_remaining >= 0)
        ? live.water_remaining : '--';
    return (cap != null) ? `${rem} / ${cap}` : `${rem}`;
}

// Colour for a device by its hex id. Each device has its own colour (default
// from the palette by its position; overridable per-device via its swatch).
function deviceColor(hex) {
    const key = normHex(hex);
    if (deviceColors[key]) return deviceColors[key];
    let idx = deviceOrder.indexOf(key);
    if (idx < 0) { idx = deviceOrder.length; deviceOrder.push(key); }
    deviceColors[key] = PALETTE[idx % PALETTE.length];
    return deviceColors[key];
}

function coordToPixel(coordX, coordY) {
    const x = Number(coordX) * CELL_STEP;
    const y = (mapData.width_y - Number(coordY)) * CELL_STEP;   // y inverted (top = max Y)
    return { x, y };
}

function clampToMap(x, y) {
    return {
        x: Math.min(Math.max(x, 0), mapData.length_x),
        y: Math.min(Math.max(y, 0), mapData.width_y),
    };
}

function createSvg(tag, attrs) {
    const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
    Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, String(v)));
    return node;
}

// SVG wedge centred at (cx,cy); heading 0° = +Oy (up). y is down on screen.
function sectorPath(cx, cy, headingDeg, halfAngleDeg, rPx) {
    const a1 = (headingDeg - halfAngleDeg) * Math.PI / 180;
    const a2 = (headingDeg + halfAngleDeg) * Math.PI / 180;
    const p1x = cx + Math.sin(a1) * rPx, p1y = cy - Math.cos(a1) * rPx;
    const p2x = cx + Math.sin(a2) * rPx, p2y = cy - Math.cos(a2) * rPx;
    const largeArc = (2 * halfAngleDeg) > 180 ? 1 : 0;
    return `M ${cx} ${cy} L ${p1x} ${p1y} A ${rPx} ${rPx} 0 ${largeArc} 1 ${p2x} ${p2y} Z`;
}

// ---------------------------------------------------------------- bootstrap
async function loadBootstrapData() {
    const [map, cells] = await Promise.all([
        API.get(`/api/maps/${runData.map_id}`),
        API.get(`/api/maps/${runData.map_id}/cells`),
    ]);
    mapData = map;
    mapCells = cells;

    // Resolve selected devices (names + hex) for the device panel — must work BEFORE Start.
    let deviceIds = (runData.device_ids || []).map(Number).filter((n) => !Number.isNaN(n));
    if (!deviceIds.length) {
        // Fallback: read device_ids straight from the backend run state (authoritative).
        try {
            const runState = await API.get(`/api/training/${runData.training_run_id}`);
            deviceIds = (runState.device_ids || []).map(Number);
            runData.device_ids = deviceIds;
        } catch (e) { /* ignore */ }
    }
    try {
        const allDevices = await API.get('/api/devices');
        const byId = new Map(allDevices.map((d) => [d.device_id, d]));
        selectedDevices = deviceIds.map((id) => byId.get(id)).filter(Boolean);
    } catch (e) {
        selectedDevices = [];
    }
}

// Algorithm 2 (UWB) has no trained model — positioning uses beacon ranges directly,
// so there is no campaign/model picker (the field is removed from the template).

// ---------------------------------------------------------------- info / timers
function setSessionInfo() {
    document.getElementById('a3-map-title').textContent =
        mapData ? `${mapData.map_name} (ID ${mapData.map_id})` : '--';
    const s = runData.session;
    document.getElementById('a3-session-title').textContent =
        s ? `${s.session_name} (ID ${s.session_id})` : 'Creative';
    document.getElementById('a3-remaining').textContent =
        (s && s.duration_seconds) ? `${s.duration_seconds}s` : '--';
}

function updateTimers() {
    document.getElementById('a3-elapsed').textContent = String(elapsedSeconds);
    const s = runData.session;
    if (s && s.duration_seconds) {
        document.getElementById('a3-remaining').textContent =
            `${Math.max(0, s.duration_seconds - elapsedSeconds)}s`;
    } else {
        document.getElementById('a3-remaining').textContent = '--';
    }
}

// ---------------------------------------------------------------- base map
function renderBaseMap() {
    const grid = document.getElementById('a3-map-grid');
    const wrap = document.getElementById('a3-map-wrap');
    const overlay = document.getElementById('a3-overlay');

    grid.style.gridTemplateColumns = `repeat(${mapData.length_x}, ${CELL_SIZE}px)`;
    grid.style.gridTemplateRows = `repeat(${mapData.width_y}, ${CELL_SIZE}px)`;
    grid.innerHTML = '';

    const sorted = [...mapCells].sort((a, b) => {
        if (b.coord_y !== a.coord_y) return b.coord_y - a.coord_y;
        return a.coord_x - b.coord_x;
    });
    sorted.forEach((cell) => {
        const div = document.createElement('div');
        div.className = `map-cell ${cell.is_passable ? 'passable' : 'blocked'}`;
        grid.appendChild(div);
    });

    const width = grid.scrollWidth;
    const height = grid.scrollHeight;
    wrap.style.width = 'fit-content';
    wrap.style.height = 'fit-content';
    overlay.setAttribute('viewBox', `0 0 ${width} ${height}`);
    overlay.setAttribute('width', String(width));
    overlay.setAttribute('height', String(height));

    const offset = Number(mapData.offset_angles || 0);
    document.getElementById('a3-compass-needle').setAttribute('transform', `rotate(${offset} 50 50)`);
    document.getElementById('a3-compass-caption').textContent = `Offset: ${offset.toFixed(2)}°`;

    renderOverlay(lastState);
}

// ---------------------------------------------------------------- overlay (dots, heading, spray, assembly)
function drawAssemblyPoint(overlay) {
    if (!assemblyPoint || !mapData) return;
    // Faint house icon centred on the cell (coord is bottom-left, centre = +0.5).
    const px = coordToPixel(assemblyPoint.x + 0.5, assemblyPoint.y + 0.5);
    const s = CELL_SIZE * 0.42;
    const g = createSvg('g', { opacity: 0.55 });
    g.appendChild(createSvg('rect', {     // body
        x: px.x - s * 0.55, y: px.y - s * 0.05, width: s * 1.1, height: s * 0.85,
        rx: 2, fill: '#42a5f5', stroke: '#0d47a1', 'stroke-width': 2,
    }));
    g.appendChild(createSvg('path', {     // roof
        d: `M ${px.x - s * 0.8} ${px.y - s * 0.05} L ${px.x} ${px.y - s} L ${px.x + s * 0.8} ${px.y - s * 0.05} Z`,
        fill: '#1976d2', stroke: '#0d47a1', 'stroke-width': 2,
    }));
    g.appendChild(createSvg('rect', {     // door
        x: px.x - s * 0.15, y: px.y + s * 0.32, width: s * 0.3, height: s * 0.48, fill: '#0d47a1',
    }));
    overlay.appendChild(g);
}

// Draw one device marker (spray cone + dot + heading sub-dot + label) at map coords.
function drawDeviceMarker(overlay, opt) {
    const clamped = clampToMap(opt.x, opt.y);
    const px = coordToPixel(clamped.x, clamped.y);
    const yaw = Number(opt.yaw || 0);
    const valveOpen = Number(opt.valveOpen || 0);
    if (valveOpen > 0 && opt.sprayMode) {
        const cfg = SPRAY[opt.sprayMode] || SPRAY.spread;
        const rPx = (valveOpen / 100) * cfg.maxRadiusM * CELL_STEP;
        if (rPx > 1) {
            overlay.appendChild(createSvg('path', {
                d: sectorPath(px.x, px.y, yaw, cfg.halfAngle, rPx),
                fill: SPRAY_FILL, stroke: SPRAY_STROKE, 'stroke-width': 1,
            }));
        }
    }
    const outerR = opt.admin ? 10 : 9;
    if (opt.admin) {  // dashed ring distinguishes the ADMIN device
        overlay.appendChild(createSvg('circle', {
            cx: px.x, cy: px.y, r: outerR + 3, fill: 'none',
            stroke: opt.color, 'stroke-width': 1.5, 'stroke-dasharray': '3 2',
        }));
    }
    overlay.appendChild(createSvg('circle', { cx: px.x, cy: px.y, r: outerR, fill: '#ffffff', stroke: '#0d0d0d', 'stroke-width': 2 }));
    overlay.appendChild(createSvg('circle', { cx: px.x, cy: px.y, r: outerR - 3, fill: opt.color, stroke: '#0d0d0d', 'stroke-width': 1 }));
    const hr = outerR + 2;
    overlay.appendChild(createSvg('circle', {
        cx: px.x + Math.sin(yaw * Math.PI / 180) * hr,
        cy: px.y - Math.cos(yaw * Math.PI / 180) * hr,
        r: 3.2, fill: '#0d0d0d', stroke: '#ffffff', 'stroke-width': 1,
    }));
    overlay.appendChild(Object.assign(createSvg('text', {
        x: px.x + 10, y: px.y - 10, fill: '#ffffff', stroke: '#0d0d0d',
        'stroke-width': 2, 'paint-order': 'stroke fill', 'font-size': 12, 'font-weight': 700,
    }), { textContent: opt.label }));
}

// Flame teardrop centred at (cx, cy), half-size s.
function flamePath(cx, cy, s) {
    return `M ${cx} ${cy - s} `
        + `C ${cx + s} ${cy - s * 0.2} ${cx + s * 0.72} ${cy + s} ${cx} ${cy + s} `
        + `C ${cx - s * 0.72} ${cy + s} ${cx - s} ${cy - s * 0.2} ${cx} ${cy - s} Z`;
}

function drawFires(overlay, fires) {
    (fires || []).forEach((f) => {
        const level = Number(f.level || 0);
        if (level <= 0) return;
        const px = coordToPixel(f.x + 0.5, f.y + 0.5);
        const scale = 0.33 + 0.67 * (Math.min(level, 5) - 1) / 4;
        const s = (CELL_SIZE / 2) * scale * 0.92;
        overlay.appendChild(createSvg('path', {
            d: flamePath(px.x, px.y, s),
            fill: FIRE_COLORS[Math.min(level, 5)] || '#fb8c00',
            'fill-opacity': 0.88, stroke: '#bf360c', 'stroke-width': 1,
        }));
    });
}

function renderOverlay(state) {
    const overlay = document.getElementById('a3-overlay');
    if (!overlay) return;
    overlay.innerHTML = '';
    drawFires(overlay, state && state.fires);
    drawAssemblyPoint(overlay);

    TrainingTrajectory.ingestState(state, adminEnabled && adminState.visible ? {
        hex: ADMIN_HEX, x: adminState.x, y: adminState.y,
    } : null);
    TrainingTrajectory.drawPaths(overlay, coordToPixel, deviceColor);

    const tags = (state && state.tags) || [];
    tags.forEach((data) => {
        if (data.is_admin) return;   // ADMIN drawn from local state below (responsive)
        const posX = Number(data.position_x);
        const posY = Number(data.position_y);
        if (!Number.isFinite(posX) || !Number.isFinite(posY)) return;
        drawDeviceMarker(overlay, {
            x: posX, y: posY, yaw: data.yaw_map, valveOpen: data.valve_open,
            sprayMode: data.spray_mode, color: deviceColor(data.tag_hex_id),
            label: formatHexId(data.tag_hex_id),
        });
    });

    // ADMIN virtual device — drawn from local control state for responsiveness.
    if (adminEnabled && adminState.visible) {
        drawDeviceMarker(overlay, {
            x: adminState.x, y: adminState.y, yaw: adminState.yaw_map,
            valveOpen: adminState.valve_open,
            sprayMode: adminState.valve_mode <= 50 ? 'spread' : 'jet',
            color: deviceColor(ADMIN_HEX), label: 'ADMIN', admin: true,
        });
    }

    renderDevicePanel(tags);
    document.getElementById('a3-updated').textContent = new Date().toLocaleTimeString();
}

// ---------------------------------------------------------------- device panel
// Built ONCE (identity + per-device colour swatch); value cells updated in place
// each poll so the native colour pickers are never clobbered mid-interaction.
function deviceList(liveTags) {
    let list;
    if (selectedDevices.length) {
        list = selectedDevices.map((d) => ({ hex: normHex(d.device_hex_id), name: d.device_name || 'Device' }));
    } else {
        list = (liveTags || []).filter((t) => !t.is_admin)
            .map((t) => ({ hex: normHex(t.tag_hex_id), name: t.device_name || 'Device' }));
    }
    if (adminEnabled) list.push({ hex: ADMIN_HEX, name: 'ADMIN', isAdmin: true });
    return list;
}

function buildDeviceCards(liveTags) {
    const container = document.getElementById('a3-devices');
    const list = deviceList(liveTags);
    if (!list.length) {
        container.innerHTML = '<p style="color: var(--text-secondary);">No device selected.</p>';
        return;  // not built yet — retry when device list is known
    }
    container.innerHTML = list.map((d) => {
        const color = deviceColor(d.hex);
        const hexLabel = formatHexId(d.hex);
        const f = (key) => `<span data-field="${key}" data-hex="${d.hex}">--</span>`;
        const adminBlock = d.isAdmin ? `
            <div class="a3-row a3-extra"><span class="a3-key">Valve (open / mode)</span>${f('valve')}</div>
            <div class="a3-ctrl-row">
                <button class="btn btn-primary btn-small a3-admin-control" data-hex="${d.hex}">CONTROL</button>
                <button class="btn btn-secondary btn-small a3-admin-visible" data-hex="${d.hex}">Disable</button>
            </div>` : '';
        const uwbRows = d.isAdmin ? '' :
            `<div class="a3-row a3-extra"><span class="a3-key">Beacons used</span>${f('beacons')}</div>
            <div class="a3-row a3-extra"><span class="a3-key">Ranges (acc / rej)</span>${f('accrej')}</div>`;
        const collapsed = collapsedCards.has(d.hex);
        return `
        <div class="a3-dev-card ${collapsed ? 'collapsed' : ''}" data-hex="${d.hex}">
            <div class="a3-dev-header">
                <input type="color" class="a3-color a3-dev-color" data-hex="${d.hex}" value="${color}" title="Device colour">
                ${escapeHtml(d.name)} <span class="a3-badge">${hexLabel}</span>
                <button class="a3-card-toggle" data-hex="${d.hex}" title="Collapse / expand">${collapsed ? '▾' : '▴'}</button>
            </div>
            <div class="a3-row"><span class="a3-key">Coordinate (x, y)</span>${f('coord')}</div>
            <div class="a3-row"><span class="a3-key">Score</span>${f('score')}</div>
            <div class="a3-row a3-extra"><span class="a3-key">Current cell</span>${f('cell')}</div>
            ${uwbRows}
            <div class="a3-row a3-extra"><span class="a3-key">Yaw (Euler${d.isAdmin ? ', map' : ', raw'})</span>${f('yaw')}</div>
            <div class="a3-row a3-extra"><span class="a3-key">Fires extinguished</span>${f('fires')}</div>
            <div class="a3-row a3-extra"><span class="a3-key">Water (left / cap)</span>${f('water')}</div>
            ${adminBlock}
        </div>`;
    }).join('');

    container.querySelectorAll('.a3-dev-color').forEach((input) => {
        input.addEventListener('input', (e) => {
            deviceColors[normHex(e.target.dataset.hex)] = e.target.value;
            renderOverlay(lastState);
        });
    });
    container.querySelectorAll('.a3-admin-control').forEach((b) =>
        b.addEventListener('click', enterAdminControl));
    container.querySelectorAll('.a3-admin-visible').forEach((b) =>
        b.addEventListener('click', toggleAdminVisible));
    container.querySelectorAll('.a3-card-toggle').forEach((b) =>
        b.addEventListener('click', toggleCardCollapse));
    devicePanelBuilt = true;
    devicePanelKey = list.map((d) => d.hex).join(',');
}

// Collapse / expand a single device sub-card (per-card, with ▴/▾ arrow).
function toggleCardCollapse(e) {
    const btn = e.currentTarget;
    const hex = normHex(btn.dataset.hex);
    const card = btn.closest('.a3-dev-card');
    if (collapsedCards.has(hex)) {
        collapsedCards.delete(hex);
        if (card) card.classList.remove('collapsed');
        btn.textContent = '▴';
    } else {
        collapsedCards.add(hex);
        if (card) card.classList.add('collapsed');
        btn.textContent = '▾';
    }
}

function setField(hex, key, value) {
    const el = document.querySelector(`#a3-devices [data-field="${key}"][data-hex="${hex}"]`);
    if (el) el.textContent = value;
}

function renderDevicePanel(liveTags) {
    // Rebuild whenever the card set changes (devices resolved late, ADMIN toggled, ...).
    const key = deviceList(liveTags).map((d) => d.hex).join(',');
    if (!devicePanelBuilt || key !== devicePanelKey) buildDeviceCards(liveTags);
    const liveByHex = new Map((liveTags || []).map((t) => [normHex(t.tag_hex_id), t]));
    deviceList(liveTags).forEach((d) => {
        const live = liveByHex.get(d.hex);
        let scoreText = '--';
        if (live && live.score != null) {
            scoreText = live.disqualified ? `${live.score} (DQ)` : String(live.score);
        }
        setField(d.hex, 'score', scoreText);
        setField(d.hex, 'cell', (live && live.cell_index != null) ? live.cell_index : '--');
        setField(d.hex, 'fires', (live && live.fires_extinguished != null) ? live.fires_extinguished : '--');
        setField(d.hex, 'water', formatWater(d.hex, live));

        if (d.isAdmin) {
            // Position/heading/valve are authoritative on the frontend (admin is controlled here).
            setField(d.hex, 'coord', `${adminState.x.toFixed(2)}, ${adminState.y.toFixed(2)}`);
            setField(d.hex, 'yaw', `${Number(adminState.yaw_map).toFixed(1)}°`);
            setField(d.hex, 'valve', `${Math.round(adminState.valve_open)} / ${adminState.valve_mode <= 50 ? 'spread' : 'jet'}`);
            return;
        }

        const coord = (live && Number.isFinite(Number(live.position_x)))
            ? `${Number(live.position_x).toFixed(2)}, ${Number(live.position_y).toFixed(2)}` : '--';
        setField(d.hex, 'coord', coord);
        setField(d.hex, 'beacons', (live && live.num_beacons != null) ? live.num_beacons : '--');
        setField(d.hex, 'accrej', (live && live.ranges_accepted != null)
            ? `${live.ranges_accepted} / ${live.ranges_rejected != null ? live.ranges_rejected : 0}` : '--');
        setField(d.hex, 'yaw', (live && live.yaw_raw != null) ? `${Number(live.yaw_raw).toFixed(1)}°` : '--');
    });
}

// ---------------------------------------------------------------- fire panel (root fires; live in Phase B)
function buildFirePanel() {
    const container = document.getElementById('a3-fires');
    const fires = runData.fires || [];
    if (!fires.length) {
        container.innerHTML = '<p style="color: var(--text-secondary);">No fires in this session (creative / tracking only).</p>';
        return;
    }
    container.innerHTML = fires.map((f, i) => {
        const rid = f.session_fire_id != null ? f.session_fire_id : i + 1;
        const fld = (k) => `<span data-fire="${k}" data-rid="${rid}">--</span>`;
        return `
        <div class="a3-fire-card" data-rid="${rid}">
            <div class="a3-fire-head">Fire #${i + 1} <span class="a3-badge">cell (${f.coord_x}, ${f.coord_y})</span></div>
            <div class="a3-row"><span class="a3-key">Appears at</span><span>${f.fire_time_seconds}s</span></div>
            <div class="a3-row"><span class="a3-key">Original intensity</span><span>${f.fire_level}</span></div>
            <div class="a3-row"><span class="a3-key">Current intensity</span>${fld('current')}</div>
            <div class="a3-row"><span class="a3-key">Spread amount / interval</span><span>${f.fire_spread} cells / ${f.fire_spread_time}s</span></div>
            <div class="a3-row"><span class="a3-key">Extinguished at</span>${fld('ext')}</div>
            <div class="a3-row"><span class="a3-key">Alive time</span>${fld('alive')}</div>
            <div class="a3-row"><span class="a3-key">Spread count</span>${fld('spread')}</div>
        </div>`;
    }).join('');
    firePanelBuilt = true;
}

function setFireField(rid, key, value) {
    const el = document.querySelector(`#a3-fires [data-fire="${key}"][data-rid="${rid}"]`);
    if (el) el.textContent = value;
}

function updateFirePanel(rootFires) {
    if (!firePanelBuilt) return;
    (rootFires || []).forEach((r) => {
        const rid = r.root_id;
        setFireField(rid, 'current', r.appeared ? r.current_level : 'waiting');
        setFireField(rid, 'ext', r.extinguished_at != null ? `${r.extinguished_at.toFixed(1)}s` : (r.appeared ? '⚠ active' : '--'));
        setFireField(rid, 'alive', r.alive_time != null ? `${r.alive_time}s` : '--');
        setFireField(rid, 'spread', r.spread_count);
    });
}

// ---------------------------------------------------------------- ADMIN virtual device
function onAdminToggle(e) {
    if (trainingStarted || countdownInProgress) { e.target.checked = adminEnabled; return; }
    adminEnabled = e.target.checked;
    if (adminEnabled) {
        adminState = {
            x: mapData ? mapData.length_x / 2 : 0,
            y: mapData ? mapData.width_y / 2 : 0,
            yaw_map: 0, valve_open: 0, valve_mode: 0, visible: true,
        };
        deviceColor(ADMIN_HEX);
    } else if (adminControlMode) {
        exitAdminControl();
    }
    devicePanelBuilt = false;
    renderDevicePanel(lastState.tags || []);
    renderOverlay(lastState);
}

function toggleAdminVisible(e) {
    adminState.visible = !adminState.visible;
    e.target.textContent = adminState.visible ? 'Disable' : 'Enable';
    renderOverlay(lastState);
}

function enterAdminControl() {
    if (!adminEnabled) return;
    adminControlMode = true;
    adminKeys = {};
    document.getElementById('a3-control-banner').classList.add('show');
    document.getElementById('a3-map-wrap').classList.add('a3-controlling');
    adminRafLast = 0;
    adminRafId = requestAnimationFrame(adminMovementTick);
}

function exitAdminControl() {
    adminControlMode = false;
    adminKeys = {};
    if (adminRafId) { cancelAnimationFrame(adminRafId); adminRafId = null; }
    const banner = document.getElementById('a3-control-banner');
    if (banner) banner.classList.remove('show');
    const wrap = document.getElementById('a3-map-wrap');
    if (wrap) wrap.classList.remove('a3-controlling');
}

function adminMovementTick(ts) {
    if (!adminControlMode) return;
    if (!adminRafLast) adminRafLast = ts;
    const dt = Math.min(0.1, (ts - adminRafLast) / 1000);
    adminRafLast = ts;
    let dx = 0, dy = 0;
    if (adminKeys.w) dy += 1;
    if (adminKeys.s) dy -= 1;
    if (adminKeys.d) dx += 1;
    if (adminKeys.a) dx -= 1;
    if ((dx || dy) && mapData) {
        const len = Math.hypot(dx, dy) || 1;
        const step = ADMIN_SPEED_CELLS_PER_SEC * dt;
        adminState.x = Math.min(Math.max(adminState.x + (dx / len) * step, 0), mapData.length_x);
        adminState.y = Math.min(Math.max(adminState.y + (dy / len) * step, 0), mapData.width_y);
    }
    renderOverlay(lastState);
    adminRafId = requestAnimationFrame(adminMovementTick);
}

function onAdminKeyDown(e) {
    if (e.key === 'Escape' && adminControlMode) { exitAdminControl(); return; }
    if (!adminControlMode) return;
    const k = e.key.toLowerCase();
    if (k === 'w' || k === 'a' || k === 's' || k === 'd') { adminKeys[k] = true; e.preventDefault(); }
}
function onAdminKeyUp(e) {
    const k = e.key.toLowerCase();
    if (adminKeys[k]) delete adminKeys[k];
}

function mapCoordsFromEvent(e) {
    const rect = document.getElementById('a3-map-wrap').getBoundingClientRect();
    return { x: (e.clientX - rect.left) / CELL_STEP, y: mapData.width_y - (e.clientY - rect.top) / CELL_STEP };
}
function onMapMouseMove(e) {
    if (!adminControlMode || !mapData) return;
    const m = mapCoordsFromEvent(e);
    const dx = m.x - adminState.x, dy = m.y - adminState.y;
    if (Math.hypot(dx, dy) > 1e-3) {
        adminState.yaw_map = (Math.atan2(dx, dy) * 180 / Math.PI + 360) % 360;  // 0° = +Oy
    }
}
function onMapWheel(e) {
    if (!adminControlMode) return;
    e.preventDefault();
    adminState.valve_open = Math.min(100, Math.max(0, adminState.valve_open + (e.deltaY < 0 ? 5 : -5)));
}
function onMapContextMenu(e) {
    if (!adminControlMode) return;
    e.preventDefault();
    adminState.valve_mode = adminState.valve_mode <= 50 ? 75 : 25;   // toggle jet / spread
}

async function pushAdminState() {
    if (!adminEnabled || !trainingStarted) return;
    try {
        await API.post(`/api/training-alg5/${runData.training_run_id}/admin`, {
            x: adminState.x, y: adminState.y, yaw_map: adminState.yaw_map,
            valve_open: adminState.valve_open, valve_mode: adminState.valve_mode,
            visible: adminState.visible,
        });
    } catch (e) { /* best effort */ }
}

// ---------------------------------------------------------------- start / stop flow
function setControlsEnabled(enabled) {
    const controls = document.getElementById('a3-controls');
    if (controls) controls.classList.toggle('a3-disabled', !enabled);
}

function getStartPayload() {
    // UWB: no model/campaign — positioning uses beacon ranges directly.
    const payload = { admin_enabled: adminEnabled };
    if (assemblyPoint) {
        payload.start_x = assemblyPoint.x + 0.5;
        payload.start_y = assemblyPoint.y + 0.5;
        payload.assembly_x = assemblyPoint.x;
        payload.assembly_y = assemblyPoint.y;
    }
    const saveHistoryEl = document.getElementById('a3-save-history');
    payload.save_history = !!(saveHistoryEl && saveHistoryEl.checked);
    return payload;
}

async function beginRealtime() {
    const payload = getStartPayload();
    TrainingTrajectory.resetSession();
    await API.post(`/api/training-alg5/${runData.training_run_id}/start`, payload);

    trainingStarted = true;
    countdownInProgress = false;
    endedHandled = false;
    setControlsEnabled(false);
    const btn = document.getElementById('a3-start-btn');
    btn.textContent = 'Stop';
    btn.className = 'btn btn-danger';
    btn.disabled = false;

    await pollState();
    pollTimer = setInterval(() => pollState().catch((e) => showToast(e.message, 'error')), 700);
    activeTimer = setInterval(() => {
        elapsedSeconds += 1;
        updateTimers();
        if (runData.session && elapsedSeconds >= runData.session.duration_seconds) {
            finishTraining(false).catch((e) => showToast(e.message, 'error'));
        }
    }, 1000);

    if (adminEnabled) {
        adminPushTimer = setInterval(() => pushAdminState(), 120);
    }
}

// A finished run is deleted server-side; re-prepare a fresh run so Start works again
// without going back to /training-select.
async function ensureRun() {
    if (runValid) return;
    const auth = AuthManager.getAuth();
    const resp = await API.post('/api/training/start', {
        username: auth.username,
        role_id: auth.role_id,
        map_id: runData.map_id,
        session_id: (runData.session && runData.session.session_id) || null,
        device_ids: runData.device_ids,
        algorithm: runData.algorithm || 5,
    });
    const data = resp.data || {};
    runData.training_run_id = data.training_run_id;
    runData.session = data.session;
    runData.fires = data.fires || [];
    sessionStorage.setItem('trainingRun', JSON.stringify(runData));
    firePanelBuilt = false;
    buildFirePanel();
    endedHandled = false;
    runValid = true;
}

async function startFlow() {
    if (trainingStarted) { finishTraining(true).catch((e) => showToast(e.message, 'error')); return; }
    if (countdownInProgress) return;

    try { getStartPayload(); } catch (e) { showToast(e.message, 'error'); return; }
    try { await ensureRun(); } catch (e) { showToast(`Cannot prepare run: ${e.message}`, 'error'); return; }

    countdownInProgress = true;
    elapsedSeconds = 0;
    updateTimers();
    const btn = document.getElementById('a3-start-btn');
    btn.disabled = true;

    let countdown = 3;
    document.getElementById('countdown-number').textContent = String(countdown);
    ModalManager.show('countdown-modal');
    countdownTimer = setInterval(() => {
        countdown -= 1;
        document.getElementById('countdown-number').textContent = String(Math.max(0, countdown));
        if (countdown <= 0) {
            clearInterval(countdownTimer);
            countdownTimer = null;
            ModalManager.hide('countdown-modal');
            beginRealtime().catch((error) => {
                countdownInProgress = false;
                btn.disabled = false;
                btn.textContent = 'Start';
                btn.className = 'btn btn-success';
                setControlsEnabled(true);
                showToast(error.message, 'error');
            });
        }
    }, 1000);
}

async function finishTraining(manual = false) {
    [countdownTimer, activeTimer, pollTimer, adminPushTimer].forEach((t) => { if (t) clearInterval(t); });
    countdownTimer = activeTimer = pollTimer = adminPushTimer = null;
    exitAdminControl();

    if (trainingStarted || countdownInProgress) {
        await API.post('/api/training/finish', { training_run_id: runData.training_run_id, score: 0 });
        runValid = false;   // run deleted server-side -> next Start re-prepares
    }

    trainingStarted = false;
    countdownInProgress = false;
    elapsedSeconds = 0;
    const btn = document.getElementById('a3-start-btn');
    btn.textContent = 'Start';
    btn.className = 'btn btn-success';
    btn.disabled = false;
    setControlsEnabled(true);
    updateTimers();
    lastState = { tags: [] };
    renderOverlay(lastState);
    renderFinishModal(null);
    ModalManager.show('finish-modal');
}

async function pollState() {
    try {
        const state = await API.get(`/api/training-alg5/${runData.training_run_id}/state`);
        lastState = state;
        renderOverlay(state);
        updateFirePanel(state.root_fires);
        if (state.ended && !endedHandled) {
            endedHandled = true;
            await handleEnded(state);
        }
    } catch (error) {
        showToast(error.message, 'error');
        if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
    }
}

function renderFinishModal(outcome) {
    const titleEl = document.getElementById('a3-finish-title');
    const bodyEl = document.getElementById('a3-finish-body');
    const REASONS = {
        cleared_success: 'All fires cleared — exercise complete.',
        timeout_success: 'Time up — all fires were cleared.',
        timeout_fail: 'Time up with fires remaining — all scores set to 0.',
    };
    if (titleEl) titleEl.textContent = 'Training finished';
    if (!bodyEl) return;
    if (!outcome) { bodyEl.innerHTML = ''; return; }
    const scores = outcome.final_scores || {};
    const rows = Object.entries(scores).map(([hex, sc]) =>
        `<div class="a3-row"><span class="a3-key">${formatHexId(hex)}</span><span>${sc}</span></div>`).join('');
    bodyEl.innerHTML = `<p style="margin-bottom:8px;">${REASONS[outcome.reason] || outcome.reason}</p>${rows}`;
}

// Natural end (server-side simulation ended). Sim already saved history; here we
// just stop the loop, show the result, and clean up the run on the server.
async function handleEnded(state) {
    [activeTimer, pollTimer, adminPushTimer].forEach((t) => { if (t) clearInterval(t); });
    activeTimer = pollTimer = adminPushTimer = null;
    exitAdminControl();
    trainingStarted = false;
    const btn = document.getElementById('a3-start-btn');
    btn.textContent = 'Start';
    btn.className = 'btn btn-success';
    btn.disabled = false;
    setControlsEnabled(true);
    renderFinishModal(state.outcome);
    ModalManager.show('finish-modal');
    try {
        await API.post('/api/training/finish', { training_run_id: runData.training_run_id, score: 0 });
    } catch (e) { /* cleanup best-effort */ }
    runValid = false;   // run deleted server-side -> next Start re-prepares
}

async function sendMapInfo() {
    const btn = document.getElementById('a3-send-map-btn');
    if (btn) btn.disabled = true;
    try {
        const result = await API.post(`/api/maps/${runData.map_id}/send-map-mqtt`, {});
        showToast(`Map info sent (${result.cells_count} cells)`, 'success');
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        if (!trainingStarted && !countdownInProgress && btn) btn.disabled = false;
    }
}

function applyAssemblyPoint() {
    const xv = document.getElementById('a3-assembly-x').value;
    const yv = document.getElementById('a3-assembly-y').value;
    if (xv === '' || yv === '') { showToast('Enter both x and y for the assembly point', 'error'); return; }
    const x = parseInt(xv, 10);
    const y = parseInt(yv, 10);
    if (x < 0 || x >= mapData.length_x || y < 0 || y >= mapData.width_y) {
        showToast(`Assembly point out of map bounds (0..${mapData.length_x - 1}, 0..${mapData.width_y - 1})`, 'error');
        return;
    }
    assemblyPoint = { x, y };
    renderOverlay(lastState);
    showToast(`Assembly point set to (${x}, ${y})`, 'success');
}

// ---------------------------------------------------------------- init
document.addEventListener('DOMContentLoaded', async () => {
    runData = readRunData();
    if (!runData || !runData.training_run_id || !runData.map_id) {
        showToast('No training run data found', 'error');
        window.location.href = '/training-select';
        return;
    }

    try {
        await loadBootstrapData();
        const sc = await fetchSprayConfig();   // nạp hình học cung phun từ backend
        if (sc) SPRAY = sc;
        setSessionInfo();
        updateTimers();
        renderBaseMap();
        renderDevicePanel([]);
        buildFirePanel();
        TrainingTrajectory.init(() => renderOverlay(lastState));

        document.getElementById('a3-start-btn').addEventListener('click', startFlow);
        document.getElementById('a3-send-map-btn').addEventListener('click', sendMapInfo);
        document.getElementById('a3-assembly-apply').addEventListener('click', applyAssemblyPoint);
        document.getElementById('finish-modal-ok').addEventListener('click', () => ModalManager.hide('finish-modal'));

        // Virtual ADMIN device: toggle + control-mode input handlers.
        document.getElementById('a3-admin-enable').addEventListener('change', onAdminToggle);
        document.addEventListener('keydown', onAdminKeyDown);
        document.addEventListener('keyup', onAdminKeyUp);
        const mapWrap = document.getElementById('a3-map-wrap');
        mapWrap.addEventListener('mousemove', onMapMouseMove);
        mapWrap.addEventListener('wheel', onMapWheel, { passive: false });
        mapWrap.addEventListener('contextmenu', onMapContextMenu);
    } catch (error) {
        showToast(error.message, 'error');
    }
});
