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
                container: options.container || null,
                gridSelector: options.gridSelector || null,
                pageSizeOptions: options.pageSizeOptions || [50, 100, 200, 500],
                defaultPageSize: options.defaultPageSize || 200,
                onPageChange: options.onPageChange || null,
                onPageSizeChange: options.onPageSizeChange || null,
                showScrollToTop: options.showScrollToTop !== false,
                ...options
            };

            this.currentPage = 1;
            this.currentPageSize = this.options.defaultPageSize;
            this.totalRecords = 0;
            this.container = null;
            // 标记容器是否由外部传入，外部容器销毁时不移除 DOM
            this.externalContainer = !!this.options.container;

            this.init();
        }

        init() {
            this.createContainer();
            this.render();
            this.bindEvents();
        }

        createContainer() {
            if (this.options.container) {
                this.container = document.querySelector(this.options.container);
            }

            if (!this.container) {
                this.container = document.createElement('div');
                this.container.className = 'custom-pagination-bar';

                let gridWrapper = null;
                const gridSelector = this.options.gridSelector;

                if (gridSelector) {
                    gridWrapper = document.querySelector(gridSelector);
                }

                // 兼容 AG Grid
                if (!gridWrapper) {
                    gridWrapper = document.querySelector('.ag-root-wrapper');
                }

                // 兼容 Handsontable
                if (!gridWrapper) {
                    gridWrapper = document.querySelector('.handsontable');
                }

                if (gridWrapper && gridWrapper.parentNode) {
                    gridWrapper.parentNode.insertBefore(this.container, gridWrapper.nextSibling);
                } else {
                    document.body.appendChild(this.container);
                }
            }

            this.container.style.cssText = `
                display: flex;
                align-items: center;
                justify-content: space-between;
                flex-wrap: wrap;
                gap: 6px 12px;
                width: 100%;
                padding: 8px 12px;
                background: #fafafa;
                border-top: 1px solid #e8e8e8;
                font-size: 12px;
                color: #666;
            `;
        }

        render() {
            const pageSizeOptionsHtml = this.options.pageSizeOptions.map(size =>
                `<option value="${size}" ${size === this.currentPageSize ? 'selected' : ''}>${size}</option>`
            ).join('');

            const totalPages = this._getTotalPages();

            this.container.innerHTML = `
                <div class="page-size-selector" style="display: flex; align-items: center; gap: 5px; flex-shrink: 0;">
                    <span>每页显示:</span>
                    <select class="cp-page-size-select" style="padding: 3px 5px; border: 1px solid #d9d9d9; border-radius: 4px; font-size: 12px; cursor: pointer;">
                        ${pageSizeOptionsHtml}
                    </select>
                    <span>条</span>
                </div>
                <div class="pagination-center" style="display: flex; align-items: center; justify-content: center; gap: 10px; flex-wrap: wrap; flex: 0 1 auto;">
                    <div class="pagination-controls" style="display: flex; align-items: center; gap: 6px; flex-shrink: 0;">
                        <button class="cp-prev-btn" style="padding: 3px 8px; border: 1px solid #d9d9d9; border-radius: 4px; background: #fff; font-size: 12px; cursor: pointer;" ${this.currentPage <= 1 ? 'disabled' : ''}>上一页</button>
                        <span class="cp-page-info" style="font-size: 12px; color: #666; white-space: nowrap;">第 ${this.currentPage} / ${totalPages} 页 (共 ${this.totalRecords} 条)</span>
                        <button class="cp-next-btn" style="padding: 3px 8px; border: 1px solid #d9d9d9; border-radius: 4px; background: #fff; font-size: 12px; cursor: pointer;" ${this.currentPage >= totalPages ? 'disabled' : ''}>下一页</button>
                    </div>
                    <div class="page-jumper" style="display: flex; align-items: center; gap: 5px; flex-shrink: 0;">
                        <span>跳至</span>
                        <input type="number" class="cp-page-input" min="1" max="${totalPages}" placeholder="页码" style="width: 42px; padding: 3px 5px; border: 1px solid #d9d9d9; border-radius: 4px; font-size: 12px; text-align: center;">
                        <span>页</span>
                        <button class="cp-jump-btn" style="padding: 3px 8px; border: 1px solid #d9d9d9; border-radius: 4px; background: #fff; font-size: 12px; cursor: pointer;">跳转</button>
                    </div>
                </div>
                ${this.options.showScrollToTop ? `
                <div class="scroll-to-top-wrapper" style="display: flex; align-items: center; flex-shrink: 0;">
                    <button class="cp-scroll-top-btn" title="回到顶部" style="width: 28px; height: 28px; border-radius: 4px; background: linear-gradient(135deg, #1890ff 0%, #40a9ff 100%); border: none; box-shadow: 0 2px 6px rgba(24, 144, 255, 0.3); cursor: pointer; display: flex; align-items: center; justify-content: center; color: white; transition: all 0.3s ease;">
                        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M12 19V5M5 12l7-7 7 7"/>
                        </svg>
                    </button>
                </div>
                ` : ''}
            `;
        }

        bindEvents() {
            const self = this;

            const pageSizeSelect = this.container.querySelector('.cp-page-size-select');
            if (pageSizeSelect) {
                pageSizeSelect.addEventListener('change', function() {
                    self.currentPageSize = parseInt(this.value);
                    self.currentPage = 1;
                    self._refresh();
                    if (self.options.onPageSizeChange) {
                        self.options.onPageSizeChange(self.currentPageSize);
                    }
                    self._triggerPageChange(self.currentPage, self.currentPageSize);
                });
            }

            const prevBtn = this.container.querySelector('.cp-prev-btn');
            if (prevBtn) {
                prevBtn.addEventListener('click', function() {
                    if (self.currentPage > 1) {
                        self.currentPage--;
                        self._refresh();
                        self._triggerPageChange(self.currentPage, self.currentPageSize);
                    }
                });
            }

            const nextBtn = this.container.querySelector('.cp-next-btn');
            if (nextBtn) {
                nextBtn.addEventListener('click', function() {
                    if (self.currentPage < self._getTotalPages()) {
                        self.currentPage++;
                        self._refresh();
                        self._triggerPageChange(self.currentPage, self.currentPageSize);
                    }
                });
            }

            const jumpBtn = this.container.querySelector('.cp-jump-btn');
            const pageInput = this.container.querySelector('.cp-page-input');
            if (jumpBtn && pageInput) {
                const doJump = function() {
                    const targetPage = parseInt(pageInput.value);
                    const totalPages = self._getTotalPages();
                    if (targetPage >= 1 && targetPage <= totalPages) {
                        self.currentPage = targetPage;
                        self._refresh();
                        self._triggerPageChange(self.currentPage, self.currentPageSize);
                    }
                };
                jumpBtn.addEventListener('click', doJump);
                pageInput.addEventListener('keypress', function(e) {
                    if (e.key === 'Enter') doJump();
                });
            }

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
                    let scrollTarget = null;
                    const gridSelector = self.options.gridSelector;

                    if (gridSelector) {
                        // 先尝试 AG Grid viewport
                        scrollTarget = document.querySelector(gridSelector + ' .ag-body-viewport');
                        // 再尝试 Handsontable 滚动容器
                        if (!scrollTarget) {
                            const gridEl = document.querySelector(gridSelector);
                            if (gridEl) {
                                scrollTarget = gridEl.querySelector('.ht_master .wtHolder');
                            }
                        }
                    }

                    // 全局查找 AG Grid viewport
                    if (!scrollTarget) {
                        scrollTarget = document.querySelector('.ag-body-viewport');
                    }

                    // 全局查找 Handsontable 滚动容器
                    if (!scrollTarget) {
                        scrollTarget = document.querySelector('.ht_master .wtHolder');
                    }

                    if (scrollTarget) {
                        scrollTarget.scrollTo({ top: 0, behavior: 'smooth' });
                    } else {
                        window.scrollTo({ top: 0, behavior: 'smooth' });
                    }
                });
            }
        }

        _getTotalPages() {
            return Math.ceil(this.totalRecords / this.currentPageSize) || 1;
        }

        _refresh() {
            this.render();
            this.bindEvents();
        }

        _triggerPageChange(page, pageSize) {
            if (this.options.onPageChange) {
                this.options.onPageChange(page, pageSize);
            }
        }

        update(totalRecords, currentPage, pageSize) {
            this.totalRecords = totalRecords;
            if (currentPage !== undefined) this.currentPage = currentPage;
            if (pageSize !== undefined) this.currentPageSize = pageSize;
            this._refresh();
        }

        getPaginationParams() {
            return {
                page: this.currentPage,
                pageSize: this.currentPageSize
            };
        }

        destroy() {
            if (this.container) {
                if (this.externalContainer) {
                    // 外部传入的容器只清空内容，不移除 DOM
                    this.container.innerHTML = '';
                } else if (this.container.parentNode) {
                    this.container.parentNode.removeChild(this.container);
                }
            }
            this.container = null;
        }
    }

    CustomPagination.init = function(options = {}) {
        return new CustomPagination(options);
    };

    global.CustomPagination = CustomPagination;

})(window);
