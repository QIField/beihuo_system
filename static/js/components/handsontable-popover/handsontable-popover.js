/**
 * HandsontablePopover
 * 基于 Handsontable 的悬停浮窗组件
 *
 * 特性：
 * - 全局单例，同时只展示一个浮窗
 * - 内部使用 Handsontable 渲染表格
 * - 支持自定义表头和列配置
 * - 支持异步加载数据
 * - 表格带细线边框
 */

var HandsontablePopover = (function() {
    'use strict';

    var instance = null;

    function Popover() {
        this.container = null;
        this.hot = null;
        this.currentTarget = null;
        this.hideTimer = null;
        this.isHovering = false;
    }

    Popover.prototype._ensureContainer = function() {
        if (this.container) return;

        var container = document.createElement('div');
        container.className = 'handsontable-popover';
        container.style.cssText = [
            'position: absolute',
            'z-index: 9999',
            'display: none',
            'background: #fff',
            'border: 1px solid #d0d0d0',
            'border-radius: 4px',
            'box-shadow: 0 4px 12px rgba(0,0,0,0.15)',
            'padding: 8px'
        ].join(';');

        var titleEl = document.createElement('div');
        titleEl.className = 'handsontable-popover-title';
        titleEl.style.cssText = 'font-size: 13px; font-weight: bold; margin-bottom: 6px; color: #333;';
        container.appendChild(titleEl);
        this.titleEl = titleEl;

        var tableContainer = document.createElement('div');
        tableContainer.className = 'handsontable-popover-table';
        container.appendChild(tableContainer);
        this.tableContainer = tableContainer;

        document.body.appendChild(container);
        this.container = container;

        this._bindContainerEvents();
    };

    Popover.prototype._bindContainerEvents = function() {
        var self = this;
        this.container.addEventListener('mouseenter', function() {
            self.isHovering = true;
            self._clearHideTimer();
        });
        this.container.addEventListener('mouseleave', function() {
            self.isHovering = false;
            self._delayHide();
        });
    };

    Popover.prototype._clearHideTimer = function() {
        if (this.hideTimer) {
            clearTimeout(this.hideTimer);
            this.hideTimer = null;
        }
    };

    Popover.prototype._delayHide = function() {
        var self = this;
        this._clearHideTimer();
        this.hideTimer = setTimeout(function() {
            if (!self.isHovering) {
                self.hide();
            }
        }, 200);
    };

    Popover.prototype._position = function(target) {
        var targetRect = target.getBoundingClientRect();
        var popoverWidth = this.container.offsetWidth || 400;
        var popoverHeight = this.container.offsetHeight || 220;

        var left = targetRect.left + window.pageXOffset;
        var top = targetRect.bottom + window.pageYOffset + 6;

        // 右侧溢出则左对齐
        if (left + popoverWidth > window.innerWidth + window.pageXOffset) {
            left = window.innerWidth + window.pageXOffset - popoverWidth - 10;
        }
        // 下方溢出则向上展示
        if (top + popoverHeight > window.innerHeight + window.pageYOffset) {
            top = targetRect.top + window.pageYOffset - popoverHeight - 6;
        }

        this.container.style.left = left + 'px';
        this.container.style.top = top + 'px';
    };

    Popover.prototype._destroyHot = function() {
        if (this.hot) {
            this.hot.destroy();
            this.hot = null;
        }
    };

    Popover.prototype.show = function(options) {
        var self = this;
        this._ensureContainer();
        this._clearHideTimer();
        this.isHovering = true;
        this.currentTarget = options.target;
        this.onHide = options.onHide;

        var title = options.title || '';
        var columns = options.columns || [];
        var data = options.data || [];
        var width = options.width || 400;
        var height = options.height || 200;
        var asyncLoader = options.asyncLoader;

        this.titleEl.innerText = title;
        this.container.style.display = 'block';
        this.container.style.width = width + 'px';

        // 异步加载数据
        if (asyncLoader) {
            var canReuse = this.hot && this._columnsEqual(this.hotColumns, columns);

            // 首次创建时展示加载中；复用实例时保留旧表格，直接更新数据
            if (!canReuse) {
                this.tableContainer.innerHTML = '<div style="padding:20px;text-align:center;color:#999;font-size:12px;">加载中...</div>';
                this._position(options.target);
            }

            asyncLoader(function(err, loadedData) {
                if (!self.container || self.container.style.display === 'none') return;
                if (err) {
                    self.tableContainer.innerHTML = '<div style="padding:20px;text-align:center;color:#f56c6c;font-size:12px;">加载失败: ' + (err.message || '') + '</div>';
                    self.hot = null;
                    self.hotColumns = null;
                    return;
                }
                self._renderTable(loadedData, columns, width, height);
                self._position(options.target);
            });
        } else {
            this._renderTable(data, columns, width, height);
            this._position(options.target);
        }
    };

    Popover.prototype._renderTable = function(data, columns, width, height) {
        var self = this;

        // 如果浮窗已隐藏，不再渲染
        if (!this.container || this.container.style.display === 'none') return;

        // 如果已有实例且列配置相同，直接复用并更新数据
        if (this.hot && this._columnsEqual(this.hotColumns, columns)) {
            this.hot.loadData(data);
            this.hot.render();
            return;
        }

        this._destroyHot();
        this.tableContainer.innerHTML = '';

        var hot = new Handsontable(this.tableContainer, {
            data: data,
            columns: columns,
            rowHeaders: false,
            colHeaders: true,
            licenseKey: 'non-commercial-and-evaluation',
            readOnly: true,
            stretchH: 'all',
            autoColumnSize: false,
            manualColumnResize: false,
            manualRowResize: false,
            contextMenu: false,
            disableVisualSelection: true,
            width: width - 16,
            height: height,
            cells: function(row, col) {
                var cellProperties = {};
                cellProperties.className = 'htMiddle htCenter popover-cell';
                return cellProperties;
            }
        });

        this.hot = hot;
        this.hotColumns = columns;
    };

    Popover.prototype._columnsEqual = function(a, b) {
        if (!a || !b) return false;
        if (a.length !== b.length) return false;
        for (var i = 0; i < a.length; i++) {
            if (a[i].data !== b[i].data) return false;
        }
        return true;
    };

    Popover.prototype.hide = function() {
        if (this.container) {
            this.container.style.display = 'none';
        }
        if (typeof this.onHide === 'function') {
            this.onHide();
        }
        this.currentTarget = null;
    };

    Popover.prototype.destroy = function() {
        this._destroyHot();
        if (this.container && this.container.parentNode) {
            this.container.parentNode.removeChild(this.container);
        }
        this.container = null;
    };

    return {
        getInstance: function() {
            if (!instance) {
                instance = new Popover();
            }
            return instance;
        },
        scheduleHide: function() {
            if (!instance) return;
            instance._delayHide();
        },
        destroy: function() {
            if (instance) {
                instance.destroy();
                instance = null;
            }
        }
    };
})();
