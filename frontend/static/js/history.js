async function loadHistory() {
    const rows = await API.get('/api/history');
    const body = document.getElementById('history-body');

    if (!rows.length) {
        body.innerHTML = '<tr><td colspan="7">No history found.</td></tr>';
        return;
    }

    body.innerHTML = rows.map(row => `
        <tr>
            <td>${row.session_history_id}</td>
            <td>${escapeHtml(row.username)}</td>
            <td>${escapeHtml(row.device_name || String(row.device_id))}</td>
            <td>${escapeHtml(row.session_name || String(row.session_id))}</td>
            <td>${row.completion_seconds}</td>
            <td>${row.score}</td>
            <td>${formatDate(row.completed_at)}</td>
        </tr>
    `).join('');
}

document.addEventListener('DOMContentLoaded', async () => {
    if (!AuthManager.ensureAllowed([1, 2, 3])) {
        return;
    }

    try {
        await loadHistory();
    } catch (error) {
        showToast(error.message, 'error');
    }
});
