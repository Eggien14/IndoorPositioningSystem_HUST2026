/* ============================================================
   Choose Map Page JavaScript
   ============================================================ */

let maps = [];

// ============================================================
// Load Maps
// ============================================================

async function loadMaps() {
    const loading = document.getElementById('loading');
    const mapsContainer = document.getElementById('maps-container');
    const emptyState = document.getElementById('empty-state');
    
    try {
        loading.classList.remove('hidden');
        mapsContainer.classList.add('hidden');
        emptyState.classList.add('hidden');
        
        maps = await API.get('/api/maps');
        
        loading.classList.add('hidden');
        
        if (maps.length === 0) {
            emptyState.classList.remove('hidden');
        } else {
            renderMaps();
            mapsContainer.classList.remove('hidden');
        }
    } catch (error) {
        loading.classList.add('hidden');
        showToast(i18n.translate('msg.error') + ': ' + error.message, 'error');
    }
}

// ============================================================
// Render Maps
// ============================================================

function renderMaps() {
    const mapsContainer = document.getElementById('maps-container');
    
    mapsContainer.innerHTML = maps.map(map => `
        <div class="card">
            <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 15px;">
                <div>
                    <h3 class="card-title">${escapeHtml(map.map_name)}</h3>
                    <p style="color: var(--text-secondary); font-size: 0.9rem;">ID: ${map.map_id}</p>
                </div>
            </div>
            
            <!-- Map Image -->
            <div style="margin-bottom: 15px; text-align: center;">
                <img
                    src="/img/map/${map.map_id}.png"
                    alt="${escapeHtml(map.map_name)}"
                    style="max-width: 100%; height: auto; border-radius: 6px; background-color: var(--bg-hover);"
                    data-fallbacks='["/img/map/${map.map_id}.jpg","/img/map/lililaho.png"]'
                    onerror="imgFallback(this)"
                >
            </div>
            
            <!-- Map Info -->
            <div style="color: var(--text-secondary); font-size: 0.9rem; margin-bottom: 15px;">
                <p>Size: ${map.length_x} × ${map.width_y} cells</p>
                <p>Created: ${formatDate(map.created_at)}</p>
            </div>
            
            <!-- Actions -->
            <div class="card-actions">
                <button class="btn btn-primary btn-small" onclick="useMap(${map.map_id})" data-i18n="maps.use">
                    Use
                </button>
                <button class="btn btn-success btn-small" onclick="collectData(${map.map_id})" data-i18n="maps.collect">
                    Collect Data
                </button>
                <button class="btn btn-secondary btn-small" onclick="editMap(${map.map_id})" data-i18n="maps.edit">
                    Edit
                </button>
                <button class="btn btn-danger btn-small" onclick="confirmDeleteMap(${map.map_id})" data-i18n="maps.delete">
                    Delete
                </button>
            </div>
        </div>
    `).join('');
}

// ============================================================
// Map Actions
// ============================================================

function useMap(mapId) {
    // TODO: This will be implemented in another module
    alert(i18n.translate('msg.helloWorld'));
}

function collectData(mapId) {
    window.location.href = `/collect-data/${mapId}`;
}

function editMap(mapId) {
    // Show warning before editing
    if (confirm(i18n.translate('editMap.warning') + '\n\n' + i18n.translate('editMap.continue') + '?')) {
        window.location.href = `/edit-map/${mapId}`;
    }
}

function confirmDeleteMap(mapId) {
    const map = maps.find(m => m.map_id === mapId);
    if (!map) return;
    
    const message = i18n.translate('maps.deleteConfirm') + '\n\n' +
                   `Map: ${map.map_name} (ID: ${mapId})`;
    
    if (confirm(message)) {
        deleteMap(mapId);
    }
}

async function deleteMap(mapId) {
    try {
        await API.delete(`/api/maps/${mapId}`);
        showToast(i18n.translate('msg.success'), 'success');
        loadMaps(); // Reload maps
    } catch (error) {
        showToast(i18n.translate('msg.error') + ': ' + error.message, 'error');
    }
}

// ============================================================
// Utility Functions
// ============================================================

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================================
// Initialize
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
    if (!AuthManager.ensureAllowed([1])) {
        return;
    }
    loadMaps();
});
