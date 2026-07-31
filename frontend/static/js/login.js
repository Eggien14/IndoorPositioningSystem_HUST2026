document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('login-form');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = document.getElementById('username').value.trim();
        const password = document.getElementById('password').value.trim();

        if (!username || !password) {
            showToast('Username and password are required', 'error');
            return;
        }

        try {
            const response = await API.post('/api/auth/login', { username, password });
            AuthManager.setAuth(response);
            window.location.href = '/home';
        } catch (error) {
            const errorMessage = (error && error.message) ? error.message : '';
            if (errorMessage.toLowerCase().includes('invalid username or password')) {
                showToast(i18n.translate('login.invalid'), 'error');
            } else if (errorMessage.toLowerCase().includes('failed to fetch')) {
                showToast('Cannot connect to server. Please restart server and try again.', 'error');
            } else {
                showToast(errorMessage || i18n.translate('msg.error'), 'error');
            }
        }
    });
});
