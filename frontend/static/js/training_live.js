let runData = null;
let runState = null;
let mapData = null;
let mapCells = [];
let activeTimer = null;
let countdownTimer = null;
let trainingStarted = false;
let countdownInProgress = false;
let elapsedSeconds = 0;

function readRunData() {
    const raw = sessionStorage.getItem('trainingRun');
    if (!raw) {
        return null;
    }
    try {
        return JSON.parse(raw);
    } catch (e) {
        return null;
    }
}

async function loadRunState(trainingRunId) {
    runState = await API.get(`/api/training/${trainingRunId}`);
    mapData = await API.get(`/api/maps/${runState.map_id}`);
    mapCells = await API.get(`/api/maps/${runState.map_id}/cells`);
}

function renderMap() {
    const grid = document.getElementById('live-map-grid');
    grid.style.gridTemplateColumns = `repeat(${mapData.length_x}, 40px)`;
    grid.style.gridTemplateRows = `repeat(${mapData.width_y}, 40px)`;

    const fireMap = {};
    if (trainingStarted) {
        const elapsed = elapsedSeconds;
        (runState.fires || []).forEach(fire => {
            if (fire.fire_time_seconds <= elapsed) {
                fireMap[`${fire.coord_x}_${fire.coord_y}`] = fire;
            }
        });
    }

    const sorted = [...mapCells].sort((a, b) => {
        if (b.coord_y !== a.coord_y) {
            return b.coord_y - a.coord_y;
        }
        return a.coord_x - b.coord_x;
    });

    grid.innerHTML = '';
    sorted.forEach(cell => {
        const cellDiv = document.createElement('div');
        cellDiv.className = `map-cell ${cell.is_passable ? 'passable' : 'blocked'}`;

        const fire = fireMap[`${cell.coord_x}_${cell.coord_y}`];
        if (fire) {
            const marker = document.createElement('div');
            marker.className = 'fire-marker';
            marker.style.backgroundImage = 'url(/img/test_img/fire.jpg)';
            marker.textContent = String(fire.fire_level);
            cellDiv.appendChild(marker);
        }

        cellDiv.addEventListener('mouseenter', () => {
            document.getElementById('info-x').textContent = String(cell.coord_x);
            document.getElementById('info-y').textContent = String(cell.coord_y);
        });

        grid.appendChild(cellDiv);
    });
}

function setSessionInfo() {
    const label = runData.session ? `${runData.session.session_name} (ID: ${runData.session.session_id})` : 'Creative';
    document.getElementById('live-session-name').textContent = label;

    if (runData.session && runData.session.duration_seconds) {
        document.getElementById('live-remaining').textContent = `${runData.session.duration_seconds}s`;
    } else {
        document.getElementById('live-remaining').textContent = '--';
    }
}

function updateTimersDisplay() {
    document.getElementById('live-elapsed').textContent = String(elapsedSeconds);

    if (runData.session && runData.session.duration_seconds) {
        const remaining = Math.max(0, runData.session.duration_seconds - elapsedSeconds);
        document.getElementById('live-remaining').textContent = `${remaining}s`;
    } else {
        document.getElementById('live-remaining').textContent = '--';
    }
}

function showFinishPopup() {
    ModalManager.show('finish-modal');
}

async function finishTraining(manual = false) {
    if (countdownTimer) {
        clearInterval(countdownTimer);
        countdownTimer = null;
    }
    if (activeTimer) {
        clearInterval(activeTimer);
        activeTimer = null;
    }

    const response = await API.post('/api/training/finish', {
        training_run_id: runData.training_run_id,
        score: parseInt(document.getElementById('live-score').textContent),
    });

    trainingStarted = false;
    elapsedSeconds = 0;
    document.getElementById('live-start-btn').textContent = i18n.translate('start');
    document.getElementById('live-start-btn').className = 'btn btn-success';
    document.getElementById('live-start-btn').disabled = false;
    document.getElementById('send-map-btn').disabled = false;

    updateTimersDisplay();
    showFinishPopup();
    renderMap();

    return response;
}

async function startActiveTraining() {
    await API.post(`/api/training/${runData.training_run_id}/start`);

    trainingStarted = true;
    countdownInProgress = false;
    document.getElementById('live-start-btn').textContent = i18n.translate('finish');
    document.getElementById('live-start-btn').className = 'btn btn-danger';
    document.getElementById('live-start-btn').disabled = false;

    activeTimer = setInterval(() => {
        elapsedSeconds += 1;
        updateTimersDisplay();
        renderMap();

        if (runData.session && elapsedSeconds >= runData.session.duration_seconds) {
            finishTraining(false).catch(err => showToast(err.message, 'error'));
        }
    }, 1000);
}

function startTrainingFlow() {
    if (trainingStarted) {
        finishTraining(true).catch(err => showToast(err.message, 'error'));
        return;
    }

    if (countdownInProgress) {
        return;
    }

    countdownInProgress = true;
    document.getElementById('live-start-btn').disabled = true;
    document.getElementById('send-map-btn').disabled = true;

    let countdown = 3;
    elapsedSeconds = 0;
    updateTimersDisplay();
    document.getElementById('live-score').textContent = '0';
    document.getElementById('countdown-number').textContent = String(countdown);
    ModalManager.show('countdown-modal');

    countdownTimer = setInterval(() => {
        countdown -= 1;
        document.getElementById('countdown-number').textContent = String(Math.max(0, countdown));
        if (countdown <= 0) {
            clearInterval(countdownTimer);
            countdownTimer = null;
            ModalManager.hide('countdown-modal');

            startActiveTraining().catch(error => {
                countdownInProgress = false;
                document.getElementById('live-start-btn').disabled = false;
                document.getElementById('send-map-btn').disabled = false;
                showToast(error.message, 'error');
            });
        }
    }, 1000);
}

async function sendMapInfo() {
    const btn = document.getElementById('send-map-btn');
    if (btn) btn.disabled = true;
    try {
        const result = await API.post(`/api/maps/${runData.map_id}/send-map-mqtt`, {});
        showToast(`Map info sent (${result.cells_count} cells)`, 'success');
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        if (!trainingStarted && !countdownInProgress) {
            if (btn) btn.disabled = false;
        }
    }
}

document.addEventListener('DOMContentLoaded', async () => {
    runData = readRunData();
    if (!runData || !runData.training_run_id) {
        showToast('No training run data found', 'error');
        window.location.href = '/training-select';
        return;
    }

    try {
        await loadRunState(runData.training_run_id);
        setSessionInfo();
        updateTimersDisplay();
        renderMap();

        const startButton = document.getElementById('live-start-btn');
        if (startButton) {
            startButton.addEventListener('click', startTrainingFlow);
        }

        const sendMapButton = document.getElementById('send-map-btn');
        if (sendMapButton) {
            sendMapButton.addEventListener('click', sendMapInfo);
        }

        const finishButton = document.getElementById('finish-modal-ok');
        if (finishButton) {
            finishButton.addEventListener('click', () => {
                ModalManager.hide('finish-modal');
            });
        }
    } catch (error) {
        showToast(error.message, 'error');
    }
});
