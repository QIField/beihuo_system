/**
 * 比价结果采购明细浮窗 Provider
 *
 * 作为 HoverPopover 的 'compare-record' 内容提供者：
 * - scope=overall：悬停「最高/最低价」单元格，展示该产品全部采购记录（日期倒序）
 * - scope=month  ：悬停月份单元格，展示该月全部采购记录（价格升序）
 *
 * 数据来自当前已加载的批次快照（setRows 注入，内存读取，不发请求）。
 * 触发单元格标记：
 *   class="hp-trigger" data-popover="compare-record"
 *   data-row="<Handsontable行号>" data-scope="overall|month" data-month="1-12"
 */
(function (global) {
    'use strict';

    var HP = global.HoverPopover;

    // 当前批次结果行（与 Handsontable 数据源同序）
    var rowsData = [];

    function setRows(rows) {
        rowsData = Array.isArray(rows) ? rows : [];
    }

    function formatPrice(value) {
        var num = Number(value);
        return isNaN(num) ? '-' : num.toFixed(2);
    }

    function uniqRecords(records) {
        var seen = new Set();
        return (records || []).filter(function (r) {
            var key = (r.date || '-') + '|' + (r.supplier || '-') + '|' + Number(r.price);
            if (seen.has(key)) return false;
            seen.add(key);
            return true;
        });
    }

    function buildContent(records) {
        var uniq = uniqRecords(records);
        if (!uniq.length) {
            return '<div class="hp-empty">无采购记录</div>';
        }

        var html = '<table class="hp-table"><thead><tr>'
            + '<th>日期</th><th>供应商</th><th class="hp-num">价格</th>'
            + '</tr></thead><tbody>';

        uniq.forEach(function (r) {
            html += '<tr>'
                + '<td>' + HP.escapeHtml(r.date || '-') + '</td>'
                + '<td>' + HP.escapeHtml(r.supplier || '-') + '</td>'
                + '<td class="hp-num hp-price">' + HP.escapeHtml(formatPrice(r.price)) + '</td>'
                + '</tr>';
        });
        return html + '</tbody></table>';
    }

    function buildOverallRecords(row) {
        var records = [];
        if (row.overall_highest && row.overall_highest.length >= 3) {
            records.push({
                date: row.overall_highest[0],
                supplier: row.overall_highest[1],
                price: row.overall_highest[2]
            });
        }
        if (row.overall_lowest && row.overall_lowest.length >= 3) {
            records.push({
                date: row.overall_lowest[0],
                supplier: row.overall_lowest[1],
                price: row.overall_lowest[2]
            });
        }
        return records;
    }

    HP.register('compare-record', {
        content: function (anchor) {
            var rowIdx = parseInt(anchor.getAttribute('data-row'), 10);
            var scope = anchor.getAttribute('data-scope') || 'overall';
            var row = rowsData[rowIdx];

            if (!row) return '<div class="hp-empty">无采购记录</div>';

            if (scope === 'month') {
                var month = anchor.getAttribute('data-month');
                var monthData = row.months && row.months[month];
                return buildContent(monthData ? monthData.records : []);
            }
            return buildContent(buildOverallRecords(row));
        }
    });

    global.CompareResultPopover = {
        setRows: setRows
    };

})(window);
