/**
 * 分页管理器
 */
class Pagination {
    constructor(grid) {
        this.grid = grid;
        this.state = {
            page: 1,
            pageSize: 100,
            total: 0,
            totalPages: 0
        };
    }

    /**
     * 获取当前页
     */
    getPage() {
        return this.state.page;
    }

    /**
     * 获取每页条数
     */
    getPageSize() {
        return this.state.pageSize;
    }

    /**
     * 获取总页数
     */
    getTotalPages() {
        return this.state.totalPages;
    }

    /**
     * 设置总条数
     */
    setTotal(total) {
        this.state.total = total;
        this.state.totalPages = Math.ceil(total / this.state.pageSize) || 1;
    }

    /**
     * 跳转到指定页
     */
    async goToPage(page) {
        if (page < 1 || page > this.state.totalPages) {
            return false;
        }

        this.state.page = page;
        await this.grid.loadData();
        return true;
    }

    /**
     * 下一页
     */
    async next() {
        return this.goToPage(this.state.page + 1);
    }

    /**
     * 上一页
     */
    async prev() {
        return this.goToPage(this.state.page - 1);
    }

    /**
     * 设置每页条数
     */
    async setPageSize(size) {
        this.state.pageSize = size;
        this.state.page = 1; // 重置到第一页
        this.state.totalPages = Math.ceil(this.state.total / size) || 1;
        await this.grid.loadData();
    }

    /**
     * 重置
     */
    reset() {
        this.state.page = 1;
        this.state.total = 0;
        this.state.totalPages = 0;
    }

    /**
     * 获取分页参数
     */
    getParams() {
        return {
            page: this.state.page,
            pageSize: this.state.pageSize
        };
    }

    /**
     * 渲染分页栏
     */
    render() {
        const { page, pageSize, total, totalPages } = this.state;

        return `
            <div class="datagrid-pagination">
                <button class="btn btn-sm" ${page <= 1 ? 'disabled' : ''} onclick="grid.pagination.prev()">
                    上一页
                </button>
                <span class="pagination-info">
                    第 ${page} 页 / 共 ${totalPages} 页 (共 ${total} 条)
                </span>
                <button class="btn btn-sm" ${page >= totalPages ? 'disabled' : ''} onclick="grid.pagination.next()">
                    下一页
                </button>
                <select class="page-size-select" onchange="grid.pagination.setPageSize(this.value)">
                    <option value="50" ${pageSize === 50 ? 'selected' : ''}>50条</option>
                    <option value="100" ${pageSize === 100 ? 'selected' : ''}>100条</option>
                    <option value="200" ${pageSize === 200 ? 'selected' : ''}>200条</option>
                </select>
            </div>
        `;
    }
}

// 导出
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Pagination;
}
