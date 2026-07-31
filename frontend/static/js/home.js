function buildActions(roleId) {
    const actions = [
        { roles: [1, 2, 3], key: 'home.training', path: '/training-select', desc: 'Start training and run realtime mode.' },
        { roles: [1, 2, 3], key: 'home.history', path: '/history', desc: 'View all session history records.' },
        { roles: [1, 2], key: 'home.createExercise', path: '/training-sessions', desc: 'Create sessions and customize fires.' },
        { roles: [1, 2], key: 'home.devices', path: '/devices', desc: 'Create, update, and delete devices.' },
        { roles: [1], key: 'home.mapCustomization', path: '/map-customization', desc: 'Open existing map customization module.' },
        { roles: [1], key: 'home.rickroll', path: '/rickroll', desc: 'Admin-only sandbox page.' },
    ];

    return actions.filter(action => action.roles.includes(roleId));
}

document.addEventListener('DOMContentLoaded', () => {
    const auth = AuthManager.getAuth();
    if (!auth) {
        return;
    }

    document.getElementById('welcome-user').textContent = `${auth.username} (${auth.role_name})`;

    const actions = buildActions(auth.role_id);
    const homeActions = document.getElementById('home-actions');
    homeActions.innerHTML = actions.map(action => `
        <a class="card home-action" href="${action.path}">
            <h3 data-i18n="${action.key}">${i18n.translate(action.key)}</h3>
            <p style="color: var(--text-secondary);">${action.desc}</p>
        </a>
    `).join('');

    i18n.updatePageText();
});
