/**
 * 在途明细浮窗 Provider
 *
 * 作为 HoverPopover 的 'intransit' 内容提供者：
 * 悬停在途数量单元格时，按条码懒加载该 frey_no 下的在途明细。
 * 结果按条码缓存（当前页面生命周期内），避免重复请求；请求失败清除缓存可重试。
 */
(function (global) {
    'use strict';

    var HP = global.HoverPopover;

    // 明细列契约（展示列名 -> 数据字段），固定顺序，不靠中文列名反推
    var COLUMNS = [
        { title: '供应商', field: 'supplier_name' },
        { title: '采购数量', field: 'purchase_quantity', num: true },
        { title: '单价', field: 'price', num: true, price: true },
        { title: '下单时间', field: 'order_date' },
        { title: '到货时间', field: 'expected_delivery_date' },
        { title: '仓库', field: 'warehouse_name' }
    ];

    var cache = {};  // barcode -> Promise<rows>

    function fetchDetails(barcode) {
        if (cache[barcode]) return cache[barcode];

        var promise = fetch('/api/intransit/detail?barcode=' + encodeURIComponent(barcode), {
            credentials: 'same-origin'
        })
            .then(function (res) { return res.json(); })
            .then(function (json) {
                if (json.code !== 0) throw new Error(json.msg || '查询失败');
                return json.data || [];
            })
            .catch(function (err) {
                delete cache[barcode];   // 失败不缓存，允许下次悬停重试
                throw err;
            });

        cache[barcode] = promise;
        return promise;
    }

    function displayValue(row, field) {
        var v = row[field];
        return (v === null || v === undefined || v === '') ? '-' : v;
    }

    function buildContent(rows) {
        if (!rows.length) return '<div class="hp-empty">当前无在途单据</div>';

        var html = '<table class="hp-table"><thead><tr>';
        COLUMNS.forEach(function (c) {
            html += '<th' + (c.num ? ' class="hp-num"' : '') + '>' + c.title + '</th>';
        });
        html += '</tr></thead><tbody>';

        rows.forEach(function (r) {
            html += '<tr>';
            COLUMNS.forEach(function (c) {
                var cls = c.price ? 'hp-num hp-price' : (c.num ? 'hp-num' : '');
                html += '<td' + (cls ? ' class="' + cls + '"' : '') + '>'
                    + HP.escapeHtml(displayValue(r, c.field)) + '</td>';
            });
            html += '</tr>';
        });
        return html + '</tbody></table>';
    }

    HP.register('intransit', {
        content: function (anchor) {
            var barcode = anchor.getAttribute('data-barcode') || '';
            return fetchDetails(barcode).then(buildContent);
        }
    });

    /* ---------------- 单元格构建工具 ---------------- */

    /**
     * Layui templet 用：在途数量 > 0 且有条码时生成触发器，否则返回纯文本
     */
    function cellHtml(barcode, qty) {
        if (barcode && Number(qty) > 0) {
            return HP.triggerHtml('intransit', { barcode: barcode }, qty);
        }
        return (qty !== null && qty !== undefined) ? HP.escapeHtml(qty) : '';
    }

    /**
     * ag-grid cellRenderer 用：返回触发器 DOM 或纯文本节点
     */
    function createCell(barcode, qty) {
        if (barcode && Number(qty) > 0) {
            return HP.createTrigger('intransit', { barcode: barcode }, qty);
        }
        return document.createTextNode(qty !== null && qty !== undefined ? String(qty) : '');
    }

    global.IntransitPopover = {
        cellHtml: cellHtml,
        createCell: createCell
    };

})(window);
