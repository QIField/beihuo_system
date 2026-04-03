/**
 * 采购计划模块 - 公共 JavaScript 函数
 */

// ==================== 工具函数 ====================

/**
 * 格式化空值
 * @param {*} value - 输入值
 * @returns {string} - 处理后的值
 */
function formatEmptyValue(value) {
    if (value === null || value === undefined || value === '' || 
        value === 'nan' || value === 'NaN' || value === 'nane' || value === 'NANE') {
        return '';
    }
    return value;
}

/**
 * 格式化价格
 * @param {*} value - 输入值
 * @returns {string} - 格式化后的价格
 */
function formatPrice(value) {
    if (!value || value === '' || value === null || value === undefined) return '';
    const num = parseFloat(value);
    if (isNaN(num)) return value;
    return '¥' + num.toFixed(2);
}

/**
 * 格式化数字
 * @param {*} value - 输入值
 * @returns {string} - 格式化后的数字
 */
function formatNumber(value) {
    if (!value || value === '' || value === null || value === undefined) return '';
    const num = parseInt(value);
    if (isNaN(num)) return value;
    return num.toLocaleString();
}

/**
 * 格式化文件大小
 * @param {number} bytes - 字节数
 * @returns {string} - 格式化后的大小
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * 格式化日期
 * @param {Date} date - 日期对象
 * @returns {string} - 格式化后的日期字符串
 */
function formatDate(date) {
    const year = date.getFullYear();
    const month = ('0' + (date.getMonth() + 1)).slice(-2);
    const day = ('0' + date.getDate()).slice(-2);
    const hour = ('0' + date.getHours()).slice(-2);
    const minute = ('0' + date.getMinutes()).slice(-2);
    const second = ('0' + date.getSeconds()).slice(-2);
    return year + month + day + '_' + hour + minute + second;
}

// ==================== Handsontable 相关 ====================

/**
 * 获取 Handsontable 公共配置
 * @param {Object} options - 额外配置选项
 * @returns {Object} - Handsontable 配置对象
 */
function getCommonHotConfig(options = {}) {
    return {
        rowHeaders: false,
        colHeaders: true,
        height: '100%',
        width: '100%',
        stretchH: 'all',
        licenseKey: 'non-commercial-and-evaluation',
        copyPaste: false,
        contextMenu: false,
        manualColumnResize: true,
        manualRowResize: false,
        filters: false,
        dropdownMenu: false,
        readOnly: true,
        disableVisualSelection: false,
        selectionMode: 'multiple',
        autoRowSize: false,
        ...options
    };
}

/**
 * 创建可展开单元格渲染器
 * @param {number} threshold - 内容长度阈值
 * @returns {Function} - Handsontable 渲染器函数
 */
function createExpandableRenderer(threshold) {
    return function(instance, td, row, col, prop, value, cellProperties) {
        const isExpanded = instance.getSettings().expandedRows?.has(row);
        const hasContent = value && value.length > threshold;

        const container = document.createElement('div');
        container.style.width = '100%';
        container.style.height = '100%';
        container.style.position = 'relative';

        const textSpan = document.createElement('span');
        textSpan.textContent = value || '';
        textSpan.style.display = 'block';
        textSpan.style.width = '100%';
        textSpan.style.overflow = 'hidden';
        textSpan.style.textOverflow = isExpanded ? 'clip' : 'ellipsis';
        textSpan.style.whiteSpace = isExpanded ? 'normal' : 'nowrap';
        textSpan.style.paddingRight = hasContent ? '20px' : '0';
        container.appendChild(textSpan);

        if (hasContent) {
            const btn = document.createElement('button');
            btn.className = 'expand-btn' + (isExpanded ? ' expanded' : '');
            btn.innerHTML = isExpanded ? '−' : '+';
            btn.style.position = 'absolute';
            btn.style.right = '2px';
            btn.style.top = '50%';
            btn.style.transform = 'translateY(-50%)';
            btn.onclick = function(e) {
                e.stopPropagation();
                const expandedRows = instance.getSettings().expandedRows || new Set();
                if (expandedRows.has(row)) {
                    expandedRows.delete(row);
                } else {
                    expandedRows.add(row);
                }
                instance.render();
            };
            container.appendChild(btn);
        }

        td.innerHTML = '';
        td.appendChild(container);
        return td;
    };
}

/**
 * 设置自定义复制功能
 * @param {Object} hotInstance - Handsontable 实例
 * @param {HTMLElement} container - 容器元素
 * @param {number} specialColIndex - 特殊列索引（逗号换行处理）
 */
function setupCustomCopy(hotInstance, container, specialColIndex) {
    container.addEventListener('keydown', function(e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 'c') {
            e.preventDefault();
            const selected = hotInstance.getSelected();
            if (!selected) return;

            let copyText = '';
            selected.forEach(function(sel) {
                for (let r = Math.min(sel[0], sel[2]); r <= Math.max(sel[0], sel[2]); r++) {
                    const row = [];
                    for (let c = Math.min(sel[1], sel[3]); c <= Math.max(sel[1], sel[3]); c++) {
                        let v = hotInstance.getDataAtCell(r, c) || '';
                        if (c === specialColIndex) {
                            v = v.replace(/,/g, '\n');
                        }
                        row.push(v);
                    }
                    copyText += row.join('\t') + '\n';
                }
            });

            const ta = document.createElement('textarea');
            ta.value = copyText;
            ta.style.cssText = 'position:fixed;opacity:0';
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
        }
    });
}

// ==================== 分页相关 ====================

/**
 * 更新分页信息
 * @param {Object} config - 配置对象
 * @param {number} config.currentPage - 当前页
 * @param {number} config.totalPages - 总页数
 * @param {number} config.totalItems - 总条目数
 * @param {string} config.pageInfoId - 分页信息元素ID
 * @param {string} config.prevBtnId - 上一页按钮ID
 * @param {string} config.nextBtnId - 下一页按钮ID
 */
function updatePaginationUI(config) {
    const pageInfo = document.getElementById(config.pageInfoId);
    const prevBtn = document.getElementById(config.prevBtnId);
    const nextBtn = document.getElementById(config.nextBtnId);

    if (pageInfo) {
        pageInfo.textContent = `第 ${config.currentPage} 页 / 共 ${config.totalPages} 页 (共 ${config.totalItems} 条)`;
    }
    if (prevBtn) prevBtn.disabled = config.currentPage <= 1;
    if (nextBtn) nextBtn.disabled = config.currentPage >= config.totalPages;
}

/**
 * 初始化分页事件
 * @param {Object} config - 配置对象
 * @param {Function} config.onPageChange - 页码变化回调
 * @param {Function} config.onPageSizeChange - 每页条数变化回调
 */
function initPaginationEvents(config) {
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    const pageSizeSelect = document.getElementById('pageSizeSelect');
    const pageJumpInput = document.getElementById('pageJumpInput');
    const pageJumpBtn = document.getElementById('pageJumpBtn');

    if (prevBtn) {
        prevBtn.addEventListener('click', () => config.onPageChange('prev'));
    }
    if (nextBtn) {
        nextBtn.addEventListener('click', () => config.onPageChange('next'));
    }
    if (pageSizeSelect) {
        pageSizeSelect.addEventListener('change', (e) => config.onPageSizeChange(parseInt(e.target.value)));
    }
    if (pageJumpBtn && pageJumpInput) {
        pageJumpBtn.addEventListener('click', () => {
            const page = parseInt(pageJumpInput.value);
            if (page) config.onPageChange('jump', page);
        });
        pageJumpInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') pageJumpBtn.click();
        });
    }
}

// ==================== 搜索相关 ====================

/**
 * 初始化搜索功能
 * @param {Object} config - 配置对象
 * @param {string[]} config.inputIds - 搜索输入框ID数组
 * @param {string} config.searchBtnId - 搜索按钮ID
 * @param {string} config.refreshBtnId - 刷新按钮ID
 * @param {Function} config.onSearch - 搜索回调函数
 * @param {Function} config.onRefresh - 刷新回调函数
 */
function initSearchEvents(config) {
    const searchBtn = document.getElementById(config.searchBtnId);
    const refreshBtn = document.getElementById(config.refreshBtnId);

    if (searchBtn) {
        searchBtn.addEventListener('click', config.onSearch);
    }

    if (refreshBtn) {
        refreshBtn.addEventListener('click', config.onRefresh);
    }

    // 输入框回车事件
    config.inputIds.forEach(id => {
        const input = document.getElementById(id);
        if (input) {
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && searchBtn) {
                    searchBtn.click();
                }
            });
        }
    });
}

// ==================== 数据处理 ====================

/**
 * 处理数据并计算合并单元格
 * @param {Array} data - 原始数据
 * @param {Object} options - 配置选项
 * @returns {Object} - 处理后的数据和合并单元格配置
 */
function processDataWithMergeCommon(data, options = {}) {
    const processedData = [];
    const mergeCells = [];
    let currentRow = 0;

    const groupField = options.groupField || 'oe';
    const subGroupField = options.subGroupField || 'brand';

    // 按主字段分组
    const groups = {};
    data.forEach(item => {
        const key = item[groupField] || '';
        if (!groups[key]) groups[key] = [];
        groups[key].push(item);
    });

    // 处理每个主分组
    for (const [key, items] of Object.entries(groups)) {
        const groupStartRow = currentRow;
        const groupRowCount = items.length;

        // 按子字段分组
        const subGroups = {};
        items.forEach(item => {
            const subKey = item[subGroupField] || '未知';
            if (!subGroups[subKey]) subGroups[subKey] = [];
            subGroups[subKey].push(item);
        });

        // 处理每个子分组
        for (const [subKey, subItems] of Object.entries(subGroups)) {
            const subGroupStartRow = currentRow;
            const subGroupRowCount = subItems.length;

            // 添加每一行数据
            subItems.forEach((item, index) => {
                const rowData = { ...item };
                // 只有每组的第一个显示主字段和子字段
                if (index > 0) {
                    rowData[groupField] = '';
                    rowData[subGroupField] = '';
                }
                processedData.push(rowData);
                currentRow++;
            });

            // 添加子分组合并
            if (subGroupRowCount > 1) {
                mergeCells.push({
                    row: subGroupStartRow,
                    col: options.subGroupColIndex || 2,
                    rowspan: subGroupRowCount,
                    colspan: 1
                });
            }
        }

        // 添加主分组合并
        if (groupRowCount > 1) {
            mergeCells.push({
                row: groupStartRow,
                col: options.groupColIndex || 1,
                rowspan: groupRowCount,
                colspan: 1
            });
        }
    }

    return { data: processedData, mergeCells };
}

// 导出公共函数
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        formatEmptyValue,
        formatPrice,
        formatNumber,
        formatFileSize,
        formatDate,
        getCommonHotConfig,
        createExpandableRenderer,
        setupCustomCopy,
        updatePaginationUI,
        initPaginationEvents,
        initSearchEvents,
        processDataWithMergeCommon
    };
}
