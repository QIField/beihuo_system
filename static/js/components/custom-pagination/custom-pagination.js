/**
 * 自定义分页组件
 * 用于 AG Grid 服务器端分页
 * 完全独立于 AG Grid 的分页栏
 */

(function(global) {
    'use strict';

    class CustomPagination {
        constructor(options = {}) {
            this.options = {
                container: options.container || null,           // 分页栏容器选择器
                gridSelector: options.gridSelector || null,     // AG Grid 容器选择器（用于滚动到顶部）
                pageSizeOptions: options.pageSizeOptions || [50, 100, 200, 500],  // 每页条数选项
                defaultPageSize: options.defaultPageSize || 200, // 默认每页条数
                onPageChange: options.onPageChange || null,     // 页码变化回调
                onPageSizeChange: options.onPageSizeChange || null,  // 每页条数变化回调
                showScrollToTop: options.showScrollToTop !== false,  // 是否显示置顶按钮
                ...options
            };

            this.currentPage = 1;
            this.currentPageSize = this.options.defaultPageSize;
            this.totalRecords = 0;
            this.container = null;

            this.init();
        }

        /**
         * 初始化分页组件
         */
        init() {
            this.createContainer();
            this.render();
            this.bindEvents();
        }

        /**
         * 创建分页栏容器
         */
        createContainer() {
            if (this.options.container) {
                this.container = document.querySelector(this.options.container);
            }

            if (!this.container) {
                // 如果没有指定容器，创建一个并插入到 AG Grid 下方
                this.container = document.createElement('div');
                this.container.className = 'custom-pagination-bar';
                this.container.style.cssText = `
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    gap: 15px;
                    width: 100%;
                    padding: 10px 20px;
                    background: #fafafa;
                    border-top: 1px solid #e8e8e8;
                    font-size: 13px;
                    color: #666;
                `;

                // 尝试插入到 AG Grid 下方
                const agGrid = document.querySelector(this.options.gridSelector || '.ag-root-wrapper');
                if (agGrid && agGrid.parentNode) {
                    agGrid.parentNode.insertBefore(this.container, agGrid.nextSibling);
                } else {
                    document.body.appendChild(this.container);
                }
            }
        }

        /**
         * 渲染分页栏
         */
        render() {
            const pageSizeOptionsHtml = this.options.pageSizeOptions.map(size =>
                `<option value="${size}" ${size === this.currentPageSize ? 'selected' : ''}>${size}</option>`
            ).join('');

            const totalPages = Math.ceil(this.totalRecords / this.currentPageSize) || 1;

            this.container.innerHTML = `
                <!-- 左侧：每页显示 -->
                <div class="page-size-selector" style="position: absolute; left: 20px; display: flex; align-items: center; gap: 8px;">
                    <span>每页显示:</span>
                    <select class="cp-page-size-select" style="padding: 4px 8px; border: 1px solid #d9d9d9; border-radius: 4px; font-size: 13px; cursor: pointer;">
                        ${pageSizeOptionsHtml}
                    </select>
                    <span>条</span>
                </div>
                <!-- 中间：分页控制 -->
                <div class="pagination-center" style="display: flex; align-items: center; gap: 15px;">
                    <div class="pagination-controls" style="display: flex; align-items: center; gap: 10px;">
                        <button class="cp-prev-btn" style="padding: 4px 12px; border: 1px solid #d9d9d9; border-radius: 4px; background: #fff; font-size: 13px; cursor: pointer;" ${this.currentPage <= 1 ? 'disabled' : ''}>上一页</button>
                        <span class="cp-page-info" style="font-size: 13px; color: #666;">第 ${this.currentPage} / ${totalPages} 页 (共 ${this.totalRecords} 条)</span>
                        <button class="cp-next-btn" style="padding: 4px 12px; border: 1px solid #d9d9d9; border-radius: 4px; background: #fff; font-size: 13px; cursor: pointer;" ${this.currentPage >= totalPages ? 'disabled' : ''}>下一页</button>
                    </div>
                    <div class="page-jumper" style="display: flex; align-items: center; gap: 8px;">
                        <span>跳至</span>
                        <input type="number" class="cp-page-input" min="1" max="${totalPages}" placeholder="页码" style="width: 50px; padding: 4px 8px; border: 1px solid #d9d9d9; border-radius: 4px; font-size: 13px; text-align: center;">
                        <span>页</span>
                        <button class="cp-jump-btn" style="padding: 4px 12px; border: 1px solid #d9d9d9; border-radius: 4px; background: #fff; font-size: 13px; cursor: pointer;">跳转</button>
                    </div>
                </div>
                ${this.options.showScrollToTop ? `
                <!-- 右侧：置顶按钮 -->
                <div class="scroll-to-top-wrapper" style="position: absolute; right: 20px;">
                    <button class="cp-scroll-top-btn" title="回到顶部" style="width: 32px; height: 32px; border-radius: 4px; background: linear-gradient(135deg, #1890ff 0%, #40a9ff 100%); border: none; box-shadow: 0 2px 6px rgba(24, 144, 255, 0.3); cursor: pointer; display: flex; align-items: center; justify-content: center; color: white; transition: all 0.3s ease;">
                        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M12 19V5M5 12l7-7 7 7"/>
                        </svg>
                    </button>
                </div>
                ` : ''}
            `;

            // 设置容器相对定位（用于绝对定位子元素）
            this.container.style.position = 'relative';
        }

        /**
         * 绑定事件
         */
        bindEvents() {
            const self = this;

            // 每页条数变化
            const pageSizeSelect = this.container.querySelector('.cp-page-size-select');
            if (pageSizeSelect) {
                pageSizeSelect.addEventListener('change', function() {
                    self.currentPageSize = parseInt(this.value);
                    self.currentPage = 1;  // 重置到第一页
                    self.render();
                    self.bindEvents();
                    if (self.options.onPageSizeChange) {
                        self.options.onPageSizeChange(self.currentPageSize);
                    }
                    if (self.options.onPageChange) {
                        self.options.onPageChange(self.currentPage, self.currentPageSize);
                    }
                });
            }

            // 上一页
            const prevBtn = this.container.querySelector('.cp-prev-btn');
            if (prevBtn) {
                prevBtn.addEventListener('click', function() {
                    if (self.currentPage > 1) {
                        self.currentPage--;
                        self.render();
                        self.bindEvents();
                        if (self.options.onPageChange) {
                            self.options.onPageChange(self.currentPage, self.currentPageSize);
                        }
                    }
                });
            }

            // 下一页
            const nextBtn = this.container.querySelector('.cp-next-btn');
            if (nextBtn) {
                nextBtn.addEventListener('click', function() {
                    const totalPages = Math.ceil(self.totalRecords / self.currentPageSize);
                    if (self.currentPage < totalPages) {
                        self.currentPage++;
                        self.render();
                        self.bindEvents();
                        if (self.options.onPageChange) {
                            self.options.onPageChange(self.currentPage, self.currentPageSize);
                        }
                    }
                });
            }

            // 页码跳转
            const jumpBtn = this.container.querySelector('.cp-jump-btn');
            const pageInput = this.container.querySelector('.cp-page-input');
            if (jumpBtn && pageInput) {
                const doJump = function() {
                    const targetPage = parseInt(pageInput.value);
                    const totalPages = Math.ceil(self.totalRecords / self.currentPageSize);
                    if (targetPage >= 1 && targetPage <= totalPages) {
                        self.currentPage = targetPage;
                        self.render();
                        self.bindEvents();
                        if (self.options.onPageChange) {
                            self.options.onPageChange(self.currentPage, self.currentPageSize);
                        }
                    }
                };
                jumpBtn.addEventListener('click', doJump);
                pageInput.addEventListener('keypress', function(e) {
                    if (e.key === 'Enter') doJump();
                });
            }

            // 置顶按钮
            const scrollTopBtn = this.container.querySelector('.cp-scroll-top-btn');
            if (scrollTopBtn) {
                scrollTopBtn.addEventListener('mouseenter', function() {
                    this.style.transform = 'scale(1.1)';
                    this.style.boxShadow = '0 4px 10px rgba(24, 144, 255, 0.5)';
                });
                scrollTopBtn.addEventListener('mouseleave', function() {
                    this.style.transform = 'scale(1)';
                    this.style.boxShadow = '0 2px 6px rgba(24, 144, 255, 0.3)';
                });
                scrollTopBtn.addEventListener('click', function() {
                    const agGridViewport = document.querySelector(self.options.gridSelector + ' .ag-body-viewport') ||
                                          document.querySelector('.ag-body-viewport');
                    if (agGridViewport) {
                        agGridViewport.scrollTo({ top: 0, behavior: 'smooth' });
                    } else {
                        window.scrollTo({ top: 0, behavior: 'smooth' });
                    }
                });
            }
        }

        /**
         * 更新分页数据
         */
        update(totalRecords, currentPage, pageSize) {
            this.totalRecords = totalRecords;
            if (currentPage !== undefined) this.currentPage = currentPage;
            if (pageSize !== undefined) this.currentPageSize = pageSize;
            this.render();
            this.bindEvents();
        }

        /**
         * 获取当前分页参数
         */
        getPaginationParams() {
            return {
                page: this.currentPage,
                pageSize: this.currentPageSize
            };
        }

        /**
         * 销毁组件
         */
        destroy() {
            if (this.container && this.container.parentNode) {
                this.container.parentNode.removeChild(this.container);
            }
            this.container = null;
        }
    }

    // 静态方法：快速初始化
    CustomPagination.init = function(options = {}) {
        return new CustomPagination(options);
    };

    // 导出到全局
    global.CustomPagination = CustomPagination;

})(window);
