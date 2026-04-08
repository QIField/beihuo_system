/**
 * 统一表格单元格选择模块
 * 支持Excel风格的拖拽多选、Ctrl+C复制、Alt+Q添加到购物车等功能
 */

(function(global) {
    'use strict';

    // 全局状态管理
    const state = {
        // 存储每个表格的选中状态
        selections: new Map(),
        // 全局拖拽状态
        isDragging: false,
        dragStartX: 0,
        dragStartY: 0,
        // 选择框元素
        rectDiv: null,
        // 是否已初始化全局事件
        globalEventsBound: false,
        // 渲染帧请求ID，用于节流
        rafId: null,
        // 上一次的选择矩形，用于避免重复渲染
        lastSelRect: null
    };

    // 默认配置
    const defaultOptions = {
        enableCopy: true,        // 启用Ctrl+C复制
        enableAddToCart: false,  // 启用Alt+Q添加到购物车
        enableRemoveFromCart: false, // 启用Alt+Q从购物车移除
        onAddToCart: null,       // 添加到购物车回调
        onRemoveFromCart: null   // 从购物车移除回调
    };

    /**
     * 获取表格视图元素
     */
    function getTableView(tableId) {
        return document.querySelector('#' + tableId + ' + .layui-table-view');
    }

    /**
     * 获取或创建选择状态
     */
    function getSelection(tableId) {
        if (!state.selections.has(tableId)) {
            state.selections.set(tableId, {
                selectedCells: [],
                tableView: null,
                options: {}
            });
        }
        return state.selections.get(tableId);
    }

    /**
     * 清除指定表格的选中状态
     */
    function clearSelection(tableId) {
        const selection = state.selections.get(tableId);
        if (selection) {
            selection.selectedCells = [];
        }
        // 清除DOM上的选中样式
        const tableView = getTableView(tableId);
        if (tableView) {
            tableView.querySelectorAll('.cell-excel-selected').forEach(el => {
                el.classList.remove('cell-excel-selected');
            });
        }
    }

    /**
     * 注入样式（只执行一次）
     */
    function injectStyles() {
        if (document.getElementById('table-cell-selector-style')) return;

        const style = document.createElement('style');
        style.id = 'table-cell-selector-style';
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
            #table-cell-selector-rect {
                position: absolute;
                border: 1px dashed #1e90ff;
                background: rgba(30, 144, 255, 0.1);
                z-index: 9999;
                pointer-events: none;
                display: none;
            }
        `;
        document.head.appendChild(style);
    }

    /**
     * 获取或创建选择框元素
     */
    function getRectDiv() {
        if (!state.rectDiv) {
            state.rectDiv = document.createElement('div');
            state.rectDiv.id = 'table-cell-selector-rect';
            document.body.appendChild(state.rectDiv);
        }
        return state.rectDiv;
    }

    /**
     * 获取单元格相对于表格视图的坐标
     */
    function getCellRect(cell, tableView) {
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

    /**
     * 判断两个矩形是否相交
     */
    function intersects(a, b) {
        return !(b.left > a.right || b.right < a.left || b.top > a.bottom || b.bottom < a.top);
    }

    /**
     * 获取单元格相对于视口的坐标（用于购物车表格）
     */
    function getCellRectViewport(cell) {
        const cellRect = cell.getBoundingClientRect();
        return {
            left: cellRect.left,
            top: cellRect.top,
            right: cellRect.right,
            bottom: cellRect.bottom,
            element: cell
        };
    }

    /**
     * 获取可见区域内的单元格（性能优化：只处理视口内的单元格）
     */
    function getVisibleCells(tableBox, selRect) {
        // 扩展选择区域，包含一定的缓冲区域
        const buffer = 100;
        const extendedRect = {
            left: selRect.left - buffer,
            top: selRect.top - buffer,
            right: selRect.right + buffer,
            bottom: selRect.bottom + buffer
        };

        // 获取所有行
        const rows = tableBox.querySelectorAll('tr[data-index]');
        const visibleCells = [];

        rows.forEach(row => {
            const rowRect = row.getBoundingClientRect();
            // 快速检测行是否在扩展的选择区域内
            if (rowRect.bottom < extendedRect.top || rowRect.top > extendedRect.bottom) {
                return; // 跳过不在区域内的行
            }

            // 只处理该行内的单元格
            const cells = row.querySelectorAll('td');
            cells.forEach(cell => {
                const cellRect = cell.getBoundingClientRect();
                // 快速检测单元格是否在扩展的选择区域内
                if (cellRect.right >= extendedRect.left &&
                    cellRect.left <= extendedRect.right &&
                    cellRect.bottom >= extendedRect.top &&
                    cellRect.top <= extendedRect.bottom) {
                    visibleCells.push(cell);
                }
            });
        });

        return visibleCells;
    }

    /**
     * 批量添加选中样式（使用 DocumentFragment 减少重排）
     */
    function batchAddSelectionClass(cellsToSelect) {
        // 使用 requestAnimationFrame 确保在下一帧批量处理
        requestAnimationFrame(() => {
            cellsToSelect.forEach(td => {
                td.classList.add('cell-excel-selected');
                const cell = td.querySelector('.layui-table-cell');
                if (cell) {
                    cell.classList.add('cell-excel-selected');
                }
            });
        });
    }

    /**
     * 更新选择区域（性能优化版本）
     */
    function updateSelection(tableId, selRect) {
        // 检查选择区域是否变化足够大（避免微小移动导致重渲染）
        if (state.lastSelRect) {
            const threshold = 5; // 5px 阈值
            if (Math.abs(selRect.left - state.lastSelRect.left) < threshold &&
                Math.abs(selRect.top - state.lastSelRect.top) < threshold &&
                Math.abs(selRect.right - state.lastSelRect.right) < threshold &&
                Math.abs(selRect.bottom - state.lastSelRect.bottom) < threshold) {
                return; // 变化太小，跳过渲染
            }
        }
        state.lastSelRect = { ...selRect };

        // 取消之前的渲染请求
        if (state.rafId) {
            cancelAnimationFrame(state.rafId);
        }

        // 使用 requestAnimationFrame 节流渲染
        state.rafId = requestAnimationFrame(() => {
            clearSelection(tableId);
            const selection = getSelection(tableId);
            const tableView = getTableView(tableId);
            if (!tableView) return;

            const tableBox = tableView.querySelector('.layui-table-box');
            if (!tableBox) return;

            // 性能优化：只获取可见区域内的单元格
            const visibleCells = getVisibleCells(tableBox, selRect);
            const matched = [];
            const cellsToSelect = [];

            visibleCells.forEach(td => {
                const cRect = getCellRectViewport(td);
                const isIntersect = intersects(cRect, selRect);

                if (isIntersect) {
                    cellsToSelect.push(td);

                    const cell = td.querySelector('.layui-table-cell');
                    const tr = td.closest('tr[data-index]');
                    if (!tr) return;
                    const rowIndex = parseInt(tr.getAttribute('data-index'), 10);
                    const tds = Array.from(tr.cells);
                    const colIndex = tds.indexOf(td);
                    matched.push({
                        text: cell ? cell.innerText.trim() : '',
                        row: rowIndex,
                        col: colIndex
                    });
                }
            });

            // 批量添加样式
            batchAddSelectionClass(cellsToSelect);
            selection.selectedCells = matched;
        });
    }

    /**
     * 生成复制文本
     */
    function generateCopyText(selectedCells) {
        if (selectedCells.length === 0) return '';

        const minRow = Math.min(...selectedCells.map(c => c.row));
        const maxRow = Math.max(...selectedCells.map(c => c.row));
        const minCol = Math.min(...selectedCells.map(c => c.col));
        const maxCol = Math.max(...selectedCells.map(c => c.col));

        const matrix = Array(maxRow - minRow + 1).fill(null).map(() =>
            Array(maxCol - minCol + 1).fill('')
        );

        selectedCells.forEach(cell => {
            matrix[cell.row - minRow][cell.col - minCol] = cell.text;
        });

        return matrix.map(row => row.join('\t')).join('\n');
    }

    /**
     * 复制文本到剪贴板
     */
    function copyText(text, callback) {
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(text).then(() => {
                if (callback) callback(true);
            }).catch(() => {
                fallbackCopy(text, callback);
            });
        } else {
            fallbackCopy(text, callback);
        }
    }

    /**
     * 降级复制方案
     */
    function fallbackCopy(text, callback) {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.cssText = 'position:fixed;top:0;left:-9999px;opacity:0;';
        document.body.appendChild(ta);
        ta.select();
        try {
            const success = document.execCommand('copy');
            if (callback) callback(success);
        } catch (e) {
            if (callback) callback(false);
        }
        document.body.removeChild(ta);
    }

    /**
     * 从选中单元格获取行数据
     */
    function getSelectedRows(selectedCells, tableId) {
        const tableCache = layui.table.cache[tableId];
        if (!tableCache) return [];

        const processedRows = new Set();
        const selectedRows = [];

        selectedCells.forEach(cellData => {
            const rowIndex = cellData.row;
            if (!processedRows.has(rowIndex) && tableCache[rowIndex]) {
                selectedRows.push(tableCache[rowIndex]);
                processedRows.add(rowIndex);
            }
        });

        return selectedRows;
    }

    /**
     * 全局键盘事件处理
     */
    function handleGlobalKeydown(e) {
        // 查找当前有选中内容的表格
        let activeTableId = null;
        let activeSelection = null;

        for (const [tableId, selection] of state.selections) {
            if (selection.selectedCells.length > 0) {
                activeTableId = tableId;
                activeSelection = selection;
                break;
            }
        }

        if (!activeTableId || !activeSelection) return;

        const { selectedCells, options } = activeSelection;

        // Ctrl+C 复制
        if (options.enableCopy && (e.ctrlKey || e.metaKey) && e.key === 'c') {
            e.preventDefault();
            const text = generateCopyText(selectedCells);
            copyText(text, (success) => {
                if (layui.layer) {
                    layui.layer.msg(success ? '已复制选区内容' : '复制失败', {
                        icon: success ? 1 : 2,
                        time: 800
                    });
                }
                if (success) clearSelection(activeTableId);
            });
            return;
        }

        // Alt+Q 添加到购物车或从购物车移除
        if (e.altKey && e.key.toLowerCase() === 'q') {
            e.preventDefault();

            if (options.enableRemoveFromCart && options.onRemoveFromCart) {
                // 从购物车移除
                const selectedRows = getSelectedRows(selectedCells, activeTableId);
                options.onRemoveFromCart(selectedRows, activeTableId);
                clearSelection(activeTableId);
            } else if (options.enableAddToCart && options.onAddToCart) {
                // 添加到购物车
                const selectedRows = getSelectedRows(selectedCells, activeTableId);
                options.onAddToCart(selectedRows, activeTableId);
                clearSelection(activeTableId);
            }
        }
    }

    /**
     * 全局鼠标按下事件
     */
    function handleGlobalMouseDown(e) {
        if (e.button !== 0) return;

        // 查找点击的是哪个表格
        let targetTableId = null;
        let targetTableView = null;

        for (const [tableId, selection] of state.selections) {
            const tableView = getTableView(tableId);
            if (tableView && tableView.contains(e.target)) {
                targetTableId = tableId;
                targetTableView = tableView;
                break;
            }
        }

        if (!targetTableId || !targetTableView) return;

        // 检查是否点击在表格工具栏、表头、合计行或分页区域
        // 分页区域包含：页码按钮、到第几页输入框、确定按钮、每页条数选择器等
        if (e.target.closest('.layui-table-tool, .layui-table-header, .layui-table-total, .layui-table-page')) {
            return;
        }

        // 清除其他表格的选中状态
        for (const [tableId, selection] of state.selections) {
            if (tableId !== targetTableId && selection.selectedCells.length > 0) {
                clearSelection(tableId);
            }
        }

        // 开始拖拽
        state.isDragging = true;
        state.activeTableId = targetTableId;
        
        const viewRect = targetTableView.getBoundingClientRect();
        
        // 所有表格都使用相对于视口的坐标（简化逻辑）
        state.dragStartX = e.clientX;
        state.dragStartY = e.clientY;
        state.viewRect = viewRect;

        // 显示选择框
        const rectDiv = getRectDiv();
        rectDiv.style.cssText = `
            position: fixed;
            left: ${state.dragStartX}px;
            top: ${state.dragStartY}px;
            width: 0;
            height: 0;
            display: block;
            border: 1px dashed #1e90ff;
            background: rgba(30, 144, 255, 0.1);
            z-index: 99999;
            pointer-events: none;
        `;

        clearSelection(targetTableId);
        e.preventDefault();
    }

    /**
     * 全局鼠标移动事件
     */
    function handleGlobalMouseMove(e) {
        if (!state.isDragging) return;

        const activeTableId = state.activeTableId;
        if (!activeTableId) return;
        
        const activeTableView = getTableView(activeTableId);
        if (!activeTableView) return;

        // 使用视口坐标
        const currentX = e.clientX;
        const currentY = e.clientY;
        
        let w = currentX - state.dragStartX;
        let h = currentY - state.dragStartY;
        let l = state.dragStartX;
        let t = state.dragStartY;

        if (w < 0) { l = currentX; w = -w; }
        if (h < 0) { t = currentY; h = -h; }

        // 更新选择框位置
        const rectDiv = getRectDiv();
        rectDiv.style.left = l + 'px';
        rectDiv.style.top = t + 'px';
        rectDiv.style.width = w + 'px';
        rectDiv.style.height = h + 'px';

        // 更新选择区域
        updateSelection(activeTableId, { left: l, top: t, right: l + w, bottom: t + h });
    }

    /**
     * 全局鼠标抬起事件
     */
    function handleGlobalMouseUp() {
        if (state.isDragging) {
            state.isDragging = false;
            state.activeTableId = null;
            state.lastSelRect = null; // 重置选择矩形缓存
            if (state.rafId) {
                cancelAnimationFrame(state.rafId);
                state.rafId = null;
            }
            if (state.rectDiv) {
                state.rectDiv.style.display = 'none';
            }
        }
    }

    /**
     * 全局点击事件（清除选中）
     */
    function handleGlobalClick(e) {
        // 检查是否点击在表格外部
        let clickedInTable = false;

        for (const [tableId, selection] of state.selections) {
            const tableView = getTableView(tableId);
            if (tableView && (
                tableView.contains(e.target) ||
                e.target.closest('.layui-table-cell') ||
                e.target.closest('.layui-table-view')
            )) {
                clickedInTable = true;
                break;
            }
        }

        if (!clickedInTable) {
            // 清除所有表格的选中状态
            for (const [tableId, selection] of state.selections) {
                if (selection.selectedCells.length > 0) {
                    clearSelection(tableId);
                }
            }
        }
    }

    /**
     * 处理单元格双击事件 - 复制单元格内容
     */
    function handleCellDblClick(e) {
        // 获取双击的单元格元素
        const cell = e.target.closest('.layui-table-cell');
        if (!cell) return;

        // 获取单元格文本内容
        const text = cell.innerText.trim();
        if (!text) return;

        // 复制到剪贴板
        copyText(text, (success) => {
            if (layui.layer) {
                const displayText = text.length > 30 ? text.substring(0, 30) + '...' : text;
                layui.layer.msg(success ? '已复制: ' + displayText : '复制失败', {
                    icon: success ? 1 : 2,
                    time: 1200,
                    offset: 't'
                });
            }
        });
    }

    /**
     * 为指定表格绑定双击事件
     */
    function bindDblClickEvent(tableId) {
        const tableView = getTableView(tableId);
        if (!tableView) return;

        // 使用事件委托监听双击事件
        tableView.addEventListener('dblclick', handleCellDblClick);
    }

    /**
     * 绑定全局事件（只执行一次）
     */
    function bindGlobalEvents() {
        if (state.globalEventsBound) return;

        document.addEventListener('keydown', handleGlobalKeydown);
        document.addEventListener('mousedown', handleGlobalMouseDown);
        document.addEventListener('mousemove', handleGlobalMouseMove);
        document.addEventListener('mouseup', handleGlobalMouseUp);
        document.addEventListener('click', handleGlobalClick);

        state.globalEventsBound = true;
    }

    /**
     * 初始化表格单元格选择功能
     * @param {string} tableId - 表格ID
     * @param {Object} options - 配置选项
     */
    function init(tableId, options) {
        if (!tableId) {
            console.warn('TableCellSelector.init: 缺少表格ID');
            return;
        }

        // 注入样式
        injectStyles();

        // 绑定全局事件
        bindGlobalEvents();

        // 保存配置
        const selection = getSelection(tableId);
        selection.options = Object.assign({}, defaultOptions, options);

        // 清除之前的选中状态
        clearSelection(tableId);

        // 绑定双击复制事件
        bindDblClickEvent(tableId);

        console.log(`TableCellSelector: 表格 ${tableId} 初始化完成`);
    }

    /**
     * 销毁表格单元格选择功能
     * @param {string} tableId - 表格ID
     */
    function destroy(tableId) {
        if (!tableId) {
            // 销毁所有
            for (const id of state.selections.keys()) {
                clearSelection(id);
            }
            state.selections.clear();
        } else {
            clearSelection(tableId);
            state.selections.delete(tableId);
        }
    }

    /**
     * 获取表格的选中单元格
     * @param {string} tableId - 表格ID
     * @returns {Array} 选中的单元格数组
     */
    function getSelectedCells(tableId) {
        const selection = state.selections.get(tableId);
        return selection ? selection.selectedCells : [];
    }

    // 暴露公共API
    global.TableCellSelector = {
        init: init,
        destroy: destroy,
        getSelectedCells: getSelectedCells,
        clearSelection: clearSelection
    };

})(window);
