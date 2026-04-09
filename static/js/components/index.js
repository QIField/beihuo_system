/**
 * DataGrid 组件库入口文件
 * Enterprise DataGrid Component Library
 * @version 1.0.0
 */

// 工具函数
// 注意：这些工具函数需要在其他模块之前加载

/**
 * LRU缓存实现
 */
class LRUCache {
    constructor(maxSize = 50) {
        this.cache = new Map();
        this.maxSize = maxSize;
    }

    get(key) {
        const item = this.cache.get(key);
        if (!item) return null;
        if (Date.now() - item.time > item.ttl) {
            this.cache.delete(key);
            return null;
        }
        this.cache.delete(key);
        this.cache.set(key, item);
        return item.data;
    }

    set(key, data, ttl = 300000) {
        if (this.cache.size >= this.maxSize) {
            const firstKey = this.cache.keys().next().value;
            this.cache.delete(firstKey);
        }
        this.cache.set(key, { data, time: Date.now(), ttl });
    }

    clear() {
        this.cache.clear();
    }
}

/**
 * 防抖函数
 */
function debounce(fn, delay) {
    let timer = null;
    return function(...args) {
        if (timer) clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}

/**
 * 请求管理器
 */
class RequestManager {
    constructor(options = {}) {
        this.defaultOptions = {
            timeout: 30000,
            headers: { 'Content-Type': 'application/json' },
            ...options
        };
        this.pendingRequests = new Map();
    }

    async request(url, options = {}) {
        const controller = new AbortController();
        const requestId = Date.now().toString(36);
        this.pendingRequests.set(requestId, controller);

        // 深度合并配置，确保 headers 被正确合并
        const config = {
            ...this.defaultOptions,
            ...options,
            headers: {
                ...this.defaultOptions.headers,
                ...(options.headers || {})
            },
            signal: controller.signal
        };

        try {
            const response = await Promise.race([
                fetch(url, config),
                new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), config.timeout))
            ]);
            this.pendingRequests.delete(requestId);
            return response;
        } catch (error) {
            this.pendingRequests.delete(requestId);
            throw error;
        }
    }

    get(url, params = {}, options = {}) {
        const query = Object.entries(params)
            .filter(([_, v]) => v != null)
            .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
            .join('&');
        return this.request(query ? `${url}?${query}` : url, { method: 'GET', ...options });
    }

    post(url, data = {}, options = {}) {
        const postOptions = {
            method: 'POST',
            body: JSON.stringify(data),
            headers: {
                'Content-Type': 'application/json',
                ...(options.headers || {})
            },
            ...options
        };
        return this.request(url, postOptions);
    }

    cancelAll() {
        this.pendingRequests.forEach(c => c.abort());
        this.pendingRequests.clear();
    }
}

/**
 * 数据源管理器
 */
class DataSource {
    constructor(options = {}) {
        this.options = {
            type: 'client',
            url: '',
            method: 'GET',
            headers: {},
            dataKey: 'data',
            totalKey: 'total',
            cache: false,
            cacheTime: 300000,
            ...options
        };
        this.allData = null;
        if (this.options.cache) this.cache = new LRUCache(50);
        this.requestManager = new RequestManager();
    }

    async load(params = {}) {
        const cacheKey = JSON.stringify(params);
        if (this.options.cache && this.cache) {
            const cached = this.cache.get(cacheKey);
            if (cached) return cached;
        }

        const data = this.options.type === 'server'
            ? await this.loadFromServer(params)
            : await this.loadFromClient(params);

        if (this.options.cache && this.cache) {
            this.cache.set(cacheKey, data, this.options.cacheTime);
        }
        return data;
    }

    async loadFromServer(params) {
        const { url, method, headers, dataKey, totalKey } = this.options;
        // 确保 POST 请求有正确的 Content-Type
        const requestOptions = method.toUpperCase() === 'POST' ? {
            headers: {
                'Content-Type': 'application/json',
                ...headers
            }
        } : { headers };
        
        const response = method.toUpperCase() === 'GET'
            ? await this.requestManager.get(url, params, requestOptions)
            : await this.requestManager.post(url, params, requestOptions);
        const result = await response.json();
        if (result.code !== 0) throw new Error(result.message || '加载失败');
        return { list: result[dataKey] || [], total: result[totalKey] || 0 };
    }

    async loadFromClient(params) {
        if (!this.allData) {
            const { url, method, headers, dataKey } = this.options;
            const response = method.toUpperCase() === 'GET'
                ? await this.requestManager.get(url, {}, { headers })
                : await this.requestManager.post(url, {}, { headers });
            const result = await response.json();
            this.allData = result[dataKey] || [];
        }

        let data = [...this.allData];
        if (params.filter) {
            data = data.filter(item =>
                Object.entries(params.filter).every(([k, v]) => {
                    if (!v) return true;
                    return String(item[k] || '').toLowerCase().includes(String(v).toLowerCase());
                })
            );
        }
        if (params.sort?.field) {
            const { field, order } = params.sort;
            data.sort((a, b) => {
                const va = a[field], vb = b[field];
                if (typeof va === 'number' && typeof vb === 'number') {
                    return order === 'asc' ? va - vb : vb - va;
                }
                const sa = String(va || '').toLowerCase(), sb = String(vb || '').toLowerCase();
                if (sa < sb) return order === 'asc' ? -1 : 1;
                if (sa > sb) return order === 'asc' ? 1 : -1;
                return 0;
            });
        }

        const total = data.length;
        const page = params.page || 1, pageSize = params.pageSize || 100;
        const start = (page - 1) * pageSize;
        return { list: data.slice(start, start + pageSize), total };
    }

    clearCache() {
        if (this.cache) this.cache.clear();
        this.allData = null;
    }

    destroy() {
        this.clearCache();
        this.requestManager.cancelAll();
    }
}

/**
 * DataGrid 主组件
 */
class DataGrid {
    constructor(container, options = {}) {
        this.container = typeof container === 'string' ? document.querySelector(container) : container;
        if (!this.container) throw new Error('Container not found');

        this.options = {
            dataSource: null,
            columns: [],
            pagination: true,
            serverSide: false,
            sorting: true,
            filtering: true,
            selection: 'multiple',
            virtualScroll: true,
            fixedColumns: { left: 0, right: 0 },
            rowHeight: 40,
            pageSize: 100,
            showSkeleton: true,
            ...options
        };

        this.state = {
            page: 1,
            pageSize: this.options.pageSize,
            total: 0,
            sort: { field: '', order: 'asc' },
            filter: {},
            selected: new Set(),
            loading: false
        };

        this.hot = null;
        // 如果传入的是 DataSource 实例，直接使用；否则创建新的 DataSource
        if (this.options.dataSource instanceof DataSource) {
            this.dataSource = this.options.dataSource;
        } else {
            this.dataSource = new DataSource(this.options.dataSource);
        }

        this.init();
    }

    async init() {
        this.renderLayout();
        await this.loadData();
    }

    renderLayout() {
        this.container.innerHTML = `
            <div class="datagrid-wrapper">
                <div class="datagrid-toolbar"></div>
                <div class="datagrid-table" style="height: 500px;"></div>
                <div class="datagrid-pagination"></div>
            </div>
        `;
        this.tableContainer = this.container.querySelector('.datagrid-table');
        this.paginationContainer = this.container.querySelector('.datagrid-pagination');
    }

    async loadData() {
        if (this.state.loading) return;
        this.state.loading = true;

        // 显示骨架屏
        if (this.options.showSkeleton) {
            this.showSkeleton();
        }

        try {
            const params = {
                page: this.state.page,
                pageSize: this.state.pageSize,
                sort: this.state.sort,
                filter: this.state.filter
            };

            const response = await this.dataSource.load(params);
            this.state.total = response.total;
            this.renderTable(response.list);
            this.renderPagination();
        } catch (error) {
            console.error('[DataGrid] 加载失败:', error);
            this.tableContainer.innerHTML = `<div class="datagrid-error">加载失败: ${error.message}</div>`;
        } finally {
            this.state.loading = false;
            this.hideSkeleton();
        }
    }

    showSkeleton() {
        const rows = 10, cols = Math.min(this.options.columns.length, 5);
        let html = '<div class="datagrid-skeleton">';
        for (let i = 0; i < rows; i++) {
            html += '<div class="skeleton-row">';
            for (let j = 0; j < cols; j++) {
                html += '<div class="skeleton-cell shine"></div>';
            }
            html += '</div>';
        }
        html += '</div>';
        this.tableContainer.innerHTML = html;
    }

    hideSkeleton() {
        // Handsontable 渲染时会自动覆盖
    }

    renderTable(data) {
        // 记录渲染开始时间
        window._renderStartTime = performance.now();
        
        if (this.hot) {
            this.hot.destroy();
        }

        const self = this;
        
        // 处理列配置，提取表头渲染器
        const columns = this.options.columns.map((col, index) => {
            const colDef = { ...col };
            // 如果有 headerRenderer，需要在 afterGetColHeader 中处理
            if (col.headerRenderer) {
                colDef._headerRenderer = col.headerRenderer;
                delete colDef.headerRenderer;
            }
            return colDef;
        });
        

        
        // 基础配置
        const baseConfig = {
            data: data,
            columns: columns,
            rowHeaders: false,
            colHeaders: function(col) {
                const column = columns[col];
                if (column && column.title) {
                    return column.title;
                }
                return '';
            },
            height: '100%',
            width: '100%',
            stretchH: 'all',
            licenseKey: 'non-commercial-and-evaluation',
            fixedColumnsLeft: this.options.fixedColumns.left,
            fixedColumnsRight: this.options.fixedColumns.right,
            rowHeights: this.options.rowHeights || this.options.rowHeight || 40,
            autoRowSize: false,
            autoColumnSize: false,
            // 只读模式，但允许编辑复选框列
            readOnly: true,
            selectionMode: this.options.selection,
            renderAllRows: !this.options.virtualScroll,
            viewportRowRenderingOffset: 10,
            observeChanges: false,
            // 启用列宽手动调整
            manualColumnResize: true,
            // 启用行高手动调整
            manualRowResize: false,
            // 启用列拖拽
            manualColumnMove: false,
            afterChange: (changes, source) => {
                if (source === 'edit' && changes) {
                    changes.forEach(([row, prop, , newVal]) => {
                        if (prop === 'selected') {
                            const data = self.hot.getSourceDataAtRow(row);
                            if (newVal) self.state.selected.add(data);
                            else self.state.selected.delete(data);
                        }
                    });
                }
            },
            afterGetColHeader: function(col, TH) {
                const column = columns[col];
                if (column && column._headerRenderer) {
                    column._headerRenderer(this, col, TH);
                }
            }
        };
        
        // 合并用户自定义配置
        const customOptions = this.options.handsontableOptions || {};
        const finalConfig = this.mergeDeep(baseConfig, customOptions);
        
        this.hot = new Handsontable(this.tableContainer, finalConfig);
    }
    
    // 深度合并对象
    mergeDeep(target, source) {
        const output = Object.assign({}, target);
        if (this.isObject(target) && this.isObject(source)) {
            Object.keys(source).forEach(key => {
                if (typeof source[key] === 'function') {
                    // 函数类型直接赋值，不合并
                    output[key] = source[key];
                } else if (this.isObject(source[key])) {
                    if (!(key in target)) {
                        Object.assign(output, { [key]: source[key] });
                    } else {
                        output[key] = this.mergeDeep(target[key], source[key]);
                    }
                } else {
                    Object.assign(output, { [key]: source[key] });
                }
            });
        }
        return output;
    }
    
    isObject(item) {
        return (item && typeof item === 'object' && !Array.isArray(item) && !(item instanceof Function));
    }

    renderPagination() {
        const { page, pageSize, total } = this.state;
        const totalPages = Math.ceil(total / pageSize) || 1;

        this.paginationContainer.innerHTML = `
            <button class="btn btn-sm" ${page <= 1 ? 'disabled' : ''} onclick="this.closest('.datagrid-wrapper').dispatchEvent(new CustomEvent('pagechange', {detail: -1}))">上一页</button>
            <span class="pagination-info">第 ${page} 页 / 共 ${totalPages} 页 (共 ${total} 条)</span>
            <button class="btn btn-sm" ${page >= totalPages ? 'disabled' : ''} onclick="this.closest('.datagrid-wrapper').dispatchEvent(new CustomEvent('pagechange', {detail: 1}))">下一页</button>
            <span style="color: #666; font-size: 14px;">跳转到</span>
            <input type="number" class="page-jump-input" min="1" max="${totalPages}" value="${page}" 
                onkeydown="if(event.key==='Enter') this.closest('.datagrid-wrapper').dispatchEvent(new CustomEvent('pagejump', {detail: this.value}))"
                style="width: 60px; padding: 6px; border: 1px solid #d9d9d9; border-radius: 4px; text-align: center;">
            <button class="btn btn-sm" onclick="this.closest('.datagrid-wrapper').dispatchEvent(new CustomEvent('pagejump', {detail: this.previousElementSibling.value}))">跳转</button>
            <select class="page-size-select" onchange="this.closest('.datagrid-wrapper').dispatchEvent(new CustomEvent('pagesizechange', {detail: this.value}))">
                <option value="20" ${pageSize == 20 ? 'selected' : ''}>20条</option>
                <option value="100" ${pageSize == 100 ? 'selected' : ''}>100条</option>
                <option value="200" ${pageSize == 200 ? 'selected' : ''}>200条</option>
                <option value="500" ${pageSize == 500 ? 'selected' : ''}>500条</option>
            </select>
        `;

        // 绑定事件
        const wrapper = this.container.querySelector('.datagrid-wrapper');
        wrapper.addEventListener('pagechange', (e) => this.changePage(e.detail));
        wrapper.addEventListener('pagesizechange', (e) => this.setPageSize(parseInt(e.detail)));
        wrapper.addEventListener('pagejump', (e) => this.jumpToPage(parseInt(e.detail)));
    }

    async changePage(delta) {
        const newPage = this.state.page + delta;
        const totalPages = Math.ceil(this.state.total / this.state.pageSize);
        if (newPage < 1 || newPage > totalPages) return;
        this.state.page = newPage;
        await this.loadData();
    }

    async jumpToPage(page) {
        const totalPages = Math.ceil(this.state.total / this.state.pageSize);
        const targetPage = parseInt(page);
        if (isNaN(targetPage) || targetPage < 1 || targetPage > totalPages) {
            alert(`请输入有效的页码 (1-${totalPages})`);
            return;
        }
        this.state.page = targetPage;
        await this.loadData();
    }

    async setPageSize(size) {
        this.state.pageSize = size;
        this.state.page = 1;
        await this.loadData();
    }

    refresh() {
        return this.loadData();
    }

    getSelected() {
        return Array.from(this.state.selected);
    }

    destroy() {
        if (this.hot) this.hot.destroy();
        this.dataSource.destroy();
    }

    // 静态方法
    static setDefaults(options) {
        DataGrid.defaultOptions = { ...DataGrid.defaultOptions, ...options };
    }

    static getVersion() {
        return '1.0.0';
    }
}

// 默认配置
DataGrid.defaultOptions = {};

// 全局导出
window.DataGrid = DataGrid;
window.LRUCache = LRUCache;
window.debounce = debounce;
window.RequestManager = RequestManager;
window.DataSource = DataSource;

// 模块导出
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { DataGrid, LRUCache, debounce, RequestManager, DataSource };
}
