/**
 * SortableUtils
 * 表格本地排序纯函数工具：解析单元格值（时间/数值/文本）并按方向比较。
 *
 * 设计约束：
 * - 无 DOM、无第三方依赖，可在浏览器与 Node 中直接加载
 * - handsontable-builder.js 的 sortLocalData 依赖本模块做单元格比较
 *
 * 比较规则（升序语义，desc 由方向包装取反）：
 * 1. 两侧均为 ISO/SQL 风格时间字符串 → 按时间戳比较
 * 2. 两侧均可解析为数值（数字，或剥离货币符号/千分位/百分号后为纯数字）→ 按数值比较
 * 3. 其余 → 按字符串比较
 */

var SortableUtils = (function() {
    'use strict';

    /**
     * ISO / SQL 风格时间字符串解析为时间戳
     * 如 '2026-01-02T03:04:05'、'2026-01-02 03:04:05'，非该格式返回 null
     */
    function parseSortableDate(value) {
        if (typeof value !== 'string') return null;
        var m = value.match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?$/);
        if (!m) return null;
        var ts = Date.UTC(parseInt(m[1], 10), parseInt(m[2], 10) - 1, parseInt(m[3], 10),
                           parseInt(m[4], 10), parseInt(m[5], 10), parseInt(m[6], 10));
        return isNaN(ts) ? null : ts;
    }

    /**
     * 解析可排序数值：
     * - number 直接返回
     * - 字符串剥离前导货币符号(¥$€£)、千分位逗号、尾部百分号后须为纯数字
     *   如 '¥1,234.50' → 1234.5，'12.00%' → 12
     * - 其余（含 '0123A' 等字母数字混排）返回 null，由调用方走字符串比较
     */
    function parseSortableNumber(value) {
        if (typeof value === 'number' && isFinite(value)) return value;
        if (typeof value !== 'string') return null;
        var s = value.trim();
        if (!s) return null;
        var stripped = s.replace(/^[¥$€£]/, '').replace(/,/g, '').replace(/%$/, '');
        if (/^-?\d+(\.\d+)?$/.test(stripped)) {
            return parseFloat(stripped);
        }
        return null;
    }

    /**
     * 升序比较单个单元格值：时间 → 数值 → 字符串
     * null/undefined 归一为空字符串后参与比较
     */
    function compareAsc(va, vb) {
        if (va === undefined || va === null) va = '';
        if (vb === undefined || vb === null) vb = '';

        var dateA = parseSortableDate(va);
        var dateB = parseSortableDate(vb);
        if (dateA !== null && dateB !== null) {
            return dateA - dateB;
        }

        var numA = parseSortableNumber(va);
        var numB = parseSortableNumber(vb);
        if (numA !== null && numB !== null) {
            return numA - numB;
        }

        va = String(va);
        vb = String(vb);
        if (va < vb) return -1;
        if (va > vb) return 1;
        return 0;
    }

    /**
     * 带方向比较：asc 原序，desc 取反
     * @param {string} dir 'asc' | 'desc'
     */
    function compareValues(va, vb, dir) {
        var result = compareAsc(va, vb);
        return dir === 'desc' ? -result : result;
    }

    return {
        parseSortableDate: parseSortableDate,
        parseSortableNumber: parseSortableNumber,
        compareValues: compareValues
    };
})();

// 浏览器：挂载到全局，供 handsontable-builder.js 使用
if (typeof window !== 'undefined') {
    window.SortableUtils = SortableUtils;
}
// Node：导出供单元测试使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SortableUtils;
}
