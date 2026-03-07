/**
 * Excel风格的单元格拖拽选择功能
 * 基于统一的 TableCellSelector 模块的轻量级封装
 */

/**
 * 初始化单元格选择功能
 * @param {string} tableId - 表格ID
 * @param {Object} table - layui table 实例
 * @param {Object} layer - layui layer 实例
 * @param {Object} options - 配置选项
 */
function initExcelCellSelection(tableId, table, layer, options = {}) {
    if (!tableId) {
        console.warn('初始化单元格选择功能失败：缺少表格ID');
        return;
    }

    // 检查 TableCellSelector 是否已加载
    if (typeof TableCellSelector === 'undefined') {
        console.warn('TableCellSelector 模块未加载，请先引入 table-cell-selector.js');
        return;
    }

    // 默认配置
    const defaultOptions = {
        enableCopy: true,
        enableAddToCart: false,
        onAddToCart: null
    };

    const opts = Object.assign({}, defaultOptions, options);

    // 调用统一模块初始化
    TableCellSelector.init(tableId, {
        enableCopy: opts.enableCopy,
        enableAddToCart: opts.enableAddToCart,
        onAddToCart: opts.onAddToCart ? function(selectedRows, tableId) {
            opts.onAddToCart(selectedRows, tableId, table, layer);
        } : null
    });
}

/**
 * 初始化购物车表格的单元格选择功能
 * @param {string} tableId - 表格ID
 * @param {Object} table - layui table 实例
 * @param {Object} layer - layui layer 实例
 * @param {Object} options - 配置选项
 */
function initExcelCellSelectionForCart(tableId, table, layer, options = {}) {
    if (tableId !== 'cartTable') return;

    const opts = Object.assign({
        enableCopy: true,
        enableRemoveFromCart: true
    }, options);

    TableCellSelector.init(tableId, {
        enableCopy: opts.enableCopy,
        enableRemoveFromCart: opts.enableRemoveFromCart,
        onRemoveFromCart: opts.onRemoveFromCart ? function(selectedRows, tableId) {
            opts.onRemoveFromCart(selectedRows, tableId, table, layer);
        } : null
    });
}

/**
 * 初始化日期查询表格的单元格选择功能
 * @param {string} tableId - 表格ID
 * @param {Object} table - layui table 实例
 * @param {Object} layer - layui layer 实例
 * @param {Object} options - 配置选项
 */
function initExcelCellSelectionForDateQuery(tableId, table, layer, options = {}) {
    if (tableId !== 'dateQueryTable') return;
    initExcelCellSelection(tableId, table, layer, options);
}

/**
 * 初始化搜索CRM表格的单元格选择功能
 * @param {string} tableId - 表格ID
 * @param {Object} table - layui table 实例
 * @param {Object} layer - layui layer 实例
 * @param {Object} options - 配置选项
 */
function initExcelCellSelectionForSearchCrm(tableId, table, layer, options = {}) {
    if (tableId !== 'searchInCrmTable') return;
    initExcelCellSelection(tableId, table, layer, options);
}
