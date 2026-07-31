let sessionId = null;
let sessionData = null;
let mapCells = [];
let fireData = [];
let pendingFireCell = null;

function parseSessionIdFromPath() {
    const parts = window.location.pathname.split('/');
    return parseInt(parts[2]);
}

async function loadEditorData() {
    sessionData = await API.get(`/api/sessions/${sessionId}`);
    mapCells = await API.get(`/api/maps/${sessionData.map_id}/cells`);
    fireData = await API.get(`/api/sessions/${sessionId}/fires`);

    document.getElementById('session-name-title').textContent = `${sessionData.session_name} (ID: ${sessionData.session_id})`;
    document.getElementById('session-map-info').textContent = `${sessionData.map_name} (ID: ${sessionData.map_id})`;

    const mapInfo = await API.get(`/api/maps/${sessionData.map_id}`);
    renderMap(mapInfo);
    renderFireTable();

    document.getElementById('loading').classList.add('hidden');
    document.getElementById('editor-layout').classList.remove('hidden');
    document.getElementById('fire-table-wrapper').classList.remove('hidden');
}

function renderMap(mapInfo) {
    const mapGrid = document.getElementById('map-grid');
    mapGrid.style.gridTemplateColumns = `repeat(${mapInfo.length_x}, 40px)`;
    mapGrid.style.gridTemplateRows = `repeat(${mapInfo.width_y}, 40px)`;

    const sorted = [...mapCells].sort((a, b) => {
        if (b.coord_y !== a.coord_y) {
            return b.coord_y - a.coord_y;
        }
        return a.coord_x - b.coord_x;
    });

    const fireByCellId = {};
    fireData.forEach(fire => {
        const key = `${fire.coord_x}_${fire.coord_y}`;
        fireByCellId[key] = fire;
    });

    mapGrid.innerHTML = '';
    sorted.forEach(cell => {
        const div = document.createElement('div');
        div.className = `map-cell ${cell.is_passable ? 'passable' : 'blocked'}`;
        div.dataset.cellId = cell.cell_id;
        div.title = `cell_index=${cell.cell_index}, x=${cell.coord_x}, y=${cell.coord_y}`;

        const fire = fireByCellId[`${cell.coord_x}_${cell.coord_y}`];
        if (fire) {
            const marker = document.createElement('div');
            marker.className = 'fire-marker';
            marker.style.backgroundImage = 'url(/img/test_img/fire.jpg)';
            marker.textContent = String(fire.fire_level);
            div.appendChild(marker);
        }

        div.addEventListener('click', () => {
            pendingFireCell = cell;
            document.getElementById('modal-fire-x').textContent = cell.coord_x;
            document.getElementById('modal-fire-y').textContent = cell.coord_y;
            document.getElementById('modal-fire-time').value = '0';
            document.getElementById('modal-fire-level').value = '1';
            document.getElementById('modal-fire-spread').value = '0';
            document.getElementById('modal-fire-spread-time').value = '0';
            ModalManager.show('fire-cell-modal');
        });

        mapGrid.appendChild(div);
    });
}

function renderFireTable() {
    const body = document.getElementById('fire-table-body');
    body.innerHTML = fireData.map(fire => `
        <tr>
            <td>${fire.session_fire_id}</td>
            <td>${fire.fire_time_seconds}</td>
            <td>${fire.fire_level}</td>
            <td>${fire.fire_spread}</td>
            <td>${fire.fire_spread_time}</td>
            <td>${fire.cell_index}</td>
            <td>${fire.coord_x}</td>
            <td>${fire.coord_y}</td>
            <td><button class="btn btn-danger btn-small" onclick="deleteFire(${fire.session_fire_id})">Delete</button></td>
        </tr>
    `).join('');
}

async function addManualFire() {
    const roleId = AuthManager.roleId();
    const payload = {
        session_id: sessionId,
        fire_time_seconds: parseInt(document.getElementById('fire-time').value),
        fire_level: parseInt(document.getElementById('fire-level').value),
        fire_spread: parseInt(document.getElementById('fire-spread').value),
        fire_spread_time: parseInt(document.getElementById('fire-spread-time').value),
        coord_x: parseInt(document.getElementById('fire-x').value),
        coord_y: parseInt(document.getElementById('fire-y').value),
    };

    await API.post(`/api/sessions/${sessionId}/fires?role_id=${roleId}`, payload);
    await loadEditorData();
}

async function deleteFire(sessionFireId) {
    const roleId = AuthManager.roleId();
    await API.delete(`/api/session-fires/${sessionFireId}?role_id=${roleId}`);
    await loadEditorData();
}

window.deleteFire = deleteFire;

document.addEventListener('DOMContentLoaded', async () => {
    if (!AuthManager.ensureAllowed([1, 2])) {
        return;
    }

    sessionId = parseSessionIdFromPath();
    if (!sessionId) {
        showToast('Invalid session ID', 'error');
        window.location.href = '/training-sessions';
        return;
    }

    document.getElementById('add-fire-manual').addEventListener('click', addManualFire);

    document.getElementById('modal-fire-cancel').addEventListener('click', () => {
        ModalManager.hide('fire-cell-modal');
        pendingFireCell = null;
    });

    document.getElementById('modal-fire-confirm').addEventListener('click', async () => {
        if (!pendingFireCell) return;
        const fireTime = parseInt(document.getElementById('modal-fire-time').value);
        const fireLevel = parseInt(document.getElementById('modal-fire-level').value);
        const fireSpread = parseInt(document.getElementById('modal-fire-spread').value);
        const fireSpreadTime = parseInt(document.getElementById('modal-fire-spread-time').value);
        if (isNaN(fireLevel) || fireLevel < 1 || isNaN(fireTime) || fireTime < 0) {
            showToast('Fire level ≥ 1 and time ≥ 0 are required', 'error');
            return;
        }
        ModalManager.hide('fire-cell-modal');
        try {
            const roleId = AuthManager.roleId();
            await API.post(`/api/sessions/${sessionId}/fires/by-cell?role_id=${roleId}`, {
                session_id: sessionId,
                fire_time_seconds: fireTime,
                fire_level: fireLevel,
                fire_spread: fireSpread || 0,
                fire_spread_time: fireSpreadTime || 0,
                cell_id: pendingFireCell.cell_id,
            });
            pendingFireCell = null;
            await loadEditorData();
        } catch (error) {
            showToast(error.message, 'error');
        }
    });

    try {
        await loadEditorData();
    } catch (error) {
        showToast(error.message, 'error');
    }
});
