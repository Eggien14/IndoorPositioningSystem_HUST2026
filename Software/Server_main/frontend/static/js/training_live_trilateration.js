let runData = null;
let mapData = null;
let mapCells = [];
let mapBeacons = [];
let pollTimer = null;
let activeTimer = null;
let countdownTimer = null;
let trainingStarted = false;
let countdownInProgress = false;
let elapsedSeconds = 0;

const CELL_SIZE = 40;
const CELL_GAP = 1;
const CELL_STEP = CELL_SIZE + CELL_GAP;
const DEVICE_COLOR_CACHE = {};
const TAG_COLOR_LIST = [
    '#00c853',
    '#d500f9',
    '#00bfa5',
    '#7c4dff',
    '#1de9b6',
    '#651fff',
    '#00e5ff',
    '#64dd17',
];
const FOV_FILL = 'rgba(100, 181, 246, 0.20)';
const FOV_STROKE = 'rgba(100, 181, 246, 0.85)';

function hashString(value) {
    let hash = 0;
    for (let index = 0; index < value.length; index += 1) {
        hash = (hash * 31 + value.charCodeAt(index)) >>> 0;
    }
    return hash;
}

function getDeviceColor(deviceId) {
    if (!DEVICE_COLOR_CACHE[deviceId]) {
        const colorIndex = hashString(String(deviceId)) % TAG_COLOR_LIST.length;
        DEVICE_COLOR_CACHE[deviceId] = TAG_COLOR_LIST[colorIndex];
    }
    return DEVICE_COLOR_CACHE[deviceId];
}

function formatHexId(value) {
    if (!value) {
        return '--';
    }
    const text = String(value).trim();
    if (text.toLowerCase().startsWith('0x')) {
        return `0x${text.slice(2).toUpperCase()}`;
    }
    return text.toUpperCase();
}

function readRunData() {
    const raw = sessionStorage.getItem('trainingRun');
    if (!raw) {
        return null;
    }
    try {
        return JSON.parse(raw);
    } catch (error) {
        return null;
    }
}

function coordToPixel(coordX, coordY) {
    const x = Number(coordX) * CELL_STEP;
    const y = (mapData.width_y - Number(coordY)) * CELL_STEP;
    return { x, y };
}

function clampToMap(x, y) {
    return {
        x: Math.min(Math.max(x, 0), mapData.length_x),
        y: Math.min(Math.max(y, 0), mapData.width_y),
    };
}

function createSvgElement(tag, attrs) {
    const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
    Object.entries(attrs).forEach(([key, value]) => {
        node.setAttribute(key, String(value));
    });
    return node;
}

async function loadBootstrapData() {
    const [map, cells, beacons] = await Promise.all([
        API.get(`/api/maps/${runData.map_id}`),
        API.get(`/api/maps/${runData.map_id}/cells`),
        API.get(`/api/maps/${runData.map_id}/beacons`),
    ]);
    mapData = map;
    mapCells = cells;
    mapBeacons = beacons;
}

function setSessionInfo() {
    const sessionLabel = runData.session ? `${runData.session.session_name} (ID: ${runData.session.session_id})` : 'Creative';
    document.getElementById('live-session-name').textContent = sessionLabel;

    if (runData.session && runData.session.duration_seconds) {
        document.getElementById('live-remaining').textContent = `${runData.session.duration_seconds}s`;
    } else {
        document.getElementById('live-remaining').textContent = '--';
    }
}

function updateTimersDisplay() {
    document.getElementById('live-elapsed').textContent = String(elapsedSeconds);

    if (runData.session && runData.session.duration_seconds) {
        const remaining = Math.max(0, runData.session.duration_seconds - elapsedSeconds);
        document.getElementById('live-remaining').textContent = `${remaining}s`;
    } else {
        document.getElementById('live-remaining').textContent = '--';
    }
}

function renderBaseMap() {
    const grid = document.getElementById('lm-map-grid');
    const wrap = document.getElementById('lm-map-wrap');
    const overlay = document.getElementById('lm-overlay');

    grid.style.gridTemplateColumns = `repeat(${mapData.length_x}, ${CELL_SIZE}px)`;
    grid.style.gridTemplateRows = `repeat(${mapData.width_y}, ${CELL_SIZE}px)`;
    grid.innerHTML = '';

    const sorted = [...mapCells].sort((a, b) => {
        if (b.coord_y !== a.coord_y) {
            return b.coord_y - a.coord_y;
        }
        return a.coord_x - b.coord_x;
    });

    sorted.forEach((cell) => {
        const cellDiv = document.createElement('div');
        cellDiv.className = `map-cell ${cell.is_passable ? 'passable' : 'blocked'}`;
        grid.appendChild(cellDiv);
    });

    const width = grid.scrollWidth;
    const height = grid.scrollHeight;
    wrap.style.width = 'fit-content';
    wrap.style.height = 'fit-content';

    overlay.setAttribute('viewBox', `0 0 ${width} ${height}`);
    overlay.setAttribute('width', String(width));
    overlay.setAttribute('height', String(height));

    document.getElementById('lm-map-title').textContent = `${mapData.map_name} (ID ${mapData.map_id})`;
    document.getElementById('lm-offset').textContent = Number(mapData.offset_angles || 0).toFixed(2);
    renderCompass();
    renderOverlay({ tags: [] });
}

function renderCompass() {
    const offset = Number(mapData.offset_angles || 0);
    const needle = document.getElementById('lm-compass-needle');
    const caption = document.getElementById('lm-compass-caption');

    if (needle) {
        needle.setAttribute('transform', `rotate(${offset} 50 50)`);
    }
    if (caption) {
        caption.textContent = `Map north offset: ${offset.toFixed(2)}°`;
    }
}

function renderOverlay(runtimeState) {
    const overlay = document.getElementById('lm-overlay');
    overlay.innerHTML = '';

    const tags = runtimeState.tags || [];
    const diagnosticsRows = [];
    const deviceLegendItems = [];

    tags.forEach((data) => {
        const deviceId = data.tag_hex_id;
        const displayTagHex = formatHexId(deviceId);
        const hasPosition = Number.isFinite(Number(data.position_x)) && Number.isFinite(Number(data.position_y));
        const valveOpen = Number(data.valve_open || 0) === 1;
        const color = getDeviceColor(deviceId);

        deviceLegendItems.push(`<span class="lm-device-chip"><span class="lm-device-dot" style="background: ${color}; border: 1px solid #111; box-shadow: 0 0 0 2px #fff;"></span>${displayTagHex}</span>`);

        if (!hasPosition) {
            diagnosticsRows.push(`<tr><td><span class="lm-device-dot" style="background: ${color}; margin-right: 6px; border: 1px solid #111; box-shadow: 0 0 0 2px #fff;"></span>${displayTagHex}</td><td>-</td><td>-</td><td>${Number(data.yaw_raw || 0).toFixed(1)}</td><td>${valveOpen ? 'ON' : 'OFF'}</td></tr>`);
            return;
        }

        const clamped = clampToMap(Number(data.position_x), Number(data.position_y));
        const px = coordToPixel(clamped.x, clamped.y);

        const yaw = Number(data.yaw_map || 0);
        const left = yaw - 30;
        const right = yaw + 30;
        const fovRange = CELL_STEP;

        const leftX = px.x + Math.sin((left * Math.PI) / 180) * fovRange;
        const leftY = px.y - Math.cos((left * Math.PI) / 180) * fovRange;
        const rightX = px.x + Math.sin((right * Math.PI) / 180) * fovRange;
        const rightY = px.y - Math.cos((right * Math.PI) / 180) * fovRange;

        overlay.appendChild(createSvgElement('path', {
            d: `M ${px.x} ${px.y} L ${leftX} ${leftY} L ${rightX} ${rightY} Z`,
            fill: FOV_FILL,
            stroke: FOV_STROKE,
            'stroke-width': 1,
        }));

        overlay.appendChild(createSvgElement('circle', {
            cx: px.x,
            cy: px.y,
            r: 8,
            fill: '#ffffff',
            stroke: '#0d0d0d',
            'stroke-width': 2,
        }));

        overlay.appendChild(createSvgElement('circle', {
            cx: px.x,
            cy: px.y,
            r: 5,
            fill: color,
            stroke: '#0d0d0d',
            'stroke-width': 1,
        }));

        overlay.appendChild(createSvgElement('text', {
            x: px.x + 8,
            y: px.y - 8,
            fill: '#ffffff',
            stroke: '#0d0d0d',
            'stroke-width': 2,
            'paint-order': 'stroke fill',
            'font-size': 12,
            'font-weight': 700,
        })).textContent = `${displayTagHex}`;

        diagnosticsRows.push(
            `<tr><td><span class="lm-device-dot" style="background: ${color}; margin-right: 6px; border: 1px solid #111; box-shadow: 0 0 0 2px #fff;"></span>${displayTagHex}</td><td>${clamped.x.toFixed(2)}, ${clamped.y.toFixed(2)}</td><td>${Number(data.yaw_map || 0).toFixed(1)}</td><td>${Number(data.yaw_raw || 0).toFixed(1)}</td><td>${valveOpen ? 'ON' : 'OFF'}</td></tr>`
        );
    });

    const diagnostics = document.getElementById('lm-diagnostics');
    if (!diagnosticsRows.length) {
        diagnostics.innerHTML = '<p style="color: var(--text-secondary);">No realtime data yet.</p>';
    } else {
        diagnostics.innerHTML = `
            <div class="lm-device-legend">${deviceLegendItems.join('')}</div>
            <div class="lm-tag-grid">${tags.map((tag) => {
                const dotColor = getDeviceColor(tag.tag_hex_id);
                const displayTagHex = formatHexId(tag.tag_hex_id);
                const rawPosX = Number(tag.position_x);
                const rawPosY = Number(tag.position_y);
                const clampedPos = (Number.isFinite(rawPosX) && Number.isFinite(rawPosY)) ? clampToMap(rawPosX, rawPosY) : null;
                const posX = clampedPos ? clampedPos.x.toFixed(2) : '--';
                const posY = clampedPos ? clampedPos.y.toFixed(2) : '--';
                const yawMap = tag.yaw_map != null ? Number(tag.yaw_map).toFixed(1) : '--';
                const yawRaw = tag.yaw_raw != null ? Number(tag.yaw_raw).toFixed(1) : '--';
                const valve = Number(tag.valve_open || 0) === 1 ? 'ON' : 'OFF';
                const speedProxy = tag.gyro_magnitude != null ? Number(tag.gyro_magnitude).toFixed(2) : '--';
                const accMag = tag.acc_magnitude != null ? Number(tag.acc_magnitude).toFixed(2) : '--';
                const deviceName = tag.device_name || 'Unknown device';
                const deviceId = tag.device_id != null ? String(tag.device_id) : '--';
                return `
                    <div class="lm-tag-card">
                        <div class="lm-tag-header"><span class="lm-device-dot" style="background: ${dotColor}; border: 1px solid #111; box-shadow: 0 0 0 2px #fff;"></span>${displayTagHex}</div>
                        <div class="lm-tag-row"><span class="lm-tag-key">Device Name</span><span>${deviceName}</span></div>
                        <div class="lm-tag-row"><span class="lm-tag-key">Device ID</span><span>${deviceId}</span></div>
                        <div class="lm-tag-row"><span class="lm-tag-key">Hex ID</span><span>${displayTagHex}</span></div>
                        <div class="lm-tag-row"><span class="lm-tag-key">Coordinate</span><span>${posX}, ${posY}</span></div>
                        <div class="lm-tag-row"><span class="lm-tag-key">Yaw Map</span><span>${yawMap}°</span></div>
                        <div class="lm-tag-row"><span class="lm-tag-key">Yaw Raw</span><span>${yawRaw}°</span></div>
                        <div class="lm-tag-row"><span class="lm-tag-key">Valve</span><span>${valve}</span></div>
                        <div class="lm-tag-row"><span class="lm-tag-key">Speed (proxy)</span><span>${speedProxy}</span></div>
                        <div class="lm-tag-row"><span class="lm-tag-key">Acc Magnitude</span><span>${accMag}</span></div>
                    </div>
                `;
            }).join('')}</div>
            <table class="lm-table">
                <thead>
                    <tr><th>Device</th><th>Position</th><th>Yaw Map</th><th>Yaw Raw</th><th>Valve</th></tr>
                </thead>
                <tbody>${diagnosticsRows.join('')}</tbody>
            </table>
        `;
    }

    document.getElementById('lm-updated').textContent = new Date().toLocaleTimeString();
}

function showFinishPopup() {
    ModalManager.show('finish-modal');
}

async function finishTraining(manual = false) {
    if (countdownTimer) {
        clearInterval(countdownTimer);
        countdownTimer = null;
    }
    if (activeTimer) {
        clearInterval(activeTimer);
        activeTimer = null;
    }
    if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
    }

    if (trainingStarted || countdownInProgress) {
        await API.post('/api/training/finish', {
            training_run_id: runData.training_run_id,
            score: 0,
        });
    }

    trainingStarted = false;
    countdownInProgress = false;
    elapsedSeconds = 0;
    document.getElementById('live-start-btn').textContent = i18n.translate('start');
    document.getElementById('live-start-btn').className = 'btn btn-success';
    document.getElementById('live-start-btn').disabled = false;
    document.getElementById('send-map-btn').disabled = false;

    updateTimersDisplay();
    renderOverlay({ tags: [] });
    showFinishPopup();

    if (!manual) {
        return;
    }
}

async function beginRealtimeTraining() {
    await API.post(`/api/training/${runData.training_run_id}/start`);

    trainingStarted = true;
    countdownInProgress = false;
    document.getElementById('live-start-btn').textContent = i18n.translate('finish');
    document.getElementById('live-start-btn').className = 'btn btn-danger';
    document.getElementById('live-start-btn').disabled = false;

    await pollRuntimeState();
    pollTimer = setInterval(() => {
        pollRuntimeState().catch((error) => {
            showToast(error.message, 'error');
        });
    }, 700);

    activeTimer = setInterval(() => {
        elapsedSeconds += 1;
        updateTimersDisplay();

        if (runData.session && elapsedSeconds >= runData.session.duration_seconds) {
            finishTraining(false).catch((error) => showToast(error.message, 'error'));
        }
    }, 1000);
}

function startTrainingFlow() {
    if (trainingStarted) {
        finishTraining(true).catch((error) => showToast(error.message, 'error'));
        return;
    }

    if (countdownInProgress) {
        return;
    }

    countdownInProgress = true;
    elapsedSeconds = 0;
    updateTimersDisplay();
    document.getElementById('live-start-btn').disabled = true;
    document.getElementById('send-map-btn').disabled = true;

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

            beginRealtimeTraining().catch((error) => {
                countdownInProgress = false;
                document.getElementById('live-start-btn').disabled = false;
                document.getElementById('live-start-btn').textContent = i18n.translate('start');
                document.getElementById('live-start-btn').className = 'btn btn-success';
                document.getElementById('send-map-btn').disabled = false;
                showToast(error.message, 'error');
            });
        }
    }, 1000);
}

async function sendMapInfo() {
    const btn = document.getElementById('send-map-btn');
    if (btn) btn.disabled = true;
    try {
        const result = await API.post(`/api/maps/${runData.map_id}/send-map-mqtt`, {});
        showToast(`Map info sent (${result.cells_count} cells)`, 'success');
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        if (!trainingStarted && !countdownInProgress) {
            if (btn) btn.disabled = false;
        }
    }
}

async function pollRuntimeState() {
    try {
        const state = await API.get(`/api/training-lm/${runData.training_run_id}/state`);
        renderOverlay(state);
    } catch (error) {
        showToast(error.message, 'error');
        clearInterval(pollTimer);
        pollTimer = null;
    }
}

document.addEventListener('DOMContentLoaded', async () => {
    runData = readRunData();
    if (!runData || !runData.training_run_id || !runData.map_id) {
        showToast('No training run data found', 'error');
        window.location.href = '/training-select';
        return;
    }

    try {
        await loadBootstrapData();
        setSessionInfo();
        updateTimersDisplay();
        renderBaseMap();

        const startButton = document.getElementById('live-start-btn');
        if (startButton) {
            startButton.addEventListener('click', startTrainingFlow);
        }

        const sendMapButton = document.getElementById('send-map-btn');
        if (sendMapButton) {
            sendMapButton.addEventListener('click', sendMapInfo);
        }

        const finishButton = document.getElementById('finish-modal-ok');
        if (finishButton) {
            finishButton.addEventListener('click', () => {
                ModalManager.hide('finish-modal');
            });
        }
    } catch (error) {
        showToast(error.message, 'error');
    }
});
