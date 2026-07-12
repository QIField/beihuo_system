/**
 * 购物车表格列定义（Handsontable）
 */
var CartColumns = (function() {
    'use strict';

    /**
     * 左侧固定列数配置
     */
    var FIXED_COLUMNS_LEFT = {
        product: 13,
        supplier: 14
    };

    /**
     * 高亮单元格背景色（库存数量、在途数量、销量）
     */
    var HIGHLIGHT_BG = '#d2d2d2';

    /**
     * 设置单元格内容与样式
     */
    function setCellContent(td, value, options) {
        options = options || {};
        td.innerHTML = (value === null || value === undefined) ? '' : String(value);
        if (options.align) td.style.textAlign = options.align;
        if (options.bg) td.style.backgroundColor = options.bg;
    }

    /**
     * 右对齐数字渲染器
     */
    function numberRenderer(instance, td, row, col, prop, value, cellProperties) {
        Handsontable.renderers.TextRenderer.apply(this, arguments);
        setCellContent(td, value, { align: 'right' });
        return td;
    }

    /**
     * 库存数量渲染器
     */
    function stockRenderer(instance, td, row, col, prop, value, cellProperties) {
        Handsontable.renderers.TextRenderer.apply(this, arguments);
        var rowData = instance.getSourceDataAtRow(row) || {};
        var barcode = rowData.barcode || '';
        td.innerHTML = '<div class="stock-cell" data-barcode="' + barcode + '">' +
            (value === null || value === undefined ? '' : String(value)) +
            '</div>';
        td.style.textAlign = 'right';
        td.style.backgroundColor = HIGHLIGHT_BG;
        return td;
    }

    /**
     * 在途数量渲染器
     */
    function onWayRenderer(instance, td, row, col, prop, value, cellProperties) {
        Handsontable.renderers.TextRenderer.apply(this, arguments);
        setCellContent(td, value, { align: 'right', bg: HIGHLIGHT_BG });
        return td;
    }

    /**
     * 销量渲染器（多行展示）
     */
    function salesRenderer(instance, td, row, col, prop, value, cellProperties) {
        Handsontable.renderers.TextRenderer.apply(this, arguments);
        td.style.backgroundColor = HIGHLIGHT_BG;
        var text = (value === null || value === undefined) ? '' : String(value);
        td.innerHTML = '<div class="sales-cell-content">' + text.replace(/\n/g, '<br>') + '</div>';
        return td;
    }

    /**
     * 供应商渲染器（保留 tooltip 结构）
     */
    function supplierRenderer(instance, td, row, col, prop, value, cellProperties) {
        Handsontable.renderers.TextRenderer.apply(this, arguments);
        var supplierContent = (value === null || value === undefined) ? '' : String(value);

        td.innerHTML = '<div class="supplier-cell" data-suppliers="' + supplierContent.replace(/"/g, '&quot;') + '">' +
            supplierContent +
            '</div>';
        return td;
    }

    /**
     * 操作列渲染器
     */
    function operationRenderer(instance, td, row, col, prop, value, cellProperties) {
        Handsontable.renderers.TextRenderer.apply(this, arguments);
        td.innerHTML = '<button class="layui-btn layui-btn-xs layui-btn-danger cart-remove-btn" data-row="' + row + '">移除</button>';
        return td;
    }

    /**
     * 创建通用列配置
     */
    function createCommonColumns() {
        return [
            { data: 'oe', title: 'OE', width: 100, readOnly: true },
            { data: 'brand', title: '品牌', width: 100, readOnly: true },
            { data: 'material_name', title: '物料名称', width: 150, readOnly: true },
            { data: 'barcode', title: '物料条码', width: 120, readOnly: true },
            { data: 'brand_code', title: '品牌号', width: 100, readOnly: true },
            { data: 'replace_no', title: '替换号', width: 100, readOnly: true },
            { data: 'car_brand', title: '车型品牌', width: 60, readOnly: true },
            { data: 'tag', title: '标签', width: 60, readOnly: true },
            { data: 'car_model', title: '车型', width: 80, readOnly: true },
            { data: 'stock', title: '库存数量', width: 88, readOnly: true, renderer: stockRenderer, className: 'cart-highlight-cell' },
            { data: 'on_way', title: '在途数量', width: 88, readOnly: true, renderer: onWayRenderer, className: 'cart-highlight-cell' },
            { data: 'sales_data', title: '销量', width: 150, readOnly: true, renderer: salesRenderer, className: 'cart-highlight-cell' },
            { data: 'inquiry_1m', title: '近1个月询价量', width: 120, readOnly: true, renderer: numberRenderer },
            { data: 'inquiry_3m', title: '近3个月月均询价量', width: 130, readOnly: true, renderer: numberRenderer },
            { data: 'national_inquiry_1m', title: '全国近1个月询价量', width: 130, readOnly: true, renderer: numberRenderer },
            { data: 'national_inquiry_3m', title: '全国近3个月月均询价量', width: 140, readOnly: true, renderer: numberRenderer },
            { data: 'internal_remarks', title: '内部备注', width: 150, readOnly: true },
            { data: 'stock_amount', title: '库存金额', width: 100, readOnly: true, renderer: numberRenderer },
            { data: 'sellable_days', title: '成品可卖天数', width: 100, readOnly: true, renderer: numberRenderer },
            { data: 'cost_price', title: '成本价', width: 100, readOnly: true, renderer: numberRenderer },
            { data: 'warning_status', title: '预警状态', width: 100, readOnly: true },
            { data: 'quantity', title: '数量', width: 120, type: 'numeric', allowInvalid: false, className: 'htCenter', readOnly: false },
            { data: 'added_time', title: '加入时间', width: 170, readOnly: true },
            { data: 'added_by', title: '账户名', width: 100, readOnly: true },
            { data: '_action', title: '操作', width: 80, readOnly: true, renderer: operationRenderer, disableVisualSelection: true }
        ];
    }

    /**
     * 获取复选列配置
     */
    function getCheckboxColumn() {
        return {
            data: '_selected',
            title: '',
            type: 'checkbox',
            width: 50,
            className: 'htCenter',
            readOnly: false,
            disableVisualSelection: true
        };
    }

    /**
     * 标记列的原始固定位置
     * @param {Array} cols - 列数组
     * @param {number} fixedLeftCount - 左侧固定列数
     */
    function markOriginalFixed(cols, fixedLeftCount) {
        for (var i = 0; i < cols.length; i++) {
            if (i < fixedLeftCount) {
                cols[i].originallyFixed = 'left';
            }
        }
        // 最后一列操作列默认右侧固定
        if (cols.length > 0) {
            cols[cols.length - 1].originallyFixed = 'right';
        }
    }

    /**
     * 获取产品维度列数组
     */
    function getProductColumns() {
        var cols = [getCheckboxColumn()];
        var commonCols = createCommonColumns();

        // 在产品维度中，把供应商列插入到预警状态左边
        var warningIndex = -1;
        for (var i = 0; i < commonCols.length; i++) {
            if (commonCols[i].data === 'warning_status') {
                warningIndex = i;
                break;
            }
        }
        if (warningIndex >= 0) {
            commonCols.splice(warningIndex, 0, {
                data: 'supplier',
                title: '供应商',
                width: 200,
                readOnly: true,
                renderer: supplierRenderer
            });
        } else {
            commonCols.push({
                data: 'supplier',
                title: '供应商',
                width: 200,
                readOnly: true,
                renderer: supplierRenderer
            });
        }

        cols = cols.concat(commonCols);
        markOriginalFixed(cols, FIXED_COLUMNS_LEFT.product);
        return cols;
    }

    /**
     * 获取供应商维度列数组
     */
    function getSupplierColumns() {
        var cols = [getCheckboxColumn()];
        // 在 OE 后插入供应商列
        cols.push({ data: 'supplier', title: '供应商', width: 200, readOnly: true, renderer: supplierRenderer });
        var commonCols = createCommonColumns();
        for (var i = 0; i < commonCols.length; i++) {
            cols.push(commonCols[i]);
        }
        markOriginalFixed(cols, FIXED_COLUMNS_LEFT.supplier);
        return cols;
    }

    return {
        getProductColumns: getProductColumns,
        getSupplierColumns: getSupplierColumns,
        fixedColumnsLeft: FIXED_COLUMNS_LEFT
    };
})();
