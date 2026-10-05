/**
 * HandsontableBuilder
 * 配置化 Handsontable 初始化构建器
 *
 * 作用：将 new Handsontable、GridColumnMenu、ColumnPreference、CustomPagination
 *      等组件的手动接线收敛到一个配置对象中。
 *
 * 依赖（页面需提前引入）：
 *   - handsontable 库
 *   - /static/js/components/handsontable-builder/sortable-utils.js
 *   - /static/js/components/grid-column-menu/grid-column-menu.js
 *   - /static/js/components/custom-pagination/custom-pagination.js
 *
 * CSS 依赖由本文件自动加载，页面无需手动引入。
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
     * 自动加载依赖 CSS（页面未引入时兜底）
     */
    function loadCssIfNotExists(cssPath) {
        var fullPath = cssPath;
        if (fullPath.indexOf('/') !== 0 && fullPath.indexOf('http') !== 0) {
            fullPath = '/' + fullPath;
        }
        var links = document.querySelectorAll('link[rel="stylesheet"]');
        for (var i = 0; i < links.length; i++) {
            var href = links[i].getAttribute('href') || '';
            if (href.indexOf(fullPath) !== -1 || href.indexOf(cssPath) !== -1) {
                return;
            }
        }
        var link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = fullPath;
        document.head.appendChild(link);
    }

    // 自动加载列菜单和筛选面板样式，避免新页面漏引入
    loadCssIfNotExists('/static/js/components/grid-column-menu/grid-column-menu.css');
    loadCssIfNotExists('/static/js/components/filter_panel/filter-panel.css');

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
     * 注入文本截断所需的 CSS（按 selector 隔离，避免全局污染）
     */
    function injectEllipsisCss(selector) {
        var styleId = 'htb-ellipsis-' + selector.replace(/[^a-zA-Z0-9]/g, '-');
        if (document.getElementById(styleId)) return;

        var css = selector + ' .htb-ellipsis-cell {' +
            'white-space: nowrap;' +
            'overflow: hidden;' +
            'text-overflow: ellipsis;' +
            'display: block;' +
            'max-width: 100%;' +
            'line-height: 1.4;' +
        '}' +
        selector + ' .handsontable .htCore td {' +
            'white-space: nowrap !important;' +
        '}';

        var style = document.createElement('style');
        style.id = styleId;
        style.textContent = css;
        document.head.appendChild(style);
    }

    /**
     * 创建文本截断渲染器（单行省略 + title tooltip）
     */
    function createEllipsisRenderer() {
        return function(instance, td, row, col, prop, value, cellProperties) {
            Handsontable.renderers.TextRenderer.apply(this, arguments);
            var text = (value === null || value === undefined) ? '' : String(value);
            td.innerHTML = '<div class="htb-ellipsis-cell" title="' +
                text.replace(/"/g, '&quot;').replace(/'/g, '&#39;') + '">' +
                text.replace(/\n/g, ' ') +
                '</div>';
            return td;
        };
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
        config.components = config.components || {};
        // 默认开启虚拟滚动，页面可显式设置为 false 关闭
        if (config.components.virtualScroll === undefined) {
            config.components.virtualScroll = true;
        }

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
                if (builder.config.dataUrl === null || builder.config.dataUrl === undefined) {
                    renderLocalData(builder);
                } else {
                    refresh(builder);
                }
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
            renderByDataMode(builder);
            return;
        }

        var url = '/new/api/column_preference?page_key=' + encodeURIComponent(pageKey) +
                  '&grid_key=' + encodeURIComponent(gridKey);
        fetch(url, { credentials: 'same-origin' })
            .then(function(r) { return r.json(); })
            .then(function(resp) {
                if (resp.code === 0 && resp.data && Array.isArray(resp.data) && resp.data.length > 0) {
                    builder.applyingState = true;
                    applyColumnState(columns, resp.data);
                    builder.applyingState = false;
                }
                builder.visibleColumns = columns.filter(function(col) {
                    return !col.hide;
                });
                renderByDataMode(builder);
            })
            .catch(function(e) {
                console.error('[HandsontableBuilder] 加载列偏好失败:', e);
                columns.forEach(function(col) { col.hide = false; });
                builder.visibleColumns = columns.slice();
                renderByDataMode(builder);
            });
    }

    /**
     * 应用后端返回的列状态：顺序、宽度、显隐
     */
    function applyColumnState(columns, state) {
        var stateMap = {};
        state.forEach(function(s, index) {
            if (!s || !s.colId) return;
            stateMap[s.colId] = { state: s, index: index };
        });

        // 按后端记录的顺序排序，未记录的列保持原顺序放在后面
        columns.sort(function(a, b) {
            var idA = String(a.field || a.colId || a.data || '');
            var idB = String(b.field || b.colId || b.data || '');
            var infoA = stateMap[idA];
            var infoB = stateMap[idB];
            if (infoA && infoB) return infoA.index - infoB.index;
            if (infoA) return -1;
            if (infoB) return 1;
            return 0;
        });

        // 应用 width 和 hide
        columns.forEach(function(col) {
            var colId = String(col.field || col.colId || col.data || '');
            var info = stateMap[colId];
            if (!info) return;
            var s = info.state;
            if (s.width !== undefined && s.width !== null && s.width !== '') {
                col.width = parseInt(s.width, 10) || col.width;
            }
            if (s.hide !== undefined) {
                col.hide = !!s.hide;
            }
        });
    }

    function renderByDataMode(builder) {
        if (builder.config.dataUrl === null || builder.config.dataUrl === undefined) {
            renderLocalData(builder);
        } else {
            refresh(builder);
        }
    }

    /**
     * 保存列偏好：顺序、宽度、显隐
     */
    function saveColumnPreference(builder) {
        var config = builder.config;
        var cmConfig = getComponentConfig(config.components, 'columnMenu') || {};
        var cpConfig = getComponentConfig(config.components, 'columnPreference') || {};
        var persist = isEnabled(config.components, 'columnPreference') ||
                      (isEnabled(config.components, 'columnMenu') && cmConfig.persist);
        var pageKey = cpConfig.pageKey || cmConfig.pageKey || config.pageKey || '';
        var gridKey = cpConfig.gridKey || cmConfig.gridKey || config.gridKey || '';

        if (!persist || !pageKey || !gridKey || builder.applyingState) {
            return;
        }

        var columns = builder.columns || [];
        var visibleColumns = builder.visibleColumns || [];
        var visibleSet = {};
        visibleColumns.forEach(function(col) {
            visibleSet[String(col.field || col.colId || col.data || '')] = true;
        });

        var state = columns.map(function(col) {
            var colId = String(col.field || col.colId || col.data || '');
            return {
                colId: colId,
                hide: !visibleSet[colId],
                width: col.width
            };
        });

        fetch('/new/api/column_preference', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                page_key: pageKey,
                grid_key: gridKey,
                column_state: state
            })
        }).catch(function(e) {
            console.error('[HandsontableBuilder] 保存列偏好失败:', e);
        });
    }

    function renderLocalData(builder) {
        var data = builder.config.localData || [];

        // 本地筛选
        if (builder.filterColumn && builder.filterValues && builder.filterValues.length > 0) {
            data = data.filter(function(row) {
                var val = row[builder.filterColumn];
                if (val === undefined || val === null) val = '';
                return builder.filterValues.indexOf(String(val)) !== -1;
            });
        }

        var pageData = data;
        if (builder.pagination) {
            var page = builder.currentPage || 1;
            var pageSize = builder.pageSize || data.length;
            var start = (page - 1) * pageSize;
            var end = start + pageSize;
            pageData = data.slice(start, end);
            builder.pagination.update(data.length, page, pageSize);
        }
        render(builder, pageData);
    }

    function sortLocalData(builder) {
        var data = builder.config.localData || [];
        var colId = builder.sortColumn;
        var dir = builder.sortDir;
        if (!colId || !dir || !data.length) return;

        data.sort(function(a, b) {
            return SortableUtils.compareValues(a[colId], b[colId], dir);
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

        // ellipsisText: 为所有未设置 renderer 的文本列自动添加截断渲染器
        if (isEnabled(components, 'ellipsisText')) {
            injectEllipsisCss(builder.selector);
            builder.visibleColumns.forEach(function(col) {
                if (!col.renderer && (!col.type || col.type === 'text')) {
                    col.renderer = createEllipsisRenderer();
                }
            });
        }

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

        initColumnStateHooks(builder);
        initColumnMenu(builder);
    }

    /**
     * 初始化列状态变化监听：移动、调整宽度
     */
    function initColumnStateHooks(builder) {
        var config = builder.config;
        var cmConfig = getComponentConfig(config.components, 'columnMenu') || {};
        var cpConfig = getComponentConfig(config.components, 'columnPreference') || {};
        var persist = isEnabled(config.components, 'columnPreference') ||
                      (isEnabled(config.components, 'columnMenu') && cmConfig.persist);
        var pageKey = cpConfig.pageKey || cmConfig.pageKey || config.pageKey || '';
        var gridKey = cpConfig.gridKey || cmConfig.gridKey || config.gridKey || '';

        if (!persist || !pageKey || !gridKey) return;
        if (!builder.hot) return;

        var hot = builder.hot;

        hot.addHook('afterColumnMove', function(movedColumns, finalIndex) {
            // Handsontable 可能会复用并清空 movedColumns，立即复制一份
            var movedColumnsCopy = Array.isArray(movedColumns) ? movedColumns.slice() : [];
            var finalIndexCopy = finalIndex;
            console.log('[列偏好] afterColumnMove 触发', { movedColumns: movedColumnsCopy, finalIndex: finalIndexCopy });
            // 延迟一帧，让 Handsontable 完成内部状态更新
            setTimeout(function() {
                try {
                    var visibleColumns = builder.visibleColumns || [];
                    var allColumns = builder.columns || [];

                    console.log('[列偏好] afterColumnMove 参数检查', {
                        isArray: Array.isArray(movedColumnsCopy),
                        length: movedColumnsCopy.length,
                        finalIndex: finalIndexCopy,
                        finalIndexType: typeof finalIndexCopy
                    });
                    if (!Array.isArray(movedColumnsCopy) || movedColumnsCopy.length === 0 ||
                        typeof finalIndexCopy !== 'number') {
                        console.log('[列偏好] afterColumnMove 参数无效，跳过');
                        return;
                    }

                    // 按索引降序取出被移动的列，保持它们在移动前的相对顺序
                    var sortedMovedIndices = movedColumnsCopy.slice().sort(function(a, b) { return b - a; });
                    var movedCols = [];
                    sortedMovedIndices.forEach(function(idx) {
                        movedCols.unshift(visibleColumns[idx]);
                    });

                    // 移除被移动的列
                    var remaining = visibleColumns.filter(function(_, idx) {
                        return movedColumnsCopy.indexOf(idx) === -1;
                    });

                    // finalIndex 即为在剩余列中的插入位置（已移除移动列后的数组）
                    var insertIndex = Math.max(0, Math.min(finalIndexCopy, remaining.length));

                    var newVisibleOrder = remaining.slice(0, insertIndex)
                        .concat(movedCols)
                        .concat(remaining.slice(insertIndex));

                    console.log('[列偏好] afterColumnMove 重排', {
                        movedColumns: movedColumnsCopy,
                        finalIndex: finalIndexCopy,
                        insertIndex: insertIndex,
                        newOrder: newVisibleOrder.map(function(c) { return c.field || c.colId || c.data; })
                    });

                    var visibleSet = {};
                    newVisibleOrder.forEach(function(col) {
                        visibleSet[String(col.field || col.colId || col.data || '')] = true;
                    });

                    var hiddenColumns = allColumns.filter(function(col) {
                        return !visibleSet[String(col.field || col.colId || col.data || '')];
                    });

                    builder.columns = newVisibleOrder.concat(hiddenColumns);
                    builder.visibleColumns = newVisibleOrder;
                    saveColumnPreference(builder);
                } catch (e) {
                    console.warn('[列偏好] afterColumnMove 处理失败:', e);
                }
            }, 0);
        });

        hot.addHook('afterColumnResize', function() {
            // 不同版本 Handsontable 参数顺序不同，直接从 grid 读取各列宽度
            setTimeout(function() {
                try {
                    var visibleColumns = builder.visibleColumns || [];
                    var changed = false;
                    for (var i = 0; i < visibleColumns.length; i++) {
                        var w = hot.getColWidth(i);
                        if (typeof w === 'number' && w > 0) {
                            visibleColumns[i].width = w;
                            changed = true;
                        }
                    }
                    if (changed) {
                        saveColumnPreference(builder);
                    }
                } catch (e) {
                    console.warn('[列偏好] afterColumnResize 处理失败:', e);
                }
            }, 0);
        });
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
            isFilterable: config.isFilterable || null,
            skipInitialLoad: true,
            _originalRows: (config.localData || []).slice()
        };

        menuOptions.onSort = function(colId, direction) {
            builder.sortColumn = colId;
            builder.sortDir = direction;
            builder.currentPage = 1;
            if (typeof config.onSort === 'function') {
                config.onSort(colId, direction);
            }
            if (builder.config.dataUrl === null || builder.config.dataUrl === undefined) {
                sortLocalData(builder);
                renderLocalData(builder);
            } else {
                refresh(builder);
            }
        };

        menuOptions.onColumnVisibilityChange = function(visibleCols) {
            builder.visibleColumns = visibleCols;
            if (typeof config.onColumnVisibilityChange === 'function') {
                config.onColumnVisibilityChange(visibleCols);
            }
            // 同步更新 builder.columns 中的 hide 状态
            var visibleSet = {};
            visibleCols.forEach(function(col) {
                visibleSet[String(col.field || col.colId || col.data || '')] = true;
            });
            builder.columns.forEach(function(col) {
                var colId = String(col.field || col.colId || col.data || '');
                col.hide = !visibleSet[colId];
            });
            // 远程数据模式下列显隐已由 updateSettings 生效，禁止 renderLocalData（localData 为空会清空表格）
            if (builder.config.dataUrl === null || builder.config.dataUrl === undefined) {
                renderLocalData(builder);
            }
            saveColumnPreference(builder);
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
            if (builder.config.dataUrl === null || builder.config.dataUrl === undefined) {
                renderLocalData(builder);
            } else {
                refresh(builder);
            }
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
            if (builder.config.dataUrl === null || builder.config.dataUrl === undefined) {
                builder.currentPage = page !== undefined ? page : builder.currentPage;
                builder.pageSize = pageSize !== undefined ? pageSize : builder.pageSize;
                renderLocalData(builder);
            } else {
                refresh(builder, page, pageSize);
            }
            return builder;
        };

        builder.showPopover = function(options) {
            if (typeof HandsontablePopover === 'undefined') {
                console.error('HandsontablePopover 未加载，请先引入 handsontable-popover.js');
                return;
            }
            HandsontablePopover.getInstance().show(options);
            return builder;
        };

        builder.hidePopover = function() {
            if (typeof HandsontablePopover === 'undefined') return builder;
            HandsontablePopover.getInstance().hide();
            return builder;
        };

        builder.schedulePopoverHide = function() {
            if (typeof HandsontablePopover === 'undefined') return builder;
            HandsontablePopover.getInstance().scheduleHide();
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
