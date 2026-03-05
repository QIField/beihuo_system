/**
 * Excel风格的单元格拖拽选择功能
 */

// 初始化单元格选择功能
function initExcelCellSelection(tableId, table, layer, options = {}) {
    // 验证参数
    if (!tableId) {
        console.warn('初始化单元格选择功能失败：缺少表格ID');
        return;
    }

    // 获取表格视图元素
    const tableView = document.querySelector('#' + tableId + ' + .layui-table-view');
    if (!tableView) {
        console.warn(`未找到表格视图元素: #${tableId} + .layui-table-view`);
        return;
    }
    
    // 检查是否已经初始化过
    if (tableView.__hasCellSel__) {
        // 清除之前的状态和事件监听器
        if (tableView.__keyHandler) {
            document.removeEventListener('keydown', tableView.__keyHandler);
            tableView.__keyHandler = null;
        }
        // 清除选中状态
        const oldSelectedCells = tableView.querySelectorAll('.cell-excel-selected');
        oldSelectedCells.forEach(el => el.classList.remove('cell-excel-selected'));
    }
    
    // 设置新的初始化标记
    tableView.__hasCellSel__ = true;

    // 获取表格盒子和主体元素
    const tableBox = tableView.querySelector('.layui-table-box');
    const tableBody = tableView.querySelector('.layui-table-body');
    
    if (!tableBox || !tableBody) {
        console.warn(`表格 ${tableId} 中未找到合适的表格盒子元素`);
        return;
    }

    // 注入样式
    if (!document.getElementById('excel-cell-sel-style')) {
        const style = document.createElement('style');
        style.id = 'excel-cell-sel-style';
        style.textContent = `
            .cell-excel-selected {
                background-color: #d0e8ff !important;
                position: relative;
            }
            .cell-excel-selected::after {
                content: '';
                position: absolute;
                top: 0; left: 0; right: 0; bottom: 0;
                border: 2px solid #1e90ff;
                pointer-events: none;
                box-sizing: border-box;
            }
            /* 确保空白单元格也能显示选中效果 */
            .layui-table-cell:empty::before {
                content: "\\200b"; /* 零宽空格，确保即使单元格为空也有内容 */
            }
            #drag-sel-rect {
                position: absolute;
                border: 1px dashed #1e90ff;
                background: rgba(30,144,255,0.1);
                z-index: 2000;  /* 调整z-index层级，用于拖拽选择框 */
                pointer-events: none;
                display: none;
            }
        `;
        document.head.appendChild(style);
    }

    let rectDiv = document.getElementById('drag-sel-rect');
    if (!rectDiv) {
        rectDiv = document.createElement('div');
        rectDiv.id = 'drag-sel-rect';
    }

    // 状态变量
    let isDragging = false;
    let selectedCells = [];
    let startX, startY;

    // 清除选中
    function clearSelection() {
        document.querySelectorAll('.cell-excel-selected').forEach(el => el.classList.remove('cell-excel-selected'));
        selectedCells = [];
    }

    // 获取单元格相对于 tableView 的坐标（考虑滚动）
    function getCellRect(cell) {
        const cellRect = cell.getBoundingClientRect();
        const viewRect = tableView.getBoundingClientRect();
        return {
            left: cellRect.left - viewRect.left + tableView.scrollLeft,
            top: cellRect.top - viewRect.top + tableView.scrollTop,
            right: cellRect.right - viewRect.left + tableView.scrollLeft,
            bottom: cellRect.bottom - viewRect.top + tableView.scrollTop,
            element: cell
        };
    }

    function intersects(a, b) {
        return !(b.left > a.right || b.right < a.left || b.top > a.bottom || b.bottom < a.top);
    }

    function updateSelection(selRect) {
        clearSelection();
        const cells = tableBox.querySelectorAll('.layui-table-cell');
        const matched = [];

        cells.forEach(cell => {
            const cRect = getCellRect(cell);
            if (intersects(cRect, selRect)) {
                // 仅对cell元素添加选中样式，不需要对td也添加（与index.html中的实现保持一致）
                cell.classList.add('cell-excel-selected');
                const tr = cell.closest('tr[data-index]');
                if (!tr) return;
                const rowIndex = parseInt(tr.getAttribute('data-index'), 10);
                const td = cell.closest('td');
                // 获取td在行中的索引
                const tds = Array.from(tr.cells); // 使用tr.cells获取所有单元格
                const colIndex = tds.indexOf(td);
                
                // 即使是空白单元格也要包含在选择中
                matched.push({
                    text: cell.innerText.trim(), // 保留原始文本，即使是空白
                    row: rowIndex,
                    col: colIndex
                });
            }
        });

        // 按照行和列排序，以确保顺序一致
        matched.sort((a, b) => {
            if (a.row === b.row) {
                return a.col - b.col;
            }
            return a.row - b.row;
        });

        selectedCells = matched;
    }

    function generateCopyText() {
        if (selectedCells.length === 0) return '';
        
        // 按照选中的实际位置来构建文本矩阵
        const minRow = Math.min(...selectedCells.map(cell => cell.row));
        const maxRow = Math.max(...selectedCells.map(cell => cell.row));
        const minCol = Math.min(...selectedCells.map(cell => cell.col));
        const maxCol = Math.max(...selectedCells.map(cell => cell.col));

        // 创建二维数组存储数据
        const matrix = Array(maxRow - minRow + 1).fill(null).map(() => 
            Array(maxCol - minCol + 1).fill('')
        );

        // 填充数据
        selectedCells.forEach(cell => {
            const rowIndex = cell.row - minRow;
            const colIndex = cell.col - minCol;
            matrix[rowIndex][colIndex] = cell.text;
        });

        // 转换为制表符分隔的字符串
        return matrix.map(row => row.join('\t')).join('\n');
    }

    function copyText(text) {
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(text).then(() => {
                if (layer) {
                    layer.msg('已复制选区内容', { icon: 1, time: 800 });
                } else {
                    alert('已复制选区内容');
                }
                // 自动清除选中
                clearSelection();
                selectedCells = [];
            }).catch(err => {
                console.error('Clipboard API 失败:', err);
                fallbackCopy(text);
            });
        } else {
            fallbackCopy(text);
        }
    }

    function fallbackCopy(text) {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.cssText = 'position:fixed;top:0;left:-9999px;opacity:0;';
        document.body.appendChild(ta);
        ta.select();
        try {
            if (document.execCommand('copy')) {
                if (layer) {
                    layer.msg('已复制到剪贴板', { icon: 1, time: 800 });
                } else {
                    alert('已复制到剪贴板');
                }
                // 自动清除选中
                clearSelection();
                selectedCells = [];
            } else {
                if (layer) {
                    layer.msg('复制失败', { icon: 2 });
                } else {
                    alert('复制失败');
                }
            }
        } catch (e) {
            console.error('execCommand 复制失败:', e);
            if (layer) {
                layer.msg('浏览器不支持复制', { icon: 2 });
            } else {
                alert('浏览器不支持复制');
            }
        }
        document.body.removeChild(ta);
    }

    // 坐标转换
    const viewRect = tableView.getBoundingClientRect();
    const offsetX = viewRect.left + window.pageXOffset - tableView.scrollLeft;
    const offsetY = viewRect.top + window.pageYOffset - tableView.scrollTop;

    function toTableCoord(clientX, clientY) {
        return {
            x: clientX - offsetX,
            y: clientY - offsetY
        };
    }

    // 鼠标事件
    tableBox.addEventListener('mousedown', function(e) {
        if (e.button !== 0 || e.target.closest('.layui-table-tool,.layui-table-header,.layui-table-total')) return;
        const pt = toTableCoord(e.clientX, e.clientY);
        isDragging = true;
        startX = pt.x;
        startY = pt.y;

        rectDiv.style.cssText = `
            position: absolute;
            left: ${startX}px;
            top: ${startY}px;
            width: 0;
            height: 0;
            display: block;
            border: 1px dashed #1e90ff;
            background: rgba(30,144,255,0.1);
            z-index: 9999;
            pointer-events: none;
        `;
        if (rectDiv.parentNode !== tableView) {
            tableView.appendChild(rectDiv);
        }
        clearSelection();
        e.preventDefault();
    });

    document.addEventListener('mousemove', function(e) {
        if (!isDragging) return;
        const pt = toTableCoord(e.clientX, e.clientY);
        let x = pt.x, y = pt.y;
        let w = x - startX, h = y - startY;
        let l = startX, t = startY;
        if (w < 0) { l = x; w = -w; }
        if (h < 0) { t = y; h = -h; }

        rectDiv.style.left = l + 'px';
        rectDiv.style.top = t + 'px';
        rectDiv.style.width = w + 'px';
        rectDiv.style.height = h + 'px';

        updateSelection({ left: l, top: t, right: l + w, bottom: t + h });
    });

    document.addEventListener('mouseup', function() {
        if (isDragging) {
            isDragging = false;
            rectDiv.style.display = 'none';
        }
    });

    // ====== 关键：绑定 Ctrl+C 复制功能 ======
    function handleKeydown(e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 'c' && selectedCells.length > 0) {
            e.preventDefault();
            copyText(generateCopyText());
        }
    }

    // 移除可能存在的旧监听器
    if (tableView.__keyHandler) {
        document.removeEventListener('keydown', tableView.__keyHandler);
    }
    tableView.__keyHandler = handleKeydown;
    document.addEventListener('keydown', handleKeydown);
    
    // 添加点击屏幕任意地方取消选中（排除表格区域）
    document.addEventListener('click', function(e) {
        // 检查点击的是否是表格内部元素或表格相关元素
        const isTableElement = tableView.contains(e.target) || 
                              e.target.closest('.layui-table-cell') ||
                              e.target.closest('.layui-table-view') ||
                              e.target.closest('.layui-table-box');
        
        if (!isTableElement) {
            // 如果点击的不是表格相关元素，则清除选中
            setTimeout(() => {
                clearSelection();
                selectedCells = [];
            }, 100); // 延迟执行，确保不影响表格内部的点击事件
        }
    });
}

// 初始化购物车表格的单元格选择功能（处理弹窗环境下的坐标偏移问题）
function initExcelCellSelectionForCart(tableId, table, layer, options = {}) {
    // 只对购物车表格生效
    if (tableId !== 'cartTable') return;
    
    // 使用通用初始化函数
    initExcelCellSelection(tableId, table, layer, options);

    // 获取表格视图元素
    const tableView = document.querySelector('#' + tableId + ' + .layui-table-view');
    if (!tableView) return;

    // 绑定Alt+Q快捷键（仅购物车表格）
    function handleKeydown(e) {
        if (e.altKey && e.key.toLowerCase() === 'q' && selectedCells.length > 0) {
            e.preventDefault();
            removeFromCartBySelection(selectedCells, tableId, layer);
        }
    }

    // 移除可能存在的旧监听器
    if (tableView.__cartKeyHandler) {
        document.removeEventListener('keydown', tableView.__cartKeyHandler);
    }
    tableView.__cartKeyHandler = handleKeydown;
    document.addEventListener('keydown', handleKeydown);
}

// 初始化日期查询表格的单元格选择功能
function initExcelCellSelectionForDateQuery(tableId, table, layer, options = {}) {
    // 只对日期查询表格生效
    if (tableId !== 'dateQueryTable') return;
    
    initExcelCellSelection(tableId, table, layer, options);
}

// 初始化搜索CRM表格的单元格选择功能
function initExcelCellSelectionForSearchCrm(tableId, table, layer, options = {}) {
    // 只对搜索CRM表格生效
    if (tableId !== 'searchInCrmTable') return;
    
    initExcelCellSelection(tableId, table, layer, options);
}