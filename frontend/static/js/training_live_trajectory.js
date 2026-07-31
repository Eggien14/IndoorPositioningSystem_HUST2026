/* Shared trajectory view modes for training-live pages (algorithms 2, 3, 5). */
const TrainingTrajectory = (function () {
    const MODE = { CURRENT: 'current', TRAIL: 'trail', FULL: 'full' };
    const TRAIL_MS = 5000;

    let mode = MODE.CURRENT;
    let sessionStartMs = null;
    const historyByHex = Object.create(null);

    function normHex(value) {
        let v = String(value || '').trim().toLowerCase();
        if (v && !v.startsWith('0x')) v = `0x${v}`;
        return v;
    }

    function resetSession() {
        sessionStartMs = Date.now();
        Object.keys(historyByHex).forEach((k) => delete historyByHex[k]);
    }

    function recordPoint(hex, x, y) {
        if (!Number.isFinite(x) || !Number.isFinite(y)) return;
        const key = normHex(hex);
        if (!historyByHex[key]) historyByHex[key] = [];
        const pts = historyByHex[key];
        const last = pts[pts.length - 1];
        if (last && last.x === x && last.y === y) return;
        pts.push({ t: Date.now(), x, y });
    }

    function ingestState(state, adminOpt) {
        (state && state.tags || []).forEach((tag) => {
            if (tag.is_admin) return;
            recordPoint(tag.tag_hex_id, Number(tag.position_x), Number(tag.position_y));
        });
        if (adminOpt && adminOpt.visible) {
            recordPoint(adminOpt.hex || '0xad', Number(adminOpt.x), Number(adminOpt.y));
        }
    }

    function pointsForHex(hex) {
        const pts = historyByHex[normHex(hex)] || [];
        if (mode === MODE.CURRENT) return [];
        if (mode === MODE.TRAIL) {
            const cutoff = Date.now() - TRAIL_MS;
            return pts.filter((p) => p.t >= cutoff);
        }
        if (sessionStartMs == null) return pts;
        return pts.filter((p) => p.t >= sessionStartMs);
    }

    function drawPaths(overlay, coordToPixel, colorFn) {
        if (mode === MODE.CURRENT || !overlay) return;

        Object.keys(historyByHex).forEach((hex) => {
            const slice = pointsForHex(hex);
            if (slice.length < 2) return;
            const color = colorFn(hex);
            const d = slice.map((p, i) => {
                const px = coordToPixel(p.x, p.y);
                return `${i === 0 ? 'M' : 'L'} ${px.x} ${px.y}`;
            }).join(' ');
            overlay.appendChild(createSvg('path', {
                d,
                fill: 'none',
                stroke: color,
                'stroke-width': 1.5,
                'stroke-linecap': 'round',
                'stroke-linejoin': 'round',
                opacity: 0.85,
            }));
        });
    }

    function init(onChange) {
        const select = document.getElementById('a3-traj-mode');
        if (!select) return;
        select.addEventListener('change', () => {
            mode = select.value || MODE.CURRENT;
            if (typeof onChange === 'function') onChange();
        });
    }

    return {
        MODE,
        init,
        resetSession,
        ingestState,
        drawPaths,
        getMode: () => mode,
    };
})();
