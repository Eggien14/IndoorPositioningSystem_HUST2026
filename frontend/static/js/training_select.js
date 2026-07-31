let maps = [];
let devices = [];
let selectedMapId = null;

// Fallback only — the canonical names are fetched from the backend
// (GET /api/algorithm-names) so frontend and server never drift apart.
let ALGORITHM_NAMES = {
    1: 'RSSI Fingerprints - CNN + PDR',
    2: 'Trilateration: Robust LM (loosely-coupled)',
    3: 'RSSI Fingerprints - Transformer + PDR + ESKF',
    4: 'RSSI Fingerprints - Multi modal cross attention',
    5: 'Trilateration: Tightly-coupled EKF',
};

async function loadAlgorithmNames() {
    try {
        const names = await API.get('/api/algorithm-names');
        ALGORITHM_NAMES = Object.fromEntries(
            Object.entries(names).map(([key, value]) => [Number(key), value])
        );
    } catch (error) {
        // keep the local fallback
    }
}

async function loadMaps() {
    maps = await API.get('/api/maps');
    const mapSelect = document.getElementById('train-map');
    mapSelect.innerHTML = maps.map(map => `<option value="${map.map_id}">${escapeHtml(map.map_name)} (ID: ${map.map_id})</option>`).join('');
    selectedMapId = maps.length ? maps[0].map_id : null;
}

async function loadAlgorithmsForMap(mapId) {
    const algorithmSelect = document.getElementById('train-algorithm');
    const algorithms = await API.get(`/api/maps/${mapId}/algorithms`);

    if (!algorithms.length) {
        algorithmSelect.innerHTML = '<option value="">No algorithm enabled for this map</option>';
        algorithmSelect.disabled = true;
        return;
    }

    algorithmSelect.disabled = false;
    algorithmSelect.innerHTML = algorithms
        .sort((a, b) => a.algorithm - b.algorithm)
        .map((item) => `<option value="${item.algorithm}">${escapeHtml(ALGORITHM_NAMES[item.algorithm] || `Algorithm ${item.algorithm}`)}</option>`)
        .join('');
}

async function loadDevices() {
    devices = await API.get('/api/devices');
    const auth = AuthManager.getAuth();
    const singleOnly = auth.role_id === 3;
    const container = document.getElementById('train-devices');

    container.innerHTML = devices.map(device => `
        <label class="card" style="padding: 10px;">
            <input type="${singleOnly ? 'radio' : 'checkbox'}" name="train-device" value="${device.device_id}">
            <strong>${escapeHtml(device.device_name)}</strong>
            <p style="color: var(--text-secondary);">ID: ${device.device_id}</p>
        </label>
    `).join('');
}

async function loadSessionsForMap(mapId) {
    const sessionSelect = document.getElementById('train-session');
    const sessions = await API.get(`/api/maps/${mapId}/sessions`);
    sessionSelect.innerHTML = `<option value="">${i18n.translate('trainingSelect.creative')}</option>` +
        sessions.map(session => `<option value="${session.session_id}">${escapeHtml(session.session_name)} (${session.duration_seconds}s)</option>`).join('');
}

function getSelectedDeviceIds() {
    return Array.from(document.querySelectorAll('input[name="train-device"]:checked')).map(i => parseInt(i.value));
}

async function startTraining() {
    const auth = AuthManager.getAuth();
    const mapId = parseInt(document.getElementById('train-map').value);
    const sessionVal = document.getElementById('train-session').value;
    const sessionId = sessionVal ? parseInt(sessionVal) : null;
    const algorithmRaw = document.getElementById('train-algorithm').value;
    const algorithm = parseInt(algorithmRaw, 10);
    const deviceIds = getSelectedDeviceIds();

    if (!mapId) {
        showToast('Please choose a map', 'error');
        return;
    }
    if (!deviceIds.length) {
        showToast('Please choose device(s)', 'error');
        return;
    }

    if (Number.isNaN(algorithm)) {
        showToast('Please choose an algorithm', 'error');
        return;
    }

    const response = await API.post('/api/training/start', {
        username: auth.username,
        role_id: auth.role_id,
        map_id: mapId,
        session_id: sessionId,
        device_ids: deviceIds,
        algorithm,
    });

    const runPayload = {
        ...(response.data || {}),
        map_id: mapId,
        device_ids: deviceIds,
    };
    sessionStorage.setItem('trainingRun', JSON.stringify(runPayload));
    if (algorithm === 2) {
        // Algo 2 (UWB Trilateration LM) — new realtime page cloned from algo 3.
        window.location.href = '/training-live-algorithm2';
    } else if (algorithm === 3) {
        window.location.href = '/training-live-algorithm3';
    } else if (algorithm === 5) {
        // Algo 5 (UWB Tightly-coupled EKF) — new realtime page cloned from algo 3.
        window.location.href = '/training-live-algorithm5';
    } else {
        window.location.href = '/training-live-test';
    }
}

document.addEventListener('DOMContentLoaded', async () => {
    const auth = AuthManager.getAuth();
    if (!auth) {
        return;
    }

    try {
        await loadAlgorithmNames();
        await loadMaps();
        await loadDevices();

        if (selectedMapId) {
            await loadSessionsForMap(selectedMapId);
            await loadAlgorithmsForMap(selectedMapId);
        }

        document.getElementById('train-map').addEventListener('change', async (e) => {
            const mapId = parseInt(e.target.value, 10);
            await Promise.all([
                loadSessionsForMap(mapId),
                loadAlgorithmsForMap(mapId),
            ]);
        });

        document.getElementById('start-training-btn').addEventListener('click', startTraining);
    } catch (error) {
        showToast(error.message, 'error');
    }
});
