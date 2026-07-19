/**
 * ks_inquiry_records 统一表格配置
 *
 * 明细列表使用 HandsontableBuilder 读取此配置，按 qpl_quote_records 风格平铺展示，
 * 主表字段（询价单维度）按 inquiryId 合并单元格，明细字段不合并。
 */

window.KsInquiryGridConfig = (function() {
    'use strict';

    // 明细标签页当前筛选状态（用于多列筛选时生成 column_filters）
    var detailFilterState = null;

    function buildDetailParams() {
        var state = getSearchParams('detail');
        return {
            inquiry_id: state.inquiry_id || '',
            garage_name: state.garage_name || '',
            seller_status: state.seller_status || '',
            begin_date: state.begin_date || '',
            end_date: state.end_date || '',
            company: userCompany
        };
    }

    /**
     * 初始不生成合并规则，避免列隐藏/重排后 visual index 错位。
     * 真正的合并逻辑在 Handsontable 初始化完成后通过 afterInit 按当前可见列计算。
     */
    function computeMergeCells(data) {
        console.log('[KS Inquiry Config] computeMergeCells: 初始合并置空，数据条数=' + (data ? data.length : 0));
        return [];
    }

    /**
     * 根据当前可见列重新计算合并单元格，解决列隐藏/重排后 visual index 变化的问题。
     * 在 Handsontable 初始化完成后调用，使用 getSettings().columns 获取实际渲染的列顺序。
     */
    function recomputeMergeCellsByField(hot) {
        var data = hot.getSourceData();
        if (!data || data.length === 0) {
            console.log('[KS Inquiry Config] recomputeMergeCellsByField: 无数据，跳过合并');
            return [];
        }

        var mainFields = ['rowNumber', 'inquiryId', 'customerName', 'carBrandName', 'vin', 'engine', 'productionDate', 'chassis'];
        var columns = hot.getSettings().columns || [];
        var mainCols = [];
        var visibleFieldMap = {};

        columns.forEach(function(colDef, idx) {
            if (colDef && colDef.data) {
                visibleFieldMap[colDef.data] = idx;
            }
        });
        console.log('[KS Inquiry Config] recomputeMergeCellsByField: 可见列映射=' + JSON.stringify(visibleFieldMap));

        mainFields.forEach(function(field) {
            var col = visibleFieldMap[field];
            console.log('[KS Inquiry Config] recomputeMergeCellsByField: 字段=' + field + ', visualCol=' + col);
            if (typeof col === 'number' && col >= 0) {
                mainCols.push(col);
            }
        });

        var merges = [];
        var i = 0;
        while (i < data.length) {
            var inquiryId = data[i].inquiryId;
            var j = i + 1;
            while (j < data.length && data[j].inquiryId === inquiryId) {
                j++;
            }
            var count = j - i;
            if (count > 1) {
                mainCols.forEach(function(col) {
                    merges.push({ row: i, col: col, rowspan: count, colspan: 1 });
                });
            }
            i = j;
        }
        console.log('[KS Inquiry Config] recomputeMergeCellsByField: 主表列索引=' + JSON.stringify(mainCols) + ', 合并块数=' + (mainCols.length > 0 ? merges.length / mainCols.length : 0) + ', 总合并单元格=' + merges.length);
        return merges;
    }

    function fetchFilterValues(url, colId, callback, params) {
        fetch(url + '?' + new URLSearchParams(params).toString(), {
            method: 'GET',
            credentials: 'same-origin'
        })
        .then(function(r) { return r.json(); })
        .then(function(result) {
            if (result.code === 0 || result.code === '0') {
                var data = result.data || {};
                var values = Array.isArray(data) ? data : (data.values || []);
                callback(values);
            } else {
                callback([]);
            }
        })
        .catch(function(e) {
            console.error('[KS Inquiry Config] 加载筛选值失败:', colId, e);
            callback([]);
        });
    }

    function resetDetailFilterState() {
        detailFilterState = null;
    }

    return {
        pageKey: 'ks_inquiry_records',
        resetDetailFilterState: resetDetailFilterState,
        detail: {
            containerSelector: '#handsontable-container',
            dataUrl: '/new/api/ks_inquiry/records',
            gridKey: 'ks_inquiry_detail_grid_v2',
            columns: [
                { data: 'rowNumber', title: '行号', width: 70, className: 'row-number-cell', readOnly: true },
                { data: 'inquiryId', title: '询价单号', width: 150, className: 'oe-cell', readOnly: true },
                { data: 'customerName', title: '客户名称', width: 180, readOnly: true },
                { data: 'carBrandName', title: '车辆品牌', width: 120, readOnly: true },
                { data: 'vin', title: '车架号', width: 150, readOnly: true },
                { data: 'engine', title: '发动机', width: 120, readOnly: true },
                { data: 'productionDate', title: '车辆生产日期', width: 140, readOnly: true },
                { data: 'chassis', title: '底盘', width: 120, readOnly: true },
                { data: 'partsName', title: '配件名称', width: 200, readOnly: true },
                { data: 'partsNum', title: 'OE号', width: 150, className: 'oe-cell', readOnly: true },
                { data: 'brandName', title: '品牌', width: 120, className: 'brand-cell', readOnly: true },
                { data: 'brandNormalized', title: '标准化品牌', width: 120, className: 'brand-cell', readOnly: true },
                { data: 'brandId', title: '品牌ID', width: 100, className: 'count-cell', readOnly: true, type: 'numeric', numericFormat: { pattern: '0' } },
                { data: 'sellerPrice', title: '含税价', width: 120, className: 'price-cell', readOnly: true, type: 'numeric', numericFormat: { pattern: '0.00' } },
                { data: 'sellerBtPrice', title: '不含税价', width: 120, className: 'price-cell', readOnly: true, type: 'numeric', numericFormat: { pattern: '0.00' } },
                { data: 'displaySellerStatus', title: '订单状态', width: 120, readOnly: true },
                { data: 'locationName', title: '发货地', width: 140, readOnly: true },
                { data: 'arrivalTime', title: '备货时间', width: 140, readOnly: true },
                { data: 'remark', title: '备注', width: 200, readOnly: true }
            ],
            paramsBuilder: buildDetailParams,
            mergeCellsBuilder: computeMergeCells,
            handsontableOptions: {
                afterInit: function() {
                    var hot = this;
                    var merges = recomputeMergeCellsByField(hot);
                    console.log('[KS Inquiry Config] afterInit: 准备应用合并，数量=' + merges.length);
                    if (merges.length > 0) {
                        try {
                            hot.updateSettings({ mergeCells: merges });
                            hot.render();
                            console.log('[KS Inquiry Config] afterInit: 合并应用完成');
                        } catch (e) {
                            console.error('[KS Inquiry Config] afterInit: 合并应用失败', e);
                        }
                    } else {
                        console.log('[KS Inquiry Config] afterInit: 无需合并');
                    }
                }
            },
            dataTransform: function(data) {
                var groupIndex = 0;
                var currentInquiry = null;
                data.forEach(function(item) {
                    if (item.inquiryId !== currentInquiry) {
                        currentInquiry = item.inquiryId;
                        groupIndex++;
                    }
                    item.rowNumber = groupIndex;
                });
                return data;
            },
            beforeLoad: function(params) {
                params.page_size = params.limit;
                delete params.limit;
                if (detailFilterState && detailFilterState.active && detailFilterState.filters) {
                    params.column_filters = JSON.stringify(detailFilterState.filters);
                }
                delete params.filter_column;
                delete params.filter_values;
                return params;
            },
            onDataRefresh: function(filterState) {
                detailFilterState = filterState;
            },
            getFilterValues: function(colId, callback, params) {
                params = params || {};
                var state = getSearchParams('detail');
                params.grid_type = 'detail';
                params.column = colId;
                params.inquiry_id = state.inquiry_id || '';
                params.garage_name = state.garage_name || '';
                params.seller_status = state.seller_status || '';
                params.begin_date = state.begin_date || '';
                params.end_date = state.end_date || '';
                params.company = userCompany;
                if (detailFilterState && detailFilterState.active && detailFilterState.filters) {
                    var otherFilters = {};
                    Object.keys(detailFilterState.filters).forEach(function(key) {
                        if (key !== colId) {
                            otherFilters[key] = detailFilterState.filters[key];
                        }
                    });
                    if (Object.keys(otherFilters).length > 0) {
                        params.column_filters = JSON.stringify(otherFilters);
                    }
                }
                fetchFilterValues('/new/api/ks_inquiry/records/column_values', colId, callback, params);
            }
        }
    };
})();
