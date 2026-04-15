/**
 * AG Grid 工具函数库
 * 
 * 提供 AG Grid 的增强功能：
 * - 拖拽选择
 * - 双击复制
 * - 快捷键支持
 * - 分页大小选择
 * - 自适应列宽
 * 
 * 使用方法：
 * 1. 在页面中引入此文件
 * 2. 初始化 AG Grid 后调用相应函数
 * 
 * 示例：
 * const gridApi = new agGrid.Grid(gridDiv, gridOptions).api;
 * const gridColumnApi = gridOptions.columnApi;
 * 
 * initDragSelection(gridApi, gridColumnApi);
 * initDoubleClickCopy(gridApi, gridColumnApi);
 * initShortcuts(gridApi, copyCallback);
 * sizeColumnsToFit(gridApi);
 */

/**
 * 初始化拖拽选择功能
 * 
 * 功能：按住鼠标拖拽批量选择单元格
 * 用法：initDragSelection(gridApi, gridColumnApi)
 * 
 * @param {Object} gridApi - AG Grid API 实例
 * @param {Object} gridColumnApi - AG Grid Column API 实例
 */
function initDragSelection(gridApi, gridColumnApi) {
    const gridDiv = document.querySelector('.ag-theme-alpine');
    if (!gridDiv) {
        console.warn('[拖拽选择] 未找到 AG Grid 容器');
        return;
    }
    
    let isDragging = false;
    let startRowIndex = -1;
    let startColIndex = -1;
    
    // 阻止默认的文本选择行为
    gridDiv.addEventListener('selectstart', function(e) {
        if (isDragging) {
            e.preventDefault();
            return false;
        }
    });
    
    // 监听 mousedown 事件
    gridDiv.addEventListener('mousedown', function(e) {
        // 只处理左键点击
        if (e.button !== 0) return;
        
        // 如果点击的是复选框或输入框，不启动拖拽
        if (e.target.closest('input[type="checkbox"]') || 
            e.target.classList.contains('ag-checkbox-input') ||
            e.target.classList.contains('ag-input-field-input')) {
            return;
        }
        
        // 检查是否点击在单元格上
        const cellElement = e.target.closest('.ag-cell');
        if (!cellElement) return;
        
        // 获取行元素
        const rowElement = cellElement.closest('.ag-row');
        if (!rowElement) return;
        
        // 获取行ID
        const rowId = rowElement.getAttribute('row-id');
        if (rowId === null) return;
        
        // 获取行节点
        const rowNode = gridApi.getRowNode(rowId);
        if (!rowNode) return;
        
        // 获取列信息
        const colId = cellElement.getAttribute('col-id');
        const allColumns = gridColumnApi.getAllDisplayedColumns();
        const colIndex = allColumns.findIndex(col => col.getColId() === colId);
        
        // 如果不是按住 Ctrl 或 Shift，开始新的选择
        if (!e.ctrlKey && !e.shiftKey) {
            clearAllCellHighlights(gridDiv);
            
            isDragging = true;
            startRowIndex = rowNode.rowIndex;
            startColIndex = colIndex;
            
            // 高亮起始单元格
            highlightCell(cellElement);
        }
    });
    
    // 监听 mousemove 事件
    gridDiv.addEventListener('mousemove', function(e) {
        if (!isDragging) return;
        
        const cellElement = e.target.closest('.ag-cell');
        if (!cellElement) return;
        
        const rowElement = cellElement.closest('.ag-row');
        if (!rowElement) return;
        
        const rowId = rowElement.getAttribute('row-id');
        if (rowId === null) return;
        
        const rowNode = gridApi.getRowNode(rowId);
        if (!rowNode) return;
        
        const currentRowIndex = rowNode.rowIndex;
        const colId = cellElement.getAttribute('col-id');
        const allColumns = gridColumnApi.getAllDisplayedColumns();
        const currentColIndex = allColumns.findIndex(col => col.getColId() === colId);
        
        // 清除之前的高亮
        clearAllCellHighlights(gridDiv);
        
        // 计算选择范围
        const minRow = Math.min(startRowIndex, currentRowIndex);
        const maxRow = Math.max(startRowIndex, currentRowIndex);
        const minCol = Math.min(startColIndex, currentColIndex);
        const maxCol = Math.max(startColIndex, currentColIndex);
        
        // 高亮范围内的所有单元格
        for (let rowIdx = minRow; rowIdx <= maxRow; rowIdx++) {
            for (let colIdx = minCol; colIdx <= maxCol; colIdx++) {
                const cell = getCellByPosition(gridDiv, rowIdx, colIdx);
                if (cell) {
                    highlightCell(cell);
                }
            }
        }
    });
    
    // 监听 mouseup 事件
    document.addEventListener('mouseup', function(e) {
        if (!isDragging) return;
        
        isDragging = false;
        
        // 获取选中的单元格数据
        const highlightedCells = gridDiv.querySelectorAll('.ag-cell.ag-grid-cell-highlighted');
        if (highlightedCells.length > 0) {
            console.log(`[拖拽选择] 选中了 ${highlightedCells.length} 个单元格`);
        }
    });
    
    console.log('[拖拽选择] 初始化完成');
}

/**
 * 高亮单元格
 * @param {HTMLElement} cell - 单元格元素
 */
function highlightCell(cell) {
    cell.classList.add('ag-grid-cell-highlighted');
    cell.style.backgroundColor = '#e6f7ff';
}

/**
 * 清除所有单元格高亮
 * @param {HTMLElement} gridDiv - Grid 容器元素
 */
function clearAllCellHighlights(gridDiv) {
    const highlightedCells = gridDiv.querySelectorAll('.ag-cell.ag-grid-cell-highlighted');
    highlightedCells.forEach(cell => {
        cell.classList.remove('ag-grid-cell-highlighted');
        cell.style.backgroundColor = '';
    });
}

/**
 * 根据位置获取单元格
 * @param {HTMLElement} gridDiv - Grid 容器元素
 * @param {number} rowIndex - 行索引
 * @param {number} colIndex - 列索引
 * @returns {HTMLElement|null} - 单元格元素
 */
function getCellByPosition(gridDiv, rowIndex, colIndex) {
    const row = gridDiv.querySelector(`.ag-row[row-index="${rowIndex}"]`);
    if (!row) return null;
    
    const cells = row.querySelectorAll('.ag-cell');
    return cells[colIndex] || null;
}

/**
 * 初始化双击复制功能
 * 
 * 功能：双击单元格复制内容到剪贴板
 * 用法：initDoubleClickCopy(gridApi, gridColumnApi)
 * 
 * @param {Object} gridApi - AG Grid API 实例
 * @param {Object} gridColumnApi - AG Grid Column API 实例
 */
function initDoubleClickCopy(gridApi, gridColumnApi) {
    const gridDiv = document.querySelector('.ag-theme-alpine');
    if (!gridDiv) {
        console.warn('[双击复制] 未找到 AG Grid 容器');
        return;
    }
    
    gridDiv.addEventListener('dblclick', function(e) {
        // 获取所有高亮的单元格
        const highlightedCells = gridDiv.querySelectorAll('.ag-cell.ag-grid-cell-highlighted');
        
        // 只有当有且只有一个单元格被选中时才生效
        if (highlightedCells.length !== 1) {
            return;
        }
        
        const cell = highlightedCells[0];
        const rowElement = cell.closest('.ag-row');
        const colId = cell.getAttribute('col-id');
        
        if (!rowElement || !colId) return;
        
        const rowId = rowElement.getAttribute('row-id');
        const rowNode = gridApi.getRowNode(rowId);
        
        if (!rowNode) return;
        
        // 获取单元格的值
        const column = gridColumnApi.getColumn(colId);
        if (!column) return;
        
        const colDef = column.getColDef();
        let value = '';
        
        if (colDef.valueGetter) {
            value = colDef.valueGetter({ node: rowNode, data: rowNode.data });
        } else if (colDef.field) {
            value = rowNode.data[colDef.field] || '';
        }
        
        // 复制到剪贴板
        copyToClipboard(String(value));
    });
    
    console.log('[双击复制] 初始化完成');
}

/**
 * 复制文本到剪贴板
 * @param {string} text - 要复制的文本
 */
function copyToClipboard(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(function() {
            showToast('已复制: ' + text.substring(0, 20) + (text.length > 20 ? '...' : ''));
        }).catch(function(err) {
            fallbackCopyText(text);
        });
    } else {
        fallbackCopyText(text);
    }
}

/**
 * 兼容性复制文本
 * @param {string} text - 要复制的文本
 */
function fallbackCopyText(text) {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    
    try {
        const success = document.execCommand('copy');
        if (success) {
            showToast('已复制: ' + text.substring(0, 20) + (text.length > 20 ? '...' : ''));
        }
    } catch (err) {
        console.error('[复制] 复制失败:', err);
    }
    
    document.body.removeChild(textarea);
}

/**
 * 显示提示信息
 * @param {string} msg - 提示内容
 */
function showToast(msg) {
    if (typeof layui !== 'undefined' && layui.layer) {
        layui.layer.msg(msg, {icon: 1, time: 1500});
    } else {
        console.log('[提示]', msg);
    }
}

/**
 * 初始化快捷键功能
 * 
 * 功能：
 * - Ctrl+C: 复制选中单元格
 * - Ctrl+A: 全选
 * - Esc: 取消选择
 * 
 * 用法：initShortcuts(gridApi, copyCallback)
 * 
 * @param {Object} gridApi - AG Grid API 实例
 * @param {Function} copyCallback - 复制回调函数（可选）
 */
function initShortcuts(gridApi, copyCallback) {
    document.addEventListener('keydown', function(e) {
        // Ctrl+C 复制选中单元格
        if (e.ctrlKey && e.key.toLowerCase() === 'c') {
            e.preventDefault();
            
            const gridDiv = document.querySelector('.ag-theme-alpine');
            if (!gridDiv) return;
            
            const highlightedCells = gridDiv.querySelectorAll('.ag-cell.ag-grid-cell-highlighted');
            if (highlightedCells.length === 1) {
                const cell = highlightedCells[0];
                const value = cell.textContent.trim();
                copyToClipboard(value);
            } else if (copyCallback) {
                copyCallback();
            }
        }
        
        // Ctrl+A 全选
        if (e.ctrlKey && e.key.toLowerCase() === 'a') {
            e.preventDefault();
            gridApi.selectAll();
        }
        
        // Esc 取消选择
        if (e.key === 'Escape') {
            const gridDiv = document.querySelector('.ag-theme-alpine');
            if (gridDiv) {
                clearAllCellHighlights(gridDiv);
            }
            gridApi.deselectAll();
        }
    });
    
    console.log('[快捷键] 初始化完成');
}

/**
 * 初始化分页大小选择器
 * 
 * 功能：添加分页大小下拉选择框
 * 用法：initPageSizeSelector(gridApi, [50, 100, 200])
 * 
 * @param {Object} gridApi - AG Grid API 实例
 * @param {Array} sizes - 分页大小选项，默认 [10, 20, 50, 100]
 */
function initPageSizeSelector(gridApi, sizes) {
    sizes = sizes || [10, 20, 50, 100];
    
    // 查找分页容器
    const paginationPanel = document.querySelector('.ag-paging-panel');
    if (!paginationPanel) {
        console.warn('[分页选择器] 未找到分页面板');
        return;
    }
    
    // 创建选择器
    const select = document.createElement('select');
    select.className = 'ag-grid-page-size-selector';
    select.style.cssText = 'margin-left: 10px; padding: 2px 5px; border: 1px solid #ccc; border-radius: 3px;';
    
    sizes.forEach(size => {
        const option = document.createElement('option');
        option.value = size;
        option.textContent = size + '条/页';
        if (size === gridApi.paginationGetPageSize()) {
            option.selected = true;
        }
        select.appendChild(option);
    });
    
    // 监听变化
    select.addEventListener('change', function(e) {
        const newSize = parseInt(e.target.value);
        gridApi.paginationSetPageSize(newSize);
    });
    
    // 插入到分页面板
    paginationPanel.insertBefore(select, paginationPanel.firstChild);
    
    console.log('[分页选择器] 初始化完成');
}

/**
 * 自适应列宽
 * 
 * 功能：自动调整所有列宽以适应容器宽度
 * 用法：sizeColumnsToFit(gridApi)
 * 
 * @param {Object} gridApi - AG Grid API 实例
 */
function sizeColumnsToFit(gridApi) {
    if (gridApi && typeof gridApi.sizeColumnsToFit === 'function') {
        gridApi.sizeColumnsToFit();
        console.log('[自适应列宽] 已调整');
    }
}

/**
 * 导出数据到 CSV
 * 
 * 功能：将表格数据导出为 CSV 文件
 * 用法：exportToCsv(gridApi, filename)
 * 
 * @param {Object} gridApi - AG Grid API 实例
 * @param {string} filename - 文件名（不含扩展名）
 */
function exportToCsv(gridApi, filename) {
    filename = filename || 'export';
    
    const params = {
        fileName: filename + '.csv',
        allColumns: true,
        onlySelected: false
    };
    
    gridApi.exportDataAsCsv(params);
    console.log('[导出CSV] 已导出:', filename + '.csv');
}

// 导出到全局作用域
if (typeof window !== 'undefined') {
    window.initDragSelection = initDragSelection;
    window.initDoubleClickCopy = initDoubleClickCopy;
    window.initShortcuts = initShortcuts;
    window.initPageSizeSelector = initPageSizeSelector;
    window.sizeColumnsToFit = sizeColumnsToFit;
    window.exportToCsv = exportToCsv;
    window.copyToClipboard = copyToClipboard;
}
