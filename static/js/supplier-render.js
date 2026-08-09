/**
 * 供应商信息公共渲染模块
 * 统一 search_in_crm 页面与购物车页面的供应商解析、展示和交互逻辑
 *
 * 数据格式：purchase_records JSON（与 crmapp_compare_summary / crmapp_cart 统一）
 * 不再支持字符串回退解析，彻底统一为 JSON 格式。
 */
(function(global) {
    'use strict';

    /**
     * 解析供应商数据
     * @param {string} jsonRecords  - purchase_records JSON 字符串
     * @returns {Array} 解析后的记录列表 [{date, name, price}]
     */
    function parseSupplierRecords(jsonRecords) {
        if (!jsonRecords) return [];

        try {
            var records = JSON.parse(jsonRecords);
            if (Array.isArray(records) && records.length > 0) {
                return records.map(function(r) {
                    return {
                        date: r.purchase_date || '',
                        name: r.supplier_name || '',
                        price: r.purchase_price !== undefined ? String(r.purchase_price) : ''
                    };
                });
            }
        } catch (e) {
            // JSON 解析失败，返回空数组
        }

        return [];
    }

    /**
     * 构建供应商 tooltip HTML 内容
     * @param {Array} records - parseSupplierRecords 返回的记录列表
     * @returns {string} tooltip HTML 字符串
     */
    function buildSupplierTooltipHtml(records) {
        var hasDate = records.some(function(s) { return s.date; });
        var tooltipContent = '';

        if (records.length > 0) {
            records.forEach(function(s) {
                if (hasDate) {
                    tooltipContent +=
                        '<div class="supplier-tooltip-row" style="display: flex; gap: 8px; padding: 8px 16px; border-bottom: 1px solid #f6f6f6;">' +
                            '<span style="min-width: 90px; color: #666;">' + (s.date || '-') + '</span>' +
                            '<span style="flex: 1; color: #333;">' + s.name + '</span>' +
                            '<span style="min-width: 60px; text-align: right; color: #e91e63; font-weight: 500; white-space: nowrap;">' + (s.price || '-') + '</span>' +
                        '</div>';
                } else {
                    tooltipContent +=
                        '<div class="supplier-tooltip-row" style="display: flex; gap: 8px; padding: 8px 16px; border-bottom: 1px solid #f6f6f6;">' +
                            '<span style="flex: 1; color: #333;">' + s.name + '</span>' +
                            '<span style="min-width: 60px; text-align: right; color: #e91e63; font-weight: 500; white-space: nowrap;">' + (s.price || '-') + '</span>' +
                        '</div>';
                }
            });
        } else {
            tooltipContent = '<div class="supplier-tooltip-row" style="padding: 8px 16px; color: #999;">暂无供应商信息</div>';
        }

        var headerText = hasDate ? '日期 - 供应商 - 单价' : '供应商 - 单价';
        return '<div class="supplier-tooltip-header" style="padding: 12px 16px; background: #f8f9fa; border-bottom: 1px solid #e6e6e6; border-radius: 8px 8px 0 0; font-weight: 500; color: #333; font-size: 14px;">' +
            headerText + '</div>' +
            '<div class="supplier-tooltip-content" style="max-height: 300px; overflow-y: auto;">' + tooltipContent + '</div>';
    }

    /**
     * 生成供应商单元格的摘要文本（用于单元格内显示）
     * @param {Array} records - parseSupplierRecords 返回的记录列表
     * @returns {string} 摘要文本
     */
    function buildSupplierSummary(records) {
        if (!records || records.length === 0) return '';
        var first = records[0];
        var summary = first.name + (first.price ? ' ¥' + first.price : '');
        return records.length > 1 ? summary + ' 等' + records.length + '条' : summary;
    }

    /**
     * 渲染供应商单元格（Layui 表格 templet 用）
     * @param {Object} d - Layui 表格行数据
     * @param {Object} options - 可选配置 { width, maxWidth }
     * @returns {string} HTML 字符串
     */
    function renderSupplierCellForLayui(d, options) {
        options = options || {};
        var jsonRecords = d.purchase_records || '';
        var records = parseSupplierRecords(jsonRecords);
        var summary = buildSupplierSummary(records);

        var width = options.width || 120;
        var maxWidth = options.maxWidth || 500;
        var minWidth = options.minWidth || 350;

        return '<div class="supplier-cell" style="position: relative; cursor: pointer; display: inline-block;" ' +
            'data-purchase-records="' + (jsonRecords || '').replace(/"/g, '&quot;') + '">' +
            (summary) +
            '<div class="supplier-tooltip" style="display: none; position: absolute; background: #fff; border: 1px solid #e6e6e6; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); max-width: ' + maxWidth + 'px; min-width: ' + minWidth + 'px; font-size: 12px; z-index: 3000; top: 100%; left: 0; margin-top: 4px;">' +
                buildSupplierTooltipHtml(records) +
            '</div>' +
            '</div>';
    }

    /**
     * 为 Handsontable 渲染供应商单元格
     * @param {Object} instance - Handsontable 实例
     * @param {HTMLElement} td - 单元格元素
     * @param {number} row - 行号
     * @param {number} col - 列号
     * @param {string} prop - 属性名
     * @param {string} value - 单元格值
     * @param {Object} cellProperties - 单元格属性
     */
    function renderSupplierCellForHandsontable(instance, td, row, col, prop, value, cellProperties) {
        if (typeof Handsontable !== 'undefined') {
            Handsontable.renderers.TextRenderer.apply(this, arguments);
        }
        var jsonRecords = instance.getDataAtRowProp(row, 'purchase_records') || '';
        var records = parseSupplierRecords(jsonRecords);
        var summary = buildSupplierSummary(records);

        td.innerHTML = '<div class="supplier-cell" data-purchase-records="' + (jsonRecords ? jsonRecords.replace(/"/g, '&quot;') : '') + '">' +
            (summary) +
            '</div>';
        return td;
    }

    /**
     * 初始化供应商 tooltip 事件委托（用于 Layui 表格等动态内容）
     * @param {string} containerSelector - 容器选择器，默认为 document
     */
    function initSupplierTooltipEvents(containerSelector) {
        var container = containerSelector ? document.querySelector(containerSelector) : document;
        if (!container) return;

        container.addEventListener('mouseenter', function(e) {
            var cell = e.target.closest('.supplier-cell');
            if (!cell) return;

            var tooltip = cell.querySelector('.supplier-tooltip');
            if (!tooltip) return;

            // 关闭其他已打开的 tooltip
            document.querySelectorAll('.supplier-tooltip[style*="block"]').forEach(function(t) {
                if (t !== tooltip) t.style.display = 'none';
            });

            tooltip.style.display = 'block';
        }, true);

        container.addEventListener('mouseleave', function(e) {
            var cell = e.target.closest('.supplier-cell');
            if (!cell) return;

            var tooltip = cell.querySelector('.supplier-tooltip');
            if (tooltip) tooltip.style.display = 'none';
        }, true);
    }

    // 暴露公共 API
    global.SupplierRender = {
        parseRecords: parseSupplierRecords,
        buildTooltipHtml: buildSupplierTooltipHtml,
        buildSummary: buildSupplierSummary,
        renderForLayui: renderSupplierCellForLayui,
        renderForHandsontable: renderSupplierCellForHandsontable,
        initTooltipEvents: initSupplierTooltipEvents
    };

})(window);
