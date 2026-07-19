/**
 * HandsontableBuilder
 * 配置化 Handsontable 初始化构建器
 *
 * 作用：将 new Handsontable、GridColumnMenu、ColumnPreference、CustomPagination
 *      等组件的手动接线收敛到一个配置对象中。
 *
 * 依赖（页面需提前引入）：
 *   - handsontable 库
 *   - /static/js/components/grid-column-menu/grid-column-menu.js
 *   - /static/js/components/custom-pagination/custom-pagination.js
 *
 * 使用示例：
 *   var builder = HandsontableBuilder.create('#myGrid', {
 *       columns: [...],
 *       dataUrl: '/api/data',
 *       paramsBuilder: function() { return {}; },
 *       components: {
 *           pagination: { pageSizeOptions: [50, 100], defaultPageSize: 100 },
 *           columnMenu: { persist: true, pageKey: 'page1', gridKey: 'grid1' },
 *           doubleClickCopy: true,
 *           copyToast: true
 *       }
 *   });
 *
 *   builder.refresh(1);
 */

var HandsontableBuilder = (function() {
    'use strict';

    /**
     * 合并对象（浅合并）
     */
    function assign(target) {
        for (var i = 1; i < arguments.length; i++) {
            var source = arguments[i];
            if (!source) continue;
            for (var key in source) {
                if (source.hasOwnProperty(key)) {
                    target[key] = source[key];
                }
            }
        }
        return target;
    }

    /**
     * 判断某个组件开关是否启用
     */
    function isEnabled(components, key) {
        if (!components) return false;
        var val = components[key];
        return val === true || (typeof val === 'object' && val !== null);
    }

    /**
     * 获取组件配置对象
     */
    function getComponentConfig(components, key) {
        if (!components) return null;
        var val = components[key];
        if (val === true) return {};
        if (typeof val === 'object' && val !== null) return val;
        return null;
    }

    /**
     * 复制文本到剪贴板
     */
    function copyToClipboard(text, onSuccess, onError) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(function() {
                if (typeof onSuccess === 'function') onSuccess();
            }, function(err) {
                if (typeof onError === 'function') onError(err);
            });
        } else {
            var textarea = document.createElement('textarea');
            textarea.value = text;
            textarea.style.position = 'fixed';
            textarea.style.left = '-9999px';
            document.body.appendChild(textarea);
            textarea.select();
            try {
                document.execCommand('copy');
                if (typeof onSuccess === 'function') onSuccess();
            } catch (err) {
                if (typeof onError === 'function') onError(err);
            }
            document.body.removeChild(textarea);
        }
    }

    /**
     * 显示复制成功提示
     */
    function showCopySuccessToast() {
        if (typeof layui !== 'undefined' && layui.layer) {
            layui.layer.msg('已复制到剪贴板', { icon: 1, time: 1000 });
        }
    }

    /**
     * 绑定原生复制事件（双击复制 + 快捷键复制提示）
     * 比 Handsontable 的 afterOnCellDblClick 更稳定，兼容合并单元格。
     */
    function bindNativeCopyEvents(builder) {
        var config = builder.config;
        var components = config.components || {};
        var enableDoubleClickCopy = isEnabled(components, 'doubleClickCopy');
        var enableCopyToast = isEnabled(components, 'copyToast');

        if (!enableDoubleClickCopy && !enableCopyToast) return;
        if (builder.copyEventsBound) return;
        builder.copyEventsBound = true;

        var container = builder.container;

        if (enableDoubleClickCopy) {
            container.addEventListener('dblclick', function(e) {
                var hot = builder.hot;
                if (!hot) return;

                var td = e.target.closest ? e.target.closest('td') : null;
                if (!td) return;

                var coords = hot.getCoords(td);
                if (!coords || coords.row < 0 || coords.col < 0) return;

                var value = hot.getDataAtCell(coords.row, coords.col);
                if (value === undefined || value === null || value === '') return;

                copyToClipboard(String(value), showCopySuccessToast, function() {
                    if (typeof layui !== 'undefined' && layui.layer) {
                        layui.layer.msg('复制失败', { icon: 2 });
                    }
                });
            });
        }

        if (enableCopyToast) {
            container.addEventListener('copy', function(e) {
                var hot = builder.hot;
                var selected = hot && typeof hot.getSelected === 'function' && hot.getSelected();
                if (selected && selected.length > 0) {
                    showCopySuccessToast();
                }
            }, true);
        }
    }

    /**
     * 创建 Handsontable 并自动接线组件
     * @param {string} selector - 网格容器 CSS 选择器
     * @param {Object} config - 构建配置
     * @returns {Object|null} builder 实例
     */
    function create(selector, config) {
        config = config || {};

        var container = document.querySelector(selector);
        if (!container) {
            console.error('[HandsontableBuilder] 找不到网格容器:', selector);
            return null;
        }

        var pgConfig = getComponentConfig(config.components, 'pagination') || {};
        var defaultPageSize = pgConfig.defaultPageSize || 100;

        var builder = {
            selector: selector,
            config: config,
            container: container,
            hot: null,
            pagination: null,
            currentPage: 1,
            pageSize: defaultPageSize,
            sortColumn: null,
            sortDir: null,
            filterColumn: null,
            filterValues: null,
            visibleColumns: null,
            destroyed: false
        };

        initPagination(builder, pgConfig);
        loadColumnPreferenceAndInit(builder);
        bindNativeCopyEvents(builder);

        return builder;
    }

    function initPagination(builder, pgConfig) {
        if (!isEnabled(builder.config.components, 'pagination')) return;
        if (typeof CustomPagination === 'undefined') {
            console.error('[HandsontableBuilder] CustomPagination 组件未加载');
            return;
        }

        builder.pagination = CustomPagination.init({
            container: pgConfig.container || null,
            gridSelector: builder.selector,
            pageSizeOptions: pgConfig.pageSizeOptions || [50, 100, 200, 500],
            defaultPageSize: pgConfig.defaultPageSize || 100,
            showScrollToTop: pgConfig.showScrollToTop !== false,
            onPageChange: function(page, pageSize) {
                builder.currentPage = page;
                builder.pageSize = pageSize;
                refresh(builder);
            }
        });
    }

    function loadColumnPreferenceAndInit(builder) {
        var config = builder.config;
        var cmConfig = getComponentConfig(config.components, 'columnMenu') || {};
        var cpConfig = getComponentConfig(config.components, 'columnPreference') || {};
        var persist = isEnabled(config.components, 'columnPreference') ||
                      (isEnabled(config.components, 'columnMenu') && cmConfig.persist);
        var pageKey = cpConfig.pageKey || cmConfig.pageKey || config.pageKey || '';
        var gridKey = cpConfig.gridKey || cmConfig.gridKey || config.gridKey || '';

        var columns = (config.columns || []).map(function(col) {
            return assign({}, col);
        });
        builder.columns = columns;

        if (!persist || !pageKey || !gridKey) {
            builder.visibleColumns = columns.filter(function(col) {
                return !col.hide;
            });
            refresh(builder);
            return;
        }

        var url = '/new/api/column_preference?page_key=' + encodeURIComponent(pageKey) +
                  '&grid_key=' + encodeURIComponent(gridKey);
        fetch(url, { credentials: 'same-origin' })
            .then(function(r) { return r.json(); })
            .then(function(resp) {
                var hiddenSet = new Set();
                if (resp.code === 0 && resp.data && Array.isArray(resp.data) && resp.data.length > 0) {
                    resp.data.forEach(function(s) {
                        if (s && s.hide) hiddenSet.add(s.colId);
                    });
                }
                columns.forEach(function(col) {
                    var f = col.field || col.colId || col.data;
                    col.hide = hiddenSet.has(f);
                });
                builder.visibleColumns = columns.filter(function(col) {
                    return !col.hide;
                });
                refresh(builder);
            })
            .catch(function(e) {
                console.error('[HandsontableBuilder] 加载列偏好失败:', e);
                columns.forEach(function(col) { col.hide = false; });
                builder.visibleColumns = columns.slice();
                refresh(builder);
            });
    }

    function buildParams(builder) {
        var config = builder.config;
        var params = {};
        if (typeof config.paramsBuilder === 'function') {
            params = assign({}, config.paramsBuilder());
        }

        params.page = builder.currentPage;
        params.limit = builder.pageSize;

        if (builder.sortColumn && builder.sortDir) {
            params.sort_column = builder.sortColumn;
            params.sort_dir = builder.sortDir;
        }

        if (builder.filterColumn && builder.filterValues && builder.filterValues.length > 0) {
            params.filter_column = builder.filterColumn;
            params.filter_values = builder.filterValues;
        }

        if (typeof config.beforeLoad === 'function') {
            params = config.beforeLoad(params) || params;
        }

        return params;
    }

    function serializeParams(params) {
        var queryParts = [];
        for (var key in params) {
            if (key === 'filter_values' && Array.isArray(params[key])) {
                params[key].forEach(function(v) {
                    queryParts.push(encodeURIComponent(key) + '=' + encodeURIComponent(v));
                });
            } else if (params[key] !== undefined && params[key] !== null && params[key] !== '') {
                queryParts.push(encodeURIComponent(key) + '=' + encodeURIComponent(params[key]));
            }
        }
        return queryParts.join('&');
    }

    function refresh(builder, page, pageSize) {
        if (builder.destroyed) return;
        if (page !== undefined) builder.currentPage = page;
        if (pageSize !== undefined) builder.pageSize = pageSize;

        builder.container.innerHTML = '<div class="loading-overlay">加载中...</div>';

        var params = buildParams(builder);
        var queryString = serializeParams(params);
        var config = builder.config;
        var url = config.dataUrl + '?' + queryString;

        console.log('[HandsontableBuilder] refresh: url=' + url);

        fetch(url, { method: 'GET', credentials: 'same-origin' })
            .then(function(response) { return response.json(); })
            .then(function(result) {
                if (builder.destroyed) return;
                console.log('[HandsontableBuilder] refresh: response code=' + result.code + ', msg=' + (result.msg || ''));
                if (result.code !== 0) {
                    builder.container.innerHTML = '<div class="loading-overlay">加载失败: ' + (result.msg || '') + '</div>';
                    if (typeof config.onError === 'function') {
                        config.onError(new Error(result.msg || '加载失败'));
                    }
                    return;
                }

                // 兼容两种返回格式：
                // 1. { code: 0, data: { list: [], total: N } }
                // 2. { code: 0, data: [], count: N }（旧版 LayUI 风格）
                var list = [];
                var total = 0;
                if (result.data && Array.isArray(result.data.list)) {
                    list = result.data.list;
                    total = result.data.total || 0;
                } else if (Array.isArray(result.data)) {
                    list = result.data;
                    total = result.count || list.length;
                }

                console.log('[HandsontableBuilder] refresh: list.length=' + list.length + ', total=' + total);

                if (typeof config.dataTransform === 'function') {
                    list = config.dataTransform(list) || list;
                    console.log('[HandsontableBuilder] refresh: after transform list.length=' + list.length);
                }

                if (builder.pagination) {
                    builder.pagination.update(total, builder.currentPage, builder.pageSize);
                }

                render(builder, list);

                if (typeof config.afterLoad === 'function') {
                    config.afterLoad(result);
                }
            })
            .catch(function(error) {
                if (builder.destroyed) return;
                console.error('[HandsontableBuilder] 加载数据失败:', error);
                builder.container.innerHTML = '<div class="loading-overlay">加载失败: ' + error.message + '</div>';
                if (typeof config.onError === 'function') {
                    config.onError(error);
                }
            });
    }

    function render(builder, data) {
        var config = builder.config;
        var mergeCells = [];
        if (typeof config.mergeCellsBuilder === 'function') {
            mergeCells = config.mergeCellsBuilder(data) || [];
        }

        var rowHeight = config.rowHeight || 24;
        var rowHeights = Array(data.length).fill(rowHeight);

        builder.container.innerHTML = '';

        if (builder.hot) {
            builder.hot.destroy();
            builder.hot = null;
        }

        var components = config.components || {};
        var enableContextMenu = isEnabled(components, 'contextMenu');
        var enableShortcuts = isEnabled(components, 'shortcuts');
        var enableVirtualScroll = isEnabled(components, 'virtualScroll');

        var userAfterGetColHeader = null;
        if (config.handsontableOptions && typeof config.handsontableOptions.afterGetColHeader === 'function') {
            userAfterGetColHeader = config.handsontableOptions.afterGetColHeader;
        }

        var stretchH = (config.handsontableOptions && config.handsontableOptions.stretchH) || 'none';

        var options = assign({}, config.handsontableOptions || {}, {
            data: data,
            columns: builder.visibleColumns,
            mergeCells: mergeCells,
            rowHeaders: false,
            colHeaders: true,
            height: '100%',
            width: '100%',
            stretchH: stretchH,
            licenseKey: 'non-commercial-and-evaluation',
            rowHeights: rowHeights,
            autoRowSize: false,
            autoColumnSize: false,
            autoWrapRow: false,
            renderAllRows: !enableVirtualScroll,
            readOnly: config.readOnly !== false,
            disableVisualSelection: false,
            selectionMode: config.selectionMode || 'multiple',
            copyPaste: enableShortcuts !== false,
            contextMenu: enableContextMenu === true,
            manualColumnResize: true,
            manualColumnMove: true,
            manualRowResize: false,
            columnSorting: false,
            filters: false,
            dropdownMenu: false,
            afterGetColHeader: function(col, TH) {
                var columns = this.getSettings().columns;
                var colDef = columns && columns[col] ? columns[col] : null;
                if (typeof GridColumnMenu !== 'undefined') {
                    GridColumnMenu.addButtonToHandsontableHeaderCell(TH, colDef, builder.selector);
                }
                if (typeof userAfterGetColHeader === 'function') {
                    userAfterGetColHeader.call(this, col, TH);
                }
            }
        });

        builder.hot = new Handsontable(builder.container, options);

        initColumnMenu(builder);
    }

    function initColumnMenu(builder) {
        var config = builder.config;
        var components = config.components || {};
        if (!isEnabled(components, 'columnMenu') && !isEnabled(components, 'columnPreference')) return;

        if (typeof GridColumnMenu === 'undefined') {
            console.warn('[HandsontableBuilder] GridColumnMenu 未加载');
            return;
        }

        var cmConfig = getComponentConfig(components, 'columnMenu') || {};
        var cpConfig = getComponentConfig(components, 'columnPreference') || {};
        var persist = isEnabled(components, 'columnPreference') ||
                      (isEnabled(components, 'columnMenu') && cmConfig.persist);
        var pageKey = cpConfig.pageKey || cmConfig.pageKey || config.pageKey || '';
        var gridKey = cpConfig.gridKey || cmConfig.gridKey || config.gridKey || '';

        var menuOptions = {
            persist: persist,
            pageKey: pageKey,
            gridKey: gridKey,
            skipInitialLoad: true
        };

        menuOptions.onSort = function(colId, direction) {
            builder.sortColumn = colId;
            builder.sortDir = direction;
            builder.currentPage = 1;
            if (typeof config.onSort === 'function') {
                config.onSort(colId, direction);
            }
            refresh(builder);
        };

        menuOptions.onColumnVisibilityChange = function(visibleCols) {
            builder.visibleColumns = visibleCols;
            if (typeof config.onColumnVisibilityChange === 'function') {
                config.onColumnVisibilityChange(visibleCols);
            }
        };

        menuOptions.onDataRefresh = function(filterState) {
            var activeFilters = filterState.filters || {};
            var keys = Object.keys(activeFilters);
            if (keys.length > 0) {
                builder.filterColumn = keys[0];
                builder.filterValues = activeFilters[keys[0]];
            } else {
                builder.filterColumn = null;
                builder.filterValues = null;
            }
            builder.currentPage = 1;
            if (typeof config.onDataRefresh === 'function') {
                config.onDataRefresh(filterState);
            } else if (typeof config.onFilter === 'function') {
                config.onFilter(filterState);
            }
            refresh(builder);
        };

        if (typeof config.getFilterValues === 'function') {
            menuOptions.getFilterValues = function(colId, callback) {
                var params = {};
                if (typeof config.paramsBuilder === 'function') {
                    params = assign({}, config.paramsBuilder());
                }
                delete params.page;
                delete params.limit;
                delete params.sort_column;
                delete params.sort_dir;
                delete params.filter_column;
                delete params.filter_values;
                params.column = colId;
                config.getFilterValues(colId, callback, params);
            };
        }

        GridColumnMenu.init(builder.hot, builder.selector, builder.columns, menuOptions);
    }

    function reset(builder) {
        builder.sortColumn = null;
        builder.sortDir = null;
        builder.filterColumn = null;
        builder.filterValues = null;
        builder.currentPage = 1;
        refresh(builder);
    }

    function destroy(builder) {
        if (!builder || builder.destroyed) return;

        if (builder.pagination && typeof builder.pagination.destroy === 'function') {
            builder.pagination.destroy();
            builder.pagination = null;
        }

        if (builder.hot && typeof builder.hot.destroy === 'function') {
            try {
                builder.hot.destroy();
            } catch (e) {}
            builder.hot = null;
        }

        builder.destroyed = true;
    }

    function createBuilderWithApi(selector, config) {
        var builder = create(selector, config);
        if (!builder) return null;

        builder.refresh = function(page, pageSize) {
            refresh(builder, page, pageSize);
            return builder;
        };

        builder.reset = function() {
            reset(builder);
            return builder;
        };

        builder.destroy = function() {
            destroy(builder);
        };

        return builder;
    }

    return {
        create: createBuilderWithApi,
        destroy: destroy
    };
})();
