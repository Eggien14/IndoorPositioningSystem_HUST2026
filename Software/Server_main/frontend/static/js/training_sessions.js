let allSessions = [];
let allMaps = [];

function authRoleId() {
    const auth = AuthManager.getAuth();
    return auth ? auth.role_id : null;
}

async function loadData() {
    allMaps = await API.get('/api/maps');
    allSessions = await API.get('/api/sessions');

    const mapSelect = document.getElementById('session-map-id');
    mapSelect.innerHTML = allMaps.map(map => `<option value="${map.map_id}">${escapeHtml(map.map_name)} (ID: ${map.map_id})</option>`).join('');

    renderSessions();
}

function renderSessions() {
    const sessionList = document.getElementById('session-list');
    if (!allSessions.length) {
        sessionList.innerHTML = '<div class="card">No exercise found.</div>';
        return;
    }

    sessionList.innerHTML = allSessions.map(session => `
        <div class="card">
            <h3>${escapeHtml(session.session_name)}</h3>
            <p style="color: var(--text-secondary);">Session ID: ${session.session_id}</p>
            <p style="color: var(--text-secondary);">Map: ${escapeHtml(session.map_name || '')}</p>
            <p style="color: var(--text-secondary);">Duration: ${session.duration_seconds}s</p>
            <div class="card-actions">
                <a href="/training-sessions/${session.session_id}/editor" class="btn btn-secondary btn-small" data-i18n="session.manage">Customize</a>
                <button class="btn btn-danger btn-small" onclick="deleteSession(${session.session_id})" data-i18n="delete">Delete</button>
            </div>
        </div>
    `).join('');
    i18n.updatePageText();
}

async function createSession() {
    const roleId = authRoleId();
    const payload = {
        session_name: document.getElementById('session-name').value.trim(),
        map_id: parseInt(document.getElementById('session-map-id').value),
        duration_seconds: parseInt(document.getElementById('session-duration').value),
    };

    if (!payload.session_name || !payload.map_id || !payload.duration_seconds) {
        showToast('Please fill all fields', 'error');
        return;
    }

    await API.post(`/api/sessions?role_id=${roleId}`, payload);
    ModalManager.hide('session-modal');
    await loadData();
}

async function deleteSession(sessionId) {
    if (!confirm(i18n.translate('session.deleteConfirm'))) {
        return;
    }

    const roleId = authRoleId();
    await API.delete(`/api/sessions/${sessionId}?role_id=${roleId}`);
    await loadData();
}

window.deleteSession = deleteSession;

document.addEventListener('DOMContentLoaded', async () => {
    if (!AuthManager.ensureAllowed([1, 2])) {
        return;
    }

    document.getElementById('create-session-btn').addEventListener('click', () => ModalManager.show('session-modal'));
    document.getElementById('session-modal-cancel').addEventListener('click', () => ModalManager.hide('session-modal'));
    document.getElementById('session-modal-save').addEventListener('click', createSession);

    try {
        await loadData();
    } catch (error) {
        showToast(error.message, 'error');
    }
});
