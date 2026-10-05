/**
 * sortable-utils.js 单元测试（node 直接运行，无测试框架依赖）
 *
 * 运行方式：
 *   node tests/frontend/test_sortable_utils.js
 *
 * 覆盖范围：
 *   - parseSortableDate：ISO/SQL 时间字符串解析
 *   - parseSortableNumber：数字 / 货币符号 / 千分位 / 百分号 / 字母数字混排
 *   - compareValues：时间 / 数值 / 字符串三种比较路径 + asc/desc 方向
 *   - 端到端：模拟 sortLocalData 对 ¥ 金额列的整体排序行为
 */

const SortableUtils = require('../../static/js/components/handsontable-builder/sortable-utils.js');

let passed = 0;
let failed = 0;

function assertEq(actual, expected, msg) {
    if (actual === expected) {
        passed++;
    } else {
        failed++;
        console.error(`[失败] ${msg}\n  期望: ${JSON.stringify(expected)}\n  实际: ${JSON.stringify(actual)}`);
    }
}

function assertSign(value, expectedSign, msg) {
    const actualSign = value > 0 ? 1 : value < 0 ? -1 : 0;
    if (actualSign === expectedSign) {
        passed++;
    } else {
        failed++;
        console.error(`[失败] ${msg}\n  期望符号: ${expectedSign}\n  实际: ${value}`);
    }
}

// ============ parseSortableNumber ============
console.log('--- parseSortableNumber ---');

assertEq(SortableUtils.parseSortableNumber(123), 123, '数字直接返回');
assertEq(SortableUtils.parseSortableNumber(-1.5), -1.5, '负数返回');
assertEq(SortableUtils.parseSortableNumber('¥100.00'), 100, '货币前缀剥离');
assertEq(SortableUtils.parseSortableNumber('¥9.00'), 9, '货币前缀个位数');
assertEq(SortableUtils.parseSortableNumber('¥1,234.50'), 1234.5, '千分位逗号剥离');
assertEq(SortableUtils.parseSortableNumber('$50'), 50, '美元符号剥离');
assertEq(SortableUtils.parseSortableNumber('12.00%'), 12, '尾部百分号剥离');
assertEq(SortableUtils.parseSortableNumber('-5%'), -5, '负数百分号');
assertEq(SortableUtils.parseSortableNumber('123'), 123, '纯数字字符串');
assertEq(SortableUtils.parseSortableNumber('0123A'), null, '字母数字混排不解析（OE号保护）');
assertEq(SortableUtils.parseSortableNumber('10A5'), null, '字母夹数字不解析');
assertEq(SortableUtils.parseSortableNumber(''), null, '空字符串返回 null');
assertEq(SortableUtils.parseSortableNumber('   '), null, '空白字符串返回 null');
assertEq(SortableUtils.parseSortableNumber(null), null, 'null 返回 null');
assertEq(SortableUtils.parseSortableNumber(undefined), null, 'undefined 返回 null');
assertEq(SortableUtils.parseSortableNumber('abc'), null, '纯文本返回 null');
assertEq(SortableUtils.parseSortableNumber('2026-01-02'), null, '日期字符串不按数值解析');
assertEq(SortableUtils.parseSortableNumber(NaN), null, 'NaN 返回 null');

// ============ parseSortableDate ============
console.log('--- parseSortableDate ---');

const ts = SortableUtils.parseSortableDate('2026-01-02 03:04:05');
assertEq(ts, Date.UTC(2026, 0, 2, 3, 4, 5), 'SQL 风格日期解析');
assertEq(SortableUtils.parseSortableDate('2026-01-02T03:04:05'), Date.UTC(2026, 0, 2, 3, 4, 5), 'ISO T 分隔解析');
assertEq(SortableUtils.parseSortableDate('2026-01-02T03:04:05.123Z'), Date.UTC(2026, 0, 2, 3, 4, 5), '含毫秒与时区');
assertEq(SortableUtils.parseSortableDate('2026-01-02'), null, '纯日期（无时间）不解析，走字符串路径');
assertEq(SortableUtils.parseSortableDate(12345), null, '非字符串返回 null');
assertEq(SortableUtils.parseSortableDate('abc'), null, '文本返回 null');

// ============ compareValues：方向与三条比较路径 ============
console.log('--- compareValues ---');

const cv = SortableUtils.compareValues;

// 数值路径（¥ 前缀金额，回归询价模块修复场景）
assertSign(cv('¥100.00', '¥9.00', 'asc'), 1, '升序：100 应排在 9 之后');
assertSign(cv('¥100.00', '¥9.00', 'desc'), -1, '降序：100 应排在 9 之前');
assertSign(cv('¥5', '5', 'asc'), 0, '¥5 与 5 等值');

// 字符串路径
assertSign(cv('abc', 'abd', 'asc'), -1, '文本升序');
assertSign(cv('abc', 'abd', 'desc'), 1, '文本降序');
assertSign(cv('0123A', '99B', 'asc'), -1, 'OE 混排按字符串比较');

// 日期路径
assertSign(cv('2026-01-02 03:04:05', '2026-01-03 03:04:05', 'asc'), -1, '日期升序');
assertSign(cv('2026-01-02 03:04:05', '2026-01-03 03:04:05', 'desc'), 1, '日期降序');

// null/undefined 归一为空串
assertSign(cv(null, 'a', 'asc'), -1, 'null 归一后小于任意文本');
assertSign(cv(undefined, null, 'asc'), 0, 'null 与 undefined 等值');
assertSign(cv('', null, 'asc'), 0, '空串与 null 等值');

// 混合类型：一侧可解析一侧不可 → 走字符串
assertSign(cv('¥100', 'abc', 'asc'), 1, '数值与文本混排按字符串（数字字符 < 字母）');

// desc 恒等于 -asc（方向对称性）
assertSign(cv('¥9.00', '¥100.00', 'desc'), 1, 'desc 与 asc 结果互反');

// ============ 端到端：模拟 sortLocalData 对金额列排序 ============
console.log('--- 端到端排序 ---');

const rows = [
    { price: '¥100.00' },
    { price: '¥9.00' },
    { price: '¥1,250.00' },
    { price: '¥75.50' }
];

const asc = rows.slice().sort((a, b) => cv(a.price, b.price, 'asc')).map(r => r.price);
assertEq(asc.join('|'), '¥9.00|¥75.50|¥100.00|¥1,250.00', '升序整体顺序正确');

const desc = rows.slice().sort((a, b) => cv(a.price, b.price, 'desc')).map(r => r.price);
assertEq(desc.join('|'), '¥1,250.00|¥100.00|¥75.50|¥9.00', '降序整体顺序正确');

const texts = [{ v: '博世' }, { v: '大众' }, { v: '法雷奥' }];
const textSorted = texts.slice().sort((a, b) => cv(a.v, b.v, 'asc')).map(r => r.v);
assertEq(textSorted.join('|'), '博世|大众|法雷奥', '文本列排序正确');

// ============ 结果 ============
console.log(`\n通过: ${passed}, 失败: ${failed}`);
process.exit(failed > 0 ? 1 : 0);
