let appConfig = null;
let runtimeState = null;
let pollTimer = null;

const SVG_NS = 'http://www.w3.org/2000/svg';
const CELL_PX = 72;
const GRID_LEFT = 78;
const GRID_TOP = 120;
const AXIS_OFFSET = 28;

function svgEl(tag, attrs = {}) {
    const node = document.createElementNS(SVG_NS, tag);
    Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, String(v)));
    return node;
}

function coordToSvg(x, y) {
    return { x: GRID_LEFT + Number(x) * CELL_PX, y: GRID_TOP + (appConfig.max_oy - Number(y)) * CELL_PX };
}

function indexToCenter(index) {
    const z = Number(index) - 1;
    return coordToSvg(z % appConfig.max_ox + 0.5, Math.floor(z / appConfig.max_ox) + 0.5);
}

function drawMidArrow(svg, start, end) {
    const dx = end.x - start.x, dy = end.y - start.y;
    const d = Math.hypot(dx, dy);
    if (d < 1) return;
    svg.appendChild(svgEl('line', { x1: start.x, y1: start.y, x2: end.x, y2: end.y, class: 'default-route' }));
    const ux = dx / d, uy = dy / d;
    const mx = (start.x + end.x) / 2, my = (start.y + end.y) / 2;
    const bx = mx - ux * 11, by = my - uy * 11, px = -uy, py = ux;
    const pts = [`${mx},${my}`, `${bx + px * 5},${by + py * 5}`, `${bx - px * 5},${by - py * 5}`].join(' ');
    svg.appendChild(svgEl('polygon', { points: pts, class: 'route-arrow' }));
}

function drawAxes(svg) {
    const gw = appConfig.max_ox * CELL_PX, gh = appConfig.max_oy * CELL_PX;
    const xAxisY = GRID_TOP + gh + AXIS_OFFSET, yAxisX = GRID_LEFT - AXIS_OFFSET;
    svg.appendChild(svgEl('line', { x1: GRID_LEFT, y1: xAxisY, x2: GRID_LEFT + gw + 18, y2: xAxisY, class: 'axis' }));
    svg.appendChild(svgEl('line', { x1: yAxisX, y1: GRID_TOP + gh, x2: yAxisX, y2: GRID_TOP - 18, class: 'axis' }));
    for (let x = 0; x <= appConfig.max_ox; x += 1) {
        const p = coordToSvg(x, 0);
        svg.appendChild(svgEl('line', { x1: p.x, y1: xAxisY - 4, x2: p.x, y2: xAxisY + 4, class: 'axis' }));
        const l = svgEl('text', { x: p.x, y: xAxisY + 20, class: 'tick-label', 'text-anchor': 'middle' });
        l.textContent = String(x); svg.appendChild(l);
    }
    for (let y = 0; y <= appConfig.max_oy; y += 1) {
        const p = coordToSvg(0, y);
        svg.appendChild(svgEl('line', { x1: yAxisX - 4, y1: p.y, x2: yAxisX + 4, y2: p.y, class: 'axis' }));
        const l = svgEl('text', { x: yAxisX - 12, y: p.y + 4, class: 'tick-label', 'text-anchor': 'end' });
        l.textContent = String(y); svg.appendChild(l);
    }
    const ox = svgEl('text', { x: GRID_LEFT + gw + 28, y: xAxisY + 4, class: 'axis-label' }); ox.textContent = 'Ox'; svg.appendChild(ox);
    const oy = svgEl('text', { x: yAxisX - 8, y: GRID_TOP - 28, class: 'axis-label', 'text-anchor': 'middle' }); oy.textContent = 'Oy'; svg.appendChild(oy);
}

function drawGrid(svg) {
    const blocked = new Set(appConfig.blocked_cells.map(Number));
    const startCell = Number(appConfig.start_cell);
    for (let index = 1; index <= appConfig.max_ox * appConfig.max_oy; index += 1) {
        const z = index - 1;
        const col = z % appConfig.max_ox, row = Math.floor(z / appConfig.max_ox);
        const x = GRID_LEFT + col * CELL_PX, y = GRID_TOP + (appConfig.max_oy - row - 1) * CELL_PX;
        let cls = 'passable';
        if (blocked.has(index)) cls = 'blocked'; else if (index === startCell) cls = 'start';
        svg.appendChild(svgEl('rect', { x, y, width: CELL_PX, height: CELL_PX, class: `cell ${cls}` }));
        const l = svgEl('text', { x: x + CELL_PX / 2, y: y + CELL_PX / 2, class: 'cell-index' });
        l.textContent = String(index); svg.appendChild(l);
    }
}

function polyline(svg, points, cls) {
    if (!points || points.length < 2) return;
    const s = points.map(p => { const q = coordToSvg(p.x, p.y); return `${q.x},${q.y}`; }).join(' ');
    svg.appendChild(svgEl('polyline', { points: s, class: cls }));
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

    // Reference trajectory (arrows)
    const centers = appConfig.trajectory_cells.map(indexToCenter);
    for (let i = 0; i < centers.length - 1; i += 1) drawMidArrow(svg, centers[i], centers[i + 1]);

    const mode = document.getElementById('view-mode').value;
    const st = runtimeState || {};

    // PDR-only path (orange dashed) — shown in 'all' and 'compare'
    if (mode !== 'fused') polyline(svg, st.pdr_only, 'pdr-path');

    // Transformer observations (green/red dots) — shown only in 'all'
    if (mode === 'all' && st.obs) {
        st.obs.forEach(o => {
            const p = coordToSvg(o.x, o.y);
            svg.appendChild(svgEl('circle', { cx: p.x, cy: p.y, r: 3, class: `obs-dot${o.accepted ? '' : ' rejected'}` }));
        });
    }

    // ESKF fused path (blue, thick) — always
    polyline(svg, st.fused, 'fused-path');
    if (st.latest_fused) {
        const p = coordToSvg(st.latest_fused.x, st.latest_fused.y);
        svg.appendChild(svgEl('circle', { cx: p.x, cy: p.y, r: 6, class: 'fused-dot' }));
    }

    // Start dot
    if (appConfig.start_center) {
        const p = coordToSvg(appConfig.start_center.x, appConfig.start_center.y);
        svg.appendChild(svgEl('circle', { cx: p.x, cy: p.y, r: 7, class: 'start-dot' }));
    }
}

async function api(path, options = {}) {
    const r = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...options });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
}

function updateStatus() {
    const s = runtimeState || {};
    document.getElementById('status-text').textContent = s.message || s.status || 'idle';
    document.getElementById('rows-text').textContent = `${s.processed_rows || 0}/${s.total_rows || 0}`;
    document.getElementById('steps-text').textContent = String(s.step_count || 0);
    document.getElementById('updates-text').textContent = String(s.update_count || 0);
    document.getElementById('rejected-text').textContent = String(s.rejected_count || 0);
    document.getElementById('fused-text').textContent = s.latest_fused
        ? `${s.latest_fused.x.toFixed(2)}, ${s.latest_fused.y.toFixed(2)}` : '--';
    document.getElementById('start-btn').disabled = Boolean(s.running);
}

async function pollState() {
    runtimeState = await api('/api/state');
    updateStatus(); renderMap();
    if (!runtimeState.running && pollTimer) { clearInterval(pollTimer); pollTimer = null; }
}

async function startStream() {
    runtimeState = await api('/api/start', { method: 'POST' });
    updateStatus(); renderMap();
    if (!pollTimer) pollTimer = setInterval(() => pollState().catch(console.error), 200);
}

async function resetStream() {
    runtimeState = await api('/api/reset', { method: 'POST' });
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
    updateStatus(); renderMap();
}

async function init() {
    appConfig = await api('/api/config');
    runtimeState = await api('/api/state');
    document.getElementById('page-title').textContent = `${appConfig.map_name} - ${appConfig.trajectory_name}`;
    document.getElementById('trajectory-order').textContent =
        `start cell ${appConfig.start_cell} | offset map ${appConfig.offset_angle}° + bno ${appConfig.offset_angle_bno}° | model ${appConfig.step_length_model} | ${appConfig.message_rate_hz.toFixed(1)} msg/s`;
    document.getElementById('start-btn').addEventListener('click', () => startStream().catch(e => alert(e.message)));
    document.getElementById('reset-btn').addEventListener('click', () => resetStream().catch(e => alert(e.message)));
    document.getElementById('view-mode').addEventListener('change', renderMap);
    updateStatus(); renderMap();
}

init().catch(error => {
    document.body.innerHTML = `<pre style="padding: 24px; color: #b42318;">${error.message}</pre>`;
});
