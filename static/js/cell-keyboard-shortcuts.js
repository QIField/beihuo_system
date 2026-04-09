/**
 * 表格单元格键盘快捷键处理
 */

// 绑定键盘快捷键事件
function bindCellKeyboardShortcuts(tableView, selectedCells, tableId, table, layer, options = {}) {
    if (!tableView || !selectedCells) {
        console.warn('绑定键盘快捷键失败：缺少必要参数');
        return;
    }

    // 默认选项
    const defaultOptions = {
        enableCopy: true,      // 启用复制功能 (Ctrl+C)
        enableAddToCart: true, // 启用添加到购物车功能 (Alt+Q)
    };
    
    const opts = Object.assign(defaultOptions, options);

    // 定义键盘事件处理函数
    function handleKeydown(e) {
        console.log('检测到键盘事件:', e);
        console.log('当前选中单元格数量:', selectedCells.length);
        
        // Ctrl+C 或 Cmd+C 复制选中的单元格内容
        if (opts.enableCopy && (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'c' && selectedCells.length > 0) {
            console.log('执行复制操作');
            e.preventDefault();
            
            // 生成要复制的文本
            const text = generateCopyText(selectedCells);
            console.log('要复制的文本:', `"${text}"`);
            
            // 调用工具函数复制文本
            copyTextToClipboard(text, function(success) {
                if (success) {
                    if (layer) {
                        layer.msg('已复制选区内容', { icon: 1, time: 800 });
                    } else {
                        console.log('已复制选区内容');
                    }
                    
                    // 自动清除选中
                    clearSelection(tableId, true); // 开启调试
                    selectedCells.splice(0, selectedCells.length); // 清空数组
                    console.log('已清除选中状态');
                } else {
                    if (layer) {
                        layer.msg('复制失败', { icon: 2 });
                    } else {
                        console.error('复制失败');
                    }
                }
            });
        }
        
        // Alt+Q 添加到购物车或从购物车移除（根据表格类型决定）
        if (opts.enableAddToCart && e.altKey && e.key.toLowerCase() === 'q' && selectedCells.length > 0) {
            console.log('执行添加/移除购物车操作');
            e.preventDefault();
            
            if (tableId === 'cartTable') {
                // 如果是购物车表格，则移除选中商品
                console.log('从购物车移除商品');
                removeFromCartBySelection(selectedCells, tableId, layer);
            } else {
                // 如果是其他表格，则添加到购物车
                console.log('添加到购物车');
                addToCartFromSelection(selectedCells, tableId, layer, table);
            }
        }
    }

    // 移除可能存在的旧监听器
    if (tableView.__cellKeyHandler) {
        document.removeEventListener('keydown', tableView.__cellKeyHandler);
        console.log('移除旧的键盘事件监听器');
    }

    // 绑定新的键盘事件监听器
    tableView.__cellKeyHandler = handleKeydown;
    document.addEventListener('keydown', handleKeydown);
    console.log('绑定新的键盘事件监听器');
}

// 解绑键盘快捷键事件
function unbindCellKeyboardShortcuts(tableView) {
    if (tableView && tableView.__cellKeyHandler) {
        document.removeEventListener('keydown', tableView.__cellKeyHandler);
        delete tableView.__cellKeyHandler;
        console.log('解绑键盘快捷键事件');
    }
}