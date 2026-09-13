document.addEventListener('alpine:init', () => {
    Alpine.data('taskApp', () => ({
        sidebarOpen: false,
        menu: menuItems,
        openModal: false,
        loading: false,
        filters: { keyword: '', status: '' },
        form: { title: '', content: '', selected: [], deadline: '' },
        users: [],
        tasks: [],
        page: 1,
        pageSize: 10,
        total: 0,
        totalPages: 1,

        init() {
            this.loadUsers();
            this.search();
        },

        async loadUsers() {
            try {
                const res = await apiGet('/user-lark-mappings/users?limit=200');
                if (res.code === 200) {
                    this.users = res.data || [];
                }
            } catch (e) {
                console.error('loadUsers error', e);
            }
        },

        statusToCode(status) {
            if (status === 'pending') return 0;
            if (status === 'done') return 1;
            return '';
        },

        async search() {
            this.loading = true;
            try {
                const params = new URLSearchParams();
                params.set('page', this.page);
                params.set('page_size', this.pageSize);
                if (this.filters.keyword) params.set('keyword', this.filters.keyword);
                const statusCode = this.statusToCode(this.filters.status);
                if (statusCode !== '') params.set('status', statusCode);

                const res = await apiGet('/business-tasks/list?' + params.toString());
                if (res.code === 200) {
                    this.total = res.data.total || 0;
                    this.totalPages = Math.max(1, Math.ceil(this.total / this.pageSize));
                    this.tasks = (res.data.list || []).map(t => ({
                        id: t.id,
                        title: t.title,
                        content: t.content || '',
                        assignee: t.assignee_name || '',
                        deadline: formatDateTime(t.deadline),
                        status: formatTaskStatus(t.status),
                        sync: formatSyncStatus(t.lark_sync_status),
                        rawStatus: t.status,
                        larkTaskGuid: t.lark_task_guid,
                    }));
                }
            } catch (e) {
                console.error('search error', e);
            } finally {
                this.loading = false;
            }
        },

        resetFilters() {
            this.filters = { keyword: '', status: '' };
            this.page = 1;
            this.search();
        },

        goPage(p) {
            if (p < 1 || p > this.totalPages) return;
            this.page = p;
            this.search();
        },

        formatDeadlineForBackend(value) {
            if (!value) return null;
            return value.replace('T', ' ') + ':00';
        },

        async saveTask() {
            if (!this.form.title || this.form.selected.length === 0) {
                alert('请填写任务标题并选择负责人');
                return;
            }
            try {
                let res;
                if (this.form.selected.length === 1) {
                    res = await apiPost('/business-tasks/create', {
                        title: this.form.title,
                        content: this.form.content,
                        assignee_id: Number(this.form.selected[0]),
                        deadline: this.formatDeadlineForBackend(this.form.deadline),
                    });
                } else {
                    const tasks = this.form.selected.map(uid => ({
                        title: this.form.title,
                        content: this.form.content,
                        assignee_id: Number(uid),
                        deadline: this.formatDeadlineForBackend(this.form.deadline),
                    }));
                    res = await apiPost('/business-tasks/batch-create', { tasks });
                }
                if (res.code === 200) {
                    this.openModal = false;
                    this.form = { title: '', content: '', selected: [], deadline: '' };
                    this.page = 1;
                    this.search();
                } else {
                    alert(res.msg || '创建失败');
                }
            } catch (e) {
                console.error('saveTask error', e);
            }
        },

        async toggleStatus(task) {
            const nextStatus = task.rawStatus === 0 ? 1 : 0;
            try {
                const res = await apiPost('/business-tasks/update-status', {
                    id: task.id,
                    status: nextStatus,
                });
                if (res.code === 200) {
                    this.search();
                } else {
                    alert(res.msg || '状态更新失败');
                }
            } catch (e) {
                console.error('toggleStatus error', e);
            }
        }
    }));
});
