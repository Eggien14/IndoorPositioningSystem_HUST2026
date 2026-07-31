/* ============================================================
   Data Collection Page JavaScript
   ============================================================ */

let mapData = null;
let cells = [];
let campaigns = [];
let campaignStatistics = [];
let campaignStatisticsByCellId = {};
let selectedCampaign = null;
let selectedCell = null;
let collectionSessionKey = null;
let collectionInterval = null;

const mapId = getMapIdFromUrl();

// ============================================================
// Initialize
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
    if (!AuthManager.ensureAllowed([1])) {
        return;
    }

    if (!mapId) {
        alert('Invalid map ID');
        window.location.href = '/choose-map';
        return;
    }
    
    loadPageData();
    initEventListeners();
});

// ============================================================
// Load Data
// ============================================================

async function loadPageData() {
    const loading = document.getElementById('loading');
    
    try {
        loading.classList.remove('hidden');
        
        // Load map info
        mapData = await API.get(`/api/maps/${mapId}`);
        document.getElementById('map-name').textContent = mapData.map_name;
        document.getElementById('map-id').textContent = mapData.map_id;
        
        // Load cells
        cells = await API.get(`/api/maps/${mapId}/cells`);
        
        // Load campaigns
        campaigns = await API.get(`/api/maps/${mapId}/campaigns`);
        
        loading.classList.add('hidden');
        document.getElementById('layout-container').classList.remove('hidden');
        
        renderCampaigns();
        if (campaigns.length > 0) {
            await selectCampaign(campaigns[0].campaign_id, { silent: true });
        } else {
            renderMap();
        }
        
    } catch (error) {
        loading.classList.add('hidden');
        showToast(i18n.translate('msg.error') + ': ' + error.message, 'error');
    }
}

async function loadCampaignStatistics() {
    if (!selectedCampaign) {
        campaignStatistics = [];
        campaignStatisticsByCellId = {};
        updateSelectedCampaignSummary();
        renderMap();
        return;
    }

    campaignStatistics = await API.get(`/api/campaigns/${selectedCampaign.campaign_id}/statistics`);
    campaignStatisticsByCellId = campaignStatistics.reduce((accumulator, stat) => {
        accumulator[stat.cell_id] = stat;
        return accumulator;
    }, {});

    updateSelectedCampaignSummary();
    renderMap();
}

function getCellStatistics(cellId) {
    return campaignStatisticsByCellId[cellId] || null;
}

function updateSelectedCampaignSummary() {
    const campaignInfo = document.getElementById('campaign-info');
    const selectedCampaignName = document.getElementById('selected-campaign-name');
    const selectedCampaignCollected = document.getElementById('selected-campaign-collected');
    const selectedCampaignTarget = document.getElementById('selected-campaign-target');

    if (!selectedCampaign) {
        if (campaignInfo) {
            campaignInfo.classList.add('hidden');
        }
        return;
    }

    if (campaignInfo) {
        campaignInfo.classList.remove('hidden');
    }

    if (selectedCampaignName) {
        selectedCampaignName.textContent = selectedCampaign.campaign_name || `Campaign ${selectedCampaign.campaign_id}`;
    }

    if (selectedCampaignCollected) {
        const passableCellIds = new Set(
            cells
                .filter(cell => Number(cell.is_passable) === 1)
                .map(cell => cell.cell_id)
        );

        const collectedPassableCells = campaignStatistics.filter(
            stat => passableCellIds.has(stat.cell_id) && Number(stat.collected_samples) > 0
        ).length;
        selectedCampaignCollected.textContent = String(collectedPassableCells);
    }

    if (selectedCampaignTarget) {
        const totalPassableCells = cells.filter(cell => Number(cell.is_passable) === 1).length;
        selectedCampaignTarget.textContent = String(totalPassableCells);
    }
}

// ============================================================
// Render Campaigns
// ============================================================

function renderCampaigns() {
    const campaignsList = document.getElementById('campaigns-list');
    
    if (campaigns.length === 0) {
        campaignsList.innerHTML = '<p style="color: var(--text-secondary); text-align: center;">No campaigns yet</p>';
        return;
    }
    
    campaignsList.innerHTML = campaigns.map(campaign => `
        <div class="campaign-item ${selectedCampaign && selectedCampaign.campaign_id === campaign.campaign_id ? 'selected' : ''}" data-campaign-id="${campaign.campaign_id}">
            <div style="display: flex; justify-content: space-between; align-items: start;">
                <div style="flex: 1;">
                    <strong>${escapeHtml(campaign.campaign_name || 'Campaign ' + campaign.campaign_id)}</strong>
                    <p style="color: var(--text-secondary); font-size: 0.85rem; margin-top: 5px;">
                        ID: ${campaign.campaign_id}<br>
                        Samples: ${campaign.sample_number}
                    </p>
                </div>
                <button class="btn btn-danger btn-small" onclick="deleteCampaign(${campaign.campaign_id}, event)" style="margin-left: 10px;">×</button>
            </div>
        </div>
    `).join('');
    
    // Add click handlers
    document.querySelectorAll('.campaign-item').forEach(item => {
        item.addEventListener('click', (e) => {
            const campaignId = parseInt(item.dataset.campaignId);
            selectCampaign(campaignId);
        });
    });
}

// ============================================================
// Render Map
// ============================================================

function renderMap() {
    const mapGrid = document.getElementById('map-grid');
    
    mapGrid.style.gridTemplateColumns = `repeat(${mapData.length_x}, 40px)`;
    mapGrid.style.gridTemplateRows = `repeat(${mapData.width_y}, 40px)`;
    mapGrid.innerHTML = '';
    
    // Sort cells: bottom-up, left-right
    const sortedCells = [...cells].sort((a, b) => {
        if (b.coord_y !== a.coord_y) {
            return b.coord_y - a.coord_y;
        }
        return a.coord_x - b.coord_x;
    });
    
    sortedCells.forEach(cell => {
        const cellDiv = document.createElement('div');
        cellDiv.className = `map-cell ${cell.is_passable ? 'passable' : 'blocked'}`;
        cellDiv.dataset.cellId = cell.cell_id;

        const cellStatistics = selectedCampaign ? getCellStatistics(cell.cell_id) : null;
        const collectedSamples = cellStatistics ? cellStatistics.collected_samples : 0;
        const targetSamples = cellStatistics ? cellStatistics.target_samples : 0;

        if (collectedSamples > 0) {
            cellDiv.classList.add('has-samples');
            if (targetSamples > 0 && collectedSamples >= targetSamples) {
                cellDiv.classList.add('completed');
            }

            const badge = document.createElement('span');
            badge.className = 'map-cell-badge';
            badge.textContent = `${collectedSamples}/${targetSamples}`;
            cellDiv.appendChild(badge);
        }

        cellDiv.title = selectedCampaign
            ? `Cell ${cell.cell_index}: ${collectedSamples}/${selectedCampaign.sample_number}`
            : `Cell ${cell.cell_index}`;
        
        // Click to open actions
        cellDiv.addEventListener('click', () => {
            if (!selectedCampaign) {
                alert(i18n.translate('collectData.selectCampaign'));
                return;
            }

            if (Number(cell.is_passable) !== 1) {
                showToast('This cell is blocked', 'error');
                return;
            }

            openCellActionModal(cell);
        });
        
        // Hover tooltip (2 seconds)
        let hoverTimeout;
        cellDiv.addEventListener('mouseenter', (e) => {
            hoverTimeout = setTimeout(() => {
                showTooltip(e, cell);
            }, 2000);
        });
        
        cellDiv.addEventListener('mouseleave', () => {
            clearTimeout(hoverTimeout);
            hideTooltip();
        });
        
        mapGrid.appendChild(cellDiv);
    });
}

// ============================================================
// Campaign Actions
// ============================================================

async function selectCampaign(campaignId, options = {}) {
    selectedCampaign = campaigns.find(c => c.campaign_id === campaignId);

    if (!selectedCampaign) {
        return;
    }
    
    // Update UI
    renderCampaigns();
    
    await loadCampaignStatistics();

    if (!options.silent) {
        updateSelectedCampaignSummary();
    }
}

async function deleteCampaign(campaignId, event) {
    event.stopPropagation(); // Prevent campaign selection
    
    if (!confirm('Delete this campaign and all its data?')) {
        return;
    }
    
    try {
        await API.delete(`/api/campaigns/${campaignId}`);
        showToast('Campaign deleted', 'success');
        
        // Reload campaigns
        campaigns = await API.get(`/api/maps/${mapId}/campaigns`);
        if (selectedCampaign && selectedCampaign.campaign_id === campaignId) {
            selectedCampaign = campaigns[0] || null;
        }

        if (selectedCampaign) {
            await loadCampaignStatistics();
        } else {
            campaignStatistics = [];
            campaignStatisticsByCellId = {};
            renderCampaigns();
            renderMap();
            updateSelectedCampaignSummary();
        }
        
        renderCampaigns();
    } catch (error) {
        showToast(i18n.translate('msg.error') + ': ' + error.message, 'error');
    }
}

function showCreateCampaignModal() {
    document.getElementById('campaign-name').value = '';
    document.getElementById('sample-number').value = '200';
    ModalManager.show('campaign-modal');
}

async function createCampaign() {
    const campaignName = document.getElementById('campaign-name').value.trim();
    const sampleNumber = parseInt(document.getElementById('sample-number').value);
    
    if (sampleNumber < 1) {
        alert('Sample number must be at least 1');
        return;
    }
    
    try {
        const response = await API.post('/api/campaigns', {
            map_id: mapId,
            sample_number: sampleNumber,
            campaign_name: campaignName || null
        });
        
        showToast('Campaign created', 'success');
        
        // Reload campaigns
        campaigns = await API.get(`/api/maps/${mapId}/campaigns`);
        if (!selectedCampaign && campaigns.length > 0) {
            await selectCampaign(campaigns[0].campaign_id, { silent: true });
        } else {
            renderCampaigns();
        }
        
        ModalManager.hide('campaign-modal');
    } catch (error) {
        showToast(i18n.translate('msg.error') + ': ' + error.message, 'error');
    }
}

// ============================================================
// Data Collection
// ============================================================

function showCollectionModal(cell) {
    selectedCell = cell;
    
    // Populate modal
    document.getElementById('col-map-id').textContent = mapData.map_id;
    document.getElementById('col-campaign-id').textContent = selectedCampaign.campaign_id;
    document.getElementById('col-cell-index').textContent = cell.cell_index;
    document.getElementById('col-coord-x').textContent = cell.coord_x;
    document.getElementById('col-coord-y').textContent = cell.coord_y;
    document.getElementById('col-progress').textContent = `0 / ${selectedCampaign.sample_number}`;
    
    // Reset button
    const startBtn = document.getElementById('collection-start-btn');
    startBtn.textContent = i18n.translate('collectData.start');
    startBtn.className = 'btn btn-success';
    startBtn.onclick = startCollection;
    
    ModalManager.show('collection-modal');
}

function openCellActionModal(cell) {
    selectedCell = cell;
    const cellStatistics = getCellStatistics(cell.cell_id) || {
        collected_samples: 0,
        target_samples: selectedCampaign.sample_number,
    };

    document.getElementById('action-map-id').textContent = mapData.map_id;
    document.getElementById('action-campaign-id').textContent = selectedCampaign.campaign_id;
    document.getElementById('action-cell-index').textContent = cell.cell_index;
    document.getElementById('action-coord-x').textContent = cell.coord_x;
    document.getElementById('action-coord-y').textContent = cell.coord_y;
    document.getElementById('action-progress').textContent = `${cellStatistics.collected_samples} / ${cellStatistics.target_samples}`;

    const hasSamples = Number(cellStatistics.collected_samples) > 0;

    const collectBtn = document.getElementById('action-collect-btn');
    collectBtn.disabled = hasSamples;
    collectBtn.title = hasSamples ? 'Reset this cell to collect again' : '';

    const resetBtn = document.getElementById('action-reset-btn');
    resetBtn.disabled = !hasSamples;

    const historyBtn = document.getElementById('action-view-history-btn');
    historyBtn.disabled = !hasSamples;

    ModalManager.show('cell-action-modal');
}

function handleActionCollect() {
    if (!selectedCell || !selectedCampaign) {
        return;
    }

    const mqttTopic = document.getElementById('mqtt-topic').value.trim();
    if (!mqttTopic) {
        alert('Please enter MQTT topic');
        return;
    }

    ModalManager.hide('cell-action-modal');
    showCollectionModal(selectedCell);
}

async function handleActionReset() {
    await resetCellData();
}

async function handleActionViewHistory() {
    if (!selectedCell) {
        return;
    }

    ModalManager.hide('cell-action-modal');
    await openCellDetailsModal(selectedCell, getCellStatistics(selectedCell.cell_id));
}

async function openCellDetailsModal(cell, cellStatistics = null) {
    selectedCell = cell;

    const statistics = cellStatistics || getCellStatistics(cell.cell_id) || {
        collected_samples: 0,
        target_samples: selectedCampaign ? selectedCampaign.sample_number : 0,
    };

    document.getElementById('details-map-id').textContent = mapData.map_id;
    document.getElementById('details-campaign-id').textContent = selectedCampaign.campaign_id;
    document.getElementById('details-cell-index').textContent = cell.cell_index;
    document.getElementById('details-coord-x').textContent = cell.coord_x;
    document.getElementById('details-coord-y').textContent = cell.coord_y;
    document.getElementById('details-collected-count').textContent = String(statistics.collected_samples);
    document.getElementById('details-target-count').textContent = String(statistics.target_samples);

    const loading = document.getElementById('cell-details-loading');
    const list = document.getElementById('cell-samples-list');
    loading.classList.remove('hidden');
    list.innerHTML = '';

    ModalManager.show('cell-details-modal');

    try {
        const samples = await API.get(`/api/campaigns/${selectedCampaign.campaign_id}/cells/${cell.cell_id}/fingerprints`);
        loading.classList.add('hidden');

        if (!samples.length) {
            list.innerHTML = `<div class="sample-empty">${i18n.translate('collectData.noSamples')}</div>`;
            return;
        }

        list.innerHTML = samples.map((sample, index) => renderSampleRecord(sample, index)).join('');
    } catch (error) {
        loading.classList.add('hidden');
        list.innerHTML = `<div class="sample-empty">${i18n.translate('msg.error')}: ${escapeHtml(error.message)}</div>`;
    }
}

async function startCollection() {
    const mqttTopic = document.getElementById('mqtt-topic').value.trim();
    const startBtn = document.getElementById('collection-start-btn');
    
    try {
        // Start collection session
        const response = await API.post('/api/data-collection/start', {
            campaign_id: selectedCampaign.campaign_id,
            cell_id: selectedCell.cell_id,
            mqtt_topic: mqttTopic
        });
        
        collectionSessionKey = response.data.session_key;
        
        // Update button
        startBtn.textContent = i18n.translate('collectData.stop');
        startBtn.className = 'btn btn-danger';
        startBtn.onclick = stopCollection;
        
        // Start polling for progress
        collectionInterval = setInterval(updateCollectionProgress, 500);
        
    } catch (error) {
        if (error.status === 409) {
            await loadCampaignStatistics();
            closeCellCollectionModal();
            openCellActionModal(selectedCell);
            return;
        }
        showToast(i18n.translate('msg.error') + ': ' + error.message, 'error');
    }
}

async function stopCollection() {
    try {
        await API.post('/api/data-collection/stop', {
            session_key: collectionSessionKey
        });

        await loadCampaignStatistics();
        
        // Stop polling
        clearInterval(collectionInterval);
        collectionInterval = null;
        collectionSessionKey = null;
        
        // Update button
        const startBtn = document.getElementById('collection-start-btn');
        startBtn.textContent = i18n.translate('collectData.done');
        startBtn.className = 'btn btn-secondary';
        startBtn.onclick = () => ModalManager.hide('collection-modal');
        
        showToast('Data collection completed', 'success');
        
    } catch (error) {
        showToast(i18n.translate('msg.error') + ': ' + error.message, 'error');
    }
}

async function updateCollectionProgress() {
    if (!collectionSessionKey) return;
    
    try {
        const status = await API.get(`/api/data-collection/status/${collectionSessionKey}`);
        const progress = status.sample_count;
        const target = selectedCampaign.sample_number;
        
        document.getElementById('col-progress').textContent = `${progress} / ${target}`;
        
        // Auto-stop when target reached
        if (progress >= target) {
            await stopCollection();
        }
    } catch (error) {
        console.error('Error updating progress:', error);
    }
}

async function resetCellData() {
    if (!selectedCampaign || !selectedCell) {
        return;
    }

    if (!confirm(i18n.translate('collectData.resetConfirm'))) {
        return;
    }

    try {
        await API.delete(`/api/campaigns/${selectedCampaign.campaign_id}/cells/${selectedCell.cell_id}/fingerprints`);
        showToast(i18n.translate('msg.success'), 'success');
        await loadCampaignStatistics();
        ModalManager.hide('cell-action-modal');
        ModalManager.hide('cell-details-modal');
    } catch (error) {
        showToast(i18n.translate('msg.error') + ': ' + error.message, 'error');
    }
}

function closeCellCollectionModal() {
    ModalManager.hide('collection-modal');
}

function formatSampleValue(value) {
    if (value === null || value === undefined) {
        return '—';
    }

    return escapeHtml(String(value));
}

function renderSampleRecord(sample, index) {
    const sections = [
        {
            title: 'WiFi RSSI',
            fields: [
                ['AP 1', sample.wifi_rssi_1],
                ['AP 2', sample.wifi_rssi_2],
                ['AP 3', sample.wifi_rssi_3],
                ['AP 4', sample.wifi_rssi_4],
            ],
        },
        {
            title: 'BLE RSSI',
            fields: [
                ['Beacon 1', sample.ble_rssi_1],
                ['Beacon 2', sample.ble_rssi_2],
                ['Beacon 3', sample.ble_rssi_3],
                ['Beacon 4', sample.ble_rssi_4],
            ],
        },
        {
            title: 'Accelerometer',
            fields: [
                ['X', sample.acc_x],
                ['Y', sample.acc_y],
                ['Z', sample.acc_z],
            ],
        },
        {
            title: 'Gyroscope',
            fields: [
                ['X', sample.gyro_x],
                ['Y', sample.gyro_y],
                ['Z', sample.gyro_z],
            ],
        },
        {
            title: 'Magnetometer',
            fields: [
                ['X', sample.mag_x],
                ['Y', sample.mag_y],
                ['Z', sample.mag_z],
            ],
        },
        {
            title: 'Orientation',
            fields: [
                ['Heading/Yaw', sample.yaw],
                ['Roll', sample.roll],
                ['Pitch', sample.pitch],
            ],
        },
    ];

    return `
        <details class="sample-record" ${index === 0 ? 'open' : ''}>
            <summary>
                <span>${i18n.translate('collectData.sampleLabel')} ${index + 1}</span>
                <span>${i18n.translate('collectData.collectedAt')}: ${formatDate(sample.collected_at)}</span>
            </summary>
            <div class="sample-record-body">
                <div class="sample-sections">
                    ${sections.map(section => `
                        <div class="sample-section">
                            <h4>${section.title}</h4>
                            <div class="sample-field-list">
                                ${section.fields.map(([label, value]) => `
                                    <div class="sample-field">
                                        <span>${label}</span>
                                        <strong>${formatSampleValue(value)}</strong>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        </details>
    `;
}

// ============================================================
// Tooltip
// ============================================================

function showTooltip(event, cell) {
    const tooltip = document.getElementById('tooltip');
    tooltip.innerHTML = `
        <strong>Cell ${cell.cell_index}</strong><br>
        X: ${cell.coord_x}, Y: ${cell.coord_y}
    `;
    tooltip.style.left = (event.clientX + 15) + 'px';
    tooltip.style.top = (event.clientY + 15) + 'px';
    tooltip.classList.add('show');
}

function hideTooltip() {
    const tooltip = document.getElementById('tooltip');
    tooltip.classList.remove('show');
}

// ============================================================
// Event Listeners
// ============================================================

function initEventListeners() {
    // Create campaign button
    document.getElementById('create-campaign-btn').addEventListener('click', showCreateCampaignModal);
    
    // Campaign modal buttons
    document.getElementById('campaign-modal-cancel').addEventListener('click', () => {
        ModalManager.hide('campaign-modal');
    });
    
    document.getElementById('campaign-modal-save').addEventListener('click', createCampaign);

    const actionCollectBtn = document.getElementById('action-collect-btn');
    if (actionCollectBtn) {
        actionCollectBtn.addEventListener('click', handleActionCollect);
    }

    const actionResetBtn = document.getElementById('action-reset-btn');
    if (actionResetBtn) {
        actionResetBtn.addEventListener('click', handleActionReset);
    }

    const actionViewHistoryBtn = document.getElementById('action-view-history-btn');
    if (actionViewHistoryBtn) {
        actionViewHistoryBtn.addEventListener('click', handleActionViewHistory);
    }

    const actionCloseBtn = document.getElementById('action-close-btn');
    if (actionCloseBtn) {
        actionCloseBtn.addEventListener('click', () => {
            ModalManager.hide('cell-action-modal');
        });
    }

    const cellDetailsCloseBtn = document.getElementById('cell-details-close-btn');
    if (cellDetailsCloseBtn) {
        cellDetailsCloseBtn.addEventListener('click', () => {
            ModalManager.hide('cell-details-modal');
        });
    }

    const cellDetailsResetBtn = document.getElementById('cell-details-reset-btn');
    if (cellDetailsResetBtn) {
        cellDetailsResetBtn.addEventListener('click', resetCellData);
    }
}

// ============================================================
// Utility Functions
// ============================================================

function getMapIdFromUrl() {
    const path = window.location.pathname;
    const parts = path.split('/');
    return parseInt(parts[parts.length - 1]);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (collectionInterval) {
        clearInterval(collectionInterval);
    }
    if (collectionSessionKey) {
        // Attempt to stop collection (fire and forget)
        fetch('/api/data-collection/stop', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_key: collectionSessionKey }),
            keepalive: true
        });
    }
});
