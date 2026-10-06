// 比价模块业务逻辑
// 视图1（导入日志）：下载模板、导入文件、导入日志列表
// 视图2（批次结果）：Handsontable 展示比对结果，最高/最低价与月份单元格悬停看采购明细

// ==================== 导入功能 ====================

function initImport() {
    const importBtn = document.getElementById('btnCompareImport');
    const importFileInput = document.getElementById('compareFileInput');
    const downloadTemplate = document.getElementById('btnCompareDownloadTemplate');

    if (importBtn && importFileInput) {
        importBtn.addEventListener('click', () => {
            importFileInput.click();
        });

        importFileInput.addEventListener('change', () => {
            if (importFileInput.files.length > 0) {
                handleImportFile(importFileInput.files[0]);
            }
        });
    }

    if (downloadTemplate) {
        downloadTemplate.addEventListener('click', downloadCompareTemplate);
    }
}

function downloadCompareTemplate() {
    const container = document.getElementById('compareModule');
    const url = container.dataset.templateUrl || '/static/excel/OE_Brand_Price_brandcode.xlsx';
    const link = document.createElement('a');
    link.href = url;
    link.download = 'compare_template.xlsx';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

async function handleImportFile(file) {
    const validTypes = ['.xlsx', '.xls'];
    const fileExt = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
    if (validTypes.indexOf(fileExt) === -1) {
        alert('请上传 Excel 文件 (.xlsx 或 .xls)');
        document.getElementById('compareFileInput').value = '';
        return;
    }

    const loadingIndex = layui.layer.load(2, { shade: [0.3, '#000'] });

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/api/purchase_plan/compare/import_search', {
            method: 'POST',
            body: formData
        });
        const result = await response.json();

        layui.layer.close(loadingIndex);

        if (result.code !== 0) {
            layui.layer.msg(result.msg || '导入查询失败', { icon: 2 });
            return;
        }

        layui.layer.msg(`导入完成：${result.file_name}<br>导入 ${result.import_count} 条，匹配 ${result.match_count} 条`, { icon: 1 });
        await loadImportLogs();

    } catch (error) {
        layui.layer.close(loadingIndex);
        console.error('导入查询失败:', error);
        layui.layer.msg('导入查询失败: ' + error.message, { icon: 2 });
    } finally {
        document.getElementById('compareFileInput').value = '';
    }
}

// ==================== 导入日志 ====================

async function loadImportLogs() {
    try {
        const response = await fetch('/api/purchase_plan/compare/import_logs?limit=50');
        const result = await response.json();

        if (result.code === 0) {
            renderImportLogs(result.data || []);
        } else {
            console.error('加载导入日志失败:', result.msg);
        }
    } catch (error) {
        console.error('加载导入日志失败:', error);
    }
}

// 导入日志数据单元格的公共内联样式（与 bbr-table 静态边框风格一致）
const LOG_TD_STYLE = 'padding: 10px; border: 1px solid #e2e8f0;';

function renderImportLogs(logs) {
    const tbody = document.querySelector('#importLogTable tbody');

    if (!logs || logs.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="padding: 20px; text-align: center; color: #94a3b8; border: 1px solid #e2e8f0;">暂无导入记录</td></tr>`;
        return;
    }

    tbody.innerHTML = logs.map(log => {
        let actionBtn;
        if (log.has_snapshot) {
            // 新批次：网页查看结果
            actionBtn = `<button class="btn btn-primary btn-sm" onclick="CompareModule.viewResult(${log.id})">查看结果</button>`;
        } else if (log.result_file_path) {
            // 历史批次：仍可下载Excel
            actionBtn = `<button class="btn btn-default btn-sm" onclick="CompareModule.downloadImportResult(${log.id})">下载结果</button>`;
        } else {
            actionBtn = '<span style="color: #94a3b8;">无结果</span>';
        }

        return `
            <tr>
                <td style="${LOG_TD_STYLE}">${log.created_time || '-'}</td>
                <td style="${LOG_TD_STYLE}">${log.file_name || '-'}</td>
                <td style="${LOG_TD_STYLE}">${log.import_count}</td>
                <td style="${LOG_TD_STYLE}">${log.match_count}</td>
                <td style="${LOG_TD_STYLE}">${log.operator || '-'}</td>
                <td style="${LOG_TD_STYLE}">${actionBtn}</td>
            </tr>
        `;
    }).join('');
}

function downloadImportResultByUrl(url) {
    const a = document.createElement('a');
    a.href = url;
    a.target = '_blank';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

function downloadImportResult(logId) {
    downloadImportResultByUrl(`/api/purchase_plan/compare/download_import_result/${logId}`);
}

// ==================== 批次结果视图 ====================

var compareResultHot = null;
var currentBatchId = null;
var currentRawRows = [];

var MONTH_TITLES = ['一月', '二月', '三月', '四月', '五月', '六月',
    '七月', '八月', '九月', '十月', '十一月', '十二月'];

// 结果表固定列（与导入结果Excel列一致），其后追加1-12月列
var BASE_COLUMNS = [
    { title: '序号', data: 'seq', width: 60, align: 'htCenter' },
    { title: '原oe/品牌号', data: 'srcOe', width: 130, ellipsis: true },
    { title: '原品牌', data: 'srcBrand', width: 100, ellipsis: true },
    { title: 'oe', data: 'oe', width: 140, ellipsis: true },
    { title: '价格/促销价', data: 'price', width: 100, align: 'htRight', renderer: 'price' },
    { title: '4s含税进价', data: 'price4sCost', width: 100, align: 'htRight', renderer: 'price' },
    { title: '4s含税售价', data: 'price4sSale', width: 100, align: 'htRight', renderer: 'price' },
    { title: '品牌', data: 'brand', width: 100, ellipsis: true },
    { title: '名称', data: 'productName', width: 180, ellipsis: true },
    { title: '规格', data: 'spec', width: 260, ellipsis: true },
    { title: '替换号', data: 'replaceName', width: 140, ellipsis: true },
    { title: '库存数量', data: 'stockQty', width: 80, align: 'htRight' },
    { title: '替换号有库存', data: 'replaceStock', width: 160, ellipsis: true },
    { title: '标签', data: 'tag', width: 60, align: 'htCenter' },
    { title: '近1个月询价量', data: 'inq1m', width: 90, align: 'htRight' },
    { title: '近3个月月均询价量', data: 'inq3mAvg', width: 110, align: 'htRight' },
    { title: '近6个月月均销量', data: 'sales6mAvg', width: 100, align: 'htRight' },
    { title: '全国近1个月询价量', data: 'inq1mNat', width: 110, align: 'htRight' },
    { title: '全国近3个月月均询价量', data: 'inq3mAvgNat', width: 120, align: 'htRight' },
    { title: '销量数据', data: 'salesText', width: 200, wrap: true },
    { title: '最高/最低价', data: 'pricePair', width: 140, align: 'htRight', trigger: 'overall' }
];

function numOrEmpty(value) {
    if (value === null || value === undefined || value === '') return '';
    return Number(value);
}

function formatPrice(value) {
    if (value === '' || value === null || value === undefined) return '';
    return Number(value).toFixed(2);
}

function formatPricePair(raw) {
    const low = raw.overall_lowest;
    const high = raw.overall_highest;
    if (!low) return '';
    return `${Number(high[2]).toFixed(2)} / ${Number(low[2]).toFixed(2)}`;
}

function formatSalesText(r) {
    const n = v => (v === null || v === undefined ? 0 : v);
    return `今/昨/近7天: ${n(r.sales_today)}/${n(r.sales_yesterday)}/${n(r.sales_7d)}\n`
        + `近1/6/12月: ${n(r.sales_month)}/${n(r.sales_6m)}/${n(r.sales_12m)}`;
}

// 快照行 → Handsontable 展示行
function buildDisplayRows(results) {
    return results.map(r => {
        const row = {
            seq: r.group_index,
            srcOe: r.brand_code || r.search_oe || '',
            srcBrand: r.search_brand || '',
            oe: r.oe || '',
            price: numOrEmpty(r.price),
            price4sCost: numOrEmpty(r.price_4s_cost),
            price4sSale: numOrEmpty(r.price_4s_sale),
            brand: r.brand || '',
            productName: r.product_name || '',
            spec: r.spec || '',
            replaceName: r.replace_name || '',
            stockQty: numOrEmpty(r.stock_quantity),
            replaceStock: r.replace_stock_text || '',
            tag: r.tag || '',
            inq1m: numOrEmpty(r.inquiry_1m),
            inq3mAvg: numOrEmpty(r.inquiry_3m_avg),
            sales6mAvg: numOrEmpty(r.sales_6m_avg),
            inq1mNat: numOrEmpty(r.inquiry_1m_national),
            inq3mAvgNat: numOrEmpty(r.inquiry_3m_avg_national),
            salesText: formatSalesText(r),
            pricePair: formatPricePair(r)
        };
        for (let m = 1; m <= 12; m++) {
            const monthData = r.months && r.months[String(m)];
            row['m' + m] = monthData ? Number(monthData.lowest_price) : '';
        }
        return row;
    });
}

function setCellTitle(td, value) {
    if (value !== '' && value !== null && value !== undefined) {
        td.title = String(value).replace(/\n/g, ' | ');
    } else {
        td.removeAttribute('title');
    }
}

function ellipsisRenderer(hot, td, row, col, prop, value, cellProperties) {
    Handsontable.renderers.TextRenderer.apply(this, arguments);
    td.classList.add('cr-ellipsis');
    setCellTitle(td, value);
}

function wrapRenderer(hot, td, row, col, prop, value, cellProperties) {
    Handsontable.renderers.TextRenderer.apply(this, arguments);
    td.classList.add('cr-wrap');
    td.removeAttribute('title');
}

function priceRenderer(hot, td, row, col, prop, value, cellProperties) {
    const display = formatPrice(value);
    Handsontable.renderers.TextRenderer.apply(this, [hot, td, row, col, prop, display, cellProperties]);
    td.classList.add('cr-ellipsis');
    setCellTitle(td, display);
}

// 悬停触发列渲染器：每次渲染先清旧标记，防止 Handsontable 复用 td 导致标记串行
function compareTriggerRenderer(hot, td, row, col, prop, value, cellProperties) {
    const display = (typeof value === 'number') ? value.toFixed(2) : value;
    Handsontable.renderers.TextRenderer.apply(this, [hot, td, row, col, prop, display, cellProperties]);

    td.classList.remove('hp-trigger');
    td.removeAttribute('data-popover');
    td.removeAttribute('data-scope');
    td.removeAttribute('data-month');
    td.removeAttribute('data-row');
    td.removeAttribute('title');
    td.classList.add('cr-ellipsis');

    const raw = currentRawRows[row];
    if (!raw || display === '' || display === null || display === undefined) return td;

    let hasRecords = false;
    if (cellProperties.scope === 'month') {
        const m = raw.months && raw.months[String(cellProperties.monthNum)];
        hasRecords = !!(m && m.records && m.records.length);
    } else {
        hasRecords = !!(raw.all_records && raw.all_records.length);
    }

    if (hasRecords) {
        td.classList.add('hp-trigger');
        td.setAttribute('data-popover', 'compare-record');
        td.setAttribute('data-row', String(row));
        td.setAttribute('data-scope', cellProperties.scope || 'overall');
        if (cellProperties.monthNum) {
            td.setAttribute('data-month', String(cellProperties.monthNum));
        }
    }
    return td;
}

function buildColumnDefs() {
    const defs = BASE_COLUMNS.map(c => {
        const def = {
            data: c.data,
            width: c.width,
            readOnly: true,
            className: c.align || ''
        };
        if (c.renderer === 'price') {
            def.renderer = priceRenderer;
        } else if (c.wrap) {
            def.renderer = wrapRenderer;
        } else if (c.ellipsis) {
            def.renderer = ellipsisRenderer;
        }
        if (c.trigger) {
            def.scope = c.trigger;
            def.renderer = compareTriggerRenderer;
        }
        return def;
    });

    MONTH_TITLES.forEach((title, idx) => {
        const monthNum = idx + 1;
        defs.push({
            data: 'm' + monthNum,
            width: 72,
            readOnly: true,
            className: 'htRight',
            scope: 'month',
            monthNum: monthNum,
            renderer: compareTriggerRenderer
        });
    });
    return defs;
}

function renderCompareResultTable(displayRows) {
    const container = document.getElementById('compareResultHot');
    if (compareResultHot) {
        compareResultHot.destroy();
        compareResultHot = null;
    }

    const headers = BASE_COLUMNS.map(c => c.title).concat(MONTH_TITLES);

    compareResultHot = new Handsontable(container, {
        data: displayRows,
        colHeaders: headers,
        columns: buildColumnDefs(),
        rowHeights: 60,
        height: container.clientHeight || 500,
        fixedColumnsLeft: 4,
        // 取消跨行合并，冻结列与主表统一固定行高，避免行错位
        renderAllRows: true,
        autoRowSize: false,
        autoColumnSize: false,
        manualColumnResize: true,
        readOnly: true,
        stretchH: 'none',
        licenseKey: 'non-commercial-and-evaluation'
    });
}

function setResultViewVisible(visible) {
    document.getElementById('compareLogView').style.display = visible ? 'none' : 'block';
    const resultView = document.getElementById('compareResultView');
    resultView.style.display = visible ? 'flex' : 'none';
}

function updateBatchUrl(logId) {
    const url = new URL(window.location.href);
    url.searchParams.set('module', 'compare');
    if (logId) {
        url.searchParams.set('batch', String(logId));
    } else {
        url.searchParams.delete('batch');
    }
    window.history.replaceState(null, '', url.toString());
}

async function viewResult(logId) {
    const loadingIndex = layui.layer.load(2, { shade: [0.3, '#000'] });
    try {
        const response = await fetch(`/api/purchase_plan/compare/import_result/${logId}`);
        const json = await response.json();

        if (json.code !== 0) {
            layui.layer.msg(json.msg || '加载结果失败', { icon: 2 });
            return;
        }

        const data = json.data;
        currentBatchId = logId;
        currentRawRows = data.results || [];
        if (window.CompareResultPopover) {
            window.CompareResultPopover.setRows(currentRawRows);
        }

        document.getElementById('compareResultTitle').textContent
            = `${data.file_name || ''}（导入 ${data.import_count} 条 / 匹配 ${data.match_count} 条）${data.created_time ? '　' + data.created_time : ''}`;

        setResultViewVisible(true);
        renderCompareResultTable(buildDisplayRows(currentRawRows));
        updateBatchUrl(logId);

    } catch (error) {
        console.error('加载结果失败:', error);
        layui.layer.msg('加载结果失败: ' + error.message, { icon: 2 });
    } finally {
        layui.layer.close(loadingIndex);
    }
}

function backToLogs() {
    if (window.HoverPopover) window.HoverPopover.hide();
    if (compareResultHot) {
        compareResultHot.destroy();
        compareResultHot = null;
    }
    currentBatchId = null;
    currentRawRows = [];
    if (window.CompareResultPopover) {
        window.CompareResultPopover.setRows([]);
    }
    setResultViewVisible(false);
    updateBatchUrl(null);
    loadImportLogs();
}

// ==================== 初始化 ====================

function initCompareModule() {
    initImport();
    loadImportLogs();

    const backBtn = document.getElementById('btnCompareBack');
    if (backBtn) {
        backBtn.addEventListener('click', backToLogs);
    }

    // 切回比价Tab或窗口缩放时，刷新结果表格尺寸
    const tabCompare = document.getElementById('moduleTabCompare');
    if (tabCompare) {
        tabCompare.addEventListener('click', () => {
            if (compareResultHot) {
                setTimeout(() => compareResultHot.render(), 50);
            }
        });
    }
    window.addEventListener('resize', () => {
        if (compareResultHot) compareResultHot.render();
    });

    // URL参数支持：?module=compare&batch=<log_id> 直接打开批次结果
    const params = new URLSearchParams(window.location.search);
    const batchId = params.get('batch');
    if (params.get('module') === 'compare' && batchId) {
        viewResult(batchId);
    }
}

window.CompareModule = {
    init: initCompareModule,
    viewResult: viewResult,
    downloadImportResult: downloadImportResult
};
