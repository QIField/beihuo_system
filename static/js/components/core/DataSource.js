/**
 * DataSource 数据源管理器
 * 支持客户端和服务端两种模式
 */
class DataSource {
    constructor(options = {}) {
        this.options = {
            type: 'client',           // 'client' 或 'server'
            url: '',                  // API地址
            method: 'GET',            // 请求方法
            headers: {},              // 自定义请求头
            dataKey: 'data',          // 响应数据字段
            totalKey: 'total',        // 响应总数字段
            cache: false,             // 是否启用缓存
            cacheTime: 300000,        // 缓存时间(ms)
            transform: null,          // 数据转换函数
            ...options
        };

        // 客户端模式缓存所有数据
        this.allData = null;

        // 创建缓存实例
        if (this.options.cache) {
            this.cache = new LRUCache(50);
        }

        // 请求管理器
        this.requestManager = new RequestManager();
    }

    /**
     * 加载数据
     * @param {object} params - 请求参数
     * @returns {Promise<{list: Array, total: number}>}
     */
    async load(params = {}) {
        const cacheKey = JSON.stringify(params);

        // 检查缓存
        if (this.options.cache && this.cache) {
            const cached = this.cache.get(cacheKey);
            if (cached) {
                console.log('[DataSource] 命中缓存');
                return cached;
            }
        }

        // 根据类型加载数据
        const data = this.options.type === 'server'
            ? await this.loadFromServer(params)
            : await this.loadFromClient(params);

        // 存入缓存
        if (this.options.cache && this.cache) {
            this.cache.set(cacheKey, data, this.options.cacheTime);
        }

        return data;
    }

    /**
     * 从服务端加载
     */
    async loadFromServer(params) {
        const { url, method, headers, dataKey, totalKey, transform } = this.options;

        try {
            let response;

            if (method.toUpperCase() === 'GET') {
                response = await this.requestManager.get(url, params, { headers });
            } else {
                response = await this.requestManager.post(url, params, { headers });
            }

            const result = await response.json();

            if (result.code !== 0) {
                throw new Error(result.message || '加载数据失败');
            }

            let list = result[dataKey] || [];
            const total = result[totalKey] || list.length;

            // 数据转换
            if (transform && typeof transform === 'function') {
                list = list.map(transform);
            }

            return { list, total };
        } catch (error) {
            console.error('[DataSource] 加载失败:', error);
            throw error;
        }
    }

    /**
     * 从客户端加载（前端分页）
     */
    async loadFromClient(params) {
        // 首次加载所有数据
        if (!this.allData) {
            const { url, method, headers, dataKey, transform } = this.options;

            try {
                let response;
                if (method.toUpperCase() === 'GET') {
                    response = await this.requestManager.get(url, {}, { headers });
                } else {
                    response = await this.requestManager.post(url, {}, { headers });
                }

                const result = await response.json();
                this.allData = result[dataKey] || [];

                // 数据转换
                if (transform && typeof transform === 'function') {
                    this.allData = this.allData.map(transform);
                }
            } catch (error) {
                console.error('[DataSource] 加载失败:', error);
                throw error;
            }
        }

        let data = [...this.allData];

        // 应用过滤
        if (params.filter) {
            data = this.applyFilter(data, params.filter);
        }

        // 应用排序
        if (params.sort && params.sort.field) {
            data = this.applySort(data, params.sort);
        }

        const total = data.length;

        // 应用分页
        const page = params.page || 1;
        const pageSize = params.pageSize || 100;
        const start = (page - 1) * pageSize;
        const end = start + pageSize;

        return {
            list: data.slice(start, end),
            total
        };
    }

    /**
     * 应用过滤
     */
    applyFilter(data, filter) {
        return data.filter(item => {
            return Object.entries(filter).every(([key, value]) => {
                if (!value) return true;
                const itemValue = String(item[key] || '').toLowerCase();
                return itemValue.includes(String(value).toLowerCase());
            });
        });
    }

    /**
     * 应用排序
     */
    applySort(data, sort) {
        const { field, order } = sort;

        return data.sort((a, b) => {
            let valA = a[field];
            let valB = b[field];

            // 处理数字排序
            if (typeof valA === 'number' && typeof valB === 'number') {
                return order === 'asc' ? valA - valB : valB - valA;
            }

            // 处理字符串排序
            valA = String(valA || '').toLowerCase();
            valB = String(valB || '').toLowerCase();

            if (valA < valB) return order === 'asc' ? -1 : 1;
            if (valA > valB) return order === 'asc' ? 1 : -1;
            return 0;
        });
    }

    /**
     * 刷新数据（清除缓存）
     */
    async refresh(params) {
        // 清除客户端缓存
        if (this.options.type === 'client') {
            this.allData = null;
        }

        // 清除缓存
        if (this.cache) {
            this.cache.clear();
        }

        return this.load(params);
    }

    /**
     * 获取所有数据（仅客户端模式）
     */
    getAllData() {
        return this.allData;
    }

    /**
     * 设置数据（仅客户端模式）
     */
    setData(data) {
        if (this.options.type === 'client') {
            this.allData = data;
        }
    }

    /**
     * 清空缓存
     */
    clearCache() {
        if (this.cache) {
            this.cache.clear();
        }
        this.allData = null;
    }

    /**
     * 销毁
     */
    destroy() {
        this.clearCache();
        this.requestManager.cancelAll();
    }
}

// 导出
if (typeof module !== 'undefined' && module.exports) {
    module.exports = DataSource;
}
