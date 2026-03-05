/**
 * 表格单元格选择工具函数
 */

// 将单个DOM元素转换为标准对象格式
function convertSingleDomCellToObject(domCell) {
    // 尝试获取行和列信息
    let row = 0;
    let col = 0;
    
    // 获取行号
    const tr = domCell.closest('tr[data-index]');
    if (tr) {
        row = parseInt(tr.getAttribute('data-index'), 10);
    }
    
    // 获取列号
    const currentTd = domCell.closest('td');
    if (currentTd && currentTd.parentNode) {
        col = Array.from(currentTd.parentNode.children).indexOf(currentTd);
    }
    
    return {
        text: domCell.innerText.trim(),
        row: row,
        col: col
    };
}

// 统一处理不同类型的单元格数据
function normalizeCellData(selectedCells) {
    if (!selectedCells || selectedCells.length === 0) {
        return [];
    }
    
    // 检查是否已经是标准化的 {text, row, col} 格式
    if (selectedCells[0] && typeof selectedCells[0] === 'object' && 
        selectedCells[0].hasOwnProperty('text') && 
        selectedCells[0].hasOwnProperty('row') && 
        selectedCells[0].hasOwnProperty('col')) {
        return selectedCells;
    }
    
    // 检查是否是DOM元素数组
    if (selectedCells[0] instanceof Element) {
        return convertDomCellsToObjects(selectedCells);
    }
    
    // 如果是其他格式，尝试提取文本
    return selectedCells.map(item => {
        if (typeof item === 'object' && item.hasOwnProperty('text')) {
            return {
                text: item.text || '',
                row: item.row || 0,
                col: item.col || 0
            };
        } else if (item instanceof Element) {
            return convertSingleDomCellToObject(item);
        } else {
            return {
                text: String(item || ''),
                row: 0,
                col: 0
            };
        }
    });
}

// 将DOM元素转换为标准对象格式
function convertDomCellsToObjects(domCells) {
    return domCells.map(convertSingleDomCellToObject);
}

// 生成复制用的文本（行列对齐）
function generateCopyText(selectedCells) {
    console.log('generateCopyText被调用，选中的单元格数量:', selectedCells.length);

    if (!selectedCells || selectedCells.length === 0) {
        console.log('没有选中任何单元格');
        return '';
    }

    // 统一处理不同类型的输入数据
    const normalizedCells = selectedCells.map(item => {
        if (item instanceof Element) {
            // 如果是DOM元素，转换为对象
            return convertSingleDomCellToObject(item);
        } else if (typeof item === 'object' && item.text !== undefined) {
            // 如果已经是对象格式，直接返回
            return item;
        } else {
            // 其他情况，返回默认值
            return { text: String(item || ''), row: 0, col: 0 };
        }
    });

    // 按行分组
    const rowsMap = new Map();
    normalizedCells.forEach(item => {
        if (!rowsMap.has(item.row)) rowsMap.set(item.row, []);
        rowsMap.get(item.row).push({ col: item.col, text: item.text });
    });

    // 对每行按列排序，并填充空单元格
    const sortedRows = Array.from(rowsMap.entries())
        .sort((a, b) => a[0] - b[0])
        .map(([rowIndex, cells]) => {
            cells.sort((a, b) => a.col - b.col);
            const minCol = Math.min(...cells.map(c => c.col));
            const maxCol = Math.max(...cells.map(c => c.col));
            const row = [];
            for (let col = minCol; col <= maxCol; col++) {
                const found = cells.find(c => c.col === col);
                row.push(found ? found.text : '');
            }
            return row.join('\t');
        });

    const result = sortedRows.join('\n');
    console.log('最终生成的复制文本:', result);
    return result;
}

// 检查元素是否可见
function isElementVisible(element) {
    const style = window.getComputedStyle(element);
    return style.display !== 'none' && 
           style.visibility !== 'hidden' && 
           style.opacity !== '0';
}

// 更新选中单元格
function updateSelection(cells, selRect, tableBox, selectedCellsRef, debug = false) {
    if (debug) {
        console.log('开始更新选中状态，单元格数量:', cells.length);
        console.log('选择区域:', selRect);
        console.log('表格盒元素:', tableBox);
    }
    
    clearSelection(tableBox.id || '', debug);
    
    const matched = [];
    let totalCells = 0;
    let intersectingCells = 0;
    
    cells.forEach(cell => {
        totalCells++;
        const cRect = getCellRect(cell, tableBox.parentElement || tableBox);
        
        if (intersects(cRect, selRect)) {
            intersectingCells++;
            
            // 只给cell添加样式，不给td添加（与index.html中的一致）
            cell.classList.add('cell-excel-selected');
            
            if (debug) {
                console.log('渲染选中样式到单元格:', cell);
                console.log('单元格文本内容:', `"${cell.innerText.trim()}"`);
                console.log('单元格是否包含cell-excel-selected类:', cell.classList.contains('cell-excel-selected'));
            }
            
            // 转换单元格数据并添加到匹配列表
            const cellData = convertSingleDomCellToObject(cell);
            matched.push(cellData);
        } 
    });
    
    if (debug) {
        console.log(`总共扫描${totalCells}个单元格，其中${intersectingCells}个被选中`);
        console.log('最终匹配的单元格数据:', matched);
        
        // 检查是否有选中的元素
        const selectedElements = tableBox.querySelectorAll('.cell-excel-selected');
        console.log('当前页面中选中的元素数量:', selectedElements.length);
        if (selectedElements.length > 0) {
            console.log('第一个选中元素:', selectedElements[0]);
            console.log('第一个选中元素的computed styles:', window.getComputedStyle(selectedElements[0]));
        } else {
            console.log('没有找到选中的元素！');
        }
        
        // 额外检查整个表格区域的选中元素
        const allSelected = document.querySelectorAll('.cell-excel-selected');
        console.log('页面中所有带cell-excel-selected类的元素数量:', allSelected.length);
    }

    if (selectedCellsRef) {
        // 清空数组并添加新数据
        selectedCellsRef.splice(0, selectedCellsRef.length);
        matched.forEach(item => selectedCellsRef.push(item));
        
        if (debug) {
            console.log('更新selectedCellsRef后的内容:', selectedCellsRef);
            if (selectedCellsRef.length > 0) {
                console.log('selectedCellsRef第一个元素类型:', typeof selectedCellsRef[0], selectedCellsRef[0]);
            }
        }
    }
    
    if (debug) {
        console.log('最终选中的单元格:', selectedCellsRef ? selectedCellsRef.length : 0);
        if (selectedCellsRef && selectedCellsRef.length > 0) {
            console.log('selectedCellsRef内容示例:', selectedCellsRef[0]);
        }
    }
}

// 辅助函数：查找最近的表格祖先元素
function findTableAncestor(element) {
    let current = element;
    while (current && current.tagName !== 'BODY' && current.tagName !== 'HTML') {
        if (current.tagName === 'TABLE' || current.classList?.contains('layui-table-view')) {
            return current;
        }
        current = current.parentElement;
    }
    return null;
}

// 清除选中状态
function clearSelection(tableView, debug = false) {
    if (debug) {
        console.log('清除选中状态，表格ID:', tableView);
    }
    
    if (!tableView) {
        const elements = document.querySelectorAll('.cell-excel-selected');
        if (debug) {
            console.log('清除所有表格的选中状态，找到元素数量:', elements.length);
        }
        elements.forEach(el => {
            el.classList.remove('cell-excel-selected');
        });
        return;
    }
    
    // 查找特定表格视图内的选中单元格
    const tableContainer = document.querySelector(`#${tableView} + .layui-table-view`) || 
                          document.querySelector('.layui-table-view');
    if (tableContainer) {
        const elements = tableContainer.querySelectorAll('td.cell-excel-selected, .layui-table-cell.cell-excel-selected');
        if (debug) {
            console.log('清除表格', tableView, '的选中状态，找到元素数量:', elements.length);
        }
        
        elements.forEach(el => {
            el.classList.remove('cell-excel-selected');
        });
    } else {
        const elements = document.querySelectorAll('.cell-excel-selected');
        if (debug) {
            console.log('未找到特定表格，清除所有选中状态，找到元素数量:', elements.length);
        }
        elements.forEach(el => {
            el.classList.remove('cell-excel-selected');
        });
    }
}

// 获取单元格矩形
function getCellRect(cell, tableContainer) {
    const cellRect = cell.getBoundingClientRect();
    const containerRect = tableContainer.getBoundingClientRect();
    
    // 计算相对于表格容器的坐标
    return {
        left: cellRect.left - containerRect.left,
        top: cellRect.top - containerRect.top,
        right: cellRect.right - containerRect.left,
        bottom: cellRect.bottom - containerRect.top
    };
}

// 判断两个矩形是否相交 - 优化算法
function intersects(rect1, rect2) {
    // 使用更精确的相交判断，考虑边界情况
    // 为了处理边缘情况，稍微扩展选择区域
    const tolerance = 1; // 1像素的容差
    
    return !(rect1.right < rect2.left - tolerance || 
             rect1.bottom < rect2.top - tolerance || 
             rect1.left > rect2.right + tolerance || 
             rect1.top > rect2.bottom + tolerance);
}

// 复制文本到剪贴板的工具函数
function copyTextToClipboard(text, callback) {
    console.log('准备复制文本:', text);
    
    if (navigator.clipboard && window.isSecureContext) {
        // 使用现代API
        navigator.clipboard.writeText(text).then(function() {
            console.log('使用navigator.clipboard复制成功:', text);
            if (callback) callback(true);
        }).catch(function(error) {
            console.error('使用navigator.clipboard复制失败:', error);
            // 回退到旧方法
            fallbackCopyTextToClipboard(text, callback);
        });
    } else {
        // 回退到旧方法
        fallbackCopyTextToClipboard(text, callback);
    }
}

// 旧的复制文本到剪贴板的方法
function fallbackCopyTextToClipboard(text, callback) {
    console.log('使用fallback方法复制文本');
    
    const textArea = document.createElement("textarea");
    textArea.value = text;
    textArea.style.top = "0";
    textArea.style.left = "0";
    textArea.style.position = "fixed";
    textArea.style.opacity = "0";
    textArea.style.zIndex = "-1000"; // 确保在最底层
    
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    
    try {
        const successful = document.execCommand('copy');
        console.log('使用document.execCommand复制' + (successful ? '成功' : '失败'));
        if (callback) callback(successful);
    } catch (err) {
        console.error('使用document.execCommand复制失败:', err);
        if (callback) callback(false);
    }
    
    document.body.removeChild(textArea);
}

// 获取相对于表格的坐标
function getTableCoordinates(event, tableView) {
    const tableBox = tableView.querySelector('.layui-table-box') || tableView;
    const boxRect = tableBox.getBoundingClientRect();
    
    // 计算相对于表格容器的坐标，考虑滚动位置
    const x = event.clientX - boxRect.left + tableBox.scrollLeft;
    const y = event.clientY - boxRect.top + tableBox.scrollTop;
    
    return {
        x: x,
        y: y
    };
}