/* ============================================================
   Common JavaScript Functions
   - Theme Management
   - Internationalization (English/Vietnamese)
   - Auth State
   - Role-aware Quick Navigation in Settings Panel
   - API Utilities
   ============================================================ */

// ============================================================
// Theme Management
// ============================================================

const ThemeManager = {
    init() {
        const savedTheme = localStorage.getItem('theme') || 'light';
        this.setTheme(savedTheme);

        const themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            if (savedTheme === 'dark') {
                themeToggle.classList.add('active');
            }
            themeToggle.addEventListener('click', () => this.toggleTheme());
        }
    },

    setTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
    },

    toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        this.setTheme(newTheme);

        const themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            themeToggle.classList.toggle('active');
        }
    }
};

// ============================================================
// Internationalization
// ============================================================

const translations = {
    en: {
        'app.title': 'Indoor Positioning System',
        'app.subtitle': 'Map Management & Data Collection',
        'settings': 'Settings',
        'theme': 'Theme',
        'language': 'Language',
        'quickNav': 'Quick Navigation',
        'close': 'Close',
        'save': 'Save',
        'cancel': 'Cancel',
        'delete': 'Delete',
        'edit': 'Edit',
        'create': 'Create',
        'back': 'Back',
        'logout': 'Logout',
        'confirm': 'Confirm',
        'yes': 'Yes',
        'no': 'No',
        'start': 'Start',
        'finish': 'Finish',

        'login.title': 'Login',
        'login.username': 'Username',
        'login.password': 'Password',
        'login.submit': 'Sign In',
        'login.invalid': 'Invalid username or password',

        'home.title': 'Homepage',
        'home.welcome': 'Welcome',
        'home.training': 'Training',
        'home.history': 'History',
        'home.createExercise': 'Create Exercise',
        'home.devices': 'Add Device',
        'home.mapCustomization': 'Map Customization',
        'home.rickroll': 'Rickroll',

        'maps.title': 'Select Map',
        'maps.createNew': 'Create New Map',
        'maps.noMaps': 'No maps available. Create your first map!',
        'maps.use': 'Use',
        'maps.collect': 'Collect Data',
        'maps.edit': 'Edit',
        'maps.delete': 'Delete',
        'maps.deleteConfirm': 'Are you sure you want to delete this map? All related data will be permanently deleted.',

        'createMap.title': 'Create New Map',
        'createMap.mapName': 'Map Name',
        'createMap.lengthX': 'Width (X-axis)',
        'createMap.widthY': 'Height (Y-axis)',
        'createMap.offsetAngles': 'Offset Angle (°)',
        'createMap.offsetAnglesDesc': 'Clockwise map offset angle from true north',
        'createMap.lengthXDesc': 'Number of cells along X-axis',
        'createMap.widthYDesc': 'Number of cells along Y-axis',
        'createMap.submit': 'Create Map',
        'createMap.success': 'Map created successfully',
        'createMap.error': 'Failed to create map',

        'editMap.title': 'Edit Map',
        'editMap.info': 'Map Information',
        'editMap.reset': 'Reset',
        'editMap.save': 'Save Changes',
        'editMap.warning': 'Warning: Editing this map may affect previously collected data.',
        'editMap.continue': 'Continue',
        'editMap.cellDetails': 'Cell Details',
        'editMap.cellIndex': 'Cell Index',
        'editMap.coordinates': 'Coordinates',
        'editMap.passable': 'Passable',
        'editMap.blocked': 'Blocked',
        'editMap.duplicateError': 'Error: Duplicate cell index detected',
        'editMap.saveSuccess': 'Map saved successfully',

        'collectData.title': 'Data Collection',
        'collectData.campaigns': 'Campaigns',
        'collectData.createCampaign': 'New Campaign',
        'collectData.campaignName': 'Campaign Name',
        'collectData.sampleNumber': 'Target Samples',
        'collectData.mqttTopic': 'MQTT Topic',
        'collectData.selectCampaign': 'Select a campaign',
        'collectData.selectedCampaign': 'Selected Campaign',
        'collectData.sampledCells': 'Sampled Passable Cells',
        'collectData.cellActions': 'Cell Actions',
        'collectData.collectData': 'Collect Data',
        'collectData.viewHistory': 'View History',
        'collectData.collected': 'Collected',
        'collectData.cellDetails': 'Cell Data Details',
        'collectData.resetData': 'Reset Data',
        'collectData.resetConfirm': 'Delete all collected data for this cell and campaign?',
        'collectData.noSamples': 'No samples collected for this cell.',
        'collectData.sampleLabel': 'Sample',
        'collectData.collectedAt': 'Collected At',
        'collectData.stop': 'Stop',
        'collectData.done': 'Done',
        'collectData.progress': 'Progress',
        'collectData.samples': 'samples',
        'collectData.collecting': 'Collecting data...',

        'session.title': 'Create Exercise',
        'session.new': 'Create New Exercise',
        'session.name': 'Exercise Name',
        'session.duration': 'Duration (seconds)',
        'session.map': 'Map',
        'session.manage': 'Customize',
        'session.deleteConfirm': 'Delete this exercise and all related fire/history data?',

        'sessionEditor.title': 'Exercise Customization',
        'sessionEditor.timeline': 'Fire Timeline',
        'sessionEditor.addManual': 'Add Fire Manually',
        'sessionEditor.time': 'Fire Time (s)',
        'sessionEditor.level': 'Fire Level',
        'sessionEditor.coordX': 'Coordinate X',
        'sessionEditor.coordY': 'Coordinate Y',

        'device.title': 'Device Management',
        'device.add': 'Add Device',
        'device.name': 'Device Name',
        'device.hexId': 'Device Hex ID',
        'device.waterCapacity': 'Water capacity (-1 = infinite)',
        'device.topicPub': 'Publish Topic',
        'device.topicSub': 'Subscribe Topic',

        'trainingSelect.title': 'Select Training',
        'trainingSelect.map': 'Map',
        'trainingSelect.devices': 'Devices',
        'trainingSelect.algorithm': 'Algorithm',
        'trainingSelect.session': 'Session',
        'trainingSelect.creative': 'Creative Mode',

        'trainingLive.title': 'Realtime Training',
        'trainingLive.coordX': 'Coordinate X',
        'trainingLive.coordY': 'Coordinate Y',
        'trainingLive.speed': 'Speed',
        'trainingLive.valve': 'Valve Open',
        'trainingLive.mode': 'Mode',
        'trainingLive.score': 'Score',
        'trainingLive.duration': 'Training Time',

        'history.title': 'Training History',

        'msg.loading': 'Loading...',
        'msg.saving': 'Saving...',
        'msg.success': 'Operation successful',
        'msg.error': 'An error occurred',
        'msg.helloWorld': 'Hello World! This feature is not yet implemented.',
    },

    vi: {
        'app.title': 'He Thong Dinh Vi Trong Nha',
        'app.subtitle': 'Quan Ly Ban Do & Thu Thap Du Lieu',
        'settings': 'Cai Dat',
        'theme': 'Giao Dien',
        'language': 'Ngon Ngu',
        'quickNav': 'Dieu Huong Nhanh',
        'close': 'Dong',
        'save': 'Luu',
        'cancel': 'Huy',
        'delete': 'Xoa',
        'edit': 'Chinh Sua',
        'create': 'Tao',
        'back': 'Quay Lai',
        'logout': 'Dang Xuat',
        'confirm': 'Xac Nhan',
        'yes': 'Co',
        'no': 'Khong',
        'start': 'Bat Dau',
        'finish': 'Ket Thuc',

        'login.title': 'Dang Nhap',
        'login.username': 'Tai Khoan',
        'login.password': 'Mat Khau',
        'login.submit': 'Dang Nhap',
        'login.invalid': 'Sai tai khoan hoac mat khau',

        'home.title': 'Trang Chu',
        'home.welcome': 'Xin Chao',
        'home.training': 'Huan Luyen',
        'home.history': 'Lich Su',
        'home.createExercise': 'Tao Bai Tap',
        'home.devices': 'Them Thiet Bi',
        'home.mapCustomization': 'Tuy Chinh Ban Do',
        'home.rickroll': 'Rickroll',

        'maps.title': 'Chon Ban Do',
        'maps.createNew': 'Tao Ban Do Moi',
        'maps.noMaps': 'Chua co ban do. Hay tao ban do dau tien',
        'maps.use': 'Su Dung',
        'maps.collect': 'Thu Du Lieu',
        'maps.edit': 'Chinh Sua',
        'maps.delete': 'Xoa',
        'maps.deleteConfirm': 'Ban co chac muon xoa ban do nay? Toan bo du lieu lien quan se bi xoa.',

        'createMap.title': 'Tao Ban Do Moi',
        'createMap.mapName': 'Ten Ban Do',
        'createMap.lengthX': 'Chieu Rong (Truc X)',
        'createMap.widthY': 'Chieu Dai (Truc Y)',
        'createMap.offsetAngles': 'Goc Lech (°)',
        'createMap.offsetAnglesDesc': 'Goc lech ban do theo chieu kim dong ho so voi huong Bac',
        'createMap.lengthXDesc': 'So o theo truc X',
        'createMap.widthYDesc': 'So o theo truc Y',
        'createMap.submit': 'Tao Ban Do',
        'createMap.success': 'Tao ban do thanh cong',
        'createMap.error': 'Tao ban do that bai',

        'editMap.title': 'Chinh Sua Ban Do',
        'editMap.info': 'Thong Tin Ban Do',
        'editMap.reset': 'Dat Lai',
        'editMap.save': 'Luu Thay Doi',
        'editMap.warning': 'Canh bao: Chinh sua ban do co the anh huong den du lieu da thu thap truoc do.',
        'editMap.continue': 'Tiep Tuc',
        'editMap.cellDetails': 'Chi Tiet O',
        'editMap.cellIndex': 'So Thu Tu',
        'editMap.coordinates': 'Toa Do',
        'editMap.passable': 'Di Duoc',
        'editMap.blocked': 'Vat Can',
        'editMap.duplicateError': 'Loi: Phat hien so thu tu o trung lap',
        'editMap.saveSuccess': 'Luu ban do thanh cong',

        'collectData.title': 'Thu Thap Du Lieu',
        'collectData.campaigns': 'Chien Dich',
        'collectData.createCampaign': 'Chien Dich Moi',
        'collectData.campaignName': 'Ten Chien Dich',
        'collectData.sampleNumber': 'So Mau Muc Tieu',
        'collectData.mqttTopic': 'MQTT Topic',
        'collectData.selectCampaign': 'Chon chien dich',
        'collectData.selectedCampaign': 'Chien dich da chon',
        'collectData.sampledCells': 'So o co the di da lay mau',
        'collectData.cellActions': 'Thao Tac O',
        'collectData.collectData': 'Thu Thap Du Lieu',
        'collectData.viewHistory': 'Xem Lich Su',
        'collectData.collected': 'Da thu thap',
        'collectData.cellDetails': 'Chi Tiet Du Lieu O',
        'collectData.resetData': 'Dat Lai Du Lieu',
        'collectData.resetConfirm': 'Xoa toan bo du lieu da thu thap cua o va chien dich nay?',
        'collectData.noSamples': 'O nay chua co mau du lieu nao.',
        'collectData.sampleLabel': 'Mau',
        'collectData.collectedAt': 'Thoi gian thu thap',
        'collectData.stop': 'Dung',
        'collectData.done': 'Xong',
        'collectData.progress': 'Tien Trinh',
        'collectData.samples': 'mau',
        'collectData.collecting': 'Dang thu thap du lieu...',

        'session.title': 'Tao Bai Tap',
        'session.new': 'Tao Bai Tap Moi',
        'session.name': 'Ten Bai Tap',
        'session.duration': 'Thoi Gian (giay)',
        'session.map': 'Ban Do',
        'session.manage': 'Tuy Chinh',
        'session.deleteConfirm': 'Xoa bai tap nay va du lieu ngun lua/lich su lien quan?',

        'sessionEditor.title': 'Tuy Chinh Bai Tap',
        'sessionEditor.timeline': 'Danh Sach Ngon Lua',
        'sessionEditor.addManual': 'Them Ngon Lua Thu Cong',
        'sessionEditor.time': 'Thoi Gian Xuat Hien (s)',
        'sessionEditor.level': 'Cap Do Ngon Lua',
        'sessionEditor.coordX': 'Toa Do X',
        'sessionEditor.coordY': 'Toa Do Y',

        'device.title': 'Quan Ly Thiet Bi',
        'device.add': 'Them Thiet Bi',
        'device.name': 'Ten Thiet Bi',
        'device.hexId': 'Ma Hex Thiet Bi',
        'device.waterCapacity': 'Dung tich nuoc (-1 = vo han)',
        'device.topicPub': 'Topic Gui',
        'device.topicSub': 'Topic Nhan',

        'trainingSelect.title': 'Chon Bai Huan Luyen',
        'trainingSelect.map': 'Ban Do',
        'trainingSelect.devices': 'Thiet Bi',
        'trainingSelect.algorithm': 'Thuat Toan',
        'trainingSelect.session': 'Bai Tap',
        'trainingSelect.creative': 'Che Do Creative',

        'trainingLive.title': 'Huan Luyen Thoi Gian Thuc',
        'trainingLive.coordX': 'Toa Do X',
        'trainingLive.coordY': 'Toa Do Y',
        'trainingLive.speed': 'Van Toc',
        'trainingLive.valve': 'Do Mo Van',
        'trainingLive.mode': 'Mode',
        'trainingLive.score': 'Diem',
        'trainingLive.duration': 'Thoi Gian Huan Luyen',

        'history.title': 'Lich Su Huan Luyen',

        'msg.loading': 'Dang tai...',
        'msg.saving': 'Dang luu...',
        'msg.success': 'Thao tac thanh cong',
        'msg.error': 'Da xay ra loi',
        'msg.helloWorld': 'Tinh nang nay chua duoc trien khai',
    }
};

const i18n = {
    currentLang: 'en',

    init() {
        const savedLang = localStorage.getItem('language') || 'en';
        this.setLanguage(savedLang);

        const langRadios = document.querySelectorAll('input[name="language"]');
        langRadios.forEach(radio => {
            if (radio.value === savedLang) {
                radio.checked = true;
            }
            radio.addEventListener('change', (e) => {
                if (e.target.checked) {
                    this.setLanguage(e.target.value);
                }
            });
        });
    },

    setLanguage(lang) {
        this.currentLang = lang;
        localStorage.setItem('language', lang);
        this.updatePageText();
    },

    translate(key) {
        return translations[this.currentLang][key] || key;
    },

    updatePageText() {
        document.querySelectorAll('[data-i18n]').forEach(element => {
            const key = element.getAttribute('data-i18n');
            element.textContent = this.translate(key);
        });

        document.querySelectorAll('[data-i18n-placeholder]').forEach(element => {
            const key = element.getAttribute('data-i18n-placeholder');
            element.placeholder = this.translate(key);
        });
    }
};

// ============================================================
// Auth Management
// ============================================================

const AuthManager = {
    setAuth(authData) {
        localStorage.setItem('auth', JSON.stringify(authData));
    },

    getAuth() {
        try {
            return JSON.parse(localStorage.getItem('auth') || 'null');
        } catch (e) {
            return null;
        }
    },

    clearAuth() {
        localStorage.removeItem('auth');
    },

    isLoggedIn() {
        return !!this.getAuth();
    },

    roleId() {
        const auth = this.getAuth();
        return auth ? auth.role_id : null;
    },

    username() {
        const auth = this.getAuth();
        return auth ? auth.username : null;
    },

    requireAuth() {
        const pageMode = document.body.getAttribute('data-auth-page');
        if (pageMode === 'login') {
            return;
        }

        if (!this.isLoggedIn()) {
            window.location.href = '/login';
        }
    },

    ensureAllowed(allowedRoles) {
        const roleId = this.roleId();
        if (!roleId || !allowedRoles.includes(roleId)) {
            showToast('Permission denied', 'error');
            window.location.href = '/home';
            return false;
        }
        return true;
    },

    logout() {
        this.clearAuth();
        window.location.href = '/login';
    }
};

window.AuthManager = AuthManager;

// ============================================================
// Modal Management
// ============================================================

const ModalManager = {
    show(modalId) {
        const modal = document.getElementById(modalId);
        if (!modal) {
            return;
        }
        modal.classList.add('show');

        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.hide(modalId);
            }
        });
    },

    hide(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('show');
        }
    }
};

// ============================================================
// API Helper
// ============================================================

const API = {
    async request(url, options = {}) {
        try {
            const response = await fetch(url, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });

            if (!response.ok) {
                const error = await response.json();
                console.error('=== API Response Error ===');
                console.error('Status:', response.status);
                console.error('Error object:', JSON.stringify(error, null, 2));
                console.error('Error detail:', error.detail);

                let errorMessage = 'Request failed';
                if (error.detail) {
                    if (typeof error.detail === 'string') {
                        errorMessage = error.detail;
                    } else if (Array.isArray(error.detail)) {
                        const errors = error.detail.map(e => {
                            const location = Array.isArray(e.loc) ? e.loc.join(' -> ') : String(e.loc);
                            return `  * ${location}: ${e.msg}`;
                        }).join('\n');
                        errorMessage = `Validation errors:\n${errors}`;
                    } else {
                        errorMessage = JSON.stringify(error.detail);
                    }
                }
                const apiError = new Error(errorMessage);
                apiError.status = response.status;
                apiError.payload = error;
                throw apiError;
            }

            return await response.json();
        } catch (error) {
            console.error('=== API Error ===');
            console.error('Error message:', error.message);
            console.error('Error stack:', error.stack);
            throw error;
        }
    },

    get(url) {
        return this.request(url);
    },

    post(url, data) {
        return this.request(url, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    put(url, data) {
        return this.request(url, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },

    delete(url) {
        return this.request(url, {
            method: 'DELETE'
        });
    }
};

// ============================================================
// Utility
// ============================================================

function showToast(message, type = 'success') {
    if (type === 'error') {
        alert(`Error: ${message}`);
        return;
    }
    alert(message);
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Ảnh nhiều định dạng: thử lần lượt các URL trong data-fallbacks (vd .jpg rồi ảnh dự
// phòng) khi src hiện tại lỗi; hết danh sách thì ẩn ảnh. Dùng: src="...png"
// data-fallbacks='["...jpg","...lililaho.png"]' onerror="imgFallback(this)".
function imgFallback(img) {
    let list = [];
    try { list = JSON.parse(img.dataset.fallbacks || '[]'); } catch (e) { list = []; }
    if (list.length) {
        img.src = list.shift();
        img.dataset.fallbacks = JSON.stringify(list);
    } else {
        img.onerror = null;
        img.style.display = 'none';
    }
}
window.imgFallback = imgFallback;

// Hình học cung phun lấy từ backend (extinguish.SPRAY) để VẼ nón khớp vùng dập thật.
// Trả {spread:{halfAngle,maxRadiusM}, jet:{halfAngle,maxRadiusM}} hoặc null nếu lỗi
// (trang giữ giá trị mặc định nội bộ làm dự phòng).
async function fetchSprayConfig() {
    try {
        const cfg = await API.get('/api/sim/spray-config');
        if (!cfg || !cfg.spread || !cfg.jet) return null;
        const map = (c) => ({ halfAngle: Number(c.half_angle_deg), maxRadiusM: Number(c.max_radius_m) });
        return { spread: map(cfg.spread), jet: map(cfg.jet) };
    } catch (e) {
        return null;
    }
}
window.fetchSprayConfig = fetchSprayConfig;

function getRoleBasedMenuItems(roleId) {
    const all = [
        { path: '/home', key: 'home.title', roles: [1, 2, 3] },
        { path: '/training-select', key: 'home.training', roles: [1, 2, 3] },
        { path: '/history', key: 'home.history', roles: [1, 2, 3] },
        { path: '/training-sessions', key: 'home.createExercise', roles: [1, 2] },
        { path: '/devices', key: 'home.devices', roles: [1, 2] },
        { path: '/map-customization', key: 'home.mapCustomization', roles: [1] },
        { path: '/rickroll', key: 'home.rickroll', roles: [1] },
    ];

    return all.filter(item => item.roles.includes(roleId));
}

function initRoleQuickNavigation() {
    const quickNav = document.getElementById('settings-quick-nav');
    if (!quickNav) {
        return;
    }

    const auth = AuthManager.getAuth();
    if (!auth) {
        quickNav.innerHTML = '';
        return;
    }

    const menuItems = getRoleBasedMenuItems(auth.role_id);
    quickNav.innerHTML = menuItems.map(item => {
        const active = window.location.pathname === item.path ? 'active' : '';
        return `<a class="quick-link ${active}" href="${item.path}" data-i18n="${item.key}">${i18n.translate(item.key)}</a>`;
    }).join('');

    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.classList.remove('hidden');
        logoutBtn.onclick = () => AuthManager.logout();
    }
}

// ============================================================
// Settings Panel
// ============================================================

function initSettingsPanel() {
    const settingsBtn = document.getElementById('settings-btn');
    const settingsPanel = document.getElementById('settings-panel');
    const closeSettingsBtn = document.getElementById('close-settings');

    if (settingsBtn && settingsPanel) {
        settingsBtn.addEventListener('click', () => {
            settingsPanel.classList.add('open');
        });
    }

    if (closeSettingsBtn && settingsPanel) {
        closeSettingsBtn.addEventListener('click', () => {
            settingsPanel.classList.remove('open');
        });
    }

    document.addEventListener('click', (e) => {
        if (
            settingsPanel &&
            !settingsPanel.contains(e.target) &&
            !settingsBtn?.contains(e.target) &&
            settingsPanel.classList.contains('open')
        ) {
            settingsPanel.classList.remove('open');
        }
    });
}

// ============================================================
// Initialize
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
    AuthManager.requireAuth();
    ThemeManager.init();
    i18n.init();
    initSettingsPanel();
    initRoleQuickNavigation();
});
