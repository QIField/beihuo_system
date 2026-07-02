/**
 * qpl_quote_records 统一表格配置
 *
 * 明细列表和 OE 统计维度共用此配置，由 HandsontableBuilder 读取。
 */

window.QplQuoteGridConfig = (function() {
    'use strict';

    function getDateRange() {
        var el = document.getElementById('dateRange');
        if (!el || !el.value) {
            return { begin_date: '', end_date: '' };
        }
        var dates = el.value.split(' - ');
        return { begin_date: dates[0] || '', end_date: dates[1] || '' };
    }

    function buildDetailParams() {
        var dates = getDateRange();
        return {
            supplier_enquiry_no: (document.getElementById('searchSupplierEnquiryNo') || {}).value || '',
            item_oe: (document.getElementById('searchItemOe') || {}).value || '',
            item_name: (document.getElementById('searchItemName') || {}).value || '',
            brand_name: (document.getElementById('searchBrandName') || {}).value || '',
            begin_date: dates.begin_date,
            end_date: dates.end_date
        };
    }

    function buildOeStatsParams() {
        var dates = getDateRange();
        return {
            item_oe: (document.getElementById('searchItemOe') || {}).value || '',
            item_name: (document.getElementById('searchItemName') || {}).value || '',
            begin_date: dates.begin_date,
            end_date: dates.end_date
        };
    }

    function buildVinStatsParams() {
        var dates = getDateRange();
        return {
            begin_date: dates.begin_date,
            end_date: dates.end_date
        };
    }

    function computeMergeCells(data) {
        var merges = [];
        var i = 0;
        while (i < data.length) {
            var orderNo = data[i].supplier_enquiry_no;
            var j = i + 1;
            while (j < data.length && data[j].supplier_enquiry_no === orderNo) {
                j++;
            }
            var orderCount = j - i;
            if (orderCount > 1) {
                merges.push({ row: i, col: 0, rowspan: orderCount, colspan: 1 });
                merges.push({ row: i, col: 1, rowspan: orderCount, colspan: 1 });
                merges.push({ row: i, col: 2, rowspan: orderCount, colspan: 1 });
            }
            var k = i;
            while (k < j) {
                var oe = data[k].item_oe;
                var m = k + 1;
                while (m < j && data[m].item_oe === oe) {
                    m++;
                }
                var oeCount = m - k;
                if (oeCount > 1) {
                    merges.push({ row: k, col: 3, rowspan: oeCount, colspan: 1 });
                    merges.push({ row: k, col: 4, rowspan: oeCount, colspan: 1 });
                }
                k = m;
            }
            i = j;
        }
        return merges;
    }

    function fetchFilterValues(url, colId, callback, params) {
        fetch(url + '?' + new URLSearchParams(params).toString(), {
            method: 'GET',
            credentials: 'same-origin'
        })
        .then(function(r) { return r.json(); })
        .then(function(result) {
            if (result.code === 0) {
                callback(result.data || []);
            } else {
                callback([]);
            }
        })
        .catch(function(e) {
            console.error('[QPL Config] 加载筛选值失败:', colId, e);
            callback([]);
        });
    }

    return {
        pageKey: 'qpl_quote_records',
        detail: {
            containerSelector: '#handsontable-container',
            dataUrl: '/new/api/qpl_quote/records',
            gridKey: 'detail_grid',
            columns: [
                { data: 'rowNumber', title: '行号', width: 70, className: 'row-number-cell', readOnly: true },
                { data: 'supplier_enquiry_no', title: '询价单号', width: 150, className: 'oe-cell', readOnly: true },
                { data: 'submit_time', title: '提交时间', width: 160, className: 'oe-cell', readOnly: true },
                { data: 'item_oe', title: 'OE号', width: 150, className: 'oe-cell', readOnly: true },
                { data: 'item_name', title: '产品名称', width: 200, readOnly: true },
                { data: 'brand_name', title: '品牌', width: 120, className: 'brand-cell', readOnly: true },
                { data: 'item_sell_price', title: '销售价格', width: 100, className: 'price-cell', readOnly: true, type: 'numeric', numericFormat: { pattern: '0.00' } },
                { data: 'delivery_aging', title: '交货周期(天)', width: 120, readOnly: true },
                { data: 'item_quality', title: '产品品质', width: 100, readOnly: true },
                { data: 'parts_no', title: '零件号', width: 130, readOnly: true },
                { data: 'quote_status', title: '报价状态', width: 100, readOnly: true },
                { data: 'result_source', title: '报价来源', width: 120, readOnly: true },
                { data: 'submit_result', title: '提交结果(日志)', width: 150, readOnly: true }
            ],
            paramsBuilder: buildDetailParams,
            mergeCellsBuilder: computeMergeCells,
            dataTransform: function(data) {
                var groupIndex = 0;
                var currentOrder = null;
                data.forEach(function(item) {
                    if (item.supplier_enquiry_no !== currentOrder) {
                        currentOrder = item.supplier_enquiry_no;
                        groupIndex++;
                    }
                    item.rowNumber = groupIndex;
                });
                return data;
            },
            getFilterValues: function(colId, callback, params) {
                fetchFilterValues('/new/api/qpl_quote/filter_values', colId, callback, params);
            }
        },
        oeStats: {
            containerSelector: '#handsontable-oe-container',
            dataUrl: '/new/api/qpl_quote/oe_stats',
            gridKey: 'oe_stats_grid',
            columns: [
                { data: 'rowNumber', title: '行号', width: 70, className: 'row-number-cell', readOnly: true },
                { data: 'item_oe', title: 'OE', width: 150, className: 'oe-cell', readOnly: true },
                { data: 'item_name', title: '产品名称', width: 200, readOnly: true },
                { data: 'occurrence_count', title: '出现次数', width: 120, className: 'count-cell', readOnly: true, type: 'numeric', numericFormat: { pattern: '0' } }
            ],
            paramsBuilder: buildOeStatsParams,
            getFilterValues: function(colId, callback, params) {
                fetchFilterValues('/new/api/qpl_quote/oe_filter_values', colId, callback, params);
            }
        },
        vinStatsOeNum: {
            containerSelector: '#handsontable-vin-oenum-container',
            dataUrl: '/new/api/qpl_quote/vin_stats_oenum',
            gridKey: 'vin_stats_oenum_grid',
            columns: [
                { data: 'rowNumber', title: '行号', width: 70, className: 'row-number-cell', readOnly: true },
                { data: 'item_oe', title: 'OE', width: 200, className: 'oe-cell', readOnly: true },
                { data: 'occurrence_count', title: '出现次数', width: 120, className: 'count-cell', readOnly: true, type: 'numeric', numericFormat: { pattern: '0' } }
            ],
            paramsBuilder: buildVinStatsParams,
            getFilterValues: function(colId, callback, params) {
                fetchFilterValues('/new/api/qpl_quote/vin_oenum_filter_values', colId, callback, params);
            }
        },
        vinStatsEngine: {
            containerSelector: '#handsontable-vin-engine-container',
            dataUrl: '/new/api/qpl_quote/vin_stats_engine',
            gridKey: 'vin_stats_engine_grid',
            columns: [
                { data: 'rowNumber', title: '行号', width: 70, className: 'row-number-cell', readOnly: true },
                { data: 'engine', title: '发动机', width: 200, className: 'engine-cell', readOnly: true },
                { data: 'occurrence_count', title: '出现次数', width: 120, className: 'count-cell', readOnly: true, type: 'numeric', numericFormat: { pattern: '0' } }
            ],
            paramsBuilder: buildVinStatsParams,
            getFilterValues: function(colId, callback, params) {
                fetchFilterValues('/new/api/qpl_quote/vin_engine_filter_values', colId, callback, params);
            }
        },
        vinStatsChassis: {
            containerSelector: '#handsontable-vin-chassis-container',
            dataUrl: '/new/api/qpl_quote/vin_stats_chassis',
            gridKey: 'vin_stats_chassis_grid',
            columns: [
                { data: 'rowNumber', title: '行号', width: 70, className: 'row-number-cell', readOnly: true },
                { data: 'chassis', title: '底盘', width: 200, className: 'chassis-cell', readOnly: true },
                { data: 'occurrence_count', title: '出现次数', width: 120, className: 'count-cell', readOnly: true, type: 'numeric', numericFormat: { pattern: '0' } }
            ],
            paramsBuilder: buildVinStatsParams,
            getFilterValues: function(colId, callback, params) {
                fetchFilterValues('/new/api/qpl_quote/vin_chassis_filter_values', colId, callback, params);
            }
        }
    };
})();
