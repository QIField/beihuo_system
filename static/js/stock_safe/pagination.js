/**
 * 安全库存模块私有 —— 服务器端分页组件
 *
 * 依赖：纯原生 DOM + 用户已经引用的 layui / AG Grid 第三方库
 * 说明：本文件是基于项目公共组件 CustomPagination 的源码，复制并重新封装为本模块私有版本。
 *       不引用任何项目内自写的公共代码（如 column-preference、CustomPagination）。
 *       只在需要第三方库 API 时直接调用全局对象（例如 layui.use）。
 *
 * 暴露全局对象：StockSafePagination
 *   - StockSafePagination.init(options)  → 返回分页实例
 *   - 实例方法：update(total, page, size) / getPaginationParams() / destroy()
 *   - 实例属性：currentPage / currentPageSize / totalRecords
 */
(function (global) {
    'use strict';

    class StockSafePagination {
        constructor(options) {
            options = options || {};
            this.options = {
                container: options.container || null,
                gridSelector: options.gridSelector || null,
                // 按截图风格默认页数：20/50/100/200/500
                pageSizeOptions: options.pageSizeOptions || [20, 50, 100, 200, 500],
                defaultPageSize: options.defaultPageSize || 50,
                onPageChange: options.onPageChange || null,
                onPageSizeChange: options.onPageSizeChange || null
            };

            this.currentPage = 1;
            this.currentPageSize = this.options.defaultPageSize;
            this.totalRecords = 0;
            this.container = null;

            this.init();
        }

        init() {
            this.createContainer();
            this.render();
            this.bindEvents();
        }

        /**
         * 创建或获取分页容器：
         * - 如果调用方提供了 container（CSS 选择器），则直接使用该元素（已在模板中摆放）
         * - 否则自动创建一个 div 并插入到 AG Grid 根节点后面（兼容旧用法）
         *
         * 样式说明：
         * - 使用 container 参数时（内嵌在 grid-wrapper 中），不加 border/background/box-shadow，
         *   这些由外层 grid-wrapper 统一提供，仅加一条顶部分隔线。
         * - 无 container 时（自动创建），沿用完整的外框样式以保持独立可用。
         */
        createContainer() {
            var isEmbedded = false;  // 是否内嵌在模板容器中
            if (this.options.container) {
                this.container = document.querySelector(this.options.container);
                if (this.container) isEmbedded = true;
            }
            if (!this.container) {
                this.container = document.createElement('div');
                var gridWrapper = null;
                var gridSelector = this.options.gridSelector;
                if (gridSelector) gridWrapper = document.querySelector(gridSelector);
                if (!gridWrapper) gridWrapper = document.querySelector('.ag-root-wrapper');
                if (gridWrapper && gridWrapper.parentNode) {
                    gridWrapper.parentNode.insertBefore(this.container, gridWrapper.nextSibling);
                } else {
                    document.body.appendChild(this.container);
                }
            }

            // 内联样式：保证零公共 CSS 依赖
            if (isEmbedded) {
                // 内嵌模式：由外层 grid-wrapper 统一提供边框/背景/圆角，此处仅加分隔线
                this.container.style.cssText =
                    'display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:6px 12px;' +
                    'width:100%;padding:12px 16px;' +
                    'border-top:1px solid #f0f0f0;' +
                    'font-size:13px;color:#595959;';
            } else {
                // 独立模式：完整的外框样式
                this.container.style.cssText =
                    'display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:6px 12px;' +
                    'width:100%;padding:12px 16px;' +
                    'background:#fff;border-top:1px solid #f0f0f0;border-radius:0 0 10px 10px;' +
                    'box-shadow:0 2px 12px rgba(0,0,0,0.05);border:1px solid #f5f5f5;border-top:none;' +
                    'font-size:13px;color:#595959;';
            }
        }

        _getTotalPages() {
            return Math.ceil(this.totalRecords / this.currentPageSize) || 1;
        }

        /**
         * 渲染截图风格的分页条：
         *  左：每页显示 [20|50|100|200|500] 条
         *  中：< 上一页  1 2 3 ... 269  下一页 >  到第 [输入框] 页 确定
         *  右：共 N 条
         */
        render() {
            var sizeOpts = this.options.pageSizeOptions;
            var sizeHtml = '';
            for (var i = 0; i < sizeOpts.length; i++) {
                var s = sizeOpts[i];
                sizeHtml += '<option value="' + s + '"' +
                    (s === this.currentPageSize ? ' selected' : '') +
                    '>' + s + '条/页</option>';
            }

            var cur = this.currentPage;
            var totalPages = this._getTotalPages();

            // 页码按钮：首末页 + 当前页±1 + 省略号（...）
            var pages = [];
            var addedDotsL = false, addedDotsR = false;
            pages.push(1);
            if (cur - 1 > 2) { addedDotsL = true; pages.push('dots-l'); }
            var start = Math.max(2, cur - 1);
            var end   = Math.min(totalPages - 1, cur + 1);
            for (var j = start; j <= end; j++) pages.push(j);
            if (cur + 1 < totalPages - 1) { addedDotsR = true; pages.push('dots-r'); }
            if (totalPages > 1) pages.push(totalPages);

            var numHtml = '';
            for (var k = 0; k < pages.length; k++) {
                var it = pages[k];
                if (it === 'dots-l' || it === 'dots-r') {
                    numHtml +=
                        '<span style="padding:0 6px;color:#8c8c8c;letter-spacing:2px;display:inline-flex;' +
                        'align-items:center;height:32px;">...</span>';
                } else {
                    numHtml +=
                        '<button class="ssp-num' + (it === cur ? ' ssp-active' : '') +
                        '" data-page="' + it + '" style="' +
                        'min-width:32px;height:32px;padding:0 10px;border:1px solid #d9d9d9;' +
                        'border-radius:4px;background:#fff;color:#595959;font-size:13px;' +
                        'margin:0 3px;cursor:pointer;' +
                        (it === cur
                            ? 'background:#1890ff;border-color:#1890ff;color:#fff;font-weight:600;'
                            : '') +
                        '">' + it + '</button>';
                }
            }

            var btnStyle =
                'min-width:32px;height:32px;padding:0 10px;border:1px solid #d9d9d9;' +
                'border-radius:4px;background:#fff;color:#595959;font-size:13px;' +
                'margin:0 3px;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;line-height:1;';
            var disStyle = btnStyle + 'color:#bfbfbf;cursor:not-allowed;background:#fafafa;';
            var inputStyle =
                'width:52px;height:32px;padding:0 8px;border:1px solid #d9d9d9;border-radius:4px;' +
                'font-size:13px;text-align:center;color:#595959;';
            var selectStyle =
                'height:32px;padding:0 26px 0 10px;border:1px solid #d9d9d9;border-radius:4px;' +
                'font-size:13px;cursor:pointer;color:#595959;' +
                'background:#fff url("data:image/svg+xml;charset=utf-8,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'12\' height=\'12\' viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'%23595959\' stroke-width=\'2\'%3E%3Cpolyline points=\'6 9 12 15 18 9\'/%3E%3C/svg%3E") no-repeat right 8px center;' +
                '-webkit-appearance:none;-moz-appearance:none;appearance:none;';
            var confirmBtnStyle =
                'height:32px;padding:0 12px;border:1px solid #d9d9d9;border-radius:4px;' +
                'background:#fff;color:#595959;font-size:13px;cursor:pointer;';

            this.container.innerHTML =
                '<div class="ssp-left" style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">' +
                    '<div style="display:flex;align-items:center;gap:5px;">' +
                        '<select class="ssp-size" style="' + selectStyle + '">' + sizeHtml + '</select>' +
                    '</div>' +
                    '<div style="display:flex;align-items:center;gap:0;">' +
                        '<button class="ssp-prev" style="' + (cur <= 1 ? disStyle : btnStyle) + '"' +
                            (cur <= 1 ? ' disabled' : '') +
                            '>&lsaquo;</button>' +
                        numHtml +
                        '<button class="ssp-next" style="' + (cur >= totalPages ? disStyle : btnStyle) + '"' +
                            (cur >= totalPages ? ' disabled' : '') +
                            '>&rsaquo;</button>' +
                    '</div>' +
                '</div>' +
                '<div class="ssp-right" style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">' +
                    '<div style="display:flex;align-items:center;gap:6px;">' +
                        '<span>到第</span>' +
                        '<input type="number" class="ssp-input" min="1" max="' + totalPages + '" value="' + cur + '" style="' + inputStyle + '">' +
                        '<span>页</span>' +
                        '<button class="ssp-jump" style="' + confirmBtnStyle + '">确定</button>' +
                    '</div>' +
                    '<span class="ssp-total" style="font-weight:500;">共 ' +
                        Number(this.totalRecords || 0).toLocaleString() + ' 条</span>' +
                '</div>';
        }

        bindEvents() {
            var self = this;
            var c = this.container;
            if (!c) return;

            var sel = c.querySelector('.ssp-size');
            if (sel) sel.addEventListener('change', function () {
                self.currentPageSize = parseInt(this.value, 10);
                self.currentPage = 1;
                self._refresh();
                if (self.options.onPageSizeChange) self.options.onPageSizeChange(self.currentPageSize);
                self._triggerPageChange();
            });

            var prevBtn = c.querySelector('.ssp-prev');
            if (prevBtn) prevBtn.addEventListener('click', function () {
                if (self.currentPage > 1) {
                    self.currentPage--;
                    self._refresh();
                    self._triggerPageChange();
                }
            });

            var nextBtn = c.querySelector('.ssp-next');
            if (nextBtn) nextBtn.addEventListener('click', function () {
                if (self.currentPage < self._getTotalPages()) {
                    self.currentPage++;
                    self._refresh();
                    self._triggerPageChange();
                }
            });

            var numBtns = c.querySelectorAll('.ssp-num');
            if (numBtns && numBtns.length) {
                for (var i = 0; i < numBtns.length; i++) {
                    (function (btn) {
                        btn.addEventListener('click', function () {
                            var p = parseInt(btn.getAttribute('data-page'), 10);
                            if (!isNaN(p) && p !== self.currentPage) {
                                self.currentPage = p;
                                self._refresh();
                                self._triggerPageChange();
                            }
                        });
                    })(numBtns[i]);
                }
            }

            var jumpBtn = c.querySelector('.ssp-jump');
            var input = c.querySelector('.ssp-input');
            if (jumpBtn && input) {
                var doJump = function () {
                    var val = parseInt(input.value, 10);
                    var tp = self._getTotalPages();
                    if (!isNaN(val) && val >= 1 && val <= tp) {
                        self.currentPage = val;
                        self._refresh();
                        self._triggerPageChange();
                    } else {
                        input.value = self.currentPage;
                    }
                };
                jumpBtn.addEventListener('click', doJump);
                input.addEventListener('keypress', function (e) {
                    if (e.key === 'Enter') doJump();
                });
            }
        }

        _refresh() {
            this.render();
            this.bindEvents();
        }

        _triggerPageChange() {
            if (this.options.onPageChange) {
                this.options.onPageChange(this.currentPage, this.currentPageSize);
            }
        }

        // 对外 API：请求成功后调用以同步后端返回的 total/page/size
        update(totalRecords, currentPage, pageSize) {
            this.totalRecords = totalRecords || 0;
            if (currentPage !== undefined) this.currentPage = currentPage;
            if (pageSize !== undefined) this.currentPageSize = pageSize;
            this._refresh();
        }

        getPaginationParams() {
            return { page: this.currentPage, pageSize: this.currentPageSize };
        }

        destroy() {
            if (this.container && this.container.parentNode) {
                this.container.parentNode.removeChild(this.container);
            }
            this.container = null;
        }
    }

    StockSafePagination.init = function (options) {
        return new StockSafePagination(options);
    };

    global.StockSafePagination = StockSafePagination;

})(window);
