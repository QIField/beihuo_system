/**
 * 安全库存看板页面
 *
 * 【本模块"零公共代码依赖"原则】
 *  仅引用第三方库：layui + AG Grid Community（ag-grid-community.min.js / ag-grid-utils.js）
 *  分页组件：复制并重新封装项目公共 CustomPagination 源码 → 放本模块同目录 pagination.js（全局 StockSafePagination）
 *  不引用任何项目自写公共组件（column-preference / custom-pagination / filter-panel / grid-column-menu 全部不引用）
 *
 *  功能：
 *   1) 排序：AG Grid 原生 sortable + onSortChanged（同步前端排序箭头显示 + 调用后端 sort_field/sort_order）
 *   2) 分页：模块私有 StockSafePagination（onPageChange 回调走后端 LIMIT/OFFSET）
 *   3) 搜索筛选：工具栏关键词 / 销售状态（下拉框）/ 库存状态（下拉框）/ ABC 分类（查询/重置按钮），走后端过滤
 *   4) 列显示：独立的工具栏按钮弹窗（批量勾选显隐），通过 gridColumnApi.applyColumnStat#e 应用
 */

(function () {
    'use strict';

    // ============================================================
    // 全局状态
    // ============================================================
    var gridApi = null;
    var gridColumnApi = null;

    // 模块私有分页组件（来自 pagination.js 暴露的全局 StockSafePagination）
    var pagination = null;

    // 排序状态（通过 onSortChanged 同步）
    var currentSortField = '';
    var currentSortOrder = 'asc';

    // 搜索筛选状态
    var currentFilter = {
        keyword: '',
        sales_status: '',
        stock_status: '',
        abc_classification: '',
        sync_enabled: '',
        data_type: 'useful'   // 默认显示有用数据
    };

    // 防止重复请求
    var isLoading = false;

    // 废弃操作防重复提交
    var isAbandoning = false;

    // Excel 式框选状态：ranges 为选区集合（每个选区 {sRow,eRow,sCol,eCol}，行列均为显示序号），
    // anchor 为锚点（最近一次普通点击的单元格），供 Shift 扩展使用。
    var excelSel = { ranges: [], anchor: null, dragging: false };

    // 列定义（升序/降序通过 onSortChanged 走后端）
    var COLUMN_DEFS = [
        {
            headerName: '序号', width: 70,
            cellRenderer: function (p) {
                // 根据当前分页计算全局序号： (page-1) * pageSize + rowIndex + 1
                var idx = p.rowIndex + 1;
                if (pagination) {
                    idx = (pagination.currentPage - 1) * pagination.currentPageSize + p.rowIndex + 1;
                }
                return '<span style="color:#8c8c8c;font-family:Roboto Mono,Consolas,monospace;font-weight:500;">' + idx + '</span>';
            },
            sortable: false
        },
        // 批量选择复选框列（供批量废弃/恢复使用）
        {
            headerCheckboxSelection: true,
            checkboxSelection: true,
            width: 50,
            pinned: 'left',
            sortable: false,
            resizable: false,
            suppressSizeToFit: true,
            suppressMenu: true,
            cellStyle: function () { return { cursor: 'pointer' }; }
        },
        { headerName: 'OE号', field: 'number', flex: 1.5, minWidth: 120 },
        { headerName: '品牌', field: 'brand_name', width: 120 },
        { headerName: '条码', field: 'frey_no', width: 150 },
        {
            headerName: '产品名称', field: 'pdname', flex: 1.6, minWidth: 200,
            cellRenderer: function (p) { return p.value == null || p.value === '' ? '<span style="color:#bbb;">-</span>' : p.value; }
        },
        {
            headerName: 'ABC', field: 'abc_classification', width: 80,
            cellRenderer: function (p) {
                if (!p.value) return '<span style="color:#bbb;">-</span>';
                var map = { 'A': 'abc-a', 'B': 'abc-b', 'C': 'abc-c' };
                return '<span class="abc-tag ' + (map[p.value] || 'abc-c') + '">' + p.value + '</span>';
            }
        },
        {
            headerName: '可用库存', field: 'available_stock', width: 110, cellClass: 'cell-number',
            valueFormatter: intFormatter,
            cellStyle: function (p) {
                if (p.value == null) return null;
                if (parseFloat(p.value) <= 0) return { color: '#cf1322', fontWeight: 'bold' };
                if (parseFloat(p.value) <= 3) return { color: '#d48806' };
                return null;
            }
        },
        { headerName: '在途数量', field: 'transit_quantity', width: 100, cellClass: 'cell-number',
            valueFormatter: intFormatter },
        { headerName: '日均销量',         field: 'avg_daily_sales',     width: 110, cellClass: 'cell-number', valueFormatter: decFormatter },
        { headerName: '基础安全库存',     field: 'base_safety_stock',   width: 130, cellClass: 'cell-number', valueFormatter: decFormatter },
        {
            headerName: '季节系数', field: 'season_coefficient', width: 100, cellClass: 'cell-number',
            valueFormatter: function (p) { return (p.value == null || isNaN(p.value)) ? '-' : parseFloat(p.value).toFixed(3); }
        },
        { headerName: '调整后安全库存',   field: 'safety_stock',        width: 140, cellClass: 'cell-number', valueFormatter: decFormatter },
        { headerName: '库存下限',         field: 'stock_lower_limit',   width: 110, cellClass: 'cell-number', valueFormatter: decFormatter },
        { headerName: '库存上限',         field: 'stock_upper_limit',   width: 110, cellClass: 'cell-number', valueFormatter: decFormatter },
        {
            headerName: '可卖天数', field: 'sellable_days', width: 110, cellClass: 'cell-number',
            valueFormatter: function (p) {
                if (p.value == null || isNaN(p.value)) return '-';
                return parseFloat(p.value).toFixed(1) + ' 天';
            },
            cellStyle: function (p) {
                if (p.value == null || isNaN(p.value)) return null;
                var d = parseFloat(p.value);
                if (d <= 3) return { color: '#cf1322', fontWeight: 'bold' };
                if (d <= 7) return { color: '#d48806' };
                if (d >= 180) return { color: '#531dab' };
                return null;
            }
        },
        {
            headerName: '销售状态', field: 'sales_status', width: 110,
            cellRenderer: renderSalesStatusCell
        },
        {
            headerName: '库存状态', field: 'stock_status', width: 180,
            cellRenderer: renderStockStatusCell
        },
        {
            headerName: '最近同步时间', field: 'synced_at', width: 150, sortable: false,
            cellRenderer: function (p) {
                if (!p.value) return '<span style="color:#bbb;">未同步</span>';
                return '<span class="cell-synced-time">' + p.value + '</span>';
            }
        },
        {
            headerName: '是否同步', field: 'sync_enabled', width: 100, sortable: false, pinned: 'right',
            cellStyle: { display: 'flex', alignItems: 'center', justifyContent: 'center' },
            cellRenderer: function (p) {
                var checked = (p.value == 1) ? 'checked' : '';
                return '<label class="sync-switch" style="margin:0;">'
                    + '<input type="checkbox" data-id="' + (p.data ? p.data.id : '') + '" '
                    + 'data-number="' + (p.data ? (p.data.number || '') : '') + '" '
                    + 'data-brand="' + (p.data ? (p.data.brand_name || '') : '') + '" '
                    + checked + '>'
                    + '<span class="sync-switch-slider"></span>'
                    + '</label>';
            }
        },
        {
            headerName: '操作', width: 110, pinned: 'right', sortable: false,
            // 整列浅蓝底纹，与其他数据列区分；按钮保持实心彩色(橙=废弃/绿=恢复)
            cellStyle: function () { return { background: '#e6f7ff' }; },
            cellRenderer: function (p) {
                var id = (p.data && p.data.id != null) ? p.data.id : '';
                var frey = (p.data && p.data.frey_no != null) ? p.data.frey_no : '';
                // 废弃数据视图下显示"恢复数据"（绿色），否则显示"废弃数据"（橙色）
                if (currentFilter.data_type === 'useless') {
                    return '<button class="btn-restore" data-frey="' + frey + '" title="将该条数据恢复为有用">恢复数据</button>';
                }
                return '<button class="btn-abandon" data-id="' + id + '" title="将本行数据移入废弃表">废弃数据</button>';
            }
        }
    ];

    // ---- 单元格渲染 & 格式化 ----
    // 销售状态：单独一列展示，按销量水平着色
    function renderSalesStatusCell(p) {
        var label = (p.data ? p.data.sales_status : '') || '';
        if (!label) return '<span style="color:#bbb;">-</span>';

        var styleMap = {
            '无销售': 'status-dead',
            '销量极低': 'status-slow',
            '销量低': 'status-warning',
            '销量正常': 'status-success',
        };
        var cls = styleMap[label] || '';
        return '<span class="cell-status ' + cls + '">' + label + '</span>';
    }

    // 库存状态：单独一列展示，按补货紧迫程度着色
    function renderStockStatusCell(p) {
        var label = (p.data ? p.data.stock_status : '') || '';
        if (!label) return '<span style="color:#bbb;">-</span>';

        var styleMap = {
            '呆滞清库': 'status-dead',
            '慢动销去库': 'status-slow',
            '库存积压': 'status-danger',
            '需补货': 'status-warning',
            '需补货|可卖天数较少': 'status-danger',
            '紧急补货': 'status-danger',
            '库存正常': 'status-success',
        };
        var cls = styleMap[label] || '';
        return '<span class="cell-status ' + cls + '">' + label + '</span>';
    }
    function intFormatter(p) {
        if (p.value == null || isNaN(p.value)) return '-';
        return parseInt(p.value).toLocaleString();
    }
    function decFormatter(p) {
        if (p.value == null || isNaN(p.value)) return '-';
        // 保留 3 位小数展示
        return parseFloat(p.value).toFixed(3);
    }

    // ============================================================
    // Excel 式框选 & 复制（自定义实现，参考公共组件 ag-grid-utils.js 的
    // initDragSelection / initShortcuts 思路，但不依赖其存在/修复其缺陷）
    // 功能：拖拽框选 / Shift 扩展 / Ctrl 追加多选区，Ctrl+C 复制选中区域
    //       （Tab 分隔，可直接粘贴到 Excel），Ctrl+A 全选，Esc 取消。
    // ============================================================
    function initExcelSelection() {
        var gridDiv = document.getElementById('stockSafeGrid');
        if (!gridDiv || !gridApi) return;

        // 由事件目标定位到 {row, col}（col 为当前显示列顺序中的序号）
        function posFromEvent(e) {
            var cell = e.target.closest('.ag-cell');
            if (!cell) return null;
            var rowEl = cell.closest('.ag-row');
            if (!rowEl) return null;
            var rowIndex = parseInt(rowEl.getAttribute('row-index'), 10);
            if (isNaN(rowIndex)) return null;
            var colId = cell.getAttribute('col-id');
            var cols = gridColumnApi.getAllDisplayedColumns();
            for (var i = 0; i < cols.length; i++) {
                if (cols[i].getColId() === colId) return { row: rowIndex, col: i };
            }
            return null;
        }

        // 鼠标按下：普通点击选单格 / Shift 扩展 / Ctrl 追加多选区
        gridDiv.addEventListener('mousedown', function (e) {
            if (e.button !== 0) return;
            // 忽略复选框、按钮、表头
            if (e.target.closest('input,button,.ag-header-cell,.ag-checkbox-input')) return;
            var pos = posFromEvent(e);
            if (!pos) return;

            if (e.shiftKey && excelSel.ranges.length && excelSel.anchor) {
                // Shift：以锚点扩展最近一次选区
                var last = excelSel.ranges[excelSel.ranges.length - 1];
                last.sRow = Math.min(excelSel.anchor.row, pos.row);
                last.eRow = Math.max(excelSel.anchor.row, pos.row);
                last.sCol = Math.min(excelSel.anchor.col, pos.col);
                last.eCol = Math.max(excelSel.anchor.col, pos.col);
                excelSel.dragging = true;
            } else if (e.ctrlKey || e.metaKey) {
                // Ctrl：追加新选区
                excelSel.ranges.push({ sRow: pos.row, eRow: pos.row, sCol: pos.col, eCol: pos.col });
                excelSel.anchor = { row: pos.row, col: pos.col };
                excelSel.dragging = true;
            } else {
                // 普通点击：仅选中该单元格
                excelSel.ranges = [{ sRow: pos.row, eRow: pos.row, sCol: pos.col, eCol: pos.col }];
                excelSel.anchor = { row: pos.row, col: pos.col };
                excelSel.dragging = true;
            }
            applyExcelHighlights();
        });

        // 鼠标拖动：动态扩展最近一次选区
        gridDiv.addEventListener('mousemove', function (e) {
            if (!excelSel.dragging || !excelSel.ranges.length) return;
            var pos = posFromEvent(e);
            if (!pos) return;
            var last = excelSel.ranges[excelSel.ranges.length - 1];
            last.eRow = pos.row;
            last.eCol = pos.col;
            scheduleHighlightRefresh();
        });

        // 松开鼠标结束拖动
        document.addEventListener('mouseup', function () {
            excelSel.dragging = false;
        });

        // 拖动时禁止浏览器文本选择
        gridDiv.addEventListener('selectstart', function (e) {
            if (excelSel.dragging) e.preventDefault();
        });

        // 快捷键（捕获阶段，先于 AG Grid 内部处理，避免冲突）
        gridDiv.addEventListener('keydown', function (e) {
            var k = (e.key || '').toLowerCase();
            if ((e.ctrlKey || e.metaKey) && k === 'c') {
                e.preventDefault();
                e.stopImmediatePropagation();
                copyExcelSelection();
            } else if ((e.ctrlKey || e.metaKey) && k === 'a') {
                e.preventDefault();
                e.stopImmediatePropagation();
                selectAllExcelCells();
            } else if (e.key === 'Escape') {
                clearExcelSelection();
            }
        }, true);
    }

    // 将当前选中的单元格区域刷上高亮（锚点单元格用 Excel 风格的白底蓝框）
    function applyExcelHighlights() {
        var gridDiv = document.getElementById('stockSafeGrid');
        if (!gridDiv) return;
        var old = gridDiv.querySelectorAll('.ag-cell.excel-range-selected, .ag-cell.excel-range-active');
        for (var i = 0; i < old.length; i++) {
            old[i].classList.remove('excel-range-selected', 'excel-range-active');
        }
        if (!excelSel.ranges.length) return;

        var cols = gridColumnApi.getAllDisplayedColumns();
        excelSel.ranges.forEach(function (rng) {
            for (var r = rng.sRow; r <= rng.eRow; r++) {
                var rowEls = gridDiv.querySelectorAll('.ag-row[row-index="' + r + '"]');
                for (var k = 0; k < rowEls.length; k++) {
                    for (var c = rng.sCol; c <= rng.eCol; c++) {
                        var col = cols[c];
                        if (!col) continue;
                        var cell = rowEls[k].querySelector('.ag-cell[col-id="' + col.getColId() + '"]');
                        if (cell) cell.classList.add('excel-range-selected');
                    }
                }
            }
        });

        if (excelSel.anchor) {
            var anchorCol = cols[excelSel.anchor.col];
            if (anchorCol) {
                var rowEls = gridDiv.querySelectorAll('.ag-row[row-index="' + excelSel.anchor.row + '"]');
                for (var k = 0; k < rowEls.length; k++) {
                    var cell = rowEls[k].querySelector('.ag-cell[col-id="' + anchorCol.getColId() + '"]');
                    if (cell) cell.classList.add('excel-range-active');
                }
            }
        }
    }

    // 滚动/重绘触发的高亮刷新（rAF 节流，避免高频 mousemove 卡顿）
    var highlightRAF = null;
    function scheduleHighlightRefresh() {
        if (highlightRAF) return;
        highlightRAF = requestAnimationFrame(function () {
            highlightRAF = null;
            applyExcelHighlights();
        });
    }

    // 清空选区
    function clearExcelSelection() {
        excelSel.ranges = [];
        excelSel.anchor = null;
        excelSel.dragging = false;
        var gridDiv = document.getElementById('stockSafeGrid');
        if (gridDiv) {
            var els = gridDiv.querySelectorAll('.ag-cell.excel-range-selected, .ag-cell.excel-range-active');
            for (var i = 0; i < els.length; i++) {
                els[i].classList.remove('excel-range-selected', 'excel-range-active');
            }
        }
    }

    // Ctrl+A：选中当前页全部行 × 全部列
    function selectAllExcelCells() {
        if (!gridApi || !gridColumnApi) return;
        var rowCount = gridApi.getDisplayedRowCount();
        var colCount = gridColumnApi.getAllDisplayedColumns().length;
        if (!rowCount || !colCount) return;
        excelSel.ranges = [{ sRow: 0, eRow: rowCount - 1, sCol: 0, eCol: colCount - 1 }];
        excelSel.anchor = { row: 0, col: 0 };
        applyExcelHighlights();
    }

    // 读取某个单元格的"复制文本"（与界面显示一致：序号/格式化数值，按钮列/复选框列不复制）
    function getCellCopyText(rowIndex, colIndex) {
        var cols = gridColumnApi.getAllDisplayedColumns();
        var col = cols[colIndex];
        if (!col) return '';
        var colDef = col.getColDef();
        var rowNode = gridApi.getDisplayedRowAtIndex(rowIndex);
        if (!rowNode) return '';

        // 操作列（废弃/恢复按钮）与复选框列：不复制
        if (colDef.headerName === '操作' || colDef.checkboxSelection) return '';
        // 序号列：输出当前页全局序号
        if (colDef.headerName === '序号') {
            var idx = rowIndex + 1;
            if (pagination) {
                idx = (pagination.currentPage - 1) * pagination.currentPageSize + rowIndex + 1;
            }
            return String(idx);
        }
        if (colDef.field == null) return '';
        var value = rowNode.data ? rowNode.data[colDef.field] : null;
        // 有 valueFormatter 的列：复制格式化后的显示值（所见即所得）
        if (typeof colDef.valueFormatter === 'function') {
            var fmt = colDef.valueFormatter({
                value: value,
                node: rowNode,
                data: rowNode.data,
                column: col,
                api: gridApi,
                columnApi: gridColumnApi,
                context: undefined
            });
            return fmt == null ? '' : String(fmt);
        }
        return value == null ? '' : String(value);
    }

    // Ctrl+C：把选中区域按 Tab 分隔输出到剪贴板（可直接粘贴到 Excel）
    function copyExcelSelection() {
        if (!excelSel.ranges.length) {
            layui.use(['layer'], function (l) { l.msg('请先拖拽框选要复制的单元格区域', { icon: 0 }); });
            return;
        }
        var parts = [];
        var totalCells = 0;
        excelSel.ranges.forEach(function (rng) {
            var lines = [];
            for (var r = rng.sRow; r <= rng.eRow; r++) {
                var cells = [];
                for (var c = rng.sCol; c <= rng.eCol; c++) {
                    cells.push(getCellCopyText(r, c));
                    totalCells++;
                }
                lines.push(cells.join('\t'));
            }
            parts.push(lines.join('\n'));
        });
        writeClipboardText(parts.join('\n\n'));
        layui.use(['layer'], function (l) {
            l.msg('已复制 ' + totalCells + ' 个单元格，可直接粘贴到 Excel', { icon: 1, time: 1600 });
        });
    }

    // 写剪贴板（优先 navigator.clipboard，失败回退 execCommand）
    function writeClipboardText(text) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).catch(function () { fallbackCopy(text); });
        } else {
            fallbackCopy(text);
        }
    }

    // ============================================================
    // DOM 初始化
    // ============================================================
    document.addEventListener('DOMContentLoaded', function () {
        initGrid();
        bindToolbarEvents();
        bindColVisibilityModalEvents();
        loadStatusCount();
        fetchData();
    });

    // ============================================================
    // 初始化 AG Grid
    // 重要：这里 pagination=false，不使用 AG Grid 内置分页；
    //       分页使用模块私有组件 StockSafePagination（零公共依赖）
    // ============================================================
    function initGrid() {
        var gridOptions = {
            columnDefs: COLUMN_DEFS,
            rowData: [],
            defaultColDef: {
                sortable: true,      // AG Grid 原生表头排序（点击表头显示箭头；实际排序走后端）
                resizable: true,
                filter: false,       // 禁用 AG Grid 内置客户端过滤（过滤统一走后端）
                suppressMenu: true,  // 禁用 AG Grid 内置列菜单（筛选/列显隐全部移到独立按钮/弹窗）
                minWidth: 80
            },
            pagination: false,
            rowSelection: 'multiple',
            suppressRowClickSelection: true,
            suppressMovableColumns: false,
            animateRows: false,
            // ---- Excel 式框选与复制（自定义实现，见 initExcelSelection） ----
            // 注意：当前 ag-grid-community.min.js 未内置 range 模块，enableRangeSelection 不可用，
            // 因此框选/复制由本页面自行实现，此处关闭单元格文本拖选以让位给框选。
            enableCellTextSelection: false,
            ensureDomOrder: true,
            // 滚动 / 重绘会导致单元格重建，滚动结束后重新刷选框高亮
            onBodyScroll: function () {
                if (excelSel && excelSel.ranges.length) scheduleHighlightRefresh();
            },
            // ---- 排序变化：保留前端箭头显示；切回第 1 页；走后端 ORDER BY ----
            onSortChanged: function (params) {
                if (!gridColumnApi) return;
                var state = [];
                try { state = gridColumnApi.getColumnState() || []; } catch (e) {}
                var sortEntry = null;
                state.forEach(function (s) {
                    if (s.sort === 'asc' || s.sort === 'desc') {
                        if (!sortEntry || (s.sortIndex != null && s.sortIndex < sortEntry.sortIndex)) sortEntry = s;
                    }
                });
                currentSortField = sortEntry ? sortEntry.colId : '';
                currentSortOrder = sortEntry ? sortEntry.sort : 'asc';
                if (pagination) pagination.currentPage = 1;
                fetchData();
            },
            onGridReady: function (params) {
                gridApi = params.api;
                gridColumnApi = params.columnApi;
                console.log('[stock_safe] AG Grid 初始化完成');

                // 模块私有分页组件（复制自公共 CustomPagination 源码，零公共依赖，全局 StockSafePagination）
                // container: '#stockSafePagination' 对应模板中 grid-wrapper 内摆放的 div，
                // 分页组件直接渲染到该元素中，与表格融为一体。
                pagination = StockSafePagination.init({
                    container: '#stockSafePagination',
                    gridSelector: '#stockSafeGrid',
                    pageSizeOptions: [20, 50, 100, 200, 500],
                    defaultPageSize: 50,
                    onPageChange: function (page, pageSize) {
                        fetchData(page, pageSize);
                    }
                });

                initDoubleClickCopy();
                initExcelSelection();
            }
        };

        new agGrid.Grid(document.getElementById('stockSafeGrid'), gridOptions);
    }

    // ============================================================
    // 工具栏绑定（搜索筛选 + 其他按钮）
    // ============================================================
    function bindToolbarEvents() {
        // 查询
        document.getElementById('btnSearch').addEventListener('click', function () {
            applyFiltersFromDOM();
            if (pagination) pagination.currentPage = 1;
            fetchData();
        });
        // 回车搜索
        document.getElementById('filterKeyword').addEventListener('keypress', function (e) {
            if (e.key === 'Enter') document.getElementById('btnSearch').click();
        });
        // 重置
        document.getElementById('btnReset').addEventListener('click', function () {
            document.getElementById('filterKeyword').value = '';
            document.getElementById('filterSalesStatus').value = '';
            document.getElementById('filterStockStatus').value = '';
            document.getElementById('filterABC').value = '';
            document.getElementById('filterDataType').value = 'useful';
            document.getElementById('filterSyncEnabled').value = '';
            currentFilter = { keyword: '', sales_status: '', stock_status: '', abc_classification: '', sync_enabled: '', data_type: 'useful' };
            if (pagination) pagination.currentPage = 1;
            fetchData();
        });
        // 列显示
        document.getElementById('btnColumns').addEventListener('click', openColVisibilityModal);
        // 刷新 / 导出
        document.getElementById('btnRefresh').addEventListener('click', function () { fetchData(); });
        document.getElementById('btnExport').addEventListener('click', exportData);

        // 批量废弃 / 批量恢复（基于复选框勾选的行）
        document.getElementById('btnBatchAbandon').addEventListener('click', batchAbandon);
        document.getElementById('btnBatchRestore').addEventListener('click', batchRestore);

        // 批量开启 / 批量关闭同步（基于复选框勾选的行）
        document.getElementById('btnBatchSyncOn').addEventListener('click', function () { batchSetSyncEnabled(1); });
        document.getElementById('btnBatchSyncOff').addEventListener('click', function () { batchSetSyncEnabled(0); });

        // 批量手动同步：加入同步队列，由每分钟轮询任务推送 CRM
        document.getElementById('btnBatchManualSync').addEventListener('click', batchManualSync);

        // 数据范围切换：同步批量按钮显示，并直接刷新当前视图数据
        document.getElementById('filterDataType').addEventListener('change', function () {
            applyFiltersFromDOM();
            updateBatchButtons();
            if (pagination) pagination.currentPage = 1;
            fetchData();
        });

        // 初始加载：按默认"有用数据"视图设置批量按钮显示
        updateBatchButtons();

        // 废弃数据 / 恢复数据：监听 grid 容器内的按钮点击（由单元格渲染器生成）
        var gridDiv = document.getElementById('stockSafeGrid');
        if (gridDiv) {
            gridDiv.addEventListener('click', function (e) {
                var abBtn = e.target.closest('.btn-abandon');
                if (abBtn) {
                    var id = abBtn.getAttribute('data-id');
                    if (id) abandonRow(parseInt(id, 10));
                    return;
                }
                var reBtn = e.target.closest('.btn-restore');
                if (reBtn) {
                    var frey = reBtn.getAttribute('data-frey');
                    if (frey) restoreRow(frey);
                }
            });

            // 是否同步开关：监听 checkbox 的 change 事件
            gridDiv.addEventListener('change', function (e) {
                var checkbox = e.target.closest('.sync-switch input[type="checkbox"]');
                if (!checkbox) return;
                var number = checkbox.getAttribute('data-number') || '';
                var brand = checkbox.getAttribute('data-brand') || '';
                var enabled = checkbox.checked ? 1 : 0;
                if (number && brand) {
                    setSyncEnabled(number, brand, enabled, checkbox);
                }
            });
        }
    }

    // ============================================================
    // 废弃数据操作
    // ============================================================
    function abandonRow(id) {
        if (!id || isNaN(id)) {
            layui.use(['layer'], function (l) { l.msg('无效的记录ID', { icon: 2 }); });
            return;
        }
        if (isAbandoning) return;   // 防止重复提交
        isAbandoning = true;

        layui.use(['layer'], function (layer) {
            layer.confirm('确定将该条数据标记为废弃并移入废弃表吗？', {
                title: '废弃数据',
                btn: ['确定', '取消']
            }, function (index) {
                layer.close(index);
                submitAbandon(id);
            }, function () {
                isAbandoning = false;
            });
        });
    }

    function submitAbandon(id) {
        layui.use(['layer'], function (layer) {
            layer.load(2);

            fetch('/new/api/stock_safe/abandon', {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ids: [id] })
            })
                .then(function (r) { return r.json(); })
                .then(function (res) {
                    layer.closeAll('loading');
                    isAbandoning = false;
                    if (res.code !== 0) {
                        layer.msg(res.msg || '废弃失败', { icon: 2 });
                        return;
                    }
                    layer.msg('已废弃', { icon: 1 });
                    // 废弃成功后刷新列表及统计卡片
                    fetchData();
                    loadStatusCount();
                })
                .catch(function (err) {
                    layer.closeAll('loading');
                    isAbandoning = false;
                    layer.msg('网络错误，请稍后重试', { icon: 2 });
                    console.error('[stock_safe] abandon 失败:', err);
                });
        });
    }

    // ============================================================
    // 批量废弃 / 批理恢复操作
    // ============================================================

    // 从 AG Grid 获取当前勾选的行
    function getSelectedRows() {
        if (!gridApi) return [];
        return gridApi.getSelectedRows() || [];
    }

    // 根据当前数据范围视图，切换批量操作按钮的显示
    // useful（有用数据）→ 显示批量废弃；useless（废弃数据）→ 显示批量恢复
    function updateBatchButtons() {
        var abn = document.getElementById('btnBatchAbandon');
        var rst = document.getElementById('btnBatchRestore');
        if (!abn || !rst) return;
        var type = (document.getElementById('filterDataType').value || 'useful');
        if (type === 'useless') {
            abn.style.display = 'none';
            rst.style.display = '';
        } else {
            abn.style.display = '';
            rst.style.display = 'none';
        }
    }

    // 批量废弃：收集选中行的 id，调用已有的批量废弃接口
    function batchAbandon() {
        var rows = getSelectedRows();
        var ids = [];
        rows.forEach(function (r) { if (r.id != null && r.id !== '') ids.push(r.id); });
        if (ids.length === 0) {
            layui.use(['layer'], function (l) { l.msg('请先勾选要废弃的数据（勾选行首复选框）', { icon: 0 }); });
            return;
        }
        layui.use(['layer'], function (layer) {
            layer.confirm('确定批量废弃所选 ' + ids.length + ' 条数据吗？', {
                title: '批量废弃',
                btn: ['确定', '取消']
            }, function (index) {
                layer.close(index);
                submitBatchAbandon(ids);
            });
        });
    }

    function submitBatchAbandon(ids) {
        layui.use(['layer'], function (layer) {
            layer.load(2);
            fetch('/new/api/stock_safe/abandon', {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ids: ids })
            })
                .then(function (r) { return r.json(); })
                .then(function (res) {
                    layer.closeAll('loading');
                    if (res.code !== 0) { layer.msg(res.msg || '批量废弃失败', { icon: 2 }); return; }
                    var n = res.data && res.data.moved ? res.data.moved : 0;
                    layer.msg('批量废弃成功，共 ' + n + ' 条', { icon: 1 });
                    fetchData();
                    loadStatusCount();
                })
                .catch(function (err) {
                    layer.closeAll('loading');
                    layer.msg('网络错误，请稍后重试', { icon: 2 });
                    console.error('[stock_safe] batch abandon 失败:', err);
                });
        });
    }

    // 批量恢复：收集选中行的 frey_no，调用已有的批量恢复（按条码删除废弃记录）
    function batchRestore() {
        var rows = getSelectedRows();
        var freys = [];
        rows.forEach(function (r) { if (r.frey_no) freys.push(r.frey_no); });
        if (freys.length === 0) {
            layui.use(['layer'], function (l) { l.msg('请先勾选要恢复的数据（勾选行首复选框）', { icon: 0 }); });
            return;
        }
        layui.use(['layer'], function (layer) {
            layer.confirm('确定批量恢复所选 ' + freys.length + ' 条数据吗？', {
                title: '批量恢复',
                btn: ['确定', '取消']
            }, function (index) {
                layer.close(index);
                submitBatchRestore(freys);
            });
        });
    }

    function submitBatchRestore(freys) {
        layui.use(['layer'], function (layer) {
            layer.load(2);
            fetch('/new/api/stock_safe/restore', {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ freys: freys })
            })
                .then(function (r) { return r.json(); })
                .then(function (res) {
                    layer.closeAll('loading');
                    if (res.code !== 0) { layer.msg(res.msg || '批量恢复失败', { icon: 2 }); return; }
                    var n = res.data && res.data.restored ? res.data.restored : 0;
                    layer.msg('批量恢复成功，共 ' + n + ' 条', { icon: 1 });
                    fetchData();
                    loadStatusCount();
                })
                .catch(function (err) {
                    layer.closeAll('loading');
                    layer.msg('网络错误，请稍后重试', { icon: 2 });
                    console.error('[stock_safe] batch restore 失败:', err);
                });
        });
    }

    // ============================================================
    // 批量开启 / 关闭同步（基于复选框勾选的行）
    // ============================================================
    function batchSetSyncEnabled(enabled) {
        var rows = getSelectedRows();
        var items = [];
        rows.forEach(function (r) {
            if (r.number && r.brand_name) {
                items.push({
                    number: r.number,
                    brand_name: r.brand_name,
                    frey_no: r.frey_no || '',
                    pdname: r.pdname || ''
                });
            }
        });
        if (items.length === 0) {
            layui.use(['layer'], function (l) { l.msg('请先勾选要设置的数据（勾选行首复选框）', { icon: 0 }); });
            return;
        }
        var actionText = enabled ? '开启' : '关闭';
        layui.use(['layer'], function (layer) {
            layer.confirm('确定批量' + actionText + '所选 ' + items.length + ' 条数据的同步吗？', {
                title: '批量' + actionText + '同步',
                btn: ['确定', '取消']
            }, function (index) {
                layer.close(index);
                submitBatchSyncEnabled(items, enabled);
            });
        });
    }

    function submitBatchSyncEnabled(items, enabled) {
        layui.use(['layer'], function (layer) {
            layer.load(2);
            fetch('/new/api/stock_safe/sync-enabled/batch', {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ items: items, enabled: enabled })
            })
                .then(function (r) { return r.json(); })
                .then(function (res) {
                    layer.closeAll('loading');
                    if (res.code !== 0) { layer.msg(res.msg || '批量设置失败', { icon: 2 }); return; }
                    var d = res.data || {};
                    var actionText = enabled ? '开启' : '关闭';
                    layer.msg('批量' + actionText + '同步成功：更新 ' + (d.updated || 0) + ' 条，新增 ' + (d.inserted || 0) + ' 条', { icon: 1 });
                    fetchData();
                })
                .catch(function (err) {
                    layer.closeAll('loading');
                    layer.msg('网络错误，请稍后重试', { icon: 2 });
                    console.error('[stock_safe] batch sync-enabled 失败:', err);
                });
        });
    }

    // ============================================================
    // 批量手动同步（基于复选框勾选的行）
    // 加入同步队列（进程内去重 + 落库展示），由每 1 分钟轮询任务推送 CRM
    // ============================================================
    function batchManualSync() {
        var rows = getSelectedRows();
        var items = [];
        rows.forEach(function (r) {
            if (r.number && r.brand_name) {
                items.push({
                    number: r.number,
                    brand_name: r.brand_name,
                    frey_no: r.frey_no || '',
                    pdname: r.pdname || ''
                });
            }
        });
        if (items.length === 0) {
            layui.use(['layer'], function (l) { l.msg('请先勾选要同步的数据（勾选行首复选框）', { icon: 0 }); });
            return;
        }
        layui.use(['layer'], function (layer) {
            layer.confirm('确定将所选 ' + items.length + ' 条数据加入手动同步队列吗？加入后将在 1 分钟内自动推送 CRM。', {
                title: '手动同步',
                btn: ['确定', '取消']
            }, function (index) {
                layer.close(index);
                submitBatchManualSync(items);
            });
        });
    }

    function submitBatchManualSync(items) {
        layui.use(['layer'], function (layer) {
            layer.load(2);
            fetch('/new/api/stock_safe/manual-sync/queue', {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ items: items })
            })
                .then(function (r) { return r.json(); })
                .then(function (res) {
                    layer.closeAll('loading');
                    if (res.code !== 0) { layer.msg(res.msg || '加入同步队列失败', { icon: 2 }); return; }
                    var d = res.data || {};
                    var invalidCount = (d.invalid && d.invalid.length) || 0;
                    var msg = '已加入同步队列：入队 ' + (d.queued || 0) + ' 条';
                    if (invalidCount > 0) msg += '，跳过无效 ' + invalidCount + ' 条';
                    msg += '，1 分钟内自动推送';
                    layer.msg(msg, { icon: 1 });
                    fetchData();
                })
                .catch(function (err) {
                    layer.closeAll('loading');
                    layer.msg('网络错误，请稍后重试', { icon: 2 });
                    console.error('[stock_safe] batch manual-sync 失败:', err);
                });
        });
    }

    // ============================================================
    // 恢复数据操作
    // ============================================================
    var isRestoring = false;   // 恢复操作防重复提交

    function restoreRow(frey) {
        if (!frey) {
            layui.use(['layer'], function (l) { l.msg('无效的数据', { icon: 2 }); });
            return;
        }
        if (isRestoring) return;
        isRestoring = true;

        layui.use(['layer'], function (layer) {
            layer.confirm('确定将该条数据恢复为有用数据吗？', {
                title: '恢复数据',
                btn: ['确定', '取消']
            }, function (index) {
                layer.close(index);
                submitRestore(frey);
            }, function () {
                isRestoring = false;
            });
        });
    }

    function submitRestore(frey) {
        layui.use(['layer'], function (layer) {
            layer.load(2);

            fetch('/new/api/stock_safe/restore', {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ frey_no: frey })
            })
                .then(function (r) { return r.json(); })
                .then(function (res) {
                    layer.closeAll('loading');
                    isRestoring = false;
                    if (res.code !== 0) {
                        layer.msg(res.msg || '恢复失败', { icon: 2 });
                        return;
                    }
                    layer.msg('已恢复', { icon: 1 });
                    // 恢复成功后刷新列表及统计卡片
                    fetchData();
                    loadStatusCount();
                })
                .catch(function (err) {
                    layer.closeAll('loading');
                    isRestoring = false;
                    layer.msg('网络错误，请稍后重试', { icon: 2 });
                    console.error('[stock_safe] restore 失败:', err);
                });
        });
    }

    // ============================================================
    // 是否同步开关操作
    // ============================================================
    function setSyncEnabled(number, brandName, enabled, checkboxEl) {
        if (!number || !brandName) {
            layui.use(['layer'], function (l) { l.msg('OE号和品牌名不能为空', { icon: 2 }); });
            if (checkboxEl) checkboxEl.checked = !enabled;
            return;
        }

        // 请求期间禁用开关，防止重复提交
        if (checkboxEl) checkboxEl.disabled = true;

        layui.use(['layer'], function (layer) {
            fetch('/new/api/stock_safe/sync-enabled', {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    number: number,
                    brand_name: brandName,
                    enabled: enabled
                })
            })
                .then(function (r) { return r.json(); })
                .then(function (res) {
                    if (checkboxEl) checkboxEl.disabled = false;
                    if (res.code !== 0) {
                        // 失败时回滚开关状态
                        if (checkboxEl) checkboxEl.checked = !enabled;
                        layer.msg(res.msg || '设置失败', { icon: 2 });
                        return;
                    }
                    layer.msg(enabled ? '已开启同步' : '已关闭同步', { icon: 1 });
                })
                .catch(function (err) {
                    if (checkboxEl) checkboxEl.disabled = false;
                    // 失败时回滚开关状态
                    if (checkboxEl) checkboxEl.checked = !enabled;
                    layer.msg('网络错误，请稍后重试', { icon: 2 });
                    console.error('[stock_safe] setSyncEnabled 失败:', err);
                });
        });
    }

    function applyFiltersFromDOM() {
        currentFilter.keyword = (document.getElementById('filterKeyword').value || '').trim();
        currentFilter.sales_status = (document.getElementById('filterSalesStatus').value || '').trim();
        currentFilter.stock_status = (document.getElementById('filterStockStatus').value || '').trim();
        currentFilter.abc_classification = (document.getElementById('filterABC').value || '').trim();
        currentFilter.sync_enabled = (document.getElementById('filterSyncEnabled').value || '').trim();
        currentFilter.data_type = (document.getElementById('filterDataType').value || 'useful').trim();
    }

    // ============================================================
    // 独立按钮：列显示设置 弹窗
    // ============================================================
    var colModalOpenSnapshot = null;  // 打开时的"列显隐快照"，取消时回滚

    function bindColVisibilityModalEvents() {
        var modal = document.getElementById('colVisibilityModal');
        document.getElementById('btnColClose').addEventListener('click', closeColVisibilityModal);
        document.getElementById('btnColCancel').addEventListener('click', closeColVisibilityModal);
        document.getElementById('btnColAll').addEventListener('click', function () { toggleAllInColModal(true); });
        document.getElementById('btnColNone').addEventListener('click', function () { toggleAllInColModal(false); });
        document.getElementById('btnColConfirm').addEventListener('click', function () {
            applyColVisibilityFromModal();
            closeColVisibilityModal();
        });
        modal.addEventListener('click', function (e) {
            if (e.target === modal) closeColVisibilityModal();
        });
    }

    function openColVisibilityModal() {
        if (!gridColumnApi) return;
        var modal = document.getElementById('colVisibilityModal');
        var list = document.getElementById('colVisibilityList');
        list.innerHTML = '';

        try {
            colModalOpenSnapshot = (gridColumnApi.getColumnState() || []).map(function (s) {
                return { colId: s.colId, hide: !!s.hide };
            });
        } catch (e) { colModalOpenSnapshot = []; }

        var colStates = [];
        try {
            colStates = gridColumnApi.getColumnState() || [];
            colStates.sort(function (a, b) {
                return (a.sortIndex != null ? a.sortIndex : 9999) - (b.sortIndex != null ? b.sortIndex : 9999);
            });
        } catch (e) {}

        colStates.forEach(function (st) {
            var def = COLUMN_DEFS.find(function (c) { return (c.field || c.colId) === st.colId; });
            var label = def ? def.headerName : st.colId;
            var checked = !st.hide ? 'checked' : '';
            var item = document.createElement('label');
            item.innerHTML =
                '<input type="checkbox" data-col-id="' + st.colId + '" ' + checked + '>' +
                '<span>' + label + '</span>';
            list.appendChild(item);
        });

        modal.classList.add('show');
    }

    function closeColVisibilityModal() {
        var modal = document.getElementById('colVisibilityModal');
        modal.classList.remove('show');
    }

    function toggleAllInColModal(visible) {
        var inputs = document.querySelectorAll('#colVisibilityList input[type="checkbox"]');
        inputs.forEach(function (i) { i.checked = visible; });
    }

    function applyColVisibilityFromModal() {
        if (!gridColumnApi) return;
        var inputs = document.querySelectorAll('#colVisibilityList input[type="checkbox"]');
        var hideMap = {};
        inputs.forEach(function (i) {
            hideMap[i.getAttribute('data-col-id')] = !i.checked;
        });
        var base = (colModalOpenSnapshot && colModalOpenSnapshot.length) ? colModalOpenSnapshot : [];
        var state = base.map(function (s) {
            return { colId: s.colId, hide: (hideMap[s.colId] !== undefined) ? hideMap[s.colId] : !!s.hide };
        });
        try {
            gridColumnApi.applyColumnState({ state: state, applyOrder: false });
        } catch (e) { console.warn('applyColumnState 失败:', e); }
        // 列显隐变化会改变显示列序号，清空已有的框选
        clearExcelSelection();
    }

    // ============================================================
    // 状态数量卡片
    // ============================================================
    function loadStatusCount() {
        fetch('/new/api/stock_safe/status-count', { credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (res) {
                if (res.code !== 0) return;
                var data = res.data || {};
                // 统计库存维度标签（后端按关键字匹配统计，一个产品可能同时计入多个维度）
                var keys = ['紧急补货', '需补货', '需补货|可卖天数较少', '慢动销去库', '呆滞清库',
                           '库存正常', '无销售', '销量极低', '销量低', '销量正常'];
                var total = 0;
                keys.forEach(function (k) {
                    var cnt = data[k] || 0;
                    total += cnt;
                    var el = document.getElementById('count_' + k);
                    if (el) el.textContent = cnt.toLocaleString();
                });
                var badge = document.getElementById('totalBadge');
                if (badge) badge.textContent = '共 ' + total.toLocaleString() + ' 条记录';
            })
            .catch(function (err) { console.warn('[stock_safe] status-count 失败:', err); });
    }

    // ============================================================
    // 后端取数（分页 + 排序 + 搜索 全部服务端）
    // ============================================================
    function fetchData(page, pageSize) {
        if (isLoading) return;
        isLoading = true;

        var pg = pagination ? pagination.getPaginationParams() : { page: 1, pageSize: 50 };
        var reqPage = page != null ? page : pg.page;
        var reqSize = pageSize != null ? pageSize : pg.pageSize;

        layui.use(['layer'], function (layer) {
            layer.load(2);

            var url = '/new/api/stock_safe/list'
                + '?page=' + reqPage
                + '&limit=' + reqSize;
            if (currentSortField) {
                url += '&sort_field=' + encodeURIComponent(currentSortField)
                    + '&sort_order=' + encodeURIComponent(currentSortOrder);
            }
            if (currentFilter.keyword)           url += '&keyword=' + encodeURIComponent(currentFilter.keyword);
            if (currentFilter.sales_status)    url += '&sales_status=' + encodeURIComponent(currentFilter.sales_status);
            if (currentFilter.stock_status)    url += '&stock_status=' + encodeURIComponent(currentFilter.stock_status);
            if (currentFilter.abc_classification) url += '&abc_classification=' + encodeURIComponent(currentFilter.abc_classification);
            if (currentFilter.sync_enabled !== '') url += '&sync_enabled=' + encodeURIComponent(currentFilter.sync_enabled);
            url += '&data_type=' + encodeURIComponent(currentFilter.data_type);

            fetch(url, { credentials: 'same-origin' })
                .then(function (r) { return r.json(); })
                .then(function (res) {
                    layer.closeAll('loading');
                    isLoading = false;
                    if (res.code !== 0) {
                        layer.msg(res.msg || '加载失败', { icon: 2 });
                        return;
                    }
                    var data = res.data || {};
                    var list = data.list || [];
                    if (gridApi) gridApi.setRowData(list);
                    // 数据刷新后，清空上一轮的框选（行序号已变化）
                    clearExcelSelection();

                    // 更新公共分页组件
                    if (pagination) {
                        pagination.update(
                            data.total || 0,
                            data.page || 1,
                            data.limit || reqSize
                        );
                    }

                    var badge = document.getElementById('totalBadge');
                    if (badge) badge.textContent = '共 ' + (data.total || 0).toLocaleString() + ' 条记录';
                })
                .catch(function (err) {
                    layer.closeAll('loading');
                    isLoading = false;
                    layer.msg('网络错误，请稍后重试', { icon: 2 });
                    console.error('[stock_safe] fetchData 失败:', err);
                });
        });
    }

    // ============================================================
    // 导出
    // ============================================================
    function exportData() {
        layui.use(['layer'], function (layer) {
            layer.msg('正在准备导出...', { icon: 16, time: 1200 });

            var url = '/new/api/stock_safe/list?page=1&limit=100000';
            if (currentSortField) {
                url += '&sort_field=' + encodeURIComponent(currentSortField)
                    + '&sort_order=' + encodeURIComponent(currentSortOrder);
            }
            if (currentFilter.keyword)           url += '&keyword=' + encodeURIComponent(currentFilter.keyword);
            if (currentFilter.sales_status)    url += '&sales_status=' + encodeURIComponent(currentFilter.sales_status);
            if (currentFilter.stock_status)    url += '&stock_status=' + encodeURIComponent(currentFilter.stock_status);
            if (currentFilter.abc_classification) url += '&abc_classification=' + encodeURIComponent(currentFilter.abc_classification);
            if (currentFilter.sync_enabled !== '') url += '&sync_enabled=' + encodeURIComponent(currentFilter.sync_enabled);
            url += '&data_type=' + encodeURIComponent(currentFilter.data_type);

            fetch(url, { credentials: 'same-origin' })
                .then(function (r) { return r.json(); })
                .then(function (res) {
                    if (res.code !== 0) {
                        layer.msg('导出失败: ' + (res.msg || '未知错误'), { icon: 2 });
                        return;
                    }
                    exportToCSV((res.data && res.data.list) || []);
                })
                .catch(function (err) {
                    layer.msg('导出失败，网络错误', { icon: 2 });
                    console.error('[stock_safe] export 失败:', err);
                });
        });
    }

    function exportToCSV(rows) {
        if (!rows || rows.length === 0) {
            layui.use(['layer'], function (l) { l.msg('没有数据可导出', { icon: 0 }); });
            return;
        }
        var headers = ['OE号', '品牌', '条码', '产品名称', 'ABC分类',
            '可用库存', '在途数量', '日均销量', '基础安全库存', '季节系数',
            '调整后安全库存', '库存下限', '库存上限', '可卖天数', '销售状态', '库存状态'];
        var keys = ['number', 'brand_name', 'frey_no', 'pdname', 'abc_classification',
            'available_stock', 'transit_quantity', 'avg_daily_sales', 'base_safety_stock', 'season_coefficient',
            'safety_stock', 'stock_lower_limit', 'stock_upper_limit', 'sellable_days', 'sales_status', 'stock_status'];

        function esc(v) {
            var s = v == null ? '' : String(v);
            return (s.indexOf(',') >= 0 || s.indexOf('"') >= 0 || s.indexOf('\n') >= 0)
                ? '"' + s.replace(/"/g, '""') + '"' : s;
        }
        var csv = '\uFEFF' + headers.join(',') + '\n';
        rows.forEach(function (r) {
            csv += keys.map(function (k) { return esc(r[k]); }).join(',') + '\n';
        });

        var blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        var a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = '安全库存_' + new Date().toISOString().slice(0, 10) + '.csv';
        a.style.display = 'none';
        document.body.appendChild(a); a.click(); document.body.removeChild(a);

        layui.use(['layer'], function (l) {
            l.msg('导出成功，共 ' + rows.length.toLocaleString() + ' 条', { icon: 1 });
        });
    }

    // ============================================================
    // 双击复制
    // ============================================================
    function initDoubleClickCopy() {
        var gridDiv = document.getElementById('stockSafeGrid');
        if (!gridDiv) return;
        gridDiv.addEventListener('dblclick', function (e) {
            var cell = e.target.closest('.ag-cell');
            if (!cell) return;
            var txt = cell.textContent.trim();
            if (!txt) return;
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(txt).then(function () {
                    layui.layer.msg('已复制: ' + txt.substring(0, 24) + (txt.length > 24 ? '...' : ''),
                        { icon: 1, time: 1400 });
                }).catch(function () { fallbackCopy(txt); });
            } else { fallbackCopy(txt); }
        });
    }
    function fallbackCopy(text) {
        var ta = document.createElement('textarea');
        ta.value = text;
        ta.style.cssText = 'position:fixed;opacity:0;';
        document.body.appendChild(ta); ta.select();
        try { document.execCommand('copy'); } catch (e) {}
        document.body.removeChild(ta);
    }

})();
