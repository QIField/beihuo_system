// 比价模块业务逻辑（当前仅保留导入日志功能）

// 导入功能
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

        // 新逻辑：刷新导入日志，提示用户下载
        layui.layer.msg(`导入完成：${result.file_name}<br>导入 ${result.import_count} 条，匹配 ${result.match_count} 条`, { icon: 1 });
        await loadImportLogs();

        if (result.download_url) {
            downloadImportResultByUrl(result.download_url);
        }

    } catch (error) {
        layui.layer.close(loadingIndex);
        console.error('导入查询失败:', error);
        layui.layer.msg('导入查询失败: ' + error.message, { icon: 2 });
    } finally {
        document.getElementById('compareFileInput').value = '';
    }
}

// 下载导入结果（根据URL）
function downloadImportResultByUrl(url) {
    const a = document.createElement('a');
    a.href = url;
    a.target = '_blank';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

// 加载导入日志
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

// 渲染导入日志表格
// 导入日志数据单元格的公共内联样式（与 bbr-table 静态边框风格一致）
const LOG_TD_STYLE = 'padding: 10px; border: 1px solid #e2e8f0;';

function renderImportLogs(logs) {
    const tbody = document.querySelector('#importLogTable tbody');

    if (!logs || logs.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="padding: 20px; text-align: center; color: #94a3b8; border: 1px solid #e2e8f0;">暂无导入记录</td></tr>`;
        return;
    }

    tbody.innerHTML = logs.map(log => {
        const downloadBtn = log.result_file_path
            ? `<button class="btn btn-primary btn-sm" onclick="CompareModule.downloadImportResult(${log.id})">下载结果</button>`
            : '<span style="color: #94a3b8;">无结果</span>';

        return `
            <tr>
                <td style="${LOG_TD_STYLE}">${log.created_time || '-'}</td>
                <td style="${LOG_TD_STYLE}">${log.file_name || '-'}</td>
                <td style="${LOG_TD_STYLE}">${log.import_count}</td>
                <td style="${LOG_TD_STYLE}">${log.match_count}</td>
                <td style="${LOG_TD_STYLE}">${log.operator || '-'}</td>
                <td style="${LOG_TD_STYLE}">${downloadBtn}</td>
            </tr>
        `;
    }).join('');
}

// 根据日志ID下载导入结果
function downloadImportResult(logId) {
    downloadImportResultByUrl(`/api/purchase_plan/compare/download_import_result/${logId}`);
}

function initCompareModule() {
    initImport();
    loadImportLogs();
}

window.CompareModule = {
    init: initCompareModule,
    downloadImportResult: downloadImportResult
};
