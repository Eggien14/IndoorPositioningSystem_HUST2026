let appConfig = null;
let runtimeState = null;
let pollTimer = null;
let predictionWindow = [];  // Window cho Simple Moving Average (SMA)
const MA_WINDOW_SIZE = 3;   // Lấy trung bình 3 điểm gần nhất

const SVG_NS = 'http://www.w3.org/2000/svg';
const CELL_PX = 72;
const GRID_LEFT = 78;
const GRID_TOP = 120;
const AXIS_OFFSET = 28;

function applyMovingAverage(predictions) {
    /**
     * Áp dụng Simple Moving Average lên predictions để làm mượt tọa độ.
     * Trả về mảng predictions với giá trị x, y đã lọc (except điểm cuối).
     */
    if (predictions.length <= MA_WINDOW_SIZE) {
        return predictions;
    }

    const smoothed = predictions.map((point, idx) => {
        if (idx < MA_WINDOW_SIZE - 1) {
            // Các điểm đầu tiên không đủ window, giữ nguyên
            return point;
        }
        // Lấy MA_WINDOW_SIZE điểm gần nhất
        const window = predictions.slice(idx - MA_WINDOW_SIZE + 1, idx + 1);
        const avgX = window.reduce((sum, p) => sum + p.x, 0) / MA_WINDOW_SIZE;
        const avgY = window.reduce((sum, p) => sum + p.y, 0) / MA_WINDOW_SIZE;
        return { ...point, x: avgX, y: avgY };
    });

    return smoothed;
}

function svgEl(tag, attrs = {}) {
    const node = document.createElementNS(SVG_NS, tag);
    Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, String(value)));
    return node;
}

function coordToSvg(x, y) {
    return {
        x: GRID_LEFT + Number(x) * CELL_PX,
        y: GRID_TOP + (appConfig.max_oy - Number(y)) * CELL_PX,
    };
}

function indexToCenter(index) {
    const zero = Number(index) - 1;
    const col = zero % appConfig.max_ox;
    const row = Math.floor(zero / appConfig.max_ox);
    return coordToSvg(col + 0.5, row + 0.5);
}

function drawMidArrow(svg, start, end) {
    const dx = end.x - start.x;
    const dy = end.y - start.y;
    const distance = Math.hypot(dx, dy);
    if (distance < 1) return;

    svg.appendChild(svgEl('line', {
        x1: start.x,
        y1: start.y,
        x2: end.x,
        y2: end.y,
        class: 'default-route',
    }));

    const ux = dx / distance;
    const uy = dy / distance;
    const midX = (start.x + end.x) / 2;
    const midY = (start.y + end.y) / 2;
    const arrowLength = 12;
    const arrowWidth = 6;
    const baseX = midX - ux * arrowLength;
    const baseY = midY - uy * arrowLength;
    const px = -uy;
    const py = ux;

    const points = [
        `${midX},${midY}`,
        `${baseX + px * arrowWidth},${baseY + py * arrowWidth}`,
        `${baseX - px * arrowWidth},${baseY - py * arrowWidth}`,
    ].join(' ');
    svg.appendChild(svgEl('polygon', { points, class: 'route-arrow' }));
}

function drawAxes(svg) {
    const gridWidth = appConfig.max_ox * CELL_PX;
    const gridHeight = appConfig.max_oy * CELL_PX;
    const xAxisY = GRID_TOP + gridHeight + AXIS_OFFSET;
    const yAxisX = GRID_LEFT - AXIS_OFFSET;

    svg.appendChild(svgEl('line', {
        x1: GRID_LEFT,
        y1: xAxisY,
        x2: GRID_LEFT + gridWidth + 18,
        y2: xAxisY,
        class: 'axis',
    }));
    svg.appendChild(svgEl('line', {
        x1: yAxisX,
        y1: GRID_TOP + gridHeight,
        x2: yAxisX,
        y2: GRID_TOP - 18,
        class: 'axis',
    }));

    svg.appendChild(svgEl('polygon', {
        points: `${GRID_LEFT + gridWidth + 18},${xAxisY} ${GRID_LEFT + gridWidth + 6},${xAxisY - 5} ${GRID_LEFT + gridWidth + 6},${xAxisY + 5}`,
        fill: '#1d2939',
    }));
    svg.appendChild(svgEl('polygon', {
        points: `${yAxisX},${GRID_TOP - 18} ${yAxisX - 5},${GRID_TOP - 6} ${yAxisX + 5},${GRID_TOP - 6}`,
        fill: '#1d2939',
    }));

    for (let x = 0; x <= appConfig.max_ox; x += 1) {
        const p = coordToSvg(x, 0);
        svg.appendChild(svgEl('line', { x1: p.x, y1: xAxisY - 4, x2: p.x, y2: xAxisY + 4, class: 'axis' }));
        const label = svgEl('text', { x: p.x, y: xAxisY + 20, class: 'tick-label', 'text-anchor': 'middle' });
        label.textContent = String(x);
        svg.appendChild(label);
    }

    for (let y = 0; y <= appConfig.max_oy; y += 1) {
        const p = coordToSvg(0, y);
        svg.appendChild(svgEl('line', { x1: yAxisX - 4, y1: p.y, x2: yAxisX + 4, y2: p.y, class: 'axis' }));
        const label = svgEl('text', { x: yAxisX - 12, y: p.y + 4, class: 'tick-label', 'text-anchor': 'end' });
        label.textContent = String(y);
        svg.appendChild(label);
    }

    const ox = svgEl('text', { x: GRID_LEFT + gridWidth + 28, y: xAxisY + 4, class: 'axis-label' });
    ox.textContent = 'Ox';
    svg.appendChild(ox);
    const oy = svgEl('text', { x: yAxisX - 8, y: GRID_TOP - 28, class: 'axis-label', 'text-anchor': 'middle' });
    oy.textContent = 'Oy';
    svg.appendChild(oy);
}

function drawGrid(svg) {
    const blocked = new Set(appConfig.blocked_cells.map(Number));
    for (let index = 1; index <= appConfig.max_ox * appConfig.max_oy; index += 1) {
        const zero = index - 1;
        const col = zero % appConfig.max_ox;
        const row = Math.floor(zero / appConfig.max_ox);
        const x = GRID_LEFT + col * CELL_PX;
        const y = GRID_TOP + (appConfig.max_oy - row - 1) * CELL_PX;
        const rect = svgEl('rect', {
            x,
            y,
            width: CELL_PX,
            height: CELL_PX,
            class: `cell ${blocked.has(index) ? 'blocked' : 'passable'}`,
        });
        svg.appendChild(rect);

        const label = svgEl('text', {
            x: x + CELL_PX / 2,
            y: y + CELL_PX / 2,
            class: 'cell-index',
        });
        label.textContent = String(index);
        svg.appendChild(label);
    }
}

function drawDefaultTrajectory(svg) {
    const centers = appConfig.trajectory_cells.map(indexToCenter);
    for (let i = 0; i < centers.length - 1; i += 1) {
        drawMidArrow(svg, centers[i], centers[i + 1]);
    }
    if (centers.length) {
        svg.appendChild(svgEl('circle', {
            cx: centers[0].x,
            cy: centers[0].y,
            r: 8,
            class: 'start-dot',
        }));
    }
}

function drawPredictions(svg) {
    const mode = document.getElementById('view-mode').value;
    const predictions = runtimeState?.predictions || [];
    const latest = runtimeState?.latest_prediction;
    const visible = mode === 'live' ? (latest ? [latest] : []) : predictions;

    // Áp dụng Simple Moving Average để làm mượt tọa độ trong chế độ path
    const smoothed = mode === 'path' ? applyMovingAverage(visible) : visible;

    if (mode === 'path' && smoothed.length >= 2) {
        const points = smoothed.map(point => {
            const p = coordToSvg(point.x, point.y);
            return `${p.x},${p.y}`;
        }).join(' ');
        svg.appendChild(svgEl('polyline', { points, class: 'prediction-path' }));
    }

    // Vẽ điểm dự đoán (sử dụng giá trị đã lọc nếu là path mode)
    const pointsToRender = mode === 'path' ? smoothed : visible;
    pointsToRender.forEach((point) => {
        const p = coordToSvg(point.x, point.y);
        svg.appendChild(svgEl('circle', {
            cx: p.x,
            cy: p.y,
            r: mode === 'live' ? 7 : 3.6,
            class: 'prediction-dot',
        }));
    });
}

function renderMap() {
    if (!appConfig) return;
    const svg = document.getElementById('map-svg');
    const width = GRID_LEFT + appConfig.max_ox * CELL_PX + 92;
    const height = GRID_TOP + appConfig.max_oy * CELL_PX + 82;
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    svg.setAttribute('width', String(width));
    svg.setAttribute('height', String(height));
    svg.innerHTML = '';

    drawGrid(svg);
    drawAxes(svg);
    drawDefaultTrajectory(svg);
    drawPredictions(svg);
}

async function api(path, options = {}) {
    const response = await fetch(path, {
        headers: { 'Content-Type': 'application/json' },
        ...options,
    });
    if (!response.ok) {
        throw new Error(await response.text());
    }
    return response.json();
}

function updateStatus() {
    const state = runtimeState || {};
    document.getElementById('status-text').textContent = state.message || state.status || 'idle';
    document.getElementById('rows-text').textContent = `${state.processed_rows || 0}/${state.total_rows || 0}`;
    document.getElementById('skipped-text').textContent = String(state.skipped_rows || 0);
    document.getElementById('predictions-text').textContent = String(state.prediction_count || 0);

    if (state.latest_prediction) {
        document.getElementById('latest-text').textContent = `${state.latest_prediction.x.toFixed(3)}, ${state.latest_prediction.y.toFixed(3)}`;
    } else {
        document.getElementById('latest-text').textContent = '--';
    }

    document.getElementById('start-btn').disabled = Boolean(state.running);
}

async function pollState() {
    runtimeState = await api('/api/state');
    updateStatus();
    renderMap();
    if (!runtimeState.running && pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
    }
}

async function startStream() {
    runtimeState = await api('/api/start', { method: 'POST' });
    updateStatus();
    renderMap();
    if (!pollTimer) {
        pollTimer = setInterval(() => pollState().catch(console.error), 180);
    }
}

async function resetStream() {
    runtimeState = await api('/api/reset', { method: 'POST' });
    if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
    }
    updateStatus();
    renderMap();
}

async function init() {
    appConfig = await api('/api/config');
    runtimeState = await api('/api/state');
    document.getElementById('page-title').textContent = `${appConfig.map_name} - ${appConfig.trajectory_name}`;
    document.getElementById('trajectory-order').textContent = `Default trajectory index order: ${appConfig.trajectory_cells.join(' -> ')}`;
    document.getElementById('rate-text').textContent = `${appConfig.message_rate_hz.toFixed(3)} msg/s`;

    document.getElementById('start-btn').addEventListener('click', () => startStream().catch(error => alert(error.message)));
    document.getElementById('reset-btn').addEventListener('click', () => resetStream().catch(error => alert(error.message)));
    document.getElementById('view-mode').addEventListener('change', renderMap);

    updateStatus();
    renderMap();
}

init().catch(error => {
    document.body.innerHTML = `<pre style="padding: 24px; color: #b42318;">${error.message}</pre>`;
});
