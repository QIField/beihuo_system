/**
 * 安全库存看板页面
 *
 * 设计说明（按用户 3 点需求实现）：
 *  1) 表头列菜单仅保留【升序 / 降序】两项；其他功能（列显示、筛选）从菜单移除
 *  2) 【列显示】放到独立的工具栏按钮里，点击弹出列勾选面板（全选/全不选 + 确定）
 *  3) 工具栏加回搜索筛选（关键词、库存状态、ABC分类 + 查询/重置），所有筛选项 + 分页 + 排序 统一走后端
 *
 * 技术栈：
 *  - AG Grid 原生 sortable（onSortChanged 拦截 → 后端 ORDER BY）
 *  - CustomPagination 服务端分页（onPageChange → 后端 LIMIT/OFFSET）
 *  - ColumnPreference 持久化：列宽 / 顺序 / 显示隐藏 自动保存
 *  - 列显示独立弹窗：通过 applyColumnState 批量设置 hide
 */

(function () {
    'use strict';

    // ============================================================
    // 全局状态
    // ============================================================
    var gridApi = null;
    var gridColumnApi = null;
    var pagination = null;

    // 排序状态（通过 onSortChanged 同步）
    var currentSortField = '';
    var currentSortOrder = 'asc';

    // 搜索筛选状态
    var currentFilter = {
        keyword: '',
        stock_status: '',
        abc_classification: ''
    };

    // 防止重复请求
    var isLoading = false;

    // 列定义（升序/降序通过 onSortChanged 走后端）
    var COLUMN_DEFS = [
        { headerName: 'OE号', field: 'number', flex: 1.5, minWidth: 180 },
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
        { headerName: '日均销量',         field: 'avg_daily_sales',     width: 110, cellClass: 'cell-number', valueFormatter: decFormatter },
        { headerName: '基础安全库存',     field: 'base_safety_stock',   width: 130, cellClass: 'cell-number', valueFormatter: decFormatter },
        {
            headerName: '季节系数', field: 'season_coefficient', width: 100, cellClass: 'cell-number',
            valueFormatter: function (p) { return (p.value == null || isNaN(p.value)) ? '-' : parseFloat(p.value).toFixed(2); }
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
            headerName: '库存状态', field: 'stock_status', width: 130,
            cellRenderer: renderStatusCell
        }
    ];

    // ---- 单元格渲染 & 格式化 ----
    function renderStatusCell(p) {
        if (!p.value) return '<span style="color:#bbb;">-</span>';
        var M = {
            '紧急补货':   { cls: 'status-danger', ic: '🚨' },
            '需补货':     { cls: 'status-warning', ic: '⚠️' },
            '慢动销去库': { cls: 'status-slow',   ic: '🐢' },
            '呆滞清库':   { cls: 'status-dead',   ic: '💀' },
            '库存积压':   { cls: 'status-info',   ic: '📦' },
            '正常':       { cls: 'status-success', ic: '✅' }
        };
        var s = M[p.value] || { cls: '', ic: '' };
        return '<span class="cell-status ' + s.cls + '">' + s.ic + ' ' + p.value + '</span>';
    }
    function intFormatter(p) {
        if (p.value == null || isNaN(p.value)) return '-';
        return parseInt(p.value).toLocaleString();
    }
    function decFormatter(p) {
        if (p.value == null || isNaN(p.value)) return '-';
        return parseFloat(p.value).toFixed(2).replace(/\.?0+$/, '');
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
    // ============================================================
    function initGrid() {
        var gridOptions = {
            columnDefs: COLUMN_DEFS,
            rowData: [],
            defaultColDef: {
                sortable: true,      // 启用 AG Grid 原生的表头点选排序（通过 onSortChanged 走后端）
                resizable: true,
                filter: false,       // 禁止 AG Grid 内置筛选
                suppressMenu: true,  // 禁止 AG Grid 内置列菜单（不在菜单里放任何功能）
                minWidth: 80
            },
            pagination: false,
            rowSelection: 'multiple',
            suppressRowClickSelection: true,
            suppressMovableColumns: false,
            animateRows: false,
            enableCellTextSelection: true,
            ensureDomOrder: true,
            localeText: {
                loadingOoo: '加载中...',
                noRowsToShow: '暂无数据'
            },
            // ---- 排序变化：清除前端排序，改走后端 ----
            onSortChanged: function (params) {
                if (!gridColumnApi) return;
                var state = [];
                try {
                    state = gridColumnApi.getColumnState() || [];
                } catch (e) {}
                var sortEntry = null;
                // sortIndex 最小者为当前排序目标（AG Grid 支持多列排序）
                state.forEach(function (s) {
                    if (s.sort === 'asc' || s.sort === 'desc') {
                        if (!sortEntry || (s.sortIndex != null && s.sortIndex < sortEntry.sortIndex)) {
                            sortEntry = s;
                        }
                    }
                });
                currentSortField = sortEntry ? sortEntry.colId : '';
                currentSortOrder = sortEntry ? sortEntry.sort : 'asc';

                // 关键：清除 AG Grid 的前端排序状态，前端不参与实际排序
                try {
                    gridColumnApi.applyColumnState({
                        state: state.map(function (s) {
                            return { colId: s.colId, sort: null, sortIndex: null };
                        }),
                        applyOrder: false
                    });
                } catch (e) {}

                if (pagination) pagination.currentPage = 1;
                fetchData();
            },
            onGridReady: function (params) {
                gridApi = params.api;
                gridColumnApi = params.columnApi;
                console.log('[stock_safe] AG Grid 初始化完成');

                // ① 服务器端分页
                pagination = CustomPagination.init({
                    gridSelector: '#stockSafeGrid',
                    pageSizeOptions: [50, 100, 200, 500],
                    defaultPageSize: 50,
                    onPageChange: function (page, pageSize) {
                        fetchData(page, pageSize);
                    }
                });

                // ② 列状态持久化（列宽/顺序/显隐按用户保存）
                if (typeof ColumnPreference !== 'undefined') {
                    ColumnPreference.init(gridApi, {
                        columnApi: gridColumnApi,
                        pageKey: 'stock_safe',
                        gridKey: 'main_grid'
                    });
                }

                initDoubleClickCopy();
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
            document.getElementById('filterStatus').value = '';
            document.getElementById('filterABC').value = '';
            currentFilter = { keyword: '', stock_status: '', abc_classification: '' };
            if (pagination) pagination.currentPage = 1;
            fetchData();
        });
        // 列显示
        document.getElementById('btnColumns').addEventListener('click', openColVisibilityModal);
        // 刷新 / 导出
        document.getElementById('btnRefresh').addEventListener('click', function () { fetchData(); });
        document.getElementById('btnExport').addEventListener('click', exportData);
    }

    function applyFiltersFromDOM() {
        currentFilter.keyword = (document.getElementById('filterKeyword').value || '').trim();
        currentFilter.stock_status = (document.getElementById('filterStatus').value || '').trim();
        currentFilter.abc_classification = (document.getElementById('filterABC').value || '').trim();
    }

    // ============================================================
    // 独立按钮：列显示设置 弹窗
    // ============================================================
    var colModalOpenSnapshot = null;  // 打开时的"列显隐快照"，取消时回滚

    function bindColVisibilityModalEvents() {
        var modal = document.getElementById('colVisibilityModal');
        // 关闭按钮 & 取消
        document.getElementById('btnColClose').addEventListener('click', closeColVisibilityModal);
        document.getElementById('btnColCancel').addEventListener('click', closeColVisibilityModal);
        // 全选 / 全不选
        document.getElementById('btnColAll').addEventListener('click', function () { toggleAllInColModal(true); });
        document.getElementById('btnColNone').addEventListener('click', function () { toggleAllInColModal(false); });
        // 确定
        document.getElementById('btnColConfirm').addEventListener('click', function () {
            applyColVisibilityFromModal();
            closeColVisibilityModal();
            // 保存列偏好
            if (typeof ColumnPreference !== 'undefined') {
                ColumnPreference.flush('stock_safe', 'main_grid');
            }
        });
        // 点击遮罩关闭
        modal.addEventListener('click', function (e) {
            if (e.target === modal) closeColVisibilityModal();
        });
    }

    function openColVisibilityModal() {
        if (!gridColumnApi) return;
        var modal = document.getElementById('colVisibilityModal');
        var list = document.getElementById('colVisibilityList');
        list.innerHTML = '';

        // 列状态快照（用于确定/取消）
        try {
            colModalOpenSnapshot = (gridColumnApi.getColumnState() || []).map(function (s) {
                return { colId: s.colId, hide: !!s.hide };
            });
        } catch (e) { colModalOpenSnapshot = []; }

        // 生成复选框列表，按当前列的实际顺序显示
        var colStates = [];
        try {
            colStates = gridColumnApi.getColumnState() || [];
            colStates.sort(function (a, b) {
                return (a.sortIndex != null ? a.sortIndex : 9999) - (b.sortIndex != null ? b.sortIndex : 9999);
            });
        } catch (e) {}

        colStates.forEach(function (st) {
            // 找对应的 colDef（获取 label）
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
        // 以快照为基础修改 hide，保持其他状态不变
        var base = (colModalOpenSnapshot && colModalOpenSnapshot.length) ? colModalOpenSnapshot : [];
        var state = base.map(function (s) {
            return { colId: s.colId, hide: (hideMap[s.colId] !== undefined) ? hideMap[s.colId] : !!s.hide };
        });
        try {
            gridColumnApi.applyColumnState({ state: state, applyOrder: false });
        } catch (e) { console.warn('applyColumnState 失败:', e); }
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
                var keys = ['紧急补货', '需补货', '慢动销去库', '呆滞清库', '库存积压', '正常'];
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
            if (currentFilter.stock_status)      url += '&stock_status=' + encodeURIComponent(currentFilter.stock_status);
            if (currentFilter.abc_classification) url += '&abc_classification=' + encodeURIComponent(currentFilter.abc_classification);

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
            if (currentFilter.stock_status)      url += '&stock_status=' + encodeURIComponent(currentFilter.stock_status);
            if (currentFilter.abc_classification) url += '&abc_classification=' + encodeURIComponent(currentFilter.abc_classification);

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
            '可用库存', '日均销量', '基础安全库存', '季节系数',
            '调整后安全库存', '库存下限', '库存上限', '可卖天数', '库存状态'];
        var keys = ['number', 'brand_name', 'frey_no', 'pdname', 'abc_classification',
            'available_stock', 'avg_daily_sales', 'base_safety_stock', 'season_coefficient',
            'safety_stock', 'stock_lower_limit', 'stock_upper_limit', 'sellable_days', 'stock_status'];

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