/**
 * 供应商价格对比标签页
 *
 * 流程：选择供应商（输入过滤下拉，可留空=全部供应商）→ 开始比对 → 调 /api/cass_inquiry/price_compare
 *       （以译码OE号+品牌为比对键、卖家价格为价格口径，基准为巴博瑞同OE同品牌最低价）→
 *       上下两个表格分别展示「高于佛山巴博瑞」「低于佛山巴博瑞」（各自独立分页，
 *       与巴博瑞持平的行不展示）→ 行内「修改价格」按钮调 CassPriceEditDialog.open(译码OE号)
 *       复用现有开思价弹窗
 * 表格延迟初始化：首次开始比对时才创建（避免隐藏容器渲染异常）
 */
var CassPriceCompare = (function () {
    'use strict';

    // 供应商下拉状态
    var stores = [];
    var selectedStore = '';

    // 表格：上下两个（高于/低于）
    var higherBuilder = null;
    var lowerBuilder = null;
    var inited = false;
    var loading = false;

    function escapeHtml(text) {
        return String(text === null || text === undefined ? '' : text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    /** 价格显示：保留2位小数，空值显示 — */
    function formatPrice(value) {
        if (value === null || value === undefined || value === '') return '—';
        var num = Number(value);
        return isFinite(num) ? num.toFixed(2) : String(value);
    }

    /** 价差显示：带正负号配色 */
    function diffCellRenderer(instance, td, row, col, prop, value) {
        Handsontable.renderers.TextRenderer.apply(this, arguments);
        var num = Number(value);
        td.textContent = (num > 0 ? '+' : '') + num.toFixed(2);
        td.className = num > 0 ? 'diff-cell positive' : (num < 0 ? 'diff-cell negative' : 'diff-cell zero');
        return td;
    }

    function priceCellRenderer(instance, td, row, col, prop, value) {
        Handsontable.renderers.TextRenderer.apply(this, arguments);
        td.textContent = formatPrice(value);
        return td;
    }

    /** 行号渲染器（每页内行号，与主表格一致） */
    function rowNumberRenderer(instance, td, row) {
        td.textContent = row + 1;
        return td;
    }

    /** 操作列：修改价格按钮（data-oe 记录译码OE号，document 级事件委托处理点击） */
    function actionCellRenderer(instance, td, row, col, prop, value) {
        Handsontable.renderers.TextRenderer.apply(this, arguments);
        var rowData = instance.getSourceDataAtRow(instance.toPhysicalRow(row));
        var oe = rowData ? String(rowData.decode_num || '').trim() : '';
        td.innerHTML = oe
            ? '<button type="button" class="price-edit-btn" data-oe="' + escapeHtml(oe) + '">修改价格</button>'
            : '';
        return td;
    }

    // 对比表列定义（行号/OE号冻结；无对比结果列，高低由所在表格区分）
    var columns = [
        { data: '_rowno', title: '行号', width: 60, readOnly: true, className: 'ht-col-rowno', renderer: rowNumberRenderer },
        { data: 'decode_num', title: '译码OE号', width: 150, readOnly: true, className: 'ht-col-oe' },
        { data: 'merchant_parts_num', title: '商家替换号', width: 120, readOnly: true },
        { data: 'brand_name', title: '品牌', width: 110, readOnly: true, className: 'ht-col-brand' },
        { data: 'parts_name', title: '零件名称', width: 150, readOnly: true },
        { data: 'quality_name', title: '品质', width: 90, readOnly: true },
        { data: 'num', title: '数量', width: 70, readOnly: true, className: 'ht-col-num' },
        { data: 'warehouse', title: '仓库', width: 110, readOnly: true },
        { data: 'seller_price', title: '卖家价格', width: 100, readOnly: true, className: 'ht-col-price', renderer: priceCellRenderer },
        { data: 'bbri_price', title: '巴博瑞基准价', width: 110, readOnly: true, className: 'ht-col-price', renderer: priceCellRenderer },
        { data: 'diff', title: '价差', width: 100, readOnly: true, className: 'ht-col-price', renderer: diffCellRenderer },
        { data: '_action', title: '操作', width: 100, readOnly: true, renderer: actionCellRenderer }
    ];

    /** 读取日期范围输入（空值不传，表示全部） */
    function getDateParams() {
        var start = (document.getElementById('compareStartDate').value || '').trim();
        var end = (document.getElementById('compareEndDate').value || '').trim();
        var params = {};
        if (start) params.start_date = start;
        if (end) params.end_date = end;
        return params;
    }

    /**
     * 获取列筛选候选值（服务端去重+计数，按其他列已生效筛选级联）
     * params 由 Builder 组装：store_name/status + column=列名 + column_filters（已排除本列）
     */
    function getFilterValues(colId, callback, params) {
        var all = Object.assign({}, params || {}, getDateParams());
        var query = Object.keys(all)
            .filter(function (key) { return all[key] !== undefined && all[key] !== null && all[key] !== ''; })
            .map(function (key) { return encodeURIComponent(key) + '=' + encodeURIComponent(all[key]); })
            .join('&');
        fetch('/api/cass_inquiry/price_compare/filter_values' + (query ? '?' + query : ''), {
            credentials: 'same-origin'
        })
            .then(function (resp) { return resp.json(); })
            .then(function (result) {
                callback(result && result.code === 0 ? (result.data.values || []) : []);
            })
            .catch(function () { callback([]); });
    }

    /**
     * 创建对比表格（Builder 服务端分页模式，与主表格一致）
     * :param status: higher/lower，决定本表展示哪个方向
     */
    function createBuilder(status, containerId, paginationId) {
        return HandsontableBuilder.create('#' + containerId, {
            columns: columns,
            dataUrl: '/api/cass_inquiry/price_compare',
            paramsBuilder: function () {
                // 供应商留空=全部供应商（不传 store_name），方向与日期恒传
                var params = Object.assign({ status: status }, getDateParams());
                if (selectedStore) params.store_name = selectedStore;
                return params;
            },
            getFilterValues: function (colId, callback, params) {
                getFilterValues(colId, callback, Object.assign({ status: status }, params || {}));
            },
            readOnly: true,
            pageKey: 'cass_price_compare_' + status,
            gridKey: 'cass_price_compare_v2_' + status,
            components: {
                virtualScroll: false,
                doubleClickCopy: true,
                copyToast: true,
                columnMenu: { persist: true },
                pagination: { container: '#' + paginationId, pageSizeOptions: [50, 100, 200], defaultPageSize: 50 },
                ellipsisText: true
            },
            handsontableOptions: {
                fixedColumnsLeft: 2
            },
            onError: function (error) {
                if (window.layui && layui.layer) {
                    layui.layer.msg('比对加载失败: ' + error.message, { icon: 2 });
                }
            }
        });
    }

    // ===== 供应商搜索下拉 =====
    function renderStoreOptions(keyword) {
        var kw = (keyword || '').trim().toLowerCase();
        var list = stores.filter(function (s) { return s.toLowerCase().indexOf(kw) !== -1; });
        var root = document.getElementById('compareStoreOptions');
        root.innerHTML = list.length
            ? list.map(function (s) {
                return '<div class="store-option" data-store="' + escapeHtml(s) + '">' + escapeHtml(s) + '</div>';
            }).join('')
            : '<div class="store-option empty">无匹配供应商</div>';
        root.classList.add('open');
    }

    function closeStoreOptions() {
        var root = document.getElementById('compareStoreOptions');
        if (root) root.classList.remove('open');
    }

    function bindStoreSelect() {
        var input = document.getElementById('compareStoreInput');

        input.addEventListener('focus', function () { renderStoreOptions(input.value); });
        input.addEventListener('input', function () {
            selectedStore = '';
            renderStoreOptions(input.value);
        });
        input.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                closeStoreOptions();
                if (selectedStore) input.value = selectedStore;
            }
        });
        input.addEventListener('blur', function () {
            // blur 先于 click 触发，延迟关闭避免选项点击落空（选中走 mousedown 已先行处理）
            setTimeout(closeStoreOptions, 200);
        });
        document.addEventListener('click', function (e) {
            if (!e.target.closest || !e.target.closest('.store-select')) closeStoreOptions();
        });
        // 选中用 mousedown：mousedown 先于 input blur，保证浮层关闭前完成选中
        document.getElementById('compareStoreOptions').addEventListener('mousedown', function (e) {
            e.preventDefault(); // 阻止输入框失焦，浮层保持展开
            var opt = e.target.closest('.store-option');
            if (!opt || opt.classList.contains('empty')) return;
            selectedStore = opt.getAttribute('data-store');
            input.value = selectedStore;
            input.focus();
            closeStoreOptions();
        });
    }

    // ===== 开始比对 =====
    function startCompare() {
        if (loading) return;
        var input = document.getElementById('compareStoreInput');
        var typed = input.value.trim();
        if (typed) {
            // 有输入时须与候选精确匹配（忽略大小写），未匹配则引导选择或留空查全部
            var kw = typed.toLowerCase();
            var hit = null;
            for (var i = 0; i < stores.length; i++) {
                if (stores[i].toLowerCase() === kw) { hit = stores[i]; break; }
            }
            if (!hit) {
                layui.layer.msg('未找到该供应商，请从下拉中选择，或留空查询全部供应商', { icon: 0 });
                input.focus();
                return;
            }
            selectedStore = hit;
            input.value = hit;
        } else {
            selectedStore = '';  // 留空=全部供应商
        }
        if (!inited) {
            higherBuilder = createBuilder('higher', 'compareHigherContainer', 'compareHigherPagination');
            lowerBuilder = createBuilder('lower', 'compareLowerContainer', 'compareLowerPagination');
            inited = true;
        } else {
            higherBuilder.refresh(1);
            lowerBuilder.refresh(1);
        }
        var title = document.getElementById('compareResultTitle');
        var start = (document.getElementById('compareStartDate').value || '').trim();
        var end = (document.getElementById('compareEndDate').value || '').trim();
        var range = start && end ? start + ' ~ ' + end
            : (start || end ? (start ? start + ' 起' : end + ' 止') : '全部日期');
        var storeLabel = selectedStore || '全部供应商';
        title.textContent = '价格对比结果 — ' + storeLabel + ' vs 佛山巴博瑞汽配（' + range + '）';
    }

    // ===== 修改价格按钮（document 级事件委托，与替换号链接同一模式） =====
    document.addEventListener('click', function (e) {
        if (!e.target || !e.target.closest) return;
        var btn = e.target.closest('.price-edit-btn');
        if (!btn) return;
        var oe = (btn.getAttribute('data-oe') || '').trim();
        if (oe) CassPriceEditDialog.open(oe);
    });

    /**
     * 标签页显示回调（由 inquiry_list.js 的 tab 切换触发，首次显示时加载供应商候选）
     */
    function onTabShown() {
        if (stores.length) return;
        fetch('/api/cass_inquiry/price_compare/stores', { credentials: 'same-origin' })
            .then(function (resp) { return resp.json(); })
            .then(function (result) {
                if (result && result.code === 0) stores = result.data.stores || [];
            })
            .catch(function () { /* 候选加载失败时下拉显示“无匹配供应商” */ });
    }

    function init() {
        bindStoreSelect();
        document.getElementById('compareStartBtn').addEventListener('click', startCompare);
        // 日期变更后自动重新比对（表格已初始化时，供应商留空也生效）
        ['compareStartDate', 'compareEndDate'].forEach(function (id) {
            document.getElementById(id).addEventListener('change', function () {
                if (inited && !loading) {
                    higherBuilder.refresh(1);
                    lowerBuilder.refresh(1);
                }
            });
        });
    }

    return { init: init, onTabShown: onTabShown };
})();
