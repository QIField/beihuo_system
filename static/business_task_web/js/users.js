document.addEventListener('alpine:init', () => {
    Alpine.data('userApp', () => ({
        sidebarOpen: false,
        menu: menuItems,
        openModal: false,
        modalMode: 'create',
        modalTitle: '新增绑定',
        userKeyword: '',
        selectedUser: null,
        binding: false,
        refreshing: false,
        selectedUserIds: [],
        selectedMappingIds: [],
        form: { id: null, userId: '', userName: '', mobile: '', email: '', openId: '' },
        candidates: [],
        mappings: [],

        init() {
            this.loadCandidates();
            this.loadMappings();
        },

        async loadCandidates() {
            try {
                const res = await apiGet('/user-lark-mappings/candidates');
                if (res.code === 200) {
                    this.candidates = (res.data || []).map(u => ({
                        id: u.id,
                        name: u.username,
                        dept: u.department || '-',
                        store: u.store || '-',
                        mobile: this._maskMobile(u.mobile),
                        email: u.email || '',
                        rawMobile: u.mobile || '',
                    }));
                }
            } catch (e) {
                console.error('loadCandidates error', e);
            }
        },

        async loadMappings() {
            try {
                const res = await apiGet('/user-lark-mappings/list?page_size=200');
                if (res.code === 200) {
                    this.mappings = (res.data.list || []).map(m => ({
                        id: m.id,
                        userId: m.user_id,
                        name: m.username || '-',
                        dept: m.department || '-',
                        store: m.store || '-',
                        openId: m.lark_open_id,
                        status: m.status === 1 ? '有效' : '无效',
                        mobile: this._maskMobile(m.mobile),
                        email: m.email || '',
                        rawMobile: m.mobile || '',
                    }));
                }
            } catch (e) {
                console.error('loadMappings error', e);
            }
        },

        get unboundUsers() {
            const keyword = this.userKeyword.trim();
            if (!keyword) return this.candidates;
            return this.candidates.filter(u => u.name.includes(keyword));
        },

        get isAllSelected() {
            return this.unboundUsers.length > 0 && this.unboundUsers.every(u => this.selectedUserIds.includes(u.id));
        },

        get isAllMappingsSelected() {
            return this.mappings.length > 0 && this.mappings.every(m => this.selectedMappingIds.includes(m.id));
        },

        toggleSelect(userId) {
            const idx = this.selectedUserIds.indexOf(userId);
            if (idx >= 0) {
                this.selectedUserIds.splice(idx, 1);
            } else {
                this.selectedUserIds.push(userId);
            }
        },

        toggleSelectAll() {
            if (this.isAllSelected) {
                this.unboundUsers.forEach(u => {
                    const idx = this.selectedUserIds.indexOf(u.id);
                    if (idx >= 0) this.selectedUserIds.splice(idx, 1);
                });
            } else {
                this.unboundUsers.forEach(u => {
                    if (!this.selectedUserIds.includes(u.id)) {
                        this.selectedUserIds.push(u.id);
                    }
                });
            }
        },

        toggleSelectMapping(mappingId) {
            const idx = this.selectedMappingIds.indexOf(mappingId);
            if (idx >= 0) {
                this.selectedMappingIds.splice(idx, 1);
            } else {
                this.selectedMappingIds.push(mappingId);
            }
        },

        toggleSelectAllMappings() {
            if (this.isAllMappingsSelected) {
                this.mappings.forEach(m => {
                    const idx = this.selectedMappingIds.indexOf(m.id);
                    if (idx >= 0) this.selectedMappingIds.splice(idx, 1);
                });
            } else {
                this.mappings.forEach(m => {
                    if (!this.selectedMappingIds.includes(m.id)) {
                        this.selectedMappingIds.push(m.id);
                    }
                });
            }
        },

        openContactModal(user) {
            this.modalMode = 'edit-contact';
            this.modalTitle = '编辑联系方式';
            this.selectedUser = null;
            this.form = {
                id: null,
                userId: user.id,
                userName: user.name,
                mobile: user.rawMobile || '',
                email: user.email || '',
                openId: '',
            };
            this.openModal = true;
        },

        editMapping(item) {
            this.modalMode = 'edit-bound';
            this.modalTitle = '编辑绑定与联系方式';
            this.selectedUser = null;
            this.form = {
                id: item.id,
                userId: item.userId,
                userName: item.name,
                mobile: item.rawMobile || '',
                email: item.email || '',
                openId: item.openId || '',
            };
            this.openModal = true;
        },

        async saveMapping() {
            if (this.modalMode === 'edit-contact') {
                if (!this.form.userId) {
                    alert('用户信息不完整');
                    return;
                }
                try {
                    const res = await apiPost('/user-lark-mappings/update-contact', {
                        user_id: this.form.userId,
                        mobile: this.form.mobile,
                        email: this.form.email,
                    });
                    if (res.code === 200) {
                        this.closeModal();
                        await this.loadCandidates();
                        await this.loadMappings();
                    } else {
                        alert(res.msg || '保存失败');
                    }
                } catch (e) {
                    console.error('saveMapping error', e);
                }
            } else if (this.modalMode === 'edit-bound') {
                if (!this.form.id || !this.form.openId) {
                    alert('绑定ID和飞书 open_id 不能为空');
                    return;
                }
                try {
                    const res = await apiPost('/user-lark-mappings/update-binding-and-contact', {
                        id: this.form.id,
                        mobile: this.form.mobile,
                        email: this.form.email,
                        lark_open_id: this.form.openId,
                    });
                    if (res.code === 200) {
                        this.closeModal();
                        await this.loadCandidates();
                        await this.loadMappings();
                    } else {
                        alert(res.msg || '保存失败');
                    }
                } catch (e) {
                    console.error('saveMapping error', e);
                }
            }
        },

        closeModal() {
            this.openModal = false;
            this.form = { id: null, userId: '', userName: '', mobile: '', email: '', openId: '' };
            this.selectedUser = null;
        },

        async batchBindByContact() {
            if (this.selectedUserIds.length === 0) return;
            if (!confirm(`确定对选中的 ${this.selectedUserIds.length} 个用户批量获取飞书 ID 并绑定吗？`)) return;

            this.binding = true;
            try {
                const res = await apiPost('/user-lark-mappings/batch-bind-by-contact', {
                    user_ids: this.selectedUserIds,
                });
                if (res.code === 200) {
                    const failed = res.data.failed || [];
                    const success = res.data.success || 0;
                    this.selectedUserIds = [];
                    await this.loadCandidates();
                    await this.loadMappings();
                    if (failed.length > 0) {
                        const reasons = failed.slice(0, 5).map(f => `用户ID ${f.user_id}: ${f.reason}`).join('\n');
                        const more = failed.length > 5 ? `\n...还有 ${failed.length - 5} 条` : '';
                        alert(`成功绑定 ${success} 个用户，以下未绑定：\n${reasons}${more}`);
                    } else {
                        alert(`成功绑定 ${success} 个用户`);
                    }
                } else {
                    alert(res.msg || '批量绑定失败');
                }
            } catch (e) {
                console.error('batchBindByContact error', e);
            } finally {
                this.binding = false;
            }
        },

        async batchRefreshByContact() {
            if (this.selectedMappingIds.length === 0) return;
            if (!confirm(`确定对选中的 ${this.selectedMappingIds.length} 个已绑定用户重新获取飞书 ID 吗？`)) return;

            this.refreshing = true;
            try {
                const res = await apiPost('/user-lark-mappings/batch-refresh-by-contact', {
                    mapping_ids: this.selectedMappingIds,
                });
                if (res.code === 200) {
                    const failed = res.data.failed || [];
                    const success = res.data.success || 0;
                    this.selectedMappingIds = [];
                    await this.loadMappings();
                    if (failed.length > 0) {
                        const reasons = failed.slice(0, 5).map(f => `绑定ID ${f.mapping_id}${f.user_id ? ` (用户ID ${f.user_id})` : ''}: ${f.reason}`).join('\n');
                        const more = failed.length > 5 ? `\n...还有 ${failed.length - 5} 条` : '';
                        alert(`成功刷新 ${success} 个用户绑定，以下未刷新：\n${reasons}${more}`);
                    } else {
                        alert(`成功刷新 ${success} 个用户绑定`);
                    }
                } else {
                    alert(res.msg || '批量刷新失败');
                }
            } catch (e) {
                console.error('batchRefreshByContact error', e);
            } finally {
                this.refreshing = false;
            }
        },

        async toggleStatus(item) {
            const nextStatus = item.status === '有效' ? 0 : 1;
            try {
                const res = await apiPost('/user-lark-mappings/toggle', {
                    id: item.id,
                    status: nextStatus,
                });
                if (res.code === 200) {
                    await this.loadMappings();
                } else {
                    alert(res.msg || '状态更新失败');
                }
            } catch (e) {
                console.error('toggleStatus error', e);
            }
        },

        _maskMobile(mobile) {
            if (!mobile) return '';
            if (mobile.length <= 7) return mobile;
            return mobile.slice(0, 3) + '****' + mobile.slice(-4);
        }
    }));
});
