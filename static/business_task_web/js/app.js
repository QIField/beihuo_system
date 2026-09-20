// 共享菜单配置
const menuItems = [
    {
        name: '仪表盘',
        href: 'index.html',
        active: location.pathname.endsWith('index.html') || location.pathname.endsWith('/'),
        icon: '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"></path></svg>'
    },
    {
        name: '任务管理',
        href: 'tasks.html',
        active: location.pathname.endsWith('tasks.html'),
        icon: '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"></path></svg>'
    },
    {
        name: '用户绑定',
        href: 'users.html',
        active: location.pathname.endsWith('users.html'),
        icon: '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"></path></svg>'
    }
];

const API_BASE = '/new/api';

function handleApiError(res) {
    if (res.status === 401) {
        window.location.href = '/login';
        return;
    }
    console.error('API error', res);
}

async function apiGet(path) {
    const res = await fetch(API_BASE + path, { credentials: 'same-origin' });
    if (!res.ok) {
        handleApiError(res);
        throw new Error('request failed');
    }
    return res.json();
}

async function apiPost(path, body) {
    const res = await fetch(API_BASE + path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify(body),
    });
    if (!res.ok) {
        handleApiError(res);
        throw new Error('request failed');
    }
    return res.json();
}

function formatTaskStatus(status) {
    return status === 1 ? '已完成' : '未完成';
}

function formatSyncStatus(sync) {
    if (sync === 'synced') return '已同步';
    if (sync === 'no_binding') return '未绑定';
    return '未同步';
}

function formatDateTime(value) {
    if (!value) return '-';
    const d = new Date(value);
    if (isNaN(d.getTime())) return value;
    const pad = n => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function formatTimeAgo(value) {
    if (!value) return '-';
    const d = new Date(value);
    if (isNaN(d.getTime())) return value;
    const now = new Date();
    const diff = Math.floor((now - d) / 1000);
    if (diff < 60) return '刚刚';
    if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`;
    return `${Math.floor(diff / 86400)} 天前`;
}

document.addEventListener('alpine:init', () => {
    Alpine.data('app', () => ({
        sidebarOpen: false,
        menu: menuItems,
        stats: { total: 0, pending: 0, completed: 0, synced: 0 },
        recentTasks: [],
        init() {
            this.loadStats();
            this.loadRecentTasks();
        },
        async loadStats() {
            try {
                const res = await apiGet('/business-tasks/statistics');
                if (res.code === 200) {
                    const data = res.data || {};
                    const total = data.total || 0;
                    const completed = data.completed || 0;
                    const boundUsers = data.bound_users || 0;
                    const totalUsers = data.total_users || 0;
                    data.completion_rate = total > 0 ? (completed / total * 100).toFixed(1) + '%' : '0%';
                    data.binding_rate = totalUsers > 0 ? (boundUsers / totalUsers * 100).toFixed(1) + '%' : '0%';
                    this.stats = data;
                }
            } catch (e) {
                console.error('loadStats error', e);
            }
        },
        async loadRecentTasks() {
            try {
                const res = await apiGet('/business-tasks/list?page_size=5');
                if (res.code === 200) {
                    this.recentTasks = (res.data.list || []).map(t => ({
                        id: t.id,
                        title: t.title,
                        assignee: t.assignee_name || '',
                        time: formatTimeAgo(t.created_at),
                        status: formatTaskStatus(t.status)
                    }));
                }
            } catch (e) {
                console.error('loadRecentTasks error', e);
            }
        }
    }));
});
