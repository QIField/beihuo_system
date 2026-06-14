/**
 * AG Grid 数据加载器
 * 封装请求取消、请求ID管理、加载动画、错误处理
 * 
 * 使用示例：
 * const loader = new AgGridLoader(gridApi);
 * loader.load('/api/data', {page: 1}, (data) => {
 *     // 处理成功
 * });
 */
class AgGridLoader {
    constructor(gridApi) {
        this.gridApi = gridApi;
        this.abortController = null;
        this.requestId = 0;
    }

    /**
     * 加载数据
     * @param {string} url - 请求地址
     * @param {Object} params - 请求参数
     * @param {Function} onSuccess - 成功回调 (data) => void
     * @param {Function} onError - 错误回调 (error) => void，可选
     * @returns {Promise<void>}
     */
    async load(url, params, onSuccess, onError) {
        // 取消旧请求
        if (this.abortController) {
            this.abortController.abort();
        }

        // 生成新请求ID
        const requestId = ++this.requestId;
        this.abortController = new AbortController();

        // 显示加载中
        if (this.gridApi) {
            this.gridApi.showLoadingOverlay();
        }

        try {
            const queryString = params ? '?' + new URLSearchParams(params) : '';
            const response = await fetch(url + queryString, {
                signal: this.abortController.signal
            });
            
            const result = await response.json();

            // 只处理最新请求的结果
            if (requestId !== this.requestId) {
                console.log('[AgGridLoader] 丢弃旧请求结果, requestId:', requestId);
                return;
            }

            if (result.code === 0 || result.code === '0') {
                const list = result.data?.list || result.data || [];
                const total = result.data?.total || list.length;
                const page = result.data?.page || 1;
                
                // 设置数据
                if (this.gridApi) {
                    this.gridApi.setRowData(list);
                    
                    // 根据数据量显示对应遮罩
                    if (!list.length) {
                        this.gridApi.showNoRowsOverlay();
                    } else {
                        this.gridApi.hideOverlay();
                    }
                }

                // 调用成功回调，传递完整数据结构
                if (onSuccess) {
                    onSuccess({
                        list: list,
                        total: total,
                        page: page,
                        raw: result.data
                    });
                }
            } else {
                // 业务错误
                if (this.gridApi) {
                    this.gridApi.showNoRowsOverlay();
                }
                if (onError) {
                    onError(new Error(result.msg || '加载失败'));
                }
            }

        } catch (error) {
            // 取消错误不处理
            if (error.name === 'AbortError') {
                console.log('[AgGridLoader] 请求被取消');
                return;
            }

            console.error('[AgGridLoader] 请求失败:', error);
            
            if (this.gridApi) {
                this.gridApi.hideOverlay();
            }
            
            if (onError) {
                onError(error);
            }
        }
    }

    /**
     * 获取当前请求ID
     * @returns {number}
     */
    getCurrentRequestId() {
        return this.requestId;
    }

    /**
     * 取消当前请求
     */
    cancel() {
        if (this.abortController) {
            this.abortController.abort();
            this.abortController = null;
        }
    }
}

// 兼容模块导出
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AgGridLoader;
}
