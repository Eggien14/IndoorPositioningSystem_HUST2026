let mapData = null;
let cells = [];
let originalCells = [];
let beacons = [];
let enabledAlgorithms = [];
let selectedCell = null;
let beaconPickMode = false;
let pickerSelectedCoord = null;
let pickerSelectedCell = null;

const CELL_SIZE = 40;
const CELL_GAP = 1;
const CELL_STEP = CELL_SIZE + CELL_GAP;
const PICKER_PAGE_ROWS = 10;
// Fallback only — canonical names are fetched from GET /api/algorithm-names so the
// list (incl. algorithm 5) always matches the backend single source of truth.
let ALGORITHMS = [
    { id: 1, name: 'RSSI Fingerprints - CNN + PDR' },
    { id: 2, name: 'Trilateration: Robust LM (loosely-coupled)' },
    { id: 3, name: 'RSSI Fingerprints - Transformer + PDR + ESKF' },
    { id: 4, name: 'RSSI Fingerprints - Multi modal cross attention' },
    { id: 5, name: 'Trilateration: Tightly-coupled EKF' },
];

async function loadAlgorithmNames() {
    try {
        const names = await API.get('/api/algorithm-names');
        ALGORITHMS = Object.entries(names)
            .map(([id, name]) => ({ id: Number(id), name }))
            .sort((a, b) => a.id - b.id);
    } catch (e) {
        // keep the local fallback
    }
}

// UWB-ranging algorithms: need >=3 UWB beacons incl. >=1 master (same rule as backend).
const UWB_ALGORITHMS = [2, 5];

const BEACON_TYPE_LABEL = { 1: 'WIFI', 2: 'BLE', 3: 'UWB', 4: 'UWB MASTER' };
const BEACON_TYPE_COLOR = { 1: '#2463eb', 2: '#0f8b5f', 3: '#e95a1a', 4: '#b43ad2' };

const mapId = getMapIdFromUrl();

document.addEventListener('DOMContentLoaded', () => {
    if (!AuthManager.ensureAllowed([1])) {
        return;
    }

    if (!mapId) {
        alert('Invalid map ID');
        window.location.href = '/choose-map';
        return;
    }

    initEventListeners();
    loadMapData();
});

async function loadMapData() {
    const loading = document.getElementById('loading');

    try {
        loading.classList.remove('hidden');

        const [mapRes, cellRes, beaconRes, algorithmRes] = await Promise.all([
            API.get(`/api/maps/${mapId}`),
            API.get(`/api/maps/${mapId}/cells`),
            API.get(`/api/maps/${mapId}/beacons`),
            API.get(`/api/maps/${mapId}/algorithms`),
            loadAlgorithmNames(),
        ]);

        mapData = mapRes;
        cells = cellRes;
        originalCells = JSON.parse(JSON.stringify(cells));
        beacons = beaconRes;
        enabledAlgorithms = algorithmRes.map(item => item.algorithm);

        displayMapInfo();
        renderGrid();
        renderBeaconList();
        renderAlgorithmList();

        document.getElementById('offset-angle-input').value = Number(mapData.offset_angles || 0);

        ['map-info', 'offset-card', 'algorithm-card', 'beacon-card', 'map-container', 'instructions', 'action-buttons'].forEach((id) => {
            document.getElementById(id).classList.remove('hidden');
        });

        // Re-render after containers are visible so SVG overlay gets real dimensions.
        renderGrid();
    } catch (error) {
        showToast(i18n.translate('msg.error') + ': ' + error.message, 'error');
    } finally {
        loading.classList.add('hidden');
    }
}

function displayMapInfo() {
    document.getElementById('map-name').textContent = mapData.map_name;
    document.getElementById('map-id').textContent = mapData.map_id;
    document.getElementById('map-size').textContent = `${mapData.length_x} x ${mapData.width_y}`;
    document.getElementById('total-cells').textContent = cells.length;
    document.getElementById('map-offset').textContent = Number(mapData.offset_angles || 0).toFixed(2);
}

function renderGrid() {
    const mapGrid = document.getElementById('map-grid');
    mapGrid.style.gridTemplateColumns = `repeat(${mapData.length_x}, ${CELL_SIZE}px)`;
    mapGrid.style.gridTemplateRows = `repeat(${mapData.width_y}, ${CELL_SIZE}px)`;
    mapGrid.innerHTML = '';

    const sortedCells = [...cells].sort((a, b) => {
        if (b.coord_y !== a.coord_y) {
            return b.coord_y - a.coord_y;
        }
        return a.coord_x - b.coord_x;
    });

    sortedCells.forEach((cell) => {
        const cellDiv = document.createElement('div');
        cellDiv.className = `map-cell ${cell.is_passable ? 'passable' : 'blocked'}`;
        cellDiv.dataset.cellId = String(cell.cell_id);
        cellDiv.style.position = 'relative';
        cellDiv.textContent = String(cell.cell_index);

        cellDiv.addEventListener('click', (event) => {
            if (event.detail !== 1) {
                return;
            }

            cellDiv.clickTimer = setTimeout(() => {
                toggleCellPassable(cell.cell_id);
            }, 170);
        });

        cellDiv.addEventListener('dblclick', () => {
            clearTimeout(cellDiv.clickTimer);
            showCellDetailModal(cell.cell_id);
        });

        mapGrid.appendChild(cellDiv);
    });

    renderBeaconOverlay();
}

function renderBeaconOverlay() {
    const mapGrid = document.getElementById('map-grid');
    let svg = mapGrid.querySelector('svg.beacon-overlay');
    if (!svg) {
        svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.classList.add('beacon-overlay');
        svg.style.position = 'absolute';
        svg.style.left = '0';
        svg.style.top = '0';
        svg.style.pointerEvents = 'none';
        mapGrid.style.position = 'relative';
        mapGrid.appendChild(svg);
    }

    const fallbackWidth = (mapData.length_x * CELL_SIZE) + ((mapData.length_x - 1) * CELL_GAP);
    const fallbackHeight = (mapData.width_y * CELL_SIZE) + ((mapData.width_y - 1) * CELL_GAP);
    const width = mapGrid.scrollWidth || fallbackWidth;
    const height = mapGrid.scrollHeight || fallbackHeight;
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    svg.setAttribute('width', String(width));
    svg.setAttribute('height', String(height));
    svg.innerHTML = '';

    beacons.forEach((beacon) => {
        const x = Number(beacon.coord_x) * CELL_STEP;
        const y = (mapData.width_y - Number(beacon.coord_y)) * CELL_STEP;

        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        circle.setAttribute('cx', String(x));
        circle.setAttribute('cy', String(y));
        circle.setAttribute('r', '6');
        circle.setAttribute('fill', BEACON_TYPE_COLOR[beacon.beacon_type] || '#444');
        circle.setAttribute('stroke', '#ffffff');
        circle.setAttribute('stroke-width', '1.5');
        circle.setAttribute('title', `${BEACON_TYPE_LABEL[beacon.beacon_type]} ${beacon.beacon_hex_id}`);
        svg.appendChild(circle);

        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        text.setAttribute('x', String(x + 8));
        text.setAttribute('y', String(y - 8));
        text.setAttribute('font-size', '11');
        text.setAttribute('font-weight', '700');
        text.setAttribute('fill', '#111111');
        text.textContent = String(beacon.beacon_id);
        svg.appendChild(text);
    });
}

function renderAlgorithmList() {
    const container = document.getElementById('algorithm-list');
    container.innerHTML = ALGORITHMS.map((algorithm) => `
        <label class="card" style="padding: 10px; display: flex; gap: 10px; align-items: center;">
            <input type="checkbox" class="algorithm-checkbox" value="${algorithm.id}" ${enabledAlgorithms.includes(algorithm.id) ? 'checked' : ''}>
            <span>${escapeHtml(algorithm.name)}</span>
        </label>
    `).join('');

    updateAlgorithmHint();
}

function getBeaconCounts() {
    const counts = { 1: 0, 2: 0, 3: 0, 4: 0 };
    beacons.forEach((beacon) => {
        counts[beacon.beacon_type] = (counts[beacon.beacon_type] || 0) + 1;
    });
    return counts;
}

function updateAlgorithmHint() {
    const counts = getBeaconCounts();
    const wifiBle = (counts[1] || 0) + (counts[2] || 0);
    const uwb = (counts[3] || 0) + (counts[4] || 0);
    const master = counts[4] || 0;
    document.getElementById('algorithm-hint').textContent = `Fingerprint (1,3,4): need >= 3 WIFI/BLE. Trilateration (2,5): need >= 3 UWB with >= 1 master. Current: WIFI/BLE=${wifiBle}, UWB=${uwb}, MASTER=${master}`;
}

function renderBeaconList() {
    const container = document.getElementById('beacon-list');
    if (!beacons.length) {
        container.innerHTML = '<p style="color: var(--text-secondary);">No beacons on this map yet.</p>';
        updateAlgorithmHint();
        renderGrid();
        return;
    }

    const rows = beacons.map((beacon) => `
        <tr>
            <td>${beacon.beacon_id}</td>
            <td>${escapeHtml(beacon.beacon_hex_id)}</td>
            <td><span style="color: ${BEACON_TYPE_COLOR[beacon.beacon_type]};">${escapeHtml(BEACON_TYPE_LABEL[beacon.beacon_type] || String(beacon.beacon_type))}</span></td>
            <td>(${Number(beacon.coord_x).toFixed(2)}, ${Number(beacon.coord_y).toFixed(2)})</td>
            <td>
                <button class="btn btn-secondary btn-small beacon-edit-btn" data-id="${beacon.beacon_id}">Edit</button>
                <button class="btn btn-danger btn-small beacon-delete-btn" data-id="${beacon.beacon_id}">Delete</button>
            </td>
        </tr>
    `).join('');

    container.innerHTML = `
        <div style="overflow-x: auto;">
            <table style="width: 100%; border-collapse: collapse;">
                <thead>
                    <tr>
                        <th style="text-align: left; padding: 8px;">ID</th>
                        <th style="text-align: left; padding: 8px;">Hex ID</th>
                        <th style="text-align: left; padding: 8px;">Type</th>
                        <th style="text-align: left; padding: 8px;">Coord</th>
                        <th style="text-align: left; padding: 8px;">Actions</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>
    `;

    updateAlgorithmHint();
    renderGrid();
}

function toggleCellPassable(cellId) {
    const cell = cells.find((item) => item.cell_id === cellId);
    if (!cell) {
        return;
    }
    cell.is_passable = cell.is_passable ? 0 : 1;
    renderGrid();
}

function showCellDetailModal(cellId) {
    const cell = cells.find((item) => item.cell_id === cellId);
    if (!cell) {
        return;
    }
    selectedCell = cell;
    document.getElementById('modal-coords').value = `(${cell.coord_x}, ${cell.coord_y})`;
    document.getElementById('modal-cell-index').value = String(cell.cell_index);
    document.querySelector(`input[name="cell-passable"][value="${cell.is_passable ? 1 : 0}"]`).checked = true;
    ModalManager.show('cell-modal');
}

function saveCellDetails() {
    if (!selectedCell) {
        return;
    }
    const nextCellIndex = parseInt(document.getElementById('modal-cell-index').value, 10);
    const nextPassable = parseInt(document.querySelector('input[name="cell-passable"]:checked').value, 10);

    const duplicate = cells.find((item) => item.cell_id !== selectedCell.cell_id && item.cell_index === nextCellIndex);
    if (duplicate) {
        alert(i18n.translate('editMap.duplicateError'));
        return;
    }

    selectedCell.cell_index = nextCellIndex;
    selectedCell.is_passable = nextPassable;
    ModalManager.hide('cell-modal');
    renderGrid();
}

function resetMap() {
    if (!confirm('Reset all map-cell changes?')) {
        return;
    }
    cells = JSON.parse(JSON.stringify(originalCells));
    renderGrid();
}

async function saveMapCells() {
    const indexes = cells.map((cell) => cell.cell_index);
    const duplicate = indexes.find((idx, i) => indexes.indexOf(idx) !== i);
    if (duplicate !== undefined) {
        alert(i18n.translate('editMap.duplicateError'));
        return;
    }

    const saveBtn = document.getElementById('save-btn');
    const prev = saveBtn.textContent;
    saveBtn.disabled = true;
    saveBtn.textContent = i18n.translate('msg.saving');

    try {
        await API.put('/api/cells/batch', {
            cells: cells.map((cell) => ({
                cell_id: cell.cell_id,
                cell_index: cell.cell_index,
                is_passable: cell.is_passable,
            })),
        });
        originalCells = JSON.parse(JSON.stringify(cells));
        showToast(i18n.translate('editMap.saveSuccess'), 'success');
    } catch (error) {
        showToast(i18n.translate('msg.error') + ': ' + error.message, 'error');
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = prev;
    }
}

async function saveOffset() {
    const raw = parseFloat(document.getElementById('offset-angle-input').value);
    if (Number.isNaN(raw) || raw < 0 || raw >= 360) {
        showToast('Offset must be in [0, 360)', 'error');
        return;
    }

    await API.put(`/api/maps/${mapId}/offset-angle`, { offset_angles: raw });
    mapData.offset_angles = raw;
    displayMapInfo();
    showToast('Map offset updated', 'success');
}

function openBeaconModal(beacon = null) {
    beaconPickMode = false;
    pickerSelectedCoord = null;
    document.getElementById('beacon-pick-hint').textContent = '';

    if (beacon) {
        document.getElementById('beacon-modal-title').textContent = 'Edit Beacon';
        document.getElementById('beacon-id').value = String(beacon.beacon_id);
        document.getElementById('beacon-hex-id').value = beacon.beacon_hex_id;
        document.getElementById('beacon-type').value = String(beacon.beacon_type);
        document.getElementById('beacon-coord-x').value = Number(beacon.coord_x).toFixed(2);
        document.getElementById('beacon-coord-y').value = Number(beacon.coord_y).toFixed(2);
    } else {
        document.getElementById('beacon-modal-title').textContent = 'Add Beacon';
        document.getElementById('beacon-id').value = '';
        document.getElementById('beacon-hex-id').value = '';
        document.getElementById('beacon-type').value = '1';
        document.getElementById('beacon-coord-x').value = '';
        document.getElementById('beacon-coord-y').value = '';
    }

    ModalManager.show('beacon-modal');
}

function initBeaconPicker() {
    const pickerWrap = document.getElementById('picker-map-wrap');
    pickerWrap.innerHTML = '';
    pickerWrap.style.width = 'fit-content';
    pickerWrap.style.height = 'auto';

    const panelRow = document.createElement('div');
    panelRow.id = 'picker-panel-row';
    panelRow.className = 'picker-panel-row';

    const panelCount = Math.max(1, Math.ceil(mapData.width_y / PICKER_PAGE_ROWS));

    for (let panelIndex = 0; panelIndex < panelCount; panelIndex += 1) {
        const startY = panelIndex * PICKER_PAGE_ROWS;
        const endY = Math.min(startY + PICKER_PAGE_ROWS, mapData.width_y);
        const panelRows = endY - startY;

        const panel = document.createElement('div');
        panel.className = 'picker-panel';
        panel.style.width = `${mapData.length_x * CELL_SIZE}px`;

        const title = document.createElement('div');
        title.className = 'picker-panel-title';
        title.textContent = `Y ${startY} - ${endY - 1}`;
        panel.appendChild(title);

        const grid = document.createElement('div');
        grid.className = 'picker-grid';
        grid.style.gridTemplateColumns = `repeat(${mapData.length_x}, ${CELL_SIZE}px)`;
        grid.style.gridTemplateRows = `repeat(${panelRows}, ${CELL_SIZE}px)`;

        for (let globalY = endY - 1; globalY >= startY; globalY -= 1) {
            for (let x = 0; x < mapData.length_x; x += 1) {
                const cell = cells.find((item) => item.coord_x === x && item.coord_y === globalY);
                if (!cell) {
                    continue;
                }

                const cellDiv = document.createElement('div');
                cellDiv.className = `map-cell ${cell.is_passable ? 'passable' : 'blocked'}`;
                cellDiv.dataset.cellId = String(cell.cell_id);
                cellDiv.style.position = 'relative';
                cellDiv.style.cursor = 'crosshair';
                cellDiv.textContent = String(cell.cell_index);

                if (pickerSelectedCell && pickerSelectedCell.x === x && pickerSelectedCell.y === globalY) {
                    cellDiv.classList.add('selected');
                }

                cellDiv.addEventListener('click', (event) => {
                    const cellRect = cellDiv.getBoundingClientRect();
                    const relX = event.clientX - cellRect.left;
                    const relY = event.clientY - cellRect.top;

                    const coordX = x + (relX / CELL_SIZE);
                    const coordY = globalY + (1 - (relY / CELL_SIZE));

                    pickerSelectedCoord = {
                        x: Number(coordX.toFixed(2)),
                        y: Number(coordY.toFixed(2)),
                    };
                    pickerSelectedCell = { x, y: globalY };

                    document.getElementById('picker-selected-coord').textContent = `(${pickerSelectedCoord.x}, ${pickerSelectedCoord.y})`;
                    highlightPickerSelection();
                });

                grid.appendChild(cellDiv);
            }
        }

        panel.appendChild(grid);
        panelRow.appendChild(panel);
    }

    pickerWrap.appendChild(panelRow);

    pickerSelectedCoord = null;
    pickerSelectedCell = null;
    document.getElementById('picker-selected-coord').textContent = '-';
    highlightPickerSelection();
}

function highlightPickerSelection() {
    document.querySelectorAll('#picker-map-wrap .map-cell.selected').forEach((cell) => {
        cell.classList.remove('selected');
    });

    if (!pickerSelectedCell) {
        return;
    }

    const selectedCell = Array.from(document.querySelectorAll('#picker-map-wrap .map-cell')).find((cell) => {
        const cellId = parseInt(cell.dataset.cellId, 10);
        const matched = cells.find((item) => item.cell_id === cellId);
        return matched && matched.coord_x === pickerSelectedCell.x && matched.coord_y === pickerSelectedCell.y;
    });

    if (selectedCell) {
        selectedCell.classList.add('selected');
    }
}

async function saveBeacon() {
    const beaconIdRaw = document.getElementById('beacon-id').value;
    const beaconHexId = document.getElementById('beacon-hex-id').value.trim();
    const beaconType = parseInt(document.getElementById('beacon-type').value, 10);
    const coordX = parseFloat(document.getElementById('beacon-coord-x').value);
    const coordY = parseFloat(document.getElementById('beacon-coord-y').value);

    if (!beaconHexId || Number.isNaN(beaconType) || Number.isNaN(coordX) || Number.isNaN(coordY)) {
        showToast('Please fill all beacon fields correctly', 'error');
        return;
    }

    if (coordX < 0 || coordY < 0) {
        showToast('Coordinates must be non-negative', 'error');
        return;
    }

    const payload = {
        beacon_hex_id: beaconHexId,
        beacon_type: beaconType,
        coord_x: Number(coordX.toFixed(2)),
        coord_y: Number(coordY.toFixed(2)),
    };

    if (beaconIdRaw) {
        await API.put(`/api/beacons/${parseInt(beaconIdRaw, 10)}`, payload);
    } else {
        await API.post(`/api/maps/${mapId}/beacons`, payload);
    }

    ModalManager.hide('beacon-modal');
    beacons = await API.get(`/api/maps/${mapId}/beacons`);
    renderBeaconList();
    showToast('Beacon saved', 'success');
}

async function deleteBeacon(beaconId) {
    if (!confirm('Delete this beacon?')) {
        return;
    }
    await API.delete(`/api/beacons/${beaconId}`);
    beacons = await API.get(`/api/maps/${mapId}/beacons`);
    renderBeaconList();
    showToast('Beacon deleted', 'success');
}

function getSelectedAlgorithmIds() {
    return Array.from(document.querySelectorAll('.algorithm-checkbox:checked')).map((input) => parseInt(input.value, 10));
}

function validateAlgorithms(algorithms) {
    const counts = getBeaconCounts();
    const wifiBle = (counts[1] || 0) + (counts[2] || 0);
    const uwb = (counts[3] || 0) + (counts[4] || 0);
    const master = counts[4] || 0;

    if (algorithms.some((id) => [1, 3, 4].includes(id)) && wifiBle < 3) {
        return 'Fingerprint algorithms require at least 3 WIFI/BLE beacons.';
    }

    if (algorithms.some((id) => UWB_ALGORITHMS.includes(id)) && !(uwb >= 3 && master >= 1)) {
        return 'Trilateration algorithms require at least 3 UWB beacons including 1 UWB master.';
    }

    return null;
}

async function saveAlgorithms() {
    const algorithms = getSelectedAlgorithmIds();
    const validationError = validateAlgorithms(algorithms);
    if (validationError) {
        showToast(validationError, 'error');
        return;
    }

    await API.put(`/api/maps/${mapId}/algorithms`, { algorithms });
    enabledAlgorithms = algorithms;
    showToast('Algorithms updated', 'success');
}

function initEventListeners() {
    document.getElementById('reset-btn').addEventListener('click', resetMap);
    document.getElementById('save-btn').addEventListener('click', saveMapCells);

    document.getElementById('modal-cancel').addEventListener('click', () => ModalManager.hide('cell-modal'));
    document.getElementById('modal-save').addEventListener('click', saveCellDetails);

    document.getElementById('save-offset-btn').addEventListener('click', () => {
        saveOffset().catch((error) => showToast(error.message, 'error'));
    });
    document.getElementById('save-algorithms-btn').addEventListener('click', () => {
        saveAlgorithms().catch((error) => showToast(error.message, 'error'));
    });

    document.getElementById('add-beacon-btn').addEventListener('click', () => openBeaconModal());
    document.getElementById('beacon-cancel-btn').addEventListener('click', () => {
        ModalManager.hide('beacon-modal');
    });
    document.getElementById('beacon-save-btn').addEventListener('click', () => {
        saveBeacon().catch((error) => showToast(error.message, 'error'));
    });

    document.getElementById('pick-beacon-coord-btn').addEventListener('click', () => {
        ModalManager.hide('beacon-modal');
        initBeaconPicker();
        ModalManager.show('beacon-picker-modal');
    });

    document.getElementById('picker-cancel-btn').addEventListener('click', () => {
        pickerSelectedCoord = null;
        pickerSelectedCell = null;
        ModalManager.hide('beacon-picker-modal');
    });

    document.getElementById('picker-confirm-btn').addEventListener('click', () => {
        if (!pickerSelectedCoord) {
            showToast('Please select a coordinate on the map', 'error');
            return;
        }
        document.getElementById('beacon-coord-x').value = String(pickerSelectedCoord.x);
        document.getElementById('beacon-coord-y').value = String(pickerSelectedCoord.y);
        document.getElementById('beacon-pick-hint').textContent = `Picked: (${pickerSelectedCoord.x}, ${pickerSelectedCoord.y})`;
        pickerSelectedCoord = null;
        pickerSelectedCell = null;
        ModalManager.hide('beacon-picker-modal');
        ModalManager.show('beacon-modal');
    });

    document.getElementById('beacon-list').addEventListener('click', (event) => {
        const editButton = event.target.closest('.beacon-edit-btn');
        if (editButton) {
            const beaconId = parseInt(editButton.dataset.id, 10);
            const beacon = beacons.find((item) => item.beacon_id === beaconId);
            if (beacon) {
                openBeaconModal(beacon);
            }
            return;
        }

        const deleteButton = event.target.closest('.beacon-delete-btn');
        if (deleteButton) {
            const beaconId = parseInt(deleteButton.dataset.id, 10);
            deleteBeacon(beaconId).catch((error) => showToast(error.message, 'error'));
        }
    });
}

function getMapIdFromUrl() {
    const parts = window.location.pathname.split('/');
    return parseInt(parts[parts.length - 1], 10);
}
