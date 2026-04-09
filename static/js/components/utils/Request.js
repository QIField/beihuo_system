/**
 * 请求管理器
 * 封装fetch，支持取消请求、超时、重试等功能
 */
class RequestManager {
    constructor(options = {}) {
        this.defaultOptions = {
            timeout: 30000,
            retries: 0,
            retryDelay: 1000,
            headers: {
                'Content-Type': 'application/json'
            },
            ...options
        };
        
        this.pendingRequests = new Map();
    }

    /**
     * 生成请求ID
     */
    generateId() {
        return Date.now().toString(36) + Math.random().toString(36).substr(2);
    }

    /**
     * 发送请求
     * @param {string} url - 请求地址
     * @param {object} options - 请求选项
     * @returns {Promise}
     */
    async request(url, options = {}) {
        const requestId = this.generateId();
        const controller = new AbortController();
        
        this.pendingRequests.set(requestId, controller);
        
        const config = {
            ...this.defaultOptions,
            ...options,
            signal: controller.signal
        };

        try {
            const response = await this.fetchWithTimeout(url, config);
            this.pendingRequests.delete(requestId);
            return response;
        } catch (error) {
            this.pendingRequests.delete(requestId);
            throw error;
        }
    }

    /**
     * 带超时的fetch
     */
    fetchWithTimeout(url, options) {
        const { timeout, ...fetchOptions } = options;
        
        return Promise.race([
            fetch(url, fetchOptions),
            new Promise((_, reject) => {
                setTimeout(() => {
                    reject(new Error('Request timeout'));
                }, timeout);
            })
        ]);
    }

    /**
     * GET请求
     */
    get(url, params = {}, options = {}) {
        const queryString = this.buildQueryString(params);
        const fullUrl = queryString ? `${url}?${queryString}` : url;
        
        return this.request(fullUrl, {
            method: 'GET',
            ...options
        });
    }

    /**
     * POST请求
     */
    post(url, data = {}, options = {}) {
        return this.request(url, {
            method: 'POST',
            body: JSON.stringify(data),
            ...options
        });
    }

    /**
     * 取消指定请求
     * @param {string} requestId - 请求ID
     */
    cancel(requestId) {
        const controller = this.pendingRequests.get(requestId);
        if (controller) {
            controller.abort();
            this.pendingRequests.delete(requestId);
        }
    }

    /**
     * 取消所有请求
     */
    cancelAll() {
        this.pendingRequests.forEach(controller => {
            controller.abort();
        });
        this.pendingRequests.clear();
    }

    /**
     * 构建查询字符串
     */
    buildQueryString(params) {
        return Object.entries(params)
            .filter(([_, value]) => value !== undefined && value !== null)
            .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
            .join('&');
    }
}

// 创建默认实例
const request = new RequestManager();

// 导出
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { RequestManager, request };
}
