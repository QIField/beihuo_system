// 询价模块业务逻辑

// 抑制 Handsontable 14.1.0 内部事件兼容性问题（不影响功能）
window.addEventListener('error', function(e) {
    const msg = e.message || '';
    if (msg.includes("Cannot read properties of undefined (reading 'toLowerCase')") &&
        e.filename && e.filename.includes('handsontable')) {
        e.preventDefault();
    }
});

let tableBuilder = null;
let allData = [];

// 当前数据类型：upload-上传文件, normal-正常询价数据, direct-友商价格记录
let currentDataType = 'upload';

// 行高固定为34px
const DEFAULT_ROW_HEIGHT = 34;

// 记录哪些行被展开（用数据索引）
let expandedRows = new Set();

// 格式化数据
function formatData(data) {
    return data.map((item) => ({
        oe: formatEmptyValue(item.oe),
        brand: formatEmptyValue(item.brand),
        supplier: formatEmptyValue(item.supplier),
        original_price: item.original_price ? '¥' + parseFloat(item.original_price).toFixed(2) : '',
        price: item.price ? '¥' + parseFloat(item.price).toFixed(2) : '',
        markup_rate: item.markup_rate ? ((parseFloat(item.markup_rate) - 1) * 100).toFixed(2) + '%' : '',
        markup_amount: item.markup_amount ? '¥' + parseFloat(item.markup_amount).toFixed(2) : '',
        warehouse: formatEmptyValue(item.warehouse),
        expire_time: formatEmptyValue(item.expire_time),
        remark: formatEmptyValue(item.remark),
        stock_quantity: formatEmptyValue(item.stock_quantity),
        common_number: formatEmptyValue(item.common_number),
        import_time: normalizeDateTime(item.import_time)
    }));
}

// 标准化日期时间为 ISO 8601 格式，便于排序和跨浏览器兼容
function normalizeDateTime(value) {
    if (value === null || value === undefined || value === '') return '';
    const s = String(value).trim();
    const m = s.match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?$/);
    if (!m) return s;
    return m[1] + '-' + m[2] + '-' + m[3] + 'T' + m[4] + ':' + m[5] + ':' + m[6];
}

// 将 ISO 格式日期时间渲染为友好的显示格式
function formatDateTimeDisplay(value) {
    if (!value) return '';
    const s = String(value);
    const m = s.match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})/);
    if (!m) return s;
    return m[1] + '-' + m[2] + '-' + m[3] + ' ' + m[4] + ':' + m[5] + ':' + m[6];
}

function importTimeRenderer(instance, td, row, col, prop, value, cellProperties) {
    Handsontable.renderers.TextRenderer.apply(this, arguments);
    td.textContent = formatDateTimeDisplay(value);
    return td;
}

// 行号渲染器：基于视觉行号计算，不绑定数据字段，排序后仍保持递增
function rowNumberRenderer(instance, td, row) {
    td.textContent = row + 1;
    return td;
}

// 创建带展开按钮的列renderer（适配Builder）
function createExpandableRenderer(threshold) {
    return function(instance, td, row, col, prop, value, cellProperties) {
        const isExpanded = expandedRows.has(row);
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
            btn.style.top = isExpanded ? '4px' : '50%';
            btn.style.transform = isExpanded ? 'none' : 'translateY(-50%)';
            btn.onclick = function(e) {
                e.stopPropagation();
                if (expandedRows.has(row)) {
                    expandedRows.delete(row);
                } else {
                    expandedRows.add(row);
                }
                if (tableBuilder) tableBuilder.refresh();
            };
            container.appendChild(btn);
        }

        td.innerHTML = '';
        td.appendChild(container);
        return td;
    };
}

// 创建通用号列的renderer（适配Builder）
function createCommonNumberRenderer(threshold) {
    return function(instance, td, row, col, prop, value, cellProperties) {
        const isExpanded = expandedRows.has(row);
        const hasContent = value && value.length > threshold;

        const container = document.createElement('div');
        container.style.width = '100%';
        container.style.height = '100%';
        container.style.position = 'relative';

        const textSpan = document.createElement('span');
        if (isExpanded && value) {
            textSpan.innerHTML = value.replace(/,/g, ',<br>');
        } else {
            textSpan.textContent = value || '';
        }
        textSpan.style.display = 'block';
        textSpan.style.width = '100%';
        textSpan.style.overflow = 'hidden';
        textSpan.style.textOverflow = isExpanded ? 'clip' : 'ellipsis';
        textSpan.style.whiteSpace = isExpanded ? 'normal' : 'nowrap';
        textSpan.style.paddingRight = hasContent ? '20px' : '0';
        textSpan.style.lineHeight = isExpanded ? '1.6' : 'normal';

        container.appendChild(textSpan);

        if (hasContent) {
            const btn = document.createElement('button');
            btn.className = 'expand-btn' + (isExpanded ? ' expanded' : '');
            btn.innerHTML = isExpanded ? '−' : '+';
            btn.style.position = 'absolute';
            btn.style.right = '2px';
            btn.style.top = isExpanded ? '4px' : '50%';
            btn.style.transform = isExpanded ? 'none' : 'translateY(-50%)';
            btn.onclick = function(e) {
                e.stopPropagation();
                if (expandedRows.has(row)) {
                    expandedRows.delete(row);
                } else {
                    expandedRows.add(row);
                }
                if (tableBuilder) tableBuilder.refresh();
            };
            container.appendChild(btn);
        }

        td.innerHTML = '';
        td.appendChild(container);
        return td;
    };
}

function initTableBuilder(data) {
    const container = document.getElementById('handsontable-container');
    container.innerHTML = '';

    if (tableBuilder) {
        tableBuilder.destroy();
        tableBuilder = null;
    }

    const isDirect = currentDataType === 'direct';
    const gridKey = isDirect ? 'direct_list' : 'normal_list';

    const normalColumns = [
        { data: null, title: '行号', width: 70, readOnly: true, className: 'ht-col-rowno', renderer: rowNumberRenderer },
        { data: 'oe', title: 'OE号', width: 150, readOnly: true, className: 'ht-col-oe' },
        { data: 'brand', title: '品牌', width: 120, readOnly: true, className: 'ht-col-brand' },
        { data: 'supplier', title: '供应商', width: 150, readOnly: true, renderer: createExpandableRenderer(10) },
        { data: 'original_price', title: '原价', width: 100, readOnly: true, className: 'ht-col-price' },
        { data: 'price', title: '售价', width: 100, readOnly: true, className: 'ht-col-price' },
        { data: 'markup_rate', title: '加价率', width: 100, readOnly: true, className: 'ht-col-num' },
        { data: 'markup_amount', title: '加价金额', width: 100, readOnly: true, className: 'ht-col-price' },
        { data: 'warehouse', title: '仓库', width: 120, readOnly: true, renderer: createExpandableRenderer(8) },
        { data: 'expire_time', title: '失效时间', width: 160, readOnly: true, className: 'ht-col-time' },
        { data: 'remark', title: '备注', width: 150, readOnly: true, renderer: createExpandableRenderer(8) },
        { data: 'stock_quantity', title: '库存数量', width: 100, readOnly: true, className: 'ht-col-num' },
        { data: 'common_number', title: '通用号', width: 150, readOnly: true, renderer: createCommonNumberRenderer(10) },
        { data: 'import_time', title: '上传时间', width: 160, readOnly: true, className: 'ht-col-time', renderer: importTimeRenderer }
    ];

    const directColumns = [
        { data: null, title: '行号', readOnly: true, className: 'ht-col-rowno', renderer: rowNumberRenderer },
        { data: 'oe', title: 'OE号', readOnly: true, className: 'ht-col-oe' },
        { data: 'brand', title: '品牌', readOnly: true, className: 'ht-col-brand' },
        { data: 'supplier', title: '供应商', readOnly: true, renderer: createExpandableRenderer(10) },
        { data: 'original_price', title: '原价', readOnly: true, className: 'ht-col-price' },
        { data: 'common_number', title: '通用号', readOnly: true, renderer: createCommonNumberRenderer(10) },
        { data: 'import_time', title: '上传时间', readOnly: true, className: 'ht-col-time', renderer: importTimeRenderer }
    ];

    const baseHotOptions = {
        rowHeaders: false,
        height: '100%',
        rowHeights: function(row) {
            return expandedRows.has(row) ? undefined : DEFAULT_ROW_HEIGHT;
        },
        autoRowSize: false,
        manualColumnResize: true,
        manualRowResize: false,
        columnSorting: true,
        sortIndicator: true,
        filters: false,
        dropdownMenu: false
    };

    tableBuilder = HandsontableBuilder.create('#handsontable-container', {
        columns: isDirect ? directColumns : normalColumns,
        localData: data,
        readOnly: true,
        pageKey: 'inquiry_module',
        gridKey: gridKey,
        components: {
            virtualScroll: false,
            doubleClickCopy: true,
            copyToast: true,
            columnMenu: { persist: true },
            pagination: { container: '#mainPaginationBar', pageSizeOptions: [50, 100, 200], defaultPageSize: 100 },
            toolbar: true
        },
        handsontableOptions: isDirect
            ? Object.assign({}, baseHotOptions, { stretchH: 'all' })
            : Object.assign({}, baseHotOptions, { fixedColumnsLeft: 1 })
    });
}

async function loadData(oe = '', brand = '', supplier = '') {
    try {
        const container = document.getElementById('handsontable-container');
        container.innerHTML = '<div class="loading-overlay">加载中...</div>';

        // 根据当前数据类型选择接口
        let url = currentDataType === 'direct'
            ? '/api/purchase_plan/inquiry/direct/list'
            : '/api/purchase_plan/inquiry/list';
        const params = new URLSearchParams();
        if (oe) params.append('oe', oe);
        if (brand) params.append('brand', brand);
        if (supplier) params.append('supplier', supplier);
        if (params.toString()) url += '?' + params.toString();

        const response = await fetch(url);
        const result = await response.json();

        if (result.code === 0) {
            allData = result.data;
            console.log('数据条数:', allData.length);

            // 更新标签页上的数量
            updateTabBadge(currentDataType, allData.length);

            // 格式化数据，然后用Builder创建表格
            const formattedData = formatData(allData);
            initTableBuilder(formattedData);
        } else {
            container.innerHTML = '<div class="loading-overlay">加载失败: ' + result.msg + '</div>';
        }
    } catch (error) {
        console.error('加载数据失败:', error);
        const container = document.getElementById('handsontable-container');
        container.innerHTML = '<div class="loading-overlay">加载失败: ' + error.message + '</div>';
    }
}

// 更新标签页数量
function updateTabBadge(type, count) {
    const badgeId = type === 'direct' ? 'directBadge' : 'normalBadge';
    const badge = document.getElementById(badgeId);
    if (badge) {
        badge.textContent = count;
    }
}

// 初始化标签页
function initTabs() {
    const tabUpload = document.getElementById('tabUpload');
    const tabNormal = document.getElementById('tabNormal');
    const tabDirect = document.getElementById('tabDirect');
    const tabGzbbr = document.getElementById('tabGzbbr');
    const dataTitle = document.getElementById('dataTitle');
    const uploadContainer = document.getElementById('uploadContainer');
    const mainContainer = document.getElementById('mainDataContainer');
    const gzbbrContainer = document.getElementById('gzbbrContainer');

    const tabs = [tabUpload, tabNormal, tabDirect, tabGzbbr];

    function switchTab(activeType, activeTab) {
        tabs.forEach(tab => tab.classList.remove('active'));
        activeTab.classList.add('active');
        currentDataType = activeType;

        if (activeType === 'upload') {
            uploadContainer.style.display = 'block';
            mainContainer.style.display = 'none';
            gzbbrContainer.style.display = 'none';
        } else if (activeType === 'gzbbr') {
            uploadContainer.style.display = 'none';
            mainContainer.style.display = 'none';
            gzbbrContainer.style.display = 'flex';
            if (gzbbrHot) {
                setTimeout(() => gzbbrHot.render(), 0);
            }
        } else {
            uploadContainer.style.display = 'none';
            mainContainer.style.display = 'flex';
            gzbbrContainer.style.display = 'none';
            dataTitle.textContent = activeType === 'normal' ? '询价比价数据' : '友商价格记录';
            expandedRows.clear();
            // 切换标签时销毁旧表格，避免gridKey冲突
            if (tableBuilder) {
                tableBuilder.destroy();
                tableBuilder = null;
            }
            loadData();
        }
        if (typeof refreshFilterPanel === 'function') {
            refreshFilterPanel();
        }
    }

    tabUpload.addEventListener('click', () => {
        if (currentDataType !== 'upload') {
            switchTab('upload', tabUpload);
        }
    });

    tabNormal.addEventListener('click', () => {
        if (currentDataType !== 'normal') {
            switchTab('normal', tabNormal);
        }
    });

    tabDirect.addEventListener('click', () => {
        if (currentDataType !== 'direct') {
            switchTab('direct', tabDirect);
        }
    });

    tabGzbbr.addEventListener('click', () => {
        if (currentDataType !== 'gzbbr') {
            switchTab('gzbbr', tabGzbbr);
        }
    });
}

// 切换到正常询价数据标签页并刷新数据
function switchToNormalTab() {
    const tabNormal = document.getElementById('tabNormal');
    if (currentDataType === 'normal') {
        loadData();
    } else {
        tabNormal.click();
    }
}

// data.gzbbr 失效时间调整相关变量和函数
let gzbbrHot;
let gzbbrFilteredData = [];
let gzbbrCurrentPageData = [];
let gzbbrPagination = null;
const GZBBR_DEFAULT_PAGE_SIZE = 100;

function initGzbbrTab() {
    document.getElementById('gzbbrSearchBtn').addEventListener('click', () => {
        if (gzbbrPagination) {
            gzbbrPagination.update(gzbbrPagination.totalRecords, 1, gzbbrPagination.currentPageSize);
        }
        loadGzbbrQuotes();
    });
    document.getElementById('gzbbrUpdateBtn').addEventListener('click', batchUpdateGzbbrLoseDate);
    document.getElementById('gzbbrSelectAll').addEventListener('change', toggleGzbbrSelectAll);
    initDateRangePicker('gzbbrDateRange', { max: '2099-12-31' });
    initGzbbrPagination();
}

function initGzbbrPagination() {
    const container = document.getElementById('gzbbrPaginationBar');
    if (!container) return;
    if (gzbbrPagination) {
        gzbbrPagination.destroy();
    }
    gzbbrPagination = new CustomPagination({
        container: '#gzbbrPaginationBar',
        pageSizeOptions: [50, 100, 200, 500],
        defaultPageSize: GZBBR_DEFAULT_PAGE_SIZE,
        onPageChange: function(page, pageSize) {
            renderGzbbrTable(page, pageSize);
        },
        onPageSizeChange: function(pageSize) {
            renderGzbbrTable(1, pageSize);
        }
    });
}

function sliceGzbbrPageData(page, pageSize) {
    page = page || (gzbbrPagination ? gzbbrPagination.currentPage : 1);
    pageSize = pageSize || (gzbbrPagination ? gzbbrPagination.currentPageSize : GZBBR_DEFAULT_PAGE_SIZE);
    const start = (page - 1) * pageSize;
    return gzbbrFilteredData.slice(start, start + pageSize);
}

function formatTimestamp(value) {
    if (!value) return '';
    const ts = parseInt(value);
    if (isNaN(ts)) return value;
    const date = new Date(ts * 1000);
    const pad = n => n < 10 ? '0' + n : n;
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

function loadGzbbrQuotes() {
    const oe = document.getElementById('gzbbrSearchOe').value.trim();
    const supplier = document.getElementById('gzbbrSearchSupplier').value.trim();
    const brand = document.getElementById('gzbbrSearchBrand').value.trim();
    const dateRangeValue = document.getElementById('gzbbrDateRange').value;

    let createDateStart = '';
    let createDateEnd = '';
    if (dateRangeValue) {
        const dates = dateRangeValue.split(' - ');
        if (dates.length === 2) {
            createDateStart = encodeURIComponent(dates[0].trim() + ' 00:00:00').replace(/%20/g, '+');
            createDateEnd = encodeURIComponent(dates[1].trim() + ' 23:59:59').replace(/%20/g, '+');
        }
    }

    const loadingMask = document.getElementById('gzbbrLoadingMask');
    if (loadingMask) {
        loadingMask.querySelector('div').innerHTML = '<div style="margin-bottom: 15px;">正在加载数据，请稍候...</div><div class="spinner" style="width: 40px; height: 40px; border: 4px solid #e2e8f0; border-top: 4px solid #1e3a8a; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto;"></div>';
        loadingMask.style.display = 'flex';
    }

    let url = `/api/purchase_plan/inquiry/gzbbr_quote_search?oe=${encodeURIComponent(oe)}&supplier=${encodeURIComponent(supplier)}&brand=${encodeURIComponent(brand)}`;
    if (createDateStart) {
        url += `&create_date_start=${createDateStart}`;
    }
    if (createDateEnd) {
        url += `&create_date_end=${createDateEnd}`;
    }

    fetch(url)
        .then(r => r.json())
        .then(res => {
            if (loadingMask) loadingMask.style.display = 'none';
            if (res.code !== 0) {
                alert(res.msg);
                return;
            }
            const result = res.data || {};
            gzbbrFilteredData = (result.rows || []).map(item => {
                item.selected = false;
                return item;
            });
            const total = result.total || 0;

            renderGzbbrTable(1);

            if (gzbbrPagination) {
                gzbbrPagination.update(total, 1, gzbbrPagination.currentPageSize);
            }
            document.getElementById('gzbbrBadge').textContent = total;
        })
        .catch(err => {
            if (loadingMask) loadingMask.style.display = 'none';
            alert('搜索失败: ' + err);
        });
}

function renderGzbbrTable(page, pageSize) {
    page = page || (gzbbrPagination ? gzbbrPagination.currentPage : 1);
    pageSize = pageSize || (gzbbrPagination ? gzbbrPagination.currentPageSize : GZBBR_DEFAULT_PAGE_SIZE);
    gzbbrCurrentPageData = sliceGzbbrPageData(page, pageSize);

    const container = document.getElementById('gzbbrHandsontableContainer');
    const data = gzbbrCurrentPageData.map(item => ({
        selected: item.selected,
        quote_price_id: item.quote_price_id,
        number: item.number,
        brand_name: item.brand_name,
        supplier_name: item.supplier_name,
        cass_warehouse_id: item.cass_warehouse_id,
        cass_warehouse_name: item.cass_warehouse_name,
        price: item.price,
        stock: item.stock,
        lose_date: formatTimestamp(item.lose_date),
        create_date: formatTimestamp(item.create_date),
        remark: item.remark,
        _raw: item
    }));

    if (gzbbrHot) {
        gzbbrHot.destroy();
    }

    gzbbrHot = new Handsontable(container, {
        data: data,
        colHeaders: ['选择', '行号', 'OE号', '品牌', '供应商', '仓库', '价格', '库存', '原失效时间', '创建时间', '备注'],
        columns: [
            { data: 'selected', type: 'checkbox', renderer: 'checkbox', width: 50, className: 'ht-col-center' },
            { data: null, readOnly: true, renderer: rowNumberRenderer, width: 60, className: 'ht-col-rowno' },
            { data: 'number', readOnly: true, className: 'ht-col-oe' },
            { data: 'brand_name', readOnly: true, className: 'ht-col-brand' },
            { data: 'supplier_name', readOnly: true },
            { data: 'cass_warehouse_name', readOnly: true },
            { data: 'price', readOnly: true, className: 'ht-col-price' },
            { data: 'stock', readOnly: true, className: 'ht-col-num' },
            { data: 'lose_date', readOnly: true, className: 'ht-col-time' },
            { data: 'create_date', readOnly: true, className: 'ht-col-time' },
            { data: 'remark', readOnly: true }
        ],
        rowHeights: DEFAULT_ROW_HEIGHT,
        height: 500,
        stretchH: 'all',
        licenseKey: 'non-commercial-and-evaluation',
        afterChange: function(changes, source) {
            if (source === 'loadData' || !changes) return;
            changes.forEach(([row, prop, oldVal, newVal]) => {
                if (prop === 'selected' && gzbbrCurrentPageData[row]) {
                    gzbbrCurrentPageData[row].selected = newVal;
                }
            });
            const selectAllCheckbox = document.getElementById('gzbbrSelectAll');
            selectAllCheckbox.checked = gzbbrFilteredData.length > 0 && gzbbrFilteredData.every(item => item.selected);
        }
    });

    // 同步全选复选框状态
    const selectAllCheckbox = document.getElementById('gzbbrSelectAll');
    const allSelected = gzbbrFilteredData.length > 0 && gzbbrFilteredData.every(item => item.selected);
    selectAllCheckbox.checked = allSelected;
}

function toggleGzbbrSelectAll(e) {
    const checked = e.target.checked;
    gzbbrFilteredData.forEach(item => {
        item.selected = checked;
    });
    if (gzbbrHot) {
        renderGzbbrTable();
    }
}

function batchUpdateGzbbrLoseDate() {
    if (!gzbbrHot) {
        alert('请先搜索数据');
        return;
    }
    const loseDateInput = document.getElementById('gzbbrLoseDate').value;
    if (!loseDateInput) {
        alert('请设置新失效时间');
        return;
    }

    const selectedRows = gzbbrFilteredData.filter(item => item.selected);
    if (selectedRows.length === 0) {
        alert('请选择要更新的记录');
        return;
    }

    const records = selectedRows.map(item => item);
    const formattedDate = loseDateInput.replace('T', ' ') + ':00';

    if (!confirm(`确定更新选中的 ${records.length} 条记录失效时间为 ${formattedDate} 吗？`)) {
        return;
    }

    const loadingMask = document.getElementById('gzbbrLoadingMask');
    if (loadingMask) {
        loadingMask.querySelector('div').innerHTML = '<div style="margin-bottom: 15px;">正在更新，请稍候...</div><div class="spinner" style="width: 40px; height: 40px; border: 4px solid #e2e8f0; border-top: 4px solid #1e3a8a; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto;"></div>';
        loadingMask.style.display = 'flex';
    }

    fetch('/api/purchase_plan/inquiry/gzbbr_quote_update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ records: records, lose_date: formattedDate })
    })
    .then(r => r.json())
    .then(res => {
        loadingMask.style.display = 'none';
        if (res.code !== 0) {
            alert(res.msg);
            return;
        }
        alert(`更新完成：成功 ${res.data.success_count} 条，失败 ${res.data.failed_count} 条，本地同步 ${res.data.total_synced_rows || 0} 条`);
        loadGzbbrQuotes();
    })
    .catch(err => {
        loadingMask.style.display = 'none';
        alert('更新失败: ' + err);
    });
}

// 上传相关全局状态
let pendingFile = null;
let currentUploadMode = null; // 'upload' | 'record' | 'compare'
let previewBuilder = null;
let previewData = [];

function initUpload() {
    const fileInput = document.getElementById('fileInput');
    const btnImport = document.getElementById('btnImport');
    const btnDownloadTemplate = document.getElementById('btnDownloadTemplate');
    const btnUploadSystem = document.getElementById('btnUploadSystem');
    const btnUploadRecordOnly = document.getElementById('btnUploadRecordOnly');

    // 导入文件
    btnImport.addEventListener('click', () => {
        currentUploadMode = null;
        fileInput.click();
    });

    // 文件选择后处理
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            handleFileSelect(fileInput.files[0]);
        }
    });

    // 下载模板
    btnDownloadTemplate.addEventListener('click', downloadTemplate);

    // 上传系统
    btnUploadSystem.addEventListener('click', () => {
        currentUploadMode = 'upload';
        handleConfirmUpload();
    });

    // 记录友商价格
    btnUploadRecordOnly.addEventListener('click', () => {
        currentUploadMode = 'record';
        handleConfirmUpload();
    });

    // 加价率事件
    initPreviewMarkupEvents();
}

// 文件选择后处理
async function handleFileSelect(file) {
    const validTypes = ['.csv', '.xls', '.xlsx'];
    const fileExt = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
    if (validTypes.indexOf(fileExt) === -1) {
        alert('请上传 Excel 或 CSV 文件');
        document.getElementById('fileInput').value = '';
        return;
    }

    pendingFile = file;
    await parsePreview(file);
}

// 解析预览数据
async function parsePreview(file) {
    const loadingLayer = layui.layer.open({
        type: 1,
        title: false,
        closeBtn: 0,
        area: '280px',
        shade: [0.3, '#000'],
        content: `<div style="padding:25px;text-align:center;">
            <div style="margin-bottom:10px;font-size:14px;">正在读取并解析文件...</div>
            <div style="font-size:12px;color:#999;">请稍候</div>
        </div>`
    });

    const formData = new FormData();
    formData.append('file', file);
    formData.append('thread_count', document.getElementById('matchThreadCount')?.value || 3);

    try {
        const response = await fetch('/api/purchase_plan/inquiry/parse_preview', {
            method: 'POST',
            body: formData
        });
        const result = await response.json();

        layui.layer.close(loadingLayer);

        if (result.code !== 0) {
            layui.layer.msg(result.msg || '解析失败', { icon: 2 });
            return;
        }

        previewData = result.data || [];
        if (previewData.length === 0) {
            layui.layer.msg('文件中没有有效数据', { icon: 0 });
            return;
        }

        layui.layer.msg(`共解析 ${previewData.length} 条数据`, { icon: 1 });

        // 显示加价率区域和表格
        document.getElementById('uploadMarkupSection').style.display = 'block';
        document.getElementById('previewTableWrapper').style.display = 'block';

        // 默认加价率 1
        document.getElementById('markupInput').value = '1.00';
        updateFinalPrices(1);

        renderPreviewTable();

    } catch (error) {
        layui.layer.close(loadingLayer);
        layui.layer.msg('解析请求失败: ' + error.message, { icon: 2 });
    }
}

// 渲染预览表格（使用 HandsontableBuilder）
function renderPreviewTable() {
    if (previewBuilder) {
        previewBuilder.destroy();
        previewBuilder = null;
    }

    const columns = [
        { data: null, title: '序号', width: 60, readOnly: true, className: 'ht-col-rowno', renderer: rowNumberRenderer },
        { data: 'oe', title: 'OE号', type: 'text', width: 150, readOnly: true, className: 'ht-col-oe' },
        { data: 'brand', title: '品牌', type: 'text', width: 100, readOnly: true, className: 'ht-col-brand' },
        { data: 'supplier', title: '供应商', type: 'text', width: 150, readOnly: true },
        { data: 'price', title: '原价', type: 'text', width: 100, readOnly: true, className: 'ht-col-price' },
        { data: 'warehouse', title: '仓库', type: 'text', width: 120 },
        { data: 'expire_time', title: '失效时间', type: 'text', width: 160, className: 'ht-col-time' },
        { data: 'remark', title: '备注', type: 'text', width: 150 },
        { data: 'stock_quantity', title: '库存数量', type: 'text', width: 100, className: 'ht-col-num' },
        { data: 'matched_oe', title: '匹配OE', type: 'text', width: 150 },
        { data: 'matched_brand', title: '匹配品牌', type: 'text', width: 120 },
        { data: 'matched_barcode', title: '匹配条码', type: 'text', width: 150, readOnly: true },
        { data: 'matched_supplier', title: '匹配供应商', type: 'text', width: 150 },
        { data: 'final_price', title: '最终价格', type: 'numeric', numericFormat: { pattern: '0.00' }, width: 120, className: 'ht-col-price' },
        { data: 'product_id', title: '产品编号', type: 'text', width: 120, readOnly: true },
        { data: 'upload_result', title: '上传结果', type: 'text', width: 200, readOnly: true },
        { data: '_action', title: '操作', type: 'text', renderer: actionRenderer, width: 80, readOnly: true, className: 'ht-col-center' }
    ];

    previewBuilder = HandsontableBuilder.create('#previewHandsontableContainer', {
        columns: columns,
        localData: previewData,
        readOnly: false,
        pageKey: 'inquiry_module_upload',
        gridKey: 'upload_preview',
        components: {
            virtualScroll: false,
            doubleClickCopy: true,
            copyToast: true,
            columnMenu: { persist: true },
            pagination: { pageSizeOptions: [50, 100, 200], defaultPageSize: 100 }
        },
        handsontableOptions: {
            rowHeaders: true,
            rowHeights: DEFAULT_ROW_HEIGHT,
            height: 460,
            afterChange: function(changes, source) {
                if (source === 'edit' && changes) {
                    changes.forEach(function(change) {
                        const [rowIndex, propName] = change;
                        if (propName === 'final_price') {
                            previewData[rowIndex]._finalPriceManual = true;
                        }
                    });
                }
            }
        }
    });
}

// 操作列渲染器
function actionRenderer(instance, td, row, col, prop, value, cellProperties) {
    td.innerHTML = '<button class="btn btn-danger btn-sm" type="button">删除</button>';

    const btn = td.querySelector('button');
    if (btn) {
        btn.onclick = function(e) {
            e.stopPropagation();
            if (!previewBuilder || !previewData.length) return;

            // 考虑分页计算真实数据索引
            const page = previewBuilder.currentPage || 1;
            const pageSize = previewBuilder.pageSize || previewData.length;
            const dataIndex = (page - 1) * pageSize + row;

            if (dataIndex >= 0 && dataIndex < previewData.length) {
                previewData.splice(dataIndex, 1);
                previewBuilder.config.localData = previewData;
                previewBuilder.refresh();
            }
        };
    }
    return td;
}

// 根据加价率更新最终价格（手动编辑过的行不再自动覆盖）
function updateFinalPrices(markupRate) {
    previewData.forEach(row => {
        if (row._finalPriceManual) return;
        const price = parseFloat(row.price) || 0;
        row.final_price = (price * markupRate).toFixed(2);
    });
    if (previewBuilder) {
        previewBuilder.config.localData = previewData;
        previewBuilder.refresh();
    }
}

// 初始化加价率事件
function initPreviewMarkupEvents() {
    const markupInput = document.getElementById('markupInput');
    const markupDecrease = document.getElementById('markupDecrease');
    const markupIncrease = document.getElementById('markupIncrease');

    if (!markupInput || !markupDecrease || !markupIncrease) return;

    markupDecrease.addEventListener('click', () => {
        let value = parseFloat(markupInput.value) || 1;
        value = Math.max(0.05, value - 0.05);
        markupInput.value = value.toFixed(2);
        updateFinalPrices(value);
    });

    markupIncrease.addEventListener('click', () => {
        let value = parseFloat(markupInput.value) || 1;
        value = value + 0.05;
        markupInput.value = value.toFixed(2);
        updateFinalPrices(value);
    });

    markupInput.addEventListener('input', () => {
        let value = markupInput.value;
        value = value.replace(/[^0-9.]/g, '');
        const parts = value.split('.');
        if (parts.length > 2) {
            value = parts[0] + '.' + parts.slice(1).join('');
        }
        markupInput.value = value;
    });

    markupInput.addEventListener('blur', () => {
        let value = parseFloat(markupInput.value);
        if (isNaN(value) || value < 0.05) {
            value = 1;
        }
        markupInput.value = value.toFixed(2);
        updateFinalPrices(value);
    });
}

// 确认上传
async function handleConfirmUpload() {
    if (!pendingFile || previewData.length === 0) {
        layui.layer.msg('请先选择文件并解析数据', { icon: 0 });
        return;
    }

    const skipB2b = currentUploadMode === 'record';

    // 校验有 product_id 的行的失效时间格式（YYYY-MM-DD HH:MM:SS）
    // 录入数据库模式允许为空，上传系统模式保持必填
    const expireTimeRegex = /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/;
    const invalidRows = [];
    previewData.forEach((row, idx) => {
        if (row.product_id) {
            const et = String(row.expire_time || '').trim();
            if (skipB2b) {
                // 录入数据库模式：为空不校验，有值必须格式正确
                if (et && !expireTimeRegex.test(et)) {
                    invalidRows.push(idx + 1);
                }
            } else {
                // 上传系统模式：保持原样，必填
                if (!et || !expireTimeRegex.test(et)) {
                    invalidRows.push(idx + 1);
                }
            }
        }
    });
    if (invalidRows.length > 0) {
        layui.layer.msg('第 ' + invalidRows.join(', ') + ' 行失效时间格式错误，请修改为 "YYYY-MM-DD HH:MM:SS" 格式后再上传', { icon: 2, time: 5000 });
        return;
    }

    const markupRate = parseFloat(document.getElementById('markupInput').value) || 1;

    // 将预览数据（已删除的行已过滤）生成 CSV 文件上传
    const uploadFile = buildUploadFileFromPreview();

    const formData = new FormData();
    formData.append('file', uploadFile);
    formData.append('markup_rate', markupRate.toFixed(2));
    formData.append('skip_b2b', skipB2b ? 'true' : 'false');
    formData.append('enable_compare', 'false');

    const loadingIndex = layui.layer.load(2, { shade: [0.3, '#000'] });

    try {
        const response = await fetch('/api/purchase_plan/inquiry/import', {
            method: 'POST',
            body: formData
        });
        const result = await response.json();

        layui.layer.close(loadingIndex);

        if (result.code !== 0) {
            layui.layer.msg(result.msg || '提交失败', { icon: 2 });
            return;
        }

        pollUploadStatus(result.data.task_id);

    } catch (error) {
        layui.layer.close(loadingIndex);
        layui.layer.msg('提交失败: ' + error.message, { icon: 2 });
    }
}

// 根据预览数据构建上传文件
function buildUploadFileFromPreview() {
    const headers = ['oe', 'brand', 'supplier', 'price', 'warehouse', 'expire_time', 'remark', 'stock_quantity', 'matched_oe', 'matched_brand', 'matched_supplier', 'final_price', 'product_id'];
    const rows = previewData.map(row => headers.map(h => {
        const value = row[h] || '';
        return '"' + String(value).replace(/"/g, '""') + '"';
    }).join(','));
    const csvContent = '\uFEFF' + headers.join(',') + '\n' + rows.join('\n');
    return new File([csvContent], 'preview_data.csv', { type: 'text/csv' });
}

// 轮询上传任务状态（展示处理条数）
function pollUploadStatus(taskId) {
    const progressLayer = layui.layer.open({
        type: 1,
        title: false,
        closeBtn: 0,
        area: '280px',
        shade: [0.3, '#000'],
        content: `<div style="padding:25px;text-align:center;">
            <div style="margin-bottom:10px;font-size:14px;">正在处理...</div>
            <div id="uploadProgressCount" style="font-size:12px;color:#999;">已处理 0 / ${previewData.length} 条</div>
        </div>`
    });

    const checkStatus = setInterval(async () => {
        try {
            const statusRes = await fetch('/api/purchase_plan/inquiry/import/status/' + taskId);
            const statusResult = await statusRes.json();

            if (statusResult.code !== 0) {
                clearInterval(checkStatus);
                layui.layer.close(progressLayer);
                layui.layer.msg(statusResult.msg || '查询状态失败', { icon: 2 });
                return;
            }

            const status = statusResult.data;
            const countEl = document.getElementById('uploadProgressCount');
            const current = status.progress || 0;
            const total = status.total || previewData.length;
            if (countEl) {
                countEl.innerText = `已处理 ${current} / ${total} 条`;
            }

            if (status.status === 'running') {
                // 继续轮询
            } else if (status.status === 'completed') {
                clearInterval(checkStatus);
                layui.layer.close(progressLayer);

                // 将每行上传结果回显到预览表格
                const rowResults = (status.result_data || {});
                previewData.forEach((row, idx) => {
                    row.upload_result = rowResults[idx] || '';
                });
                if (previewBuilder) {
                    previewBuilder.config.localData = previewData;
                    previewBuilder.refresh();
                }

                const successCount = Object.values(rowResults).filter(msg => String(msg).indexOf('成功') !== -1).length;
                const failCount = previewData.length - successCount;
                layui.layer.msg(`处理完成：成功 ${successCount} 条，失败/跳过 ${failCount} 条`, { icon: 1 });
            } else if (status.status === 'failed') {
                clearInterval(checkStatus);
                layui.layer.close(progressLayer);
                layui.layer.msg(status.error || '处理失败', { icon: 2 });
            }
        } catch (error) {
            clearInterval(checkStatus);
            layui.layer.close(progressLayer);
            layui.layer.msg('查询状态失败: ' + error.message, { icon: 2 });
        }
    }, 2000);
}

// 重置上传区域
function resetUploadArea() {
    previewData = [];
    if (previewBuilder) {
        previewBuilder.destroy();
        previewBuilder = null;
    }
    document.getElementById('uploadMarkupSection').style.display = 'none';
    document.getElementById('previewTableWrapper').style.display = 'none';
    document.getElementById('fileInput').value = '';
    pendingFile = null;
    currentUploadMode = null;
}

// 下载询价模板
function downloadTemplate() {
    const container = document.getElementById('inquiryModule');
    const url = container.dataset.templateUrl || '/static/excel/virtual_inventory.xlsx';
    const link = document.createElement('a');
    link.href = url;
    link.download = 'inquiry_template.xlsx';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

function initSearch() {
    ['searchOe', 'searchBrand', 'searchSupplier'].forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;
        el.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                const oe = document.getElementById('searchOe').value;
                const brand = document.getElementById('searchBrand').value;
                const supplier = document.getElementById('searchSupplier').value;
                loadData(oe, brand, supplier);
            }
        });
    });
}

function refreshFilterPanel() {
    const dateRangeItem = document.getElementById('dateRangeFilterItem');
    if (!dateRangeItem) return;
    const tabGzbbr = document.getElementById('tabGzbbr');
    if (tabGzbbr && tabGzbbr.classList.contains('active')) {
        dateRangeItem.style.display = 'block';
    } else {
        dateRangeItem.style.display = 'none';
    }
}

function initInquiryModule() {
    initUpload();
    initSearch();
    initTabs();
    initGzbbrTab();
    refreshFilterPanel();
    if (currentDataType !== 'upload') {
        loadData();
    }
}

window.InquiryModule = {
    init: initInquiryModule,
    loadData: loadData,
    refreshFilterPanel: refreshFilterPanel
};
