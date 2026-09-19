/**
 * Grid Column Menu Component
 * AG Grid 表头列菜单组件
 *
 * 功能：
 *  - 在表头标题旁渲染下拉箭头按钮
 *  - 一级菜单：升序 / 降序 / 表格列 / 筛选
 *  - 二级面板：列勾选（显隐）/ 值筛选（带搜索框 + 复选框）
 *  - 列显隐变更：批量 applyColumnState 提交
 *  - 排序：仅维护状态，通过 onSort 回调由调用方决定如何排序（默认场景为后端排序）
 *  - 筛选：内部数据筛选（基于 _originalRows 缓存）或 onDataRefresh 回调
 *  - 持久化：通过 persist:true 自动接入 ColumnPreference（按用户保存列状态）
 *
 * Usage:
 *   GridColumnMenu.init(gridApi, '#myGrid', columnDefs, {
 *       columnApi: gridColumnApi,
 *       gridOptions: gridOptions,
 *       onSort: function(colId, direction) { ... },
 *       onDataRefresh: function(filterState) { ... },
 *       persist: true,
 *       pageKey: 'ks_inquiry_records',
 *       gridKey: 'detail_grid'
 *   });
 *
 * 依赖：
 *  - filter-panel.css 中的 .filter-dropdown-panel / .filter-dropdown-item 等通用样式
 *  - 可选：column-preference.js（开启 persist 时）
 */

var GridColumnMenu = (function() {
    'use strict';

    var menuConfig = {
        grids: {},
        activeLevel1Menu: null,
        activeLevel2Panel: null
    };
    var currentPanel = null;
    var currentMode = null;   // 'columnVisibility' | 'columnFilter'
    var currentField = null;

    // ==================== Handsontable 检测 ====================

    function _isHandsontable(api) {
        return api && typeof api.updateSettings === 'function' && typeof api.getPlugin === 'function';
    }

    // ==================== 视口边界适配 ====================

    /**
     * 检测元素是否超出视口右侧，若超出则向左翻转
     * @param {HTMLElement} element - 已挂载到 DOM 的定位元素
     * @param {DOMRect} anchorRect - 触发源（按钮/一级菜单）的边界矩形
     * @param {string} direction - 当前展开方向：'right'（二级面板默认向右）|'bottom'（一级菜单默认向下）
     */
    function _fitToViewport(element, anchorRect, direction) {
        if (!element || !anchorRect) return;
        var rect = element.getBoundingClientRect();
        // 未获得有效尺寸时不调整，避免元素尚未完成布局导致误判
        if (!rect.width || !rect.height) return;

        var viewportWidth = document.documentElement.clientWidth || window.innerWidth;
        if (rect.right <= viewportWidth) return;

        var gap = 4;
        var newLeft;
        if (direction === 'right') {
            // 二级面板：从右侧翻转到锚点左侧
            newLeft = anchorRect.left - rect.width - gap;
        } else {
            // 一级菜单：右边缘与锚点右边缘对齐
            newLeft = anchorRect.right - rect.width;
        }
        element.style.left = Math.max(gap, newLeft) + 'px';
    }

    // ==================== 初始化 ====================

    function init(gridApi, gridSelector, columnDefs, options) {
        if (!gridApi) return;
        options = options || {};

        var isHandsontable = _isHandsontable(gridApi);

        // 解析 columnApi / gridOptions
        var columnApi = options.columnApi || null;
        var gridOptions = options.gridOptions || null;
        if (!isHandsontable) {
            try {
                if (!columnApi && gridApi.gridOptionsWrapper && gridApi.gridOptionsWrapper.columnApi) {
                    columnApi = gridApi.gridOptionsWrapper.columnApi;
                }
            } catch (e) {}
            try {
                if (!columnApi && gridApi.columnApi) columnApi = gridApi.columnApi;
            } catch (e) {}
            try {
                if (!columnApi && typeof gridApi.getColumnDef === 'function') columnApi = gridApi;
            } catch (e) {}
        }

        // 收集初始隐藏列
        var hiddenCols = new Set();
        if (isHandsontable) {
            columnDefs.forEach(function(col) {
                if (col.hide) hiddenCols.add(col.field || col.colId || col.data);
            });
        } else {
            try {
                var states = null;
                if (columnApi && typeof columnApi.getColumnState === 'function') {
                    states = columnApi.getColumnState();
                } else if (typeof gridApi.getColumnState === 'function') {
                    states = gridApi.getColumnState();
                }
                if (states) {
                    states.forEach(function(s) { if (s.hide) hiddenCols.add(s.colId); });
                }
            } catch (e) {
                columnDefs.forEach(function(col) {
                    if (col.hide) hiddenCols.add(col.field || col.colId);
                });
            }
        }

        // 若该表格已初始化过，保留之前的筛选、排序、列显隐状态，避免表格重绘后状态丢失
        var existingInfo = menuConfig.grids[gridSelector] || null;
        var preservedHiddenColumns = existingInfo ? existingInfo.hiddenColumns : null;
        var preservedColumnFilters = existingInfo ? existingInfo.columnFilters : null;
        var preservedSortColumn = existingInfo ? existingInfo.sortColumn : null;
        var preservedSortDir = existingInfo ? existingInfo.sortDir : null;

        menuConfig.grids[gridSelector] = {
            api: gridApi,
            columnApi: columnApi,
            gridOptions: gridOptions,
            columnDefs: columnDefs,
            hiddenColumns: preservedHiddenColumns || hiddenCols,
            columnFilters: preservedColumnFilters || {},
            _originalRows: null,
            hasExternalFilter: false,
            isHandsontable: isHandsontable,
            sortColumn: preservedSortColumn || null,
            sortDir: preservedSortDir || null,
            onSort: options.onSort || null,
            onDataRefresh: options.onDataRefresh || null,
            getFilterValues: options.getFilterValues || null,
            isFilterable: options.isFilterable || null,
            onColumnVisibilityChange: options.onColumnVisibilityChange || null,
            persist: !!options.persist,
            pageKey: options.pageKey || '',
            gridKey: options.gridKey || '',
            skipInitialLoad: !!options.skipInitialLoad
        };

        if (!isHandsontable) {
            // 注册外部筛选器（用于 AG Grid 内部 onFilterChanged 触发筛选时回调到我们）
            _registerExternalFilter(gridApi, gridSelector);

            // 禁用 AG Grid 内部 sort 状态：sort 由本组件统一接管。
            // 否则 setRowData 后 AG Grid 会按它自己缓存的 sort 状态再排一次，
            // 覆盖调用方在 onSort 回调里做的前端排序结果。
            try {
                var sortApi = columnApi || gridApi;
                if (sortApi && typeof sortApi.applyColumnState === 'function') {
                    sortApi.applyColumnState({ defaultState: { sort: null, sortIndex: null } });
                } else if (typeof gridApi.setSortModel === 'function') {
                    gridApi.setSortModel(null);
                }
            } catch (e) {}

            // 接入持久化组件
            if (options.persist && typeof ColumnPreference !== 'undefined' &&
                options.pageKey && options.gridKey) {
                ColumnPreference.init(gridApi, {
                    columnApi: columnApi,
                    pageKey: options.pageKey,
                    gridKey: options.gridKey,
                    onApplied: function(state) {
                        // 列状态恢复后，同步内部 hiddenColumns，并刷新表头按钮
                        var info = menuConfig.grids[gridSelector];
                        if (!info) return;
                        info.hiddenColumns = new Set();
                        state.forEach(function(s) {
                            if (s.hide) info.hiddenColumns.add(s.colId);
                        });
                        setTimeout(function() {
                            addMenuButtonsToHeaders(gridSelector);
                        }, 50);

                        // 调用外部 onApplied 回调（如果提供）
                        if (typeof options.onApplied === 'function') {
                            try {
                                options.onApplied(state);
                            } catch (e) {
                                console.warn('[GridColumnMenu] onApplied callback error:', e);
                            }
                        }

                        // 外部回调可能修改了列状态，重新同步 hiddenColumns
                        setTimeout(function() {
                            var api = info.columnApi || info.api;
                            if (!api || typeof api.getColumnState !== 'function') return;
                            var currentState = api.getColumnState();
                            info.hiddenColumns = new Set();
                            currentState.forEach(function(s) {
                                if (s.hide) info.hiddenColumns.add(s.colId);
                            });
                            addMenuButtonsToHeaders(gridSelector);
                        }, 100);
                    }
                });
            }
        }

        // Handsontable 持久化：默认加载列状态；若外部已预加载，则跳过
        if (isHandsontable && options.persist && options.pageKey && options.gridKey && !options.skipInitialLoad) {
            _loadHandsontableColumnPreference(gridApi, gridSelector, options.pageKey, options.gridKey);
        }

        // 延迟添加菜单按钮（等表格渲染表头，作为兜底）
        setTimeout(function() {
            addMenuButtonsToHeaders(gridSelector);
        }, 100);
    }

    function _loadHandsontableColumnPreference(hot, gridSelector, pageKey, gridKey) {
        var url = '/new/api/column_preference?page_key=' + encodeURIComponent(pageKey) +
                  '&grid_key=' + encodeURIComponent(gridKey);
        fetch(url, { credentials: 'same-origin' })
            .then(function(r) { return r.json(); })
            .then(function(resp) {
                if (resp.code !== 0 || !resp.data) return;
                var state = resp.data;
                if (!Array.isArray(state) || state.length === 0) return;

                var info = menuConfig.grids[gridSelector];
                if (!info) return;

                info.hiddenColumns = new Set();
                state.forEach(function(s) {
                    if (s && s.hide) info.hiddenColumns.add(s.colId);
                });

                // 应用显隐
                var visibleColumns = info.columnDefs.filter(function(col) {
                    var f = col.field || col.colId || col.data;
                    return !info.hiddenColumns.has(f);
                });
                hot.updateSettings({ columns: visibleColumns });

                // 表头重建后重新挂按钮
                setTimeout(function() {
                    addMenuButtonsToHeaders(gridSelector);
                }, 100);
            })
            .catch(function(e) {
                console.error('[GridColumnMenu] Handsontable 加载列偏好失败:', e);
            });
    }

    function _saveHandsontableColumnPreference(hot, gridSelector, pageKey, gridKey) {
        var info = menuConfig.grids[gridSelector];
        if (!info || !info.columnDefs) return;

        var state = info.columnDefs.map(function(col) {
            var f = col.field || col.colId || col.data;
            return { colId: f, hide: info.hiddenColumns.has(f) };
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
            console.error('[GridColumnMenu] Handsontable 保存列偏好失败:', e);
        });
    }

    function _registerExternalFilter(gridApi, gridSelector) {
        // 优先：AG Grid Enterprise 提供的 addExternalFilter
        try {
            if (typeof gridApi.addExternalFilter === 'function') {
                gridApi.addExternalFilter({
                    doesFilterPass: function(params) {
                        return _doesRowPass(params.data, gridSelector);
                    },
                    isFilterActive: function() {
                        return _hasActiveFilter(gridSelector);
                    }
                });
                menuConfig.grids[gridSelector].hasExternalFilter = true;
                return;
            }
        } catch (e) {}

        // 回退：注入 gridOptions（社区版）
        try {
            var targetGridOptions = null;
            if (gridApi.gridOptionsWrapper && gridApi.gridOptionsWrapper.gridOptions) {
                targetGridOptions = gridApi.gridOptionsWrapper.gridOptions;
            }
            if (targetGridOptions) {
                var origIsActive = targetGridOptions.isExternalFilterPresent;
                var origDoesPass = targetGridOptions.doesExternalFilterPass;
                targetGridOptions.isExternalFilterPresent = function() {
                    if (_hasActiveFilter(gridSelector)) return true;
                    if (typeof origIsActive === 'function') return origIsActive.call(this);
                    return false;
                };
                targetGridOptions.doesExternalFilterPass = function(node) {
                    if (!_doesRowPass(node.data, gridSelector)) return false;
                    if (typeof origDoesPass === 'function') return origDoesPass.call(this, node);
                    return true;
                };
                menuConfig.grids[gridSelector].hasExternalFilter = true;
            }
        } catch (e) {}
    }

    function _hasActiveFilter(gridSelector) {
        var info = menuConfig.grids[gridSelector];
        if (!info || !info.columnFilters) return false;
        for (var k in info.columnFilters) {
            if (info.columnFilters[k] && info.columnFilters[k].length > 0) return true;
        }
        return false;
    }

    function _doesRowPass(rowData, gridSelector) {
        var info = menuConfig.grids[gridSelector];
        if (!info || !info.columnFilters || !rowData) return true;
        for (var fColId in info.columnFilters) {
            var values = info.columnFilters[fColId];
            if (!values || values.length === 0) continue;
            var cellValue = rowData[fColId];
            var cellStr = cellValue === undefined || cellValue === null ? '' : String(cellValue);
            if (values.indexOf(cellStr) === -1) return false;
        }
        return true;
    }

    // ==================== 表头按钮 ====================

    function addMenuButtonsToHeaders(gridSelector) {
        var gridDiv = document.querySelector(gridSelector);
        if (!gridDiv) return;

        var info = menuConfig.grids[gridSelector];
        if (!info) return;

        if (info.isHandsontable) {
            _addMenuButtonsToHandsontableHeaders(gridDiv, gridSelector, info);
        } else {
            _addMenuButtonsToAgGridHeaders(gridDiv, gridSelector, info);
        }
    }

    function _addMenuButtonsToAgGridHeaders(gridDiv, gridSelector, info) {
        var headerCells = gridDiv.querySelectorAll('.ag-header-cell');
        if (headerCells.length === 0) {
            setTimeout(function() { addMenuButtonsToHeaders(gridSelector); }, 200);
            return;
        }

        headerCells.forEach(function(cell) {
            if (cell.querySelector('.ag-col-menu-btn')) return;

            var headerTextDiv = cell.querySelector('.ag-header-cell-text');
            if (!headerTextDiv) return;

            var colId = cell.getAttribute('col-id') || cell.getAttribute('data-col-id');
            if (!colId) return;

            var menuBtn = _createMenuBtn(colId, gridSelector);
            headerTextDiv.appendChild(menuBtn);
        });

        // 刷新表头按钮高亮状态
        refreshMenuButtonStates(gridSelector);
    }

    function _addMenuButtonsToHandsontableHeaders(gridDiv, gridSelector, info) {
        // 通过 afterGetColHeader 钩子稳定挂载按钮，这里仅做兜底重试
        var headerCells = gridDiv.querySelectorAll('.ht_clone_top .htCore thead th');
        if (headerCells.length === 0) {
            setTimeout(function() { addMenuButtonsToHeaders(gridSelector); }, 200);
            return;
        }

        headerCells.forEach(function(cell, index) {
            var colDef = info.columnDefs[index];
            _addButtonToHandsontableHeaderCell(cell, colDef, gridSelector);
        });

        // 刷新表头按钮高亮状态
        refreshMenuButtonStates(gridSelector);
    }



    function _addButtonToHandsontableHeaderCell(TH, colDef, gridSelector) {
        if (!TH) return;
        var colHeader = TH.querySelector('.colHeader') || TH;
        if (colHeader.querySelector('.ag-col-menu-btn')) return;
        // 跳过角标单元格
        if (TH.classList.contains('ht__corner')) return;

        if (!colDef) return;
        var colId = colDef.field || colDef.colId || colDef.data || 'index';

        var menuBtn = _createMenuBtn(colId, gridSelector, { noHover: true });
        // Handsontable 表头：按钮绝对定位到标题右方，默认显示，大小与 AG Grid 一致
        colHeader.style.position = 'relative';
        colHeader.style.paddingRight = '22px';
        menuBtn.style.position = 'absolute';
        menuBtn.style.right = '0px';
        menuBtn.style.top = '50%';
        menuBtn.style.transform = 'translateY(-50%)';
        colHeader.appendChild(menuBtn);
        refreshMenuButtonStates(gridSelector);
    }

    function _createMenuBtn(colId, gridSelector, options) {
        options = options || {};
        var menuBtn = document.createElement('span');
        menuBtn.className = 'ag-col-menu-btn';
        menuBtn.setAttribute('data-col-id', colId);
        menuBtn.setAttribute('data-grid-selector', gridSelector);
        menuBtn.innerHTML = '';
        menuBtn.style.cssText = 'cursor: pointer; user-select: none;';

        if (!options.noHover) {
            menuBtn.addEventListener('mouseenter', function() { this.style.opacity = '1'; });
            menuBtn.addEventListener('mouseleave', function() { this.style.opacity = ''; });
        } else {
            menuBtn.style.opacity = '1';
        }

        function onMenuBtnActivate(e) {
            e.stopPropagation();
            e.preventDefault();
            var targetColId = this.getAttribute('data-col-id');
            var targetGridSelector = this.getAttribute('data-grid-selector');
            var targetInfo = menuConfig.grids[targetGridSelector];
            if (targetInfo) showLevel1Menu(this, targetColId, targetInfo, targetGridSelector);
        }

        menuBtn.addEventListener('mousedown', function(e) {
            e.stopPropagation();
            e.preventDefault();
        });
        menuBtn.addEventListener('click', onMenuBtnActivate);

        return menuBtn;
    }

    /**
     * 刷新表头菜单按钮状态（排序/筛选后高亮提醒）
     * @param {string} gridSelector - 网格选择器
     */
    function refreshMenuButtonStates(gridSelector) {
        var info = menuConfig.grids[gridSelector];
        if (!info) return;

        var buttons = document.querySelectorAll('.ag-col-menu-btn[data-grid-selector="' + gridSelector + '"]');
        buttons.forEach(function(btn) {
            var colId = btn.getAttribute('data-col-id');
            var hasSort = info.sortColumn === colId;
            var hasFilter = info.columnFilters[colId] && info.columnFilters[colId].length > 0;

            if (hasSort || hasFilter) {
                btn.classList.add('has-condition');
            } else {
                btn.classList.remove('has-condition');
            }
        });
    }

    // ==================== 一级菜单 ====================

    function showLevel1Menu(anchor, colId, gridInfo, gridSelector) {
        closeAll();

        var menu = document.createElement('div');
        menu.className = 'filter-dropdown-panel show';
        menu.style.cssText = 'position: fixed; display: block; min-width: 110px; z-index: 999999999; padding: 4px 0;';

        var isActiveSort = gridInfo.sortColumn === colId;
        var isAsc = isActiveSort && gridInfo.sortDir === 'asc';
        var isDesc = isActiveSort && gridInfo.sortDir === 'desc';
        var activeBg = 'background: #2196f3; color: #fff;';
        var sortAscStyle = isAsc ? activeBg : '';
        var sortDescStyle = isDesc ? activeBg : '';

        var filterEnabled = !gridInfo.isFilterable || gridInfo.isFilterable(colId);
        var filterItemHtml = filterEnabled ?
            '<div class="col-menu-item" data-action="filter" style="padding: 8px 16px; cursor: pointer; font-size: 13px; color: #333; display: flex; justify-content: space-between; align-items: center;">' +
                '<span>筛选</span><span style="color: #999; font-size: 10px;">▸</span>' +
            '</div>' : '';

        menu.innerHTML =
            '<div class="col-menu-item" data-action="sortAsc" style="padding: 8px 16px; cursor: pointer; font-size: 13px; color: #333; display: flex; align-items: center;' + sortAscStyle + '">' +
                '<span style="margin-right: 8px;">↑</span><span>升序</span>' +
            '</div>' +
            '<div class="col-menu-item" data-action="sortDesc" style="padding: 8px 16px; cursor: pointer; font-size: 13px; color: #333; display: flex; align-items: center;' + sortDescStyle + '">' +
                '<span style="margin-right: 8px;">↓</span><span>降序</span>' +
            '</div>' +
            '<div style="height: 1px; background: #e0e0e0; margin: 4px 0;"></div>' +
            '<div class="col-menu-item" data-action="columns" style="padding: 8px 16px; cursor: pointer; font-size: 13px; color: #333; display: flex; justify-content: space-between; align-items: center;">' +
                '<span>表格列</span><span style="color: #999; font-size: 10px;">▸</span>' +
            '</div>' +
            filterItemHtml;

        var rect = anchor.getBoundingClientRect();
        // 初始位置左对齐按钮并保留原有 20px 偏移，左侧不超出视口
        menu.style.left = Math.max(4, rect.left - 20) + 'px';
        menu.style.top = (rect.bottom + 2) + 'px';

        document.body.appendChild(menu);
        menuConfig.activeLevel1Menu = menu;

        menu.querySelectorAll('.col-menu-item').forEach(function(item) {
            var action = item.getAttribute('data-action');
            var originalBg = item.style.background;
            var originalColor = item.style.color;
            item.addEventListener('mouseenter', function() {
                if ((action === 'sortAsc' && isAsc) || (action === 'sortDesc' && isDesc)) {
                    this.style.background = '#1976d2';
                } else {
                    this.style.background = '#f5f5f5';
                    this.style.color = '#333';
                }
            });
            item.addEventListener('mouseleave', function() {
                this.style.background = originalBg;
                this.style.color = originalColor || '#333';
            });
            item.addEventListener('click', function(e) {
                e.stopPropagation();
                if (action === 'columns') {
                    showColumnVisibilityPanel(menu, gridInfo, gridSelector);
                } else if (action === 'filter') {
                    showColumnFilterPanel(menu, colId, gridInfo, gridSelector);
                } else if (action === 'sortAsc') {
                    applyColumnSort(colId, 'asc', gridSelector);
                } else if (action === 'sortDesc') {
                    applyColumnSort(colId, 'desc', gridSelector);
                }
            });
        });
    }

    // ==================== 二级面板：列勾选 ====================

    function showColumnVisibilityPanel(anchorMenu, gridInfo, gridSelector) {
        closeLevel2Panel();

        var panel = document.createElement('div');
        panel.className = 'filter-dropdown-panel show';
        panel.style.cssText = 'position: fixed; display: block; min-width: 180px; z-index: 999999999; max-height: 400px;';

        var allColumns = gridInfo.columnDefs;
        var hiddenCols = gridInfo.hiddenColumns;

        var listHtml = '';
        allColumns.forEach(function(col) {
            var colField = col.field || col.colId || col.data;
            var colLabel = col.headerName || col.title || col.field || col.data || String(colField);
            var isVisible = !hiddenCols.has(colField);
            var checkedAttr = isVisible ? 'checked' : '';
            listHtml += '<div class="filter-dropdown-item col-visibility-item" data-field="' + colField +
                '" data-grid="' + gridSelector + '" onclick="GridColumnMenu.toggleColVisibilityCheckbox(this)">' +
                '<input type="checkbox" ' + checkedAttr + ' onclick="event.stopPropagation()">' +
                '<label>' + colLabel + '</label>' +
            '</div>';
        });

        panel.innerHTML =
            '<div class="filter-dropdown-header">列显示</div>' +
            '<div class="filter-dropdown-list" style="max-height: 300px; overflow-y: auto;">' + listHtml + '</div>' +
            '<div class="filter-dropdown-footer">' +
                '<button onclick="GridColumnMenu.colVisibilitySelectAll(\'' + gridSelector + '\', true)">全选</button>' +
                '<button onclick="GridColumnMenu.colVisibilitySelectAll(\'' + gridSelector + '\', false)">全不选</button>' +
            '</div>';

        var anchorRect = anchorMenu.getBoundingClientRect();
        panel.style.left = (anchorRect.right + 4) + 'px';
        panel.style.top = anchorRect.top + 'px';

        document.body.appendChild(panel);
        _fitToViewport(panel, anchorRect, 'right');
        menuConfig.activeLevel2Panel = panel;
        currentPanel = panel;
        currentMode = 'columnVisibility';
        currentField = gridSelector;
    }

    function toggleColVisibilityCheckbox(item) {
        var checkbox = item.querySelector('input');
        checkbox.checked = !checkbox.checked;
        var field = item.getAttribute('data-field');
        var gridSelector = item.getAttribute('data-grid');
        var info = menuConfig.grids[gridSelector];
        if (!info || !field) return;
        if (checkbox.checked) info.hiddenColumns.delete(field);
        else info.hiddenColumns.add(field);
    }

    function colVisibilitySelectAll(gridSelector, visible) {
        var info = menuConfig.grids[gridSelector];
        if (!info) return;
        info.columnDefs.forEach(function(col) {
            var field = col.field || col.colId || col.data;
            if (!field) return;
            if (visible) info.hiddenColumns.delete(field);
            else info.hiddenColumns.add(field);
        });
        if (menuConfig.activeLevel2Panel) {
            var checkboxes = menuConfig.activeLevel2Panel.querySelectorAll('.col-visibility-item input');
            checkboxes.forEach(function(cb) { cb.checked = visible; });
        }
    }

    // ==================== 二级面板：值筛选 ====================

    function showColumnFilterPanel(anchorMenu, colId, gridInfo, gridSelector) {
        closeLevel2Panel();

        var api = gridInfo.api;
        var colLabel = colId;
        for (var ci = 0; ci < gridInfo.columnDefs.length; ci++) {
            var col = gridInfo.columnDefs[ci];
            if ((col.field || col.colId) === colId) {
                colLabel = col.headerName || col.field;
                break;
            }
        }

        var hasActiveFilter = gridInfo.columnFilters &&
            gridInfo.columnFilters[colId] && gridInfo.columnFilters[colId].length > 0;
        var currentFilter = hasActiveFilter ? gridInfo.columnFilters[colId] : null;
        var allValuesChecked = !hasActiveFilter;

        // 创建面板，默认显示加载中
        var panel = document.createElement('div');
        panel.className = 'filter-dropdown-panel show';
        panel.style.cssText = 'position: fixed; display: block; min-width: 200px; z-index: 999999999; max-height: 400px;';
        panel.innerHTML =
            '<div class="filter-dropdown-header">' + colLabel + ' 筛选</div>' +
            '<div class="filter-dropdown-search" style="padding: 8px 12px; box-sizing: border-box;">' +
                '<input type="text" placeholder="搜索..." oninput="GridColumnMenu.filterSearch(this)" style="width: 100%; padding: 5px 8px; border: 1px solid #d9d9d9; border-radius: 4px; font-size: 12px; box-sizing: border-box;">' +
            '</div>' +
            '<div class="filter-dropdown-list" style="max-height: 240px; overflow-y: auto;">' +
                '<div style="padding: 12px; text-align: center; color: #999; font-size: 12px;">正在加载...</div>' +
            '</div>' +
            '<div class="filter-dropdown-footer">' +
                '<button onclick="GridColumnMenu.selectAll()">全选</button>' +
                '<button onclick="GridColumnMenu.invert()">反选</button>' +
                '<button class="btn-confirm" onclick="GridColumnMenu.applyColumnFilter(\'' + colId + '\', \'' + gridSelector + '\')">确定</button>' +
                '<button onclick="GridColumnMenu.cancelColumnFilter()">取消</button>' +
            '</div>';

        var anchorRect = anchorMenu.getBoundingClientRect();
        panel.style.left = (anchorRect.right + 4) + 'px';
        panel.style.top = anchorRect.top + 'px';

        document.body.appendChild(panel);
        _fitToViewport(panel, anchorRect, 'right');
        currentPanel = panel;
        currentMode = 'columnFilter';
        currentField = colId;
        menuConfig.activeLevel2Panel = panel;

        // 如果提供了异步取值的回调，优先使用；否则从 _originalRows 或当前行数据取
        if (typeof gridInfo.getFilterValues === 'function') {
            try {
                gridInfo.getFilterValues(colId, function(values) {
                    if (!currentPanel || currentPanel !== panel) return;
                    renderFilterValueList(values, currentFilter, allValuesChecked);
                });
            } catch (e) {
                console.error('[GridColumnMenu] getFilterValues 执行失败:', e);
                renderFilterValueListFromRows(colId, gridInfo, currentFilter, allValuesChecked);
            }
        } else {
            renderFilterValueListFromRows(colId, gridInfo, currentFilter, allValuesChecked);
        }
    }

    // 从本地行数据渲染筛选列表（兼容旧逻辑）
    function renderFilterValueListFromRows(colId, gridInfo, currentFilter, allValuesChecked) {
        var api = gridInfo.api;
        var rowData = [];
        if (gridInfo._originalRows && gridInfo._originalRows.length > 0) {
            rowData = gridInfo._originalRows;
        } else if (gridInfo.isHandsontable && api) {
            try {
                rowData = api.getSourceData() || [];
            } catch (e) {}
        } else {
            try {
                api.forEachNode(function(node) { if (node.data) rowData.push(node.data); });
            } catch (e) {}
        }

        var valueCount = {};
        rowData.forEach(function(row) {
            var val = row[colId];
            if (val !== undefined && val !== null && val !== '') {
                var s = String(val);
                valueCount[s] = (valueCount[s] || 0) + 1;
            }
        });
        var values = Object.keys(valueCount)
            .map(function(v) { return { value: v, count: valueCount[v] }; })
            .sort(function(a, b) { return a.value.localeCompare(b.value); });

        renderFilterValueList(values, currentFilter, allValuesChecked);
    }

    // 渲染筛选值列表（values 为对象数组 {value, count} 或字符串数组）
    function renderFilterValueList(values, currentFilter, allValuesChecked) {
        if (!currentPanel) return;

        var listContainer = currentPanel.querySelector('.filter-dropdown-list');
        if (!listContainer) return;

        var listHtml = '';
        if (values && values.length > 0) {
            values.forEach(function(item) {
                var value = typeof item === 'object' ? item.value : item;
                var count = typeof item === 'object' ? item.count : 0;
                var isChecked = '';
                if (allValuesChecked) isChecked = 'checked';
                else if (currentFilter && currentFilter.indexOf(value) !== -1) isChecked = 'checked';
                var countHtml = count > 0 ? ' <span class="count">(' + count + ')</span>' : '';
                listHtml += '<div class="filter-dropdown-item col-filter-item" data-value="' + value +
                    '" onclick="GridColumnMenu.toggleItemCheckbox(this)">' +
                    '<input type="checkbox" value="' + value + '" ' + isChecked + ' onclick="event.stopPropagation()">' +
                    '<label>' + value + countHtml + '</label>' +
                '</div>';
            });
        } else {
            listHtml = '<div style="padding: 12px; text-align: center; color: #999; font-size: 12px;">暂无数据</div>';
        }
        listContainer.innerHTML = listHtml;
    }

    function toggleItemCheckbox(item) {
        var checkbox = item.querySelector('input');
        checkbox.checked = !checkbox.checked;
    }

    function filterSearch(input) {
        if (!currentPanel) return;
        var keyword = input.value.toLowerCase();
        var items = currentPanel.querySelectorAll('.col-filter-item');
        items.forEach(function(item) {
            var text = item.textContent.toLowerCase();
            item.style.display = text.indexOf(keyword) !== -1 ? '' : 'none';
        });
    }

    function selectAll() {
        if (!currentPanel) return;
        var checkboxes = currentPanel.querySelectorAll('.col-filter-item input[type="checkbox"]');
        checkboxes.forEach(function(cb) { cb.checked = true; });
    }

    function invert() {
        if (!currentPanel) return;
        var checkboxes = currentPanel.querySelectorAll('.col-filter-item input[type="checkbox"]');
        checkboxes.forEach(function(cb) { cb.checked = !cb.checked; });
    }

    function cancelColumnFilter() {
        closeAll();
    }

    function applyColumnFilter(colId, gridSelector) {
        if (!currentPanel) return;
        var checkboxes = currentPanel.querySelectorAll('.col-filter-item input[type="checkbox"]:checked');
        var allCheckboxes = currentPanel.querySelectorAll('.col-filter-item input[type="checkbox"]');
        var selectedValues = [];
        for (var i = 0; i < checkboxes.length; i++) selectedValues.push(checkboxes[i].value);

        var info = menuConfig.grids[gridSelector];
        if (!info) return;

        // 全选 / 全不选 → 视为清除该列筛选
        if (selectedValues.length === 0 || selectedValues.length === allCheckboxes.length) {
            delete info.columnFilters[colId];
        } else {
            info.columnFilters[colId] = selectedValues;
        }

        var activeCount = 0;
        for (var k in info.columnFilters) {
            if (info.columnFilters[k] && info.columnFilters[k].length > 0) activeCount++;
        }
        var filterState = {
            active: activeCount > 0,
            filters: JSON.parse(JSON.stringify(info.columnFilters))
        };

        // 优先：调用方提供的回调
        if (typeof info.onDataRefresh === 'function') {
            try {
                info.onDataRefresh(filterState);
                closeAll();
                refreshMenuButtonStates(gridSelector);
                return;
            } catch (e) {}
        }

        // 次选：外部筛选器已注册
        if (info.hasExternalFilter) {
            try {
                if (typeof info.api.onFilterChanged === 'function') {
                    info.api.onFilterChanged();
                    closeAll();
                    refreshMenuButtonStates(gridSelector);
                    return;
                }
            } catch (e) {}
        }

        // 兜底：手动 setRowData
        try {
            var allRows = info._originalRows || [];
            if (allRows.length === 0 && typeof info.api.forEachNode === 'function') {
                info.api.forEachNode(function(n) { if (n && n.data) allRows.push(n.data); });
                if (allRows.length > 0) info._originalRows = allRows.slice();
            }
            var filtered = allRows.slice();
            if (activeCount > 0) {
                filtered = allRows.filter(function(row) { return _doesRowPass(row, gridSelector); });
            }
            if (typeof info.api.setRowData === 'function') {
                info.api.setRowData(filtered);
            }
        } catch (e) {}

        closeAll();
        refreshMenuButtonStates(gridSelector);
    }

    // ==================== 排序 ====================

    function applyColumnSort(colId, direction, gridSelector) {
        var info = menuConfig.grids[gridSelector];
        if (!info) return;

        if (info.sortColumn === colId && info.sortDir === direction) {
            info.sortColumn = null;
            info.sortDir = null;
        } else {
            info.sortColumn = colId;
            info.sortDir = direction;
        }
        closeAll();
        if (typeof info.onSort === 'function') {
            info.onSort(info.sortColumn, info.sortDir);
        }

        // 刷新表头按钮高亮
        refreshMenuButtonStates(gridSelector);
    }

    function getSortState(gridSelector) {
        var info = menuConfig.grids[gridSelector];
        if (!info) return { sortColumn: null, sortDir: null };
        return { sortColumn: info.sortColumn, sortDir: info.sortDir };
    }

    function setSortState(gridSelector, sortColumn, sortDir) {
        var info = menuConfig.grids[gridSelector];
        if (!info) return;
        info.sortColumn = sortColumn || null;
        info.sortDir = sortDir || null;

        // 刷新表头按钮高亮
        refreshMenuButtonStates(gridSelector);
    }

    // ==================== 数据缓存（供列筛选使用）====================

    function setOriginalRows(gridSelector, rows) {
        var info = menuConfig.grids[gridSelector];
        if (info) info._originalRows = rows ? rows.slice() : null;
    }

    function filterRows(rows, gridSelector) {
        var info = menuConfig.grids[gridSelector];
        if (!info) return rows;
        if (!_hasActiveFilter(gridSelector)) return rows;
        return rows.filter(function(row) { return _doesRowPass(row, gridSelector); });
    }

    function getFilterState(gridSelector) {
        var info = menuConfig.grids[gridSelector];
        if (!info) return { active: false, filters: {} };
        return {
            active: _hasActiveFilter(gridSelector),
            filters: JSON.parse(JSON.stringify(info.columnFilters))
        };
    }

    // ==================== 关闭面板 ====================

    function closeLevel2Panel() {
        var pendingGridSelector = null;

        // 列勾选关闭时：批量应用列显隐
        if (currentMode === 'columnVisibility' && currentField) {
            var info = menuConfig.grids[currentField];
            pendingGridSelector = currentField;
            if (info && info.columnDefs) {
                if (info.isHandsontable) {
                    // Handsontable：通过 updateSettings({ columns }) 更新可见列
                    try {
                        var visibleColumns = info.columnDefs.filter(function(col) {
                            var f = col.field || col.colId || col.data;
                            return !info.hiddenColumns.has(f);
                        });
                        info.api.updateSettings({ columns: visibleColumns });

                        // 通知调用方当前可见列已变更
                        if (typeof info.onColumnVisibilityChange === 'function') {
                            info.onColumnVisibilityChange(visibleColumns);
                        }

                        // 列重新可见后，header DOM 被重建，重新挂菜单按钮
                        setTimeout(function() {
                            addMenuButtonsToHeaders(pendingGridSelector);
                        }, 100);

                        // 保存列偏好
                        if (info.persist && info.pageKey && info.gridKey) {
                            _saveHandsontableColumnPreference(info.api, pendingGridSelector, info.pageKey, info.gridKey);
                        }
                    } catch (e) {
                        console.error('[GridColumnMenu] Handsontable 列显隐失败:', e);
                    }
                } else {
                    try {
                        var targetApi = (info.columnApi && typeof info.columnApi.applyColumnState === 'function')
                            ? info.columnApi
                            : ((typeof info.api.applyColumnState === 'function') ? info.api : null);
                        if (targetApi) {
                            var states = [];
                            info.columnDefs.forEach(function(col) {
                                var f = col.field || col.colId || col.data;
                                if (!f) return;
                                states.push({ colId: f, hide: info.hiddenColumns.has(f) });
                            });
                            targetApi.applyColumnState({ state: states, applyOrder: false });
                        } else {
                            var visApi = (info.columnApi && typeof info.columnApi.setColumnVisible === 'function')
                                ? info.columnApi
                                : ((typeof info.api.setColumnVisible === 'function') ? info.api : null);
                            if (visApi) {
                                info.columnDefs.forEach(function(col) {
                                    var f = col.field || col.colId || col.data;
                                    if (!f) return;
                                    visApi.setColumnVisible(f, !info.hiddenColumns.has(f));
                                });
                            }
                        }
                    } catch (e) {}

                    // 列重新可见后，header DOM 被重建，重新挂菜单按钮
                    setTimeout(function() {
                        addMenuButtonsToHeaders(pendingGridSelector);
                    }, 50);

                    // 持久化：手动触发保存（applyColumnState 已被 ColumnPreference 监听到 columnVisible，
                    // 但批量提交在某些 AG Grid 版本中不会逐个触发，故主动 flush 一次）
                    if (info.persist && typeof ColumnPreference !== 'undefined' &&
                        info.pageKey && info.gridKey) {
                        setTimeout(function() {
                            ColumnPreference.flush(info.pageKey, info.gridKey);
                        }, 100);
                    }

                    // 通知调用方当前可见列已变更
                    if (typeof info.onColumnVisibilityChange === 'function') {
                        var visibleColumns = info.columnDefs.filter(function(col) {
                            var f = col.field || col.colId || col.data;
                            return !info.hiddenColumns.has(f);
                        });
                        info.onColumnVisibilityChange(visibleColumns);
                    }
                }
            }
        }

        if (menuConfig.activeLevel2Panel) {
            menuConfig.activeLevel2Panel.remove();
            menuConfig.activeLevel2Panel = null;
        }
        currentPanel = null;
        currentMode = null;
        currentField = null;
    }

    function closeAll() {
        closeLevel2Panel();
        if (menuConfig.activeLevel1Menu) {
            menuConfig.activeLevel1Menu.remove();
            menuConfig.activeLevel1Menu = null;
        }
    }

    // 全局点击外部关闭
    document.addEventListener('click', function(e) {
        var isMenuBtn = e.target.closest('.ag-col-menu-btn');
        var isDropdown = e.target.closest('.filter-dropdown-panel');
        if (!isMenuBtn && !isDropdown) closeAll();
    });

    return {
        init: init,
        addMenuButtonsToHeaders: addMenuButtonsToHeaders,
        addButtonToHandsontableHeaderCell: _addButtonToHandsontableHeaderCell,
        toggleColVisibilityCheckbox: toggleColVisibilityCheckbox,
        colVisibilitySelectAll: colVisibilitySelectAll,
        toggleItemCheckbox: toggleItemCheckbox,
        filterSearch: filterSearch,
        selectAll: selectAll,
        invert: invert,
        applyColumnFilter: applyColumnFilter,
        cancelColumnFilter: cancelColumnFilter,
        applyColumnSort: applyColumnSort,
        getSortState: getSortState,
        setSortState: setSortState,
        setOriginalRows: setOriginalRows,
        filterRows: filterRows,
        getFilterState: getFilterState,
        closeAll: closeAll
    };
})();
