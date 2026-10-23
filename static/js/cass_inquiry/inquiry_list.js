/**
 * 修理厂询价单页面
 * 数据源：/api/cass_inquiry/list（cass_inquiry_quote 表，fsbbr_data 线上库）
 * 表格：HandsontableBuilder 服务端分页模式，风格与询比价模块一致
 */

var CassInquiryList = (function() {
    'use strict';

    // 行号渲染器（每页内行号，与询价模块一致）
    function rowNumberRenderer(instance, td, row) {
        td.textContent = row + 1;
        return td;
    }

    /**
     * OE号规范化：去空白、去横杠/点等分隔符、转大写
     */
    function normalizeOe(value) {
        return String(value === null || value === undefined ? '' : value)
            .replace(/[\s\-–—_.·／/\\]/g, '')
            .toUpperCase();
    }

    /**
     * 判断商家替换号与译码OE号是否一致（规范化后比较，空替换号视为一致不高亮）
     */
    function isSameOe(decodeNum, merchantNum) {
        var merchant = normalizeOe(merchantNum);
        if (!merchant) return true;
        return merchant === normalizeOe(decodeNum);
    }

    /**
     * 商家替换号渲染器：省略号 + title（与统一省略号组件同结构），
     * 与译码OE号不一致时单元格淡黄背景高亮
     */
    function merchantPartsRenderer(instance, td, row, col, prop, value) {
        Handsontable.renderers.TextRenderer.apply(this, arguments);
        var text = (value === null || value === undefined) ? '' : String(value);
        td.innerHTML = '<div class="htb-ellipsis-cell" title="' +
            text.replace(/"/g, '&quot;').replace(/'/g, '&#39;') + '">' +
            text.replace(/\n/g, ' ') +
            '</div>';

        var rowData = instance.getSourceDataAtRow(instance.toPhysicalRow(row));
        if (rowData && !isSameOe(rowData.decode_num, value)) {
            td.style.backgroundColor = '#FFF3CD';
        }
        return td;
    }

    /**
     * 询单日期渲染器：日期与时间之间补空格（如 2026-10-1522:31 → 2026-10-15 22:31），
     * 保留省略号 + title 效果
     */
    function inquiryDateRenderer(instance, td, row, col, prop, value) {
        Handsontable.renderers.TextRenderer.apply(this, arguments);
        var text = (value === null || value === undefined) ? '' : String(value);
        var display = text.replace(/^(\d{4}-\d{2}-\d{2})(\d{2}:\d{2}(?::\d{2})?)$/, '$1 $2');
        td.innerHTML = '<div class="htb-ellipsis-cell" title="' +
            display.replace(/"/g, '&quot;').replace(/'/g, '&#39;') + '">' +
            display.replace(/\n/g, ' ') +
            '</div>';
        return td;
    }

    // 表格列定义（与数据库字段一一对应，全部只读；行号/询单日期/询单ID固定在冻结线左侧）
    var columns = [
        { data: '_rowno', title: '行号', width: 70, readOnly: true, className: 'ht-col-rowno', renderer: rowNumberRenderer },
        { data: 'inquiry_date', title: '询单日期', width: 125, readOnly: true, className: 'ht-col-time', renderer: inquiryDateRenderer },
        { data: 'inquiry_id', title: '询单ID', width: 140, readOnly: true },
        { data: 'decode_num', title: '译码OE号', width: 150, readOnly: true, className: 'ht-col-oe' },
        { data: 'parts_name', title: '零件名称', width: 150, readOnly: true },
        { data: 'brand_name', title: '品牌', width: 120, readOnly: true, className: 'ht-col-brand' },
        { data: 'quality_name', title: '品质', width: 110, readOnly: true },
        { data: 'merchant_parts_num', title: '商家替换号', width: 150, readOnly: true, renderer: merchantPartsRenderer },
        { data: 'car_model', title: '车型', width: 200, readOnly: true },
        { data: 'description', title: '描述', width: 200, readOnly: true },
        { data: 'vin', title: 'VIN码', width: 190, readOnly: true, className: 'ht-col-num' },
        { data: 'num', title: '数量', width: 80, readOnly: true, className: 'ht-col-num' },
        { data: 'price_4s', title: '4S参考价', width: 100, readOnly: true, className: 'ht-col-price' },
        { data: 'seller_price', title: '卖家价格', width: 100, readOnly: true, className: 'ht-col-price' },
        { data: 'store_name', title: '供应商', width: 160, readOnly: true },
        { data: 'location_name', title: '仓库', width: 110, readOnly: true },
        { data: 'selling_point_tag', title: '卖点标签', width: 150, readOnly: true },
        { data: 'replacement', title: '替换标记', width: 90, readOnly: true },
        { data: 'remark', title: '报价备注', width: 200, readOnly: true }
    ];

    var builder = null;

    /**
     * 收集左侧筛选面板条件，作为接口查询参数
     */
    function buildFilterParams() {
        var params = {};

        var dateRange = document.getElementById('inquiryDateRange').value.trim();
        if (dateRange) {
            var dates = dateRange.split(' - ');
            if (dates.length === 2) {
                params.inquiry_start = dates[0].trim();
                params.inquiry_end = dates[1].trim();
            }
        }

        var decodeNum = document.getElementById('searchDecodeNum').value.trim();
        if (decodeNum) params.decode_num = decodeNum;

        var brand = document.getElementById('searchBrand').value.trim();
        if (brand) params.brand_name = brand;

        var store = document.getElementById('searchStore').value.trim();
        if (store) params.store_name = store;

        var inquiryId = document.getElementById('searchInquiryId').value.trim();
        if (inquiryId) params.inquiry_id = inquiryId;

        return params;
    }

    /**
     * 获取列筛选候选值（服务端全量去重+计数，按左侧面板条件与其他列已生效筛选级联）
     * params 由 Builder 组装：面板条件 + column=列名 + column_filters（已排除本列）
     * 返回 [{value, count}]，与日期查询页面筛选值后的数量显示一致
     */
    function getFilterValues(colId, callback, params) {
        var query = Object.keys(params || {})
            .filter(function(key) { return params[key] !== undefined && params[key] !== null && params[key] !== ''; })
            .map(function(key) { return encodeURIComponent(key) + '=' + encodeURIComponent(params[key]); })
            .join('&');
        fetch('/api/cass_inquiry/filter_values' + (query ? '?' + query : ''), {
            method: 'GET',
            credentials: 'same-origin'
        })
            .then(function(response) { return response.json(); })
            .then(function(result) {
                callback(result && result.code === 0 ? (result.data.values || []) : []);
            })
            .catch(function() { callback([]); });
    }

    /**
     * 创建表格（Builder 服务端分页模式）
     */
    function initBuilder() {
        builder = HandsontableBuilder.create('#handsontable-container', {
            columns: columns,
            dataUrl: '/api/cass_inquiry/list',
            paramsBuilder: buildFilterParams,
            getFilterValues: getFilterValues,
            readOnly: true,
            pageKey: 'cass_inquiry',
            gridKey: 'cass_inquiry_list_v2',
            components: {
                virtualScroll: false,
                doubleClickCopy: true,
                copyToast: true,
                columnMenu: { persist: true },
                pagination: { container: '#mainPaginationBar', pageSizeOptions: [50, 100, 200], defaultPageSize: 50 },
                ellipsisText: true
            },
            handsontableOptions: {
                fixedColumnsLeft: 3
            },
            onError: function(error) {
                if (window.layui && layui.layer) {
                    layui.layer.msg('加载失败: ' + error.message, { icon: 2 });
                }
            }
        });
    }

    /**
     * 绑定筛选面板按钮与回车键
     */
    function bindFilterActions() {
        var searchBtn = document.getElementById('filterSearchBtn');
        var resetBtn = document.getElementById('filterResetBtn');

        searchBtn.addEventListener('click', function() {
            if (builder) builder.refresh(1);
        });

        resetBtn.addEventListener('click', function() {
            ['inquiryDateRange', 'searchDecodeNum', 'searchBrand', 'searchStore', 'searchInquiryId']
                .forEach(function(id) { document.getElementById(id).value = ''; });
            if (builder) builder.refresh(1);
        });

        ['searchDecodeNum', 'searchBrand', 'searchStore', 'searchInquiryId'].forEach(function(id) {
            document.getElementById(id).addEventListener('keypress', function(e) {
                if (e.key === 'Enter') searchBtn.click();
            });
        });
    }

    function init() {
        initDateRangePicker('inquiryDateRange');
        initBuilder();
        bindFilterActions();
    }

    return { init: init };
})();

document.addEventListener('DOMContentLoaded', function() {
    CassInquiryList.init();
});
