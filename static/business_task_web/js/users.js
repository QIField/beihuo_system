document.addEventListener('alpine:init', () => {
    Alpine.data('userApp', () => ({
        sidebarOpen: false,
        menu: menuItems,
        openModal: false,
        contactModal: false,
        userKeyword: '',
        selectedUser: null,
        editingId: null,
        binding: false,
        selectedUserIds: [],
        form: { userId: '', openId: '', status: '1' },
        contactForm: { userId: '', name: '', mobile: '', email: '' },
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

        selectUser(user) {
            this.selectedUser = user;
            this.editingId = null;
            this.form = { userId: String(user.id), openId: '', status: '1' };
            this.openModal = true;
        },

        openContactModal(user) {
            this.contactForm = {
                userId: user.id,
                name: user.name,
                mobile: user.rawMobile,
                email: user.email,
            };
            this.contactModal = true;
        },

        async saveContact() {
            try {
                const res = await apiPost('/user-lark-mappings/update-contact', {
                    user_id: this.contactForm.userId,
                    mobile: this.contactForm.mobile,
                    email: this.contactForm.email,
                });
                if (res.code === 200) {
                    this.contactModal = false;
                    await this.loadCandidates();
                } else {
                    alert(res.msg || '保存失败');
                }
            } catch (e) {
                console.error('saveContact error', e);
            }
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

        editMapping(item) {
            this.selectedUser = null;
            this.editingId = item.id;
            this.form = {
                userId: String(item.userId),
                openId: item.openId,
                status: item.status === '有效' ? '1' : '0',
            };
            this.openModal = true;
        },

        async saveMapping() {
            if (!this.form.userId || !this.form.openId) {
                alert('请填写完整信息');
                return;
            }
            try {
                let res;
                if (this.editingId) {
                    res = await apiPost('/user-lark-mappings/update', {
                        id: this.editingId,
                        lark_open_id: this.form.openId,
                    });
                } else {
                    res = await apiPost('/user-lark-mappings/bind', {
                        user_id: Number(this.form.userId),
                        lark_open_id: this.form.openId,
                    });
                }
                if (res.code === 200) {
                    this.openModal = false;
                    this.form = { userId: '', openId: '', status: '1' };
                    this.editingId = null;
                    this.selectedUser = null;
                    await this.loadCandidates();
                    await this.loadMappings();
                } else {
                    alert(res.msg || '保存失败');
                }
            } catch (e) {
                console.error('saveMapping error', e);
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
