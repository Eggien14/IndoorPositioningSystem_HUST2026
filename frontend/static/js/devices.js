let devices = [];
let editing = false;

async function loadDevices() {
    devices = await API.get('/api/devices');
    renderDevices();
}

function renderDevices() {
    const grid = document.getElementById('device-grid');
    if (!devices.length) {
        grid.innerHTML = '<div class="card">No devices found.</div>';
        return;
    }

    grid.innerHTML = devices.map(device => `
        <div class="card">
            <img class="device-image" src="/img/device/${device.device_id}.png" alt="${escapeHtml(device.device_name)}" data-fallbacks='["/img/device/${device.device_id}.jpg","/img/device/lililaho.png"]' onerror="imgFallback(this)">
            <h3 class="mt-20">${escapeHtml(device.device_name)}</h3>
            <p style="color: var(--text-secondary);">ID: ${device.device_id}</p>
            <p style="color: var(--text-secondary);">HEX: ${escapeHtml(device.device_hex_id)}</p>
            <p style="color: var(--text-secondary);">Water: ${device.water_capacity === -1 ? '∞' : (device.water_capacity != null ? device.water_capacity : 100)}</p>
            <div class="card-actions">
                <button class="btn btn-secondary btn-small" onclick="openEditDevice(${device.device_id})">Edit</button>
                <button class="btn btn-danger btn-small" onclick="removeDevice(${device.device_id})">Delete</button>
            </div>
        </div>
    `).join('');
}

function openCreateDevice() {
    editing = false;
    document.getElementById('device-modal-title').textContent = i18n.translate('device.add');
    document.getElementById('device-id').value = '';
    document.getElementById('device-name').value = '';
    document.getElementById('device-hex-id').value = '';
    document.getElementById('device-water-capacity').value = '100';
    ModalManager.show('device-modal');
}

function openEditDevice(deviceId) {
    const device = devices.find(d => d.device_id === deviceId);
    if (!device) {
        return;
    }

    editing = true;
    document.getElementById('device-modal-title').textContent = i18n.translate('edit');
    document.getElementById('device-id').value = String(device.device_id);
    document.getElementById('device-name').value = device.device_name;
    document.getElementById('device-hex-id').value = device.device_hex_id;
    document.getElementById('device-water-capacity').value =
        String(device.water_capacity != null ? device.water_capacity : 100);
    ModalManager.show('device-modal');
}

async function saveDevice() {
    const roleId = AuthManager.roleId();
    const payload = {
        device_name: document.getElementById('device-name').value.trim(),
        device_hex_id: document.getElementById('device-hex-id').value.trim(),
    };

    if (!payload.device_name || !payload.device_hex_id) {
        showToast('Please fill all fields', 'error');
        return;
    }

    // Dung tích nước: -1 = vô hạn; >= 0 = hữu hạn.
    const waterCapacity = parseInt(document.getElementById('device-water-capacity').value, 10);
    if (Number.isNaN(waterCapacity) || waterCapacity < -1) {
        showToast('Water capacity must be -1 (infinite) or a number >= 0', 'error');
        return;
    }
    payload.water_capacity = waterCapacity;

    if (editing) {
        const deviceId = parseInt(document.getElementById('device-id').value);
        await API.put(`/api/devices/${deviceId}?role_id=${roleId}`, payload);
    } else {
        await API.post(`/api/devices?role_id=${roleId}`, payload);
    }

    ModalManager.hide('device-modal');
    await loadDevices();
}

async function removeDevice(deviceId) {
    if (!confirm('Delete this device?')) {
        return;
    }

    const roleId = AuthManager.roleId();
    await API.delete(`/api/devices/${deviceId}?role_id=${roleId}`);
    await loadDevices();
}

window.openEditDevice = openEditDevice;
window.removeDevice = removeDevice;

document.addEventListener('DOMContentLoaded', async () => {
    if (!AuthManager.ensureAllowed([1, 2])) {
        return;
    }

    document.getElementById('add-device-btn').addEventListener('click', openCreateDevice);
    document.getElementById('device-modal-cancel').addEventListener('click', () => ModalManager.hide('device-modal'));
    document.getElementById('device-modal-save').addEventListener('click', saveDevice);

    try {
        await loadDevices();
    } catch (error) {
        showToast(error.message, 'error');
    }
});
