/**
 * 供应商浮窗 Provider
 *
 * 作为 HoverPopover 的 'supplier' 类型内容提供者，收敛原先散落在
 * index.html / date_query_ag.html / supplier-render.js 中的三份重复解析逻辑。
 *
 * 数据格式：
 * - 主：purchase_records JSON 字符串 [{purchase_date, supplier_name, purchase_quantity, purchase_price}]
 * - 兼容：旧版字符串 "供应商A：123.00, 供应商B：456.00"（正则回退）
 */
(function (global) {
    'use strict';

    var HP = global.HoverPopover;

    /**
     * 解析供应商记录（JSON 优先，旧字符串格式回退）
     * @returns {Array<{date:string,name:string,quantity:string,price:string}>}
     */
    function parseRecords(jsonRecords, fallbackText) {
        if (jsonRecords) {
            try {
                var records = JSON.parse(jsonRecords);
                if (Array.isArray(records) && records.length > 0) {
                    return records.map(function (r) {
                        return {
                            date: r.purchase_date || '',
                            name: r.supplier_name || '',
                            quantity: r.purchase_quantity !== undefined && r.purchase_quantity !== null
                                ? String(r.purchase_quantity) : '',
                            price: r.purchase_price !== undefined ? String(r.purchase_price) : ''
                        };
                    });
                }
            } catch (e) {
                // JSON 解析失败，继续走旧字符串回退
            }
        }

        var list = [];
        if (fallbackText) {
            var regex = /(.+?)：(\d+\.?\d*)/g;
            var match;
            while ((match = regex.exec(fallbackText)) !== null) {
                var name = match[1].trim();
                if (name) {
                    list.push({ name: name, price: match[2].trim(), quantity: '', date: '' });
                }
            }
        }
        return list;
    }

    /**
     * 单元格摘要文本：首条供应商 + 单价，多条时标注条数
     */
    function buildSummary(records, fallbackText) {
        if (records.length > 0) {
            var first = records[0];
            var summary = first.name + (first.price ? ' ¥' + first.price : '');
            return records.length > 1 ? summary + ' 等' + records.length + '条' : summary;
        }
        return fallbackText || '';
    }

    /**
     * 浮窗内容：固定四列明细表（日期 - 供应商 - 数量 - 单价）
     * 与购物车 / 日期查询浮窗模板保持一致，不随有无日期动态切换
     */
    function buildContent(records, fallbackText) {
        if (records.length === 0) {
            return '<div class="hp-empty">' + HP.escapeHtml(fallbackText || '暂无供应商信息') + '</div>';
        }

        var html = '<table class="hp-table"><thead><tr>'
            + '<th>日期</th><th>供应商</th>'
            + '<th class="hp-num">数量</th><th class="hp-num">单价</th>'
            + '</tr></thead><tbody>';

        records.forEach(function (s) {
            html += '<tr>'
                + '<td>' + HP.escapeHtml(s.date || '-') + '</td>'
                + '<td>' + HP.escapeHtml(s.name) + '</td>'
                + '<td class="hp-num">' + HP.escapeHtml(s.quantity || '-') + '</td>'
                + '<td class="hp-num hp-price">' + HP.escapeHtml(s.price || '-') + '</td>'
                + '</tr>';
        });

        return html + '</tbody></table>';
    }

    /**
     * Layui templet 用：返回触发单元格 HTML
     * @param {string} jsonRecords 行内 purchase_records JSON
     * @param {string} fallbackText 旧版供应商字段原文
     */
    function cellHtml(jsonRecords, fallbackText) {
        var records = parseRecords(jsonRecords, fallbackText);
        var text = buildSummary(records, fallbackText);
        if (!text) return '';
        return HP.triggerHtml('supplier', {
            records: jsonRecords || '',
            supplier: fallbackText || ''
        }, text);
    }

    /**
     * ag-grid cellRenderer 用：返回触发单元格 DOM
     */
    function createCell(jsonRecords, fallbackText) {
        var records = parseRecords(jsonRecords, fallbackText);
        var text = buildSummary(records, fallbackText);
        return HP.createTrigger('supplier', {
            records: jsonRecords || '',
            supplier: fallbackText || ''
        }, text);
    }

    // 注册为 HoverPopover 的供应商内容提供者
    HP.register('supplier', {
        content: function (anchor) {
            var records = parseRecords(
                anchor.getAttribute('data-records') || '',
                anchor.getAttribute('data-supplier') || ''
            );
            return buildContent(records, anchor.getAttribute('data-supplier') || '');
        }
    });

    global.SupplierPopover = {
        parseRecords: parseRecords,
        buildSummary: buildSummary,
        buildContent: buildContent,
        cellHtml: cellHtml,
        createCell: createCell
    };

})(window);
