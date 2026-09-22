document.addEventListener('alpine:init', () => {
    Alpine.data('taskApp', () => ({
        sidebarOpen: false,
        menu: menuItems,
        openModal: false,
        loading: false,
        filters: { keyword: '', status: '' },
        form: { title: '', content: '', selected: [], start_time: '', deadline: '', subtasks: [] },
        detailTask: null,
        subtasks: [],
        newSubtaskTitle: '',
        subtaskLoading: false,
        users: [],
        tasks: [],
        page: 1,
        pageSize: 10,
        total: 0,
        totalPages: 1,

        init() {
            this.loadUsers();
            this.search();
            this.setupWebSocketListener();
        },

        setupWebSocketListener() {
            window.addEventListener('business_data_update', (e) => {
                const payload = e.detail || {};
                if (payload.data_type === 'business_task' && payload.action === 'update') {
                    console.log('[任务列表] 收到飞书状态同步通知, record_id=', payload.record_id);
                    this.search();
                }
                if (payload.data_type === 'business_subtask' && payload.action === 'update') {
                    const taskId = Number((payload.data || {}).task_id || payload.record_id);
                    console.log('[子任务] 收到飞书状态同步通知, task_id=', taskId);
                    if (this.detailTask && Number(this.detailTask.id) === taskId) {
                        this.loadSubtasks(taskId);
                    }
                }
            });
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
                        start_time: formatDateTime(t.start_time),
                        deadline: formatDateTime(t.deadline),
                        status: formatTaskStatus(t.status),
                        sync: formatSyncStatus(t.lark_sync_status),
                        rawStatus: t.status,
                        rawSync: t.lark_sync_status,
                        larkTaskGuid: t.lark_task_guid,
                    }));
                }
            } catch (e) {
                console.error('search error', e);
            } finally {
                this.loading = false;
            }
        },

        pollSync(attemptsLeft) {
            if (attemptsLeft <= 0) return;
            const hasPending = this.tasks.some(t => t.rawSync === 'not_synced');
            if (!hasPending) return;

            setTimeout(async () => {
                await this.search();
                this.pollSync(attemptsLeft - 1);
            }, 2000);
        },

        resetFilters() {
            this.filters = { keyword: '', status: '' };
            this.page = 1;
            this.search();
        },

        searchWithReset() {
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

        getDefaultStartTime() {
            const now = new Date();
            now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
            return now.toISOString().slice(0, 16);
        },

        openCreateModal() {
            this.form = {
                title: '', content: '', selected: [],
                start_time: this.getDefaultStartTime(), deadline: '', subtasks: [],
            };
            this.openModal = true;
        },

        addSubtaskRow() {
            this.form.subtasks.push({ title: '' });
        },

        removeSubtaskRow(index) {
            this.form.subtasks.splice(index, 1);
        },

        collectSubtaskTitles() {
            return this.form.subtasks
                .map(st => (st.title || '').trim())
                .filter(Boolean);
        },

        async openDetail(task) {
            this.detailTask = task;
            this.subtasks = [];
            this.newSubtaskTitle = '';
            try {
                const res = await apiGet('/business-tasks/detail?id=' + task.id);
                if (res.code === 200 && res.data) {
                    const t = res.data;
                    this.detailTask = {
                        id: t.id,
                        title: t.title,
                        content: t.content || '',
                        assignee: t.assignee_name || '',
                        start_time: formatDateTime(t.start_time),
                        deadline: formatDateTime(t.deadline),
                        status: formatTaskStatus(t.status),
                        sync: formatSyncStatus(t.lark_sync_status),
                    };
                    this.subtasks = t.subtasks || [];
                }
            } catch (e) {
                console.error('openDetail error', e);
            }
        },

        async loadSubtasks(taskId) {
            try {
                const res = await apiGet('/business-tasks/subtasks/list?task_id=' + taskId);
                if (res.code === 200) {
                    this.subtasks = res.data || [];
                }
            } catch (e) {
                console.error('loadSubtasks error', e);
            }
        },

        closeDetail() {
            this.detailTask = null;
            this.subtasks = [];
            this.newSubtaskTitle = '';
        },

        subtaskProgressText() {
            const total = this.subtasks.length;
            const done = this.subtasks.filter(st => st.status === 1).length;
            return total === 0 ? '' : `${done} / ${total}`;
        },

        async addSubtask() {
            const title = (this.newSubtaskTitle || '').trim();
            if (!title) {
                alert('请输入子任务标题');
                return;
            }
            this.subtaskLoading = true;
            try {
                const res = await apiPost('/business-tasks/subtasks/create', {
                    task_id: Number(this.detailTask.id),
                    title: title,
                });
                if (res.code === 200) {
                    this.newSubtaskTitle = '';
                    await this.loadSubtasks(this.detailTask.id);
                } else {
                    alert(res.msg || '添加失败');
                }
            } catch (e) {
                console.error('addSubtask error', e);
            } finally {
                this.subtaskLoading = false;
            }
        },

        async toggleSubtask(st) {
            const nextStatus = st.status === 1 ? 0 : 1;
            try {
                const res = await apiPost('/business-tasks/subtasks/update-status', {
                    id: st.id,
                    status: nextStatus,
                });
                if (res.code === 200) {
                    await this.loadSubtasks(this.detailTask.id);
                } else {
                    alert(res.msg || '状态更新失败');
                }
            } catch (e) {
                console.error('toggleSubtask error', e);
            }
        },

        async removeSubtask(st) {
            if (!confirm('确定删除该子任务吗？飞书侧子任务也会同步删除。')) return;
            try {
                const res = await apiPost('/business-tasks/subtasks/delete', { id: st.id });
                if (res.code === 200) {
                    await this.loadSubtasks(this.detailTask.id);
                } else {
                    alert(res.msg || '删除失败');
                }
            } catch (e) {
                console.error('removeSubtask error', e);
            }
        },

        async saveTask() {
            if (!this.form.title || this.form.selected.length === 0) {
                alert('请填写任务标题并选择负责人');
                return;
            }
            const subtaskTitles = this.collectSubtaskTitles();
            try {
                let res;
                if (this.form.selected.length === 1) {
                    res = await apiPost('/business-tasks/create', {
                        title: this.form.title,
                        content: this.form.content,
                        assignee_id: Number(this.form.selected[0]),
                        start_time: this.formatDeadlineForBackend(this.form.start_time),
                        deadline: this.formatDeadlineForBackend(this.form.deadline),
                        subtasks: subtaskTitles,
                    });
                } else {
                    const tasks = this.form.selected.map(uid => ({
                        title: this.form.title,
                        content: this.form.content,
                        assignee_id: Number(uid),
                        start_time: this.formatDeadlineForBackend(this.form.start_time),
                        deadline: this.formatDeadlineForBackend(this.form.deadline),
                        subtasks: subtaskTitles,
                    }));
                    res = await apiPost('/business-tasks/batch-create', { tasks });
                }
                if (res.code === 200) {
                    this.openModal = false;
                    this.form = {
                        title: '', content: '', selected: [],
                        start_time: '', deadline: '', subtasks: [],
                    };
                    this.page = 1;
                    await this.search();
                    this.pollSync(3);
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
