/**
 * 安全库存管理页面 - AG Grid版本
 * 参考询比价模块和询价单监控风格
 */

// AG Grid 实例
let gridApi = null;
let gridColumnApi = null;

// 当前筛选条件
let currentFilter = {
    keyword: '',
    stock_status: '',
    abc_class: ''
};

// 当前排序状态
let currentSort = { field: null, direction: null };

// 所有数据缓存
let allData = [];

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    initGrid();
    bindEvents();
    loadStatusCount();
    loadData();
});

/**
 * 初始化 AG Grid
 */
function initGrid() {
    // 列定义
    const columnDefs = [
        {
            headerName: 'OE号',
            field: 'oe',
            flex: 2,
            minWidth: 150,
            sortable: true,
            filter: 'agTextColumnFilter',
            resizable: true,
            cellClass: 'cell-text'
        },
        {
            headerName: '品牌',
            field: 'brand',
            width: 120,
            sortable: true,
            filter: 'agTextColumnFilter',
            resizable: true,
            cellClass: 'cell-text'
        },
        {
            headerName: '产品名称',
            field: 'product_name',
            flex: 2,
            minWidth: 180,
            sortable: true,
            filter: 'agTextColumnFilter',
            resizable: true,
            cellClass: 'cell-text'
        },
        {
            headerName: 'ABC',
            field: 'abc_class',
            width: 80,
            sortable: true,
            filter: 'agTextColumnFilter',
            resizable: true,
            cellRenderer: function(params) {
                if (!params.value) return '-';
                const classMap = {
                    'A': 'abc-a',
                    'B': 'abc-b',
                    'C': 'abc-c'
                };
                return `<span class="abc-tag ${classMap[params.value] || 'abc-c'}">${params.value}</span>`;
            }
        },
        {
            headerName: '当前库存',
            field: 'current_stock',
            width: 100,
            sortable: true,
            filter: 'agNumberColumnFilter',
            resizable: true,
            cellClass: 'cell-number',
            valueFormatter: numberFormatter
        },
        {
            headerName: '在途',
            field: 'in_transit_qty',
            width: 80,
            sortable: true,
            filter: 'agNumberColumnFilter',
            resizable: true,
            cellClass: 'cell-number',
            valueFormatter: numberFormatter
        },
        {
            headerName: '可用库存',
            field: 'available_stock',
            width: 100,
            sortable: true,
            filter: 'agNumberColumnFilter',
            resizable: true,
            cellClass: 'cell-number',
            valueFormatter: numberFormatter,
            cellStyle: function(params) {
                if (params.value <= 0) {
                    return { color: '#cf1322', fontWeight: 'bold' };
                }
                return null;
            }
        },
        {
            headerName: '日均销量',
            field: 'avg_daily_sales',
            width: 100,
            sortable: true,
            filter: 'agNumberColumnFilter',
            resizable: true,
            cellClass: 'cell-number',
            valueFormatter: numberFormatter
        },
        {
            headerName: '基础安全库存',
            field: 'base_safety_stock',
            width: 110,
            sortable: true,
            filter: 'agNumberColumnFilter',
            resizable: true,
            cellClass: 'cell-number',
            valueFormatter: numberFormatter
        },
        {
            headerName: '季节系数',
            field: 'seasonal_factor',
            width: 90,
            sortable: true,
            filter: 'agNumberColumnFilter',
            resizable: true,
            cellClass: 'cell-number',
            valueFormatter: function(params) {
                if (params.value === null || params.value === undefined || isNaN(params.value)) return '-';
                return parseFloat(params.value).toFixed(2);
            }
        },
        {
            headerName: '调整后安全库存',
            field: 'safety_stock',
            width: 120,
            sortable: true,
            filter: 'agNumberColumnFilter',
            resizable: true,
            cellClass: 'cell-number',
            valueFormatter: numberFormatter
        },
        {
            headerName: '库存下限',
            field: 'reorder_point',
            width: 100,
            sortable: true,
            filter: 'agNumberColumnFilter',
            resizable: true,
            cellClass: 'cell-number',
            valueFormatter: numberFormatter
        },
        {
            headerName: '库存上限',
            field: 'target_stock',
            width: 100,
            sortable: true,
            filter: 'agNumberColumnFilter',
            resizable: true,
            cellClass: 'cell-number',
            valueFormatter: numberFormatter
        },
        {
            headerName: '可卖天数',
            field: 'sellable_days',
            width: 100,
            sortable: true,
            filter: 'agNumberColumnFilter',
            resizable: true,
            cellClass: 'cell-number',
            valueFormatter: function(params) {
                if (params.value === null || params.value === undefined || isNaN(params.value)) return '-';
                return parseFloat(params.value).toFixed(1) + '天';
            }
        },
        {
            headerName: '库存状态',
            field: 'stock_status',
            width: 120,
            sortable: true,
            filter: 'agTextColumnFilter',
            resizable: true,
            cellRenderer: function(params) {
                if (!params.value) return '-';
                const statusMap = {
                    '需补货': { class: 'status-danger', icon: '🚨' },
                    '库存偏低': { class: 'status-warning', icon: '⚠️' },
                    '库存积压': { class: 'status-info', icon: '📦' },
                    '正常': { class: 'status-success', icon: '✅' }
                };
                const status = statusMap[params.value] || { class: '', icon: '' };
                return `<span class="cell-status ${status.class}">${status.icon} ${params.value}</span>`;
            }
        },
        {
            headerName: '库存金额',
            field: 'inventory_amount',
            width: 120,
            sortable: true,
            filter: 'agNumberColumnFilter',
            resizable: true,
            cellClass: 'cell-number',
            valueFormatter: function(params) {
                if (params.value === null || params.value === undefined || isNaN(params.value)) return '-';
                return '¥' + parseFloat(params.value).toFixed(2);
            }
        },
        {
            headerName: '替换号',
            field: 'replace_number',
            width: 120,
            sortable: true,
            filter: 'agTextColumnFilter',
            resizable: true,
            cellClass: 'cell-text'
        },
        {
            headerName: '产品等级',
            field: 'product_level',
            width: 100,
            sortable: true,
            filter: 'agTextColumnFilter',
            resizable: true,
            cellClass: 'cell-text'
        },
        {
            headerName: '中文车型',
            field: 'l_model_zh',
            width: 150,
            sortable: true,
            filter: 'agTextColumnFilter',
            resizable: true,
            cellClass: 'cell-text'
        }
    ];

    // Grid 配置
    const gridOptions = {
        columnDefs: columnDefs,
        rowData: [],
        defaultColDef: {
            sortable: true,
            filter: true,
            resizable: true
        },
        pagination: true,
        paginationPageSize: 50,
        rowSelection: 'multiple',
        suppressRowClickSelection: true,
        animateRows: true,
        localeText: {
            page: '页',
            more: '更多',
            to: '到',
            of: '共',
            next: '下一页',
            last: '最后一页',
            first: '第一页',
            previous: '上一页',
            loadingOoo: '加载中...',
            noRowsToShow: '暂无数据',
            filterOoo: '筛选...',
            equals: '等于',
            notEqual: '不等于',
            lessThan: '小于',
            greaterThan: '大于',
            contains: '包含',
            notContains: '不包含',
            startsWith: '开始于',
            endsWith: '结束于'
        },
        onGridReady: function(params) {
            gridApi = params.api;
            gridColumnApi = params.columnApi;
            console.log('AG Grid 初始化完成');

            // 初始化双击复制功能
            initDoubleClickCopy();

            // 初始化分页大小选择器和页码跳转器
            setTimeout(initPageSizeSelector, 500);
            setTimeout(initPageJumper, 600);
        },
        onSortChanged: function(params) {
            const sortModel = params.api.getSortModel();
            if (sortModel.length > 0) {
                currentSort = {
                    field: sortModel[0].colId,
                    direction: sortModel[0].sort
                };
            } else {
                currentSort = { field: null, direction: null };
            }
            applyFilter();
        }
    };

    // 创建 Grid
    const gridDiv = document.getElementById('safetyStockGrid');
    new agGrid.Grid(gridDiv, gridOptions);
}

/**
 * 绑定事件
 */
function bindEvents() {
    // 查询按钮
    document.getElementById('btnSearch').addEventListener('click', function() {
        currentFilter.keyword = document.getElementById('filterKeyword').value.trim();
        currentFilter.stock_status = document.getElementById('filterStatus').value;
        currentFilter.abc_class = document.getElementById('filterABC').value;
        applyFilter();
    });

    // 重置按钮
    document.getElementById('btnReset').addEventListener('click', function() {
        document.getElementById('filterKeyword').value = '';
        document.getElementById('filterStatus').value = '';
        document.getElementById('filterABC').value = '';
        currentFilter = { keyword: '', stock_status: '', abc_class: '' };
        
        // 清除卡片选中状态
        document.querySelectorAll('.stat-card').forEach(card => {
            card.classList.remove('active');
        });
        
        applyFilter();
    });

    // 导出按钮
    document.getElementById('btnExport').addEventListener('click', function() {
        exportData();
    });

    // 统计卡片点击筛选
    document.querySelectorAll('.stat-card').forEach(card => {
        card.addEventListener('click', function() {
            const status = this.dataset.status;
            document.getElementById('filterStatus').value = status;
            currentFilter.stock_status = status;
            
            // 切换选中状态
            document.querySelectorAll('.stat-card').forEach(c => c.classList.remove('active'));
            this.classList.add('active');
            
            applyFilter();
        });
    });

    // 回车搜索
    document.getElementById('filterKeyword').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            document.getElementById('btnSearch').click();
        }
    });
}

/**
 * 加载状态统计
 */
function loadStatusCount() {
    fetch('/api/safety-stock/status-count')
        .then(response => response.json())
        .then(res => {
            if (res.code === 0) {
                const data = res.data;
                document.getElementById('countDanger').textContent = data['需补货'] || 0;
                document.getElementById('countWarning').textContent = data['库存偏低'] || 0;
                document.getElementById('countInfo').textContent = data['库存积压'] || 0;
                document.getElementById('countSuccess').textContent = data['正常'] || 0;
            }
        })
        .catch(error => {
            console.error('加载状态统计失败:', error);
        });
}

/**
 * 加载数据
 */
function loadData() {
    layui.use(['layer'], function(layer) {
        layer.load(2);
        
        fetch('/api/safety-stock/list?limit=100000')
            .then(response => response.json())
            .then(res => {
                layer.closeAll('loading');
                
                if (res.code === 0) {
                    allData = res.data || [];
                    console.log('=== loadData 调试信息 ===');
                    console.log('加载数据成功:', allData.length, '条');
                    if (allData.length > 0) {
                        console.log('第一条数据:', allData[0]);
                        // 统计各种状态的数据量
                        const statusCount = {};
                        const abcCount = {};
                        allData.forEach(item => {
                            const status = item.stock_status || '空';
                            const abc = item.abc_class || '空';
                            statusCount[status] = (statusCount[status] || 0) + 1;
                            abcCount[abc] = (abcCount[abc] || 0) + 1;
                        });
                        console.log('库存状态分布:', statusCount);
                        console.log('ABC分类分布:', abcCount);
                    }
                    console.log('========================');
                    applyFilter();
                } else {
                    layer.msg(res.msg || '加载失败', { icon: 2 });
                }
            })
            .catch(error => {
                layer.closeAll('loading');
                layer.msg('网络错误，请稍后重试', { icon: 2 });
                console.error('加载数据失败:', error);
            });
    });
}

/**
 * 应用筛选
 */
function applyFilter() {
    console.log('=== applyFilter 调试信息 ===');
    console.log('当前筛选条件:', currentFilter);
    console.log('allData 总数:', allData.length);
    
    let filteredData = allData;
    
    // 关键词筛选
    if (currentFilter.keyword) {
        const keyword = currentFilter.keyword.toLowerCase();
        console.log('关键词筛选:', keyword);
        filteredData = filteredData.filter(item => {
            return (item.oe && item.oe.toLowerCase().includes(keyword)) ||
                   (item.brand && item.brand.toLowerCase().includes(keyword)) ||
                   (item.product_name && item.product_name.toLowerCase().includes(keyword));
        });
        console.log('关键词筛选后数量:', filteredData.length);
    }
    
    // 状态筛选
    if (currentFilter.stock_status) {
        console.log('状态筛选:', currentFilter.stock_status);
        console.log('筛选前数据样本:', filteredData.slice(0, 3).map(item => ({oe: item.oe, stock_status: item.stock_status})));
        filteredData = filteredData.filter(item => {
            const match = item.stock_status === currentFilter.stock_status;
            if (!match && item.stock_status) {
                console.log('不匹配项:', item.oe, '的 stock_status:', item.stock_status, '!==', currentFilter.stock_status);
            }
            return match;
        });
        console.log('状态筛选后数量:', filteredData.length);
    }
    
    // ABC分类筛选
    if (currentFilter.abc_class) {
        console.log('ABC分类筛选:', currentFilter.abc_class);
        console.log('筛选前数据样本:', filteredData.slice(0, 3).map(item => ({oe: item.oe, abc_class: item.abc_class})));
        filteredData = filteredData.filter(item => {
            const match = item.abc_class === currentFilter.abc_class;
            if (!match && item.abc_class) {
                console.log('不匹配项:', item.oe, '的 abc_class:', item.abc_class, '!==', currentFilter.abc_class);
            }
            return match;
        });
        console.log('ABC分类筛选后数量:', filteredData.length);
    }
    
    // 应用排序（对全部筛选后的数据排序）
    if (currentSort.field && currentSort.direction) {
        filteredData = sortData(filteredData, currentSort.field, currentSort.direction);
    }
    
    console.log('最终筛选结果数量:', filteredData.length);
    console.log('========================');
    
    // 更新表格数据
    if (gridApi) {
        gridApi.setRowData(filteredData);
        // 刷新分页
        gridApi.paginationGoToPage(0);
    }
}

/**
 * 对数据进行排序
 * @param {Array} data - 要排序的数据
 * @param {string} field - 排序字段
 * @param {string} direction - 排序方向 'asc' 或 'desc'
 * @returns {Array} 排序后的数据
 */
function sortData(data, field, direction) {
    if (!field || !direction) return data;
    
    return [...data].sort((a, b) => {
        let valA = a[field];
        let valB = b[field];
        
        // 处理空值
        if (valA === null || valA === undefined) valA = '';
        if (valB === null || valB === undefined) valB = '';
        
        // 数字排序
        if (typeof valA === 'number' && typeof valB === 'number') {
            return direction === 'asc' ? valA - valB : valB - valA;
        }
        
        // 字符串排序（不区分大小写）
        const strA = String(valA).toLowerCase();
        const strB = String(valB).toLowerCase();
        
        if (strA < strB) return direction === 'asc' ? -1 : 1;
        if (strA > strB) return direction === 'asc' ? 1 : -1;
        return 0;
    });
}

/**
 * 执行计算
 */
function executeCalculate() {
    layui.use(['layer'], function(layer) {
        layer.load(2);
        
        fetch('/api/safety-stock/calculate', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(res => {
            layer.closeAll('loading');
            
            if (res.code === 0) {
                layer.msg(res.msg, { icon: 1 });
                // 刷新数据
                loadStatusCount();
                loadData();
            } else {
                layer.msg(res.msg || '计算失败', { icon: 2 });
            }
        })
        .catch(error => {
            layer.closeAll('loading');
            layer.msg('网络错误，请稍后重试', { icon: 2 });
            console.error('计算失败:', error);
        });
    });
}

/**
 * 导出数据
 */
function exportData() {
    layui.use(['layer'], function(layer) {
        layer.msg('正在准备导出...', { icon: 16, time: 1000 });
        
        // 获取当前筛选后的数据
        let exportData = allData;
        
        if (currentFilter.keyword) {
            const keyword = currentFilter.keyword.toLowerCase();
            exportData = exportData.filter(item => {
                return (item.oe && item.oe.toLowerCase().includes(keyword)) ||
                       (item.brand && item.brand.toLowerCase().includes(keyword)) ||
                       (item.product_name && item.product_name.toLowerCase().includes(keyword));
            });
        }
        
        if (currentFilter.stock_status) {
            exportData = exportData.filter(item => 
                item.stock_status === currentFilter.stock_status
            );
        }
        
        if (currentFilter.abc_class) {
            exportData = exportData.filter(item => 
                item.abc_class === currentFilter.abc_class
            );
        }
        
        // 导出为CSV
        exportToCSV(exportData);
    });
}

/**
 * 导出为CSV
 */
function exportToCSV(data) {
    if (!data || data.length === 0) {
        layui.use(['layer'], function(layer) {
            layer.msg('没有数据可导出', { icon: 0 });
        });
        return;
    }
    
    // 表头
    const headers = ['OE号', '品牌', '产品名称', 'ABC分类', '当前库存', '在途数量', '可用库存',
                     '平均日销量', '安全库存', '库存下限', '库存上限', '可卖天数', '库存状态', '库存金额',
                     '替换号', '产品等级', '中文车型'];

    // 数据行
    const rows = data.map(item => [
        item.oe || '',
        item.brand || '',
        item.product_name || '',
        item.abc_class || '',
        item.current_stock || 0,
        item.in_transit_qty || 0,
        item.available_stock || 0,
        item.avg_daily_sales || 0,
        item.safety_stock || 0,
        item.reorder_point || 0,
        item.target_stock || 0,
        item.sellable_days || 0,
        item.stock_status || '',
        item.inventory_amount || 0,
        item.replace_number || '',
        item.product_level || '',
        item.l_model_zh || ''
    ]);
    
    // 创建CSV内容
    let csvContent = '\uFEFF'; // BOM for UTF-8
    csvContent += headers.join(',') + '\n';
    rows.forEach(row => {
        // 处理包含逗号的字段
        const processedRow = row.map(cell => {
            const cellStr = String(cell);
            if (cellStr.includes(',') || cellStr.includes('"') || cellStr.includes('\n')) {
                return '"' + cellStr.replace(/"/g, '""') + '"';
            }
            return cellStr;
        });
        csvContent += processedRow.join(',') + '\n';
    });
    
    // 下载
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', '安全库存_' + new Date().toISOString().slice(0, 10) + '.csv');
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    layui.use(['layer'], function(layer) {
        layer.msg('导出成功', { icon: 1 });
    });
}

/**
 * 数字格式化
 */
function numberFormatter(params) {
    if (params.value === null || params.value === undefined || isNaN(params.value)) {
        return '-';
    }
    // 保留2位小数，去除末尾0
    return parseFloat(params.value).toFixed(2).replace(/\.?0+$/, '');
}

/**
 * 初始化双击复制功能
 */
function initDoubleClickCopy() {
    const gridDiv = document.getElementById('safetyStockGrid');
    if (!gridDiv) return;
    
    gridDiv.addEventListener('dblclick', function(e) {
        const cell = e.target.closest('.ag-cell');
        if (!cell) return;
        
        const value = cell.textContent.trim();
        if (!value) return;
        
        // 复制到剪贴板
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(value).then(function() {
                layui.layer.msg('已复制: ' + value.substring(0, 20) + (value.length > 20 ? '...' : ''), {icon: 1, time: 1500});
            }).catch(function() {
                fallbackCopyText(value);
            });
        } else {
            fallbackCopyText(value);
        }
    });
    
    console.log('[双击复制] 初始化完成');
}

/**
 * 兼容性复制文本
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
            layui.layer.msg('已复制: ' + text.substring(0, 20) + (text.length > 20 ? '...' : ''), {icon: 1, time: 1500});
        }
    } catch (err) {
        console.error('[双击复制] 复制失败:', err);
    }
    
    document.body.removeChild(textarea);
}

/**
 * 初始化分页大小选择器
 */
function initPageSizeSelector() {
    const pagingPanel = document.querySelector('.ag-paging-panel');
    if (!pagingPanel) {
        console.log('[分页选择器] 未找到分页面板，稍后重试');
        setTimeout(initPageSizeSelector, 500);
        return;
    }
    
    // 检查是否已存在
    if (pagingPanel.querySelector('.page-size-selector')) {
        return;
    }
    
    // 创建选择器容器
    const selectorContainer = document.createElement('div');
    selectorContainer.className = 'page-size-selector';
    selectorContainer.innerHTML = `
        <span>每页显示:</span>
        <select id="pageSizeSelect">
            <option value="50">50</option>
            <option value="100">100</option>
            <option value="200">200</option>
        </select>
        <span>条</span>
    `;
    
    pagingPanel.appendChild(selectorContainer);
    
    // 绑定事件
    const select = selectorContainer.querySelector('#pageSizeSelect');
    select.addEventListener('change', function() {
        const newPageSize = parseInt(this.value);
        if (gridApi) {
            gridApi.paginationSetPageSize(newPageSize);
            console.log('[分页选择器] 切换到每页', newPageSize, '条');
        }
    });
    
    console.log('[分页选择器] 初始化完成');
}

/**
 * 初始化页码跳转器
 */
function initPageJumper() {
    const pagingPanel = document.querySelector('.ag-paging-panel');
    const rowSummaryPanel = pagingPanel.querySelector('.ag-paging-row-summary-panel');
    
    if (!pagingPanel || !rowSummaryPanel) return;
    
    // 检查是否已存在
    if (rowSummaryPanel.querySelector('.page-jumper')) {
        return;
    }
    
    // 将rowSummaryPanel改为水平布局，使内容和跳转器并排
    rowSummaryPanel.style.display = 'flex';
    rowSummaryPanel.style.flexDirection = 'row';
    rowSummaryPanel.style.alignItems = 'center';
    rowSummaryPanel.style.gap = '15px';
    rowSummaryPanel.style.flexWrap = 'wrap';
    rowSummaryPanel.style.justifyContent = 'center';
    
    // 创建跳转器容器
    const jumperDiv = document.createElement('div');
    jumperDiv.className = 'page-jumper';
    jumperDiv.innerHTML = `
        <span>跳至</span>
        <input type="number" id="pageJumperInput" min="1" placeholder="页码">
        <span>页</span>
        <button id="pageJumperBtn">跳转</button>
    `;
    
    // 将跳转器添加到rowSummaryPanel中，与统计信息并排
    rowSummaryPanel.appendChild(jumperDiv);
    
    // 绑定事件
    const input = jumperDiv.querySelector('#pageJumperInput');
    const btn = jumperDiv.querySelector('#pageJumperBtn');
    
    const doJump = function() {
        const pageNum = parseInt(input.value);
        if (!pageNum || pageNum < 1) {
            layui.layer.msg('请输入有效的页码', {icon: 0});
            return;
        }
        
        const totalPages = gridApi.paginationGetTotalPages();
        if (pageNum > totalPages) {
            layui.layer.msg('页码超出范围，最大页码: ' + totalPages, {icon: 0});
            return;
        }
        
        // AG Grid 页码从0开始，所以减1
        gridApi.paginationGoToPage(pageNum - 1);
        input.value = '';
        console.log('[页码跳转] 跳转到第', pageNum, '页');
    };
    
    btn.addEventListener('click', doJump);
    input.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            doJump();
        }
    });
    
    console.log('[页码跳转器] 初始化完成');
}
