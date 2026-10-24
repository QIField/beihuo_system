/**
 * Excel 处理独立页面逻辑
 * 功能：对账 / 单据 / 新建产品 / 更新产品 / 更新替换号
 * 从 index.html 旧弹窗迁移而来，接口调用与校验逻辑保持不变
 */
layui.use('layer', function () {
    var layer = layui.layer;

    // 各功能Tab当前选择的文件
    var currentTab = 'bill';
    var tabFiles = {
        bill: [],
        order: [],
        crm: [],
        update_crm: [],
        replace_number: []
    };

    // 共享的任务数据（供结果下载按钮使用）
    var currentTaskId = null;
    var currentTaskData = null;

    // 新建产品两阶段数据
    var crmCheckTaskId = null;      // 阶段一匹配检查任务ID
    var crmCheckMode = '';          // 匹配检查时的模式
    var crmCheckItems = [];         // 阶段一核对清单（含实际更新品牌号输入值）
    var crmPendingCreateItems = []; // 阶段二确认提交清单（待新建 + 已存在更新）
    var crmStage = '';              // crm 流程阶段：''=待检查 / 'checked'=核对中（footer 按钮变"开始新建"）

    // 替换号两阶段数据（compare 模式页内核对编辑）
    var rnCheckTaskId = null;       // 阶段一匹配检查任务ID
    var rnCheckItems = [];          // 阶段一核对清单（含替换号编辑值）
    var rnStage = '';               // 流程阶段：''=待检查 / 'checked'=核对中（footer 按钮变"开始更新"）

    // ====== 权限控制：无权限的功能Tab直接隐藏 ======
    fetch('/api/current_user')
        .then(function (response) { return response.json(); })
        .then(function (result) {
            if (result.logged_in) {
                var canProcessOrders = result.can_process_orders;
                var canUpdateCrm = result.can_update_crm;
                if (!canProcessOrders) {
                    document.getElementById('tabOrder').style.display = 'none';
                }
                if (!canUpdateCrm) {
                    document.getElementById('tabUpdateCrm').style.display = 'none';
                }
            }
        })
        .catch(function (error) {
            console.error('获取用户权限失败:', error);
        });

    // ====== Tab 切换 ======
    var tabs = document.querySelectorAll('.module-tab');
    tabs.forEach(function (tab) {
        tab.addEventListener('click', function () {
            if (tab.style.display === 'none') return;
            var target = tab.getAttribute('data-tab');
            if (target === currentTab) return;

            currentTab = target;
            tabs.forEach(function (t) { t.classList.remove('active'); });
            tab.classList.add('active');

            document.querySelectorAll('.ep-panel').forEach(function (panel) {
                panel.classList.remove('active');
            });
            document.querySelector('.ep-panel[data-panel="' + target + '"]').classList.add('active');

            updateFileList();
            updateConfirmBtnState();
        });
    });

    function getFileInputId(tab) {
        if (tab === 'bill') return 'billFileSelect';
        if (tab === 'order') return 'orderFileSelect';
        if (tab === 'crm') return 'crmFileSelect';
        if (tab === 'update_crm') return 'updateCrmFileSelect';
        if (tab === 'replace_number') return 'replaceNumberFileSelect';
        return 'billFileSelect';
    }

    function updateFileList() {
        var files = tabFiles[currentTab];
        var fileListDiv = document.getElementById('selectedFilesList');
        if (!files || files.length === 0) {
            fileListDiv.innerHTML = '暂无选择文件';
            return;
        }
        var html = '<strong>已选择文件：</strong><br>';
        for (var i = 0; i < files.length; i++) {
            html += (i + 1) + '. ' + files[i].name + '<br>';
        }
        fileListDiv.innerHTML = html;
    }

    // ====== 文件选择事件 ======
    ['bill', 'order', 'crm', 'update_crm', 'replace_number'].forEach(function (tab) {
        var inputId = getFileInputId(tab);
        var input = document.getElementById(inputId);
        if (!input) return;
        input.addEventListener('change', function (e) {
            tabFiles[tab] = Array.from(e.target.files);
            if (currentTab === tab) {
                updateFileList();
            }
        });
    });

    // ====== 上传框显示控制：处理进入核对/结果阶段后隐藏，重置后恢复 ======
    function setUploadZoneVisible(tab, visible) {
        var zone = document.querySelector('.ep-panel[data-panel="' + tab + '"] .ep-upload-zone');
        if (zone) {
            zone.style.display = visible ? '' : 'none';
        }
    }

    // ====== 底部确认按钮状态：crm/替换号 核对阶段显示红色"开始新建/开始更新"，其余显示"开始处理" ======
    function updateConfirmBtnState() {
        var btn = document.getElementById('confirmProcessBtn');
        if (currentTab === 'crm' && crmStage === 'checked') {
            btn.textContent = '开始新建';
            btn.classList.remove('btn-primary');
            btn.classList.add('btn-danger');
        } else if (currentTab === 'replace_number' && rnStage === 'checked') {
            btn.textContent = '开始更新';
            btn.classList.remove('btn-primary');
            btn.classList.add('btn-danger');
        } else {
            btn.textContent = '开始处理';
            btn.classList.remove('btn-danger');
            btn.classList.add('btn-primary');
        }
    }

    // ====== 上传区拖拽高亮：拖入时边框变蓝 + 底色微变，拖出/落下恢复 ======
    function initUploadDragHighlight() {
        document.querySelectorAll('.ep-upload-zone').forEach(function (zone) {
            zone.addEventListener('dragover', function (e) {
                e.preventDefault();
                zone.classList.add('dragover');
            });
            zone.addEventListener('dragleave', function (e) {
                if (!zone.contains(e.relatedTarget)) {
                    zone.classList.remove('dragover');
                }
            });
            zone.addEventListener('drop', function () {
                zone.classList.remove('dragover');
            });
        });
    }

    initUploadDragHighlight();

    // ====== 重置：清空当前功能已选文件并隐藏结果区 ======
    document.getElementById('epResetBtn').addEventListener('click', function () {
        tabFiles[currentTab] = [];
        var input = document.getElementById(getFileInputId(currentTab));
        if (input) {
            input.value = '';
        }
        document.getElementById('crmResultArea').style.display = 'none';
        document.getElementById('crmCheckArea').style.display = 'none';
        document.getElementById('replaceNumberResultArea').style.display = 'none';
        document.getElementById('rnCheckArea').style.display = 'none';
        crmCheckTaskId = null;
        crmCheckItems = [];
        crmPendingCreateItems = [];
        crmStage = '';
        rnCheckTaskId = null;
        rnCheckItems = [];
        rnStage = '';
        setUploadZoneVisible('crm', true);
        setUploadZoneVisible('replace_number', true);
        updateConfirmBtnState();
        updateFileList();
    });

    // ====== 模板下载 ======
    document.getElementById('orderTemplateLink').addEventListener('click', function () {
        var orderType = document.getElementById('orderTypeSelect').value;
        if (orderType === '广州龙星景丰') {
            window.location.href = '/download_template/guangzhou_lxjf';
        } else if (orderType === '厦门华禹') {
            window.location.href = '/download_template/xiamen_huayu';
        } else {
            layer.msg('请选择单据类型', {icon: 2});
        }
    });

    document.getElementById('updateCrmTemplateLink').addEventListener('click', function () {
        window.location.href = '/api/excel/template/updateview';
    });

    document.getElementById('crmTemplateLink').addEventListener('click', function () {
        window.location.href = '/static/excel/productadd.xlsx';
    });

    document.getElementById('replaceNumberTemplateLink').addEventListener('click', function () {
        window.location.href = '/static/excel/numberlist.xlsx';
    });

    // ====== 开始处理 ======
    document.getElementById('confirmProcessBtn').onclick = function () {
        // crm 核对阶段：按钮为红色"开始新建"，触发阶段二确认处理
        if (currentTab === 'crm' && crmStage === 'checked') {
            startCrmConfirm();
            return;
        }

        // 替换号核对阶段：按钮为红色"开始更新"，触发阶段二确认更新
        if (currentTab === 'replace_number' && rnStage === 'checked') {
            startReplaceNumberUpdate();
            return;
        }

        var files = tabFiles[currentTab];
        var formData = new FormData();
        var processType = currentTab;
        var crmMode = '';
        var orderType = '';

        if (!files || files.length === 0) {
            layer.msg('请至少选择一个文件', {icon: 2});
            return;
        }

        if (currentTab === 'order') {
            orderType = document.getElementById('orderTypeSelect').value;
            if (!orderType) {
                layer.msg('请选择单据类型', {icon: 2});
                return;
            }
            for (var i = 0; i < files.length; i++) {
                formData.append('files', files[i]);
            }
        } else if (currentTab === 'crm') {
            crmMode = document.getElementById('crmModeSelect').value;
            if (!crmMode) {
                layer.msg('请选择品牌编码模式', {icon: 2});
                return;
            }
            if (files.length > 1) {
                layer.msg('新建CRM档案仅支持单个文件', {icon: 2});
                return;
            }
            var fileName = files[0].name.toLowerCase();
            if (!fileName.endsWith('.xlsx') && !fileName.endsWith('.xls') && !fileName.endsWith('.csv')) {
                layer.msg('新建CRM档案仅支持Excel或CSV文件', {icon: 2});
                return;
            }
            formData.append('file', files[0]);
            formData.append('mode', crmMode);
        } else if (currentTab === 'update_crm') {
            if (files.length > 1) {
                layer.msg('更新CRM产品信息仅支持单个文件', {icon: 2});
                return;
            }
            var fileName = files[0].name.toLowerCase();
            if (!fileName.endsWith('.xlsx') && !fileName.endsWith('.xls') && !fileName.endsWith('.csv')) {
                layer.msg('更新CRM产品信息仅支持Excel或CSV文件', {icon: 2});
                return;
            }
            formData.append('file', files[0]);
        } else if (currentTab === 'replace_number') {
            var rnMode = document.getElementById('replaceNumberModeSelect').value;
            if (!rnMode) {
                layer.msg('请选择处理方式', {icon: 2});
                return;
            }
            if (files.length > 1) {
                layer.msg('更新替换号仅支持单个文件', {icon: 2});
                return;
            }
            var fileName = files[0].name.toLowerCase();
            if (!fileName.endsWith('.xlsx') && !fileName.endsWith('.xls') && !fileName.endsWith('.csv')) {
                layer.msg('更新替换号仅支持Excel或CSV文件', {icon: 2});
                return;
            }
            formData.append('file', files[0]);
            formData.append('mode', rnMode);
        } else {
            // bill
            for (var i = 0; i < files.length; i++) {
                formData.append('files', files[i]);
            }
        }

        formData.append('process_type', processType);
        if (orderType) {
            formData.append('order_type', orderType);
        }

        // 隐藏上次 CRM/替换号 结果
        document.getElementById('crmResultArea').style.display = 'none';
        document.getElementById('crmCheckArea').style.display = 'none';
        document.getElementById('replaceNumberResultArea').style.display = 'none';
        document.getElementById('rnCheckArea').style.display = 'none';
        currentTaskId = null;
        currentTaskData = null;
        crmCheckTaskId = null;
        crmCheckItems = [];
        crmPendingCreateItems = [];
        crmStage = '';
        rnCheckTaskId = null;
        rnCheckItems = [];
        rnStage = '';
        updateConfirmBtnState();

        // 显示处理进度
        var processLoading = layer.load(1, { shade: [0.1, '#fff'] });

        if (currentTab === 'crm') {
            crmCheckMode = crmMode;
            handleCrmAsyncProcess(formData, processLoading, '/api/excel/async/product_archive', function (taskId, resultData) {
                // 阶段一完成：渲染核对表格，等待用户确认后再新建
                crmCheckTaskId = taskId;
                renderCrmCheckTable(resultData || {});
            });
        } else if (currentTab === 'update_crm') {
            handleCrmAsyncProcess(formData, processLoading, '/api/excel/async/update_crm_product');
        } else if (currentTab === 'replace_number') {
            var rnMode = document.getElementById('replaceNumberModeSelect').value;
            handleReplaceNumberProcess(formData, processLoading, rnMode);
        } else {
            handleSyncProcess(formData, processLoading, processType, files);
        }
    };

    // ====== 结果下载 ======
    document.getElementById('crmDownloadBtn').addEventListener('click', function () {
        if (currentTaskId) {
            window.location.href = '/api/excel/async/download/' + currentTaskId;
        }
    });

    document.getElementById('replaceNumberDownloadBtn').addEventListener('click', function () {
        if (currentTaskId) {
            window.location.href = '/api/excel/async/download/' + currentTaskId;
        }
    });

    // ====== 创建进度提示层 ======
    function createProgressLayer(contentId, textId) {
        return layer.open({
            type: 1,
            title: false,
            closeBtn: 0,
            shade: 0.3,
            area: ['280px', '100px'],
            content: '<div id="' + contentId + '" style="padding: 28px 0; text-align: center; font-size: 14px; color: #1e293b;"><i class="layui-icon layui-icon-loading layui-anim layui-anim-rotate layui-anim-loop" style="color: #1e3a8a; font-size: 18px;"></i> <span id="' + textId + '">初始化中...</span></div>'
        });
    }

    // ====== 轮询异步任务状态 ======
    // onCompleted(taskId, resultData)：有回调则交给调用方处理，无回调则自动下载结果
    // onFailed()：任务失败/超时/查询异常时回调（可选）
    function pollExcelTask(taskId, loadingIndex, progressLayerIndex, textId, onCompleted, onFailed) {
        var fail = function (msg) {
            layer.close(loadingIndex);
            layer.close(progressLayerIndex);
            layer.msg(msg, {icon: 2});
            if (typeof onFailed === 'function') {
                onFailed();
            }
        };
        var pollCount = 0;
        var maxPollCount = 900; // 最多轮询 900 次，约 30 分钟
        var checkInterval = setInterval(function () {
            pollCount++;
            if (pollCount > maxPollCount) {
                clearInterval(checkInterval);
                fail('处理超时，请稍后重试');
                return;
            }

            fetch('/api/excel/async/status/' + taskId)
            .then(response => response.json())
            .then(statusResult => {
                if (statusResult.code !== 0) {
                    clearInterval(checkInterval);
                    fail('查询状态失败: ' + statusResult.msg);
                    return;
                }

                var status = statusResult.data;

                if (status.status === 'running') {
                    var progress = status.progress || 0;
                    var total = status.total || 0;
                    var message = status.message || '处理中...';
                    var displayMsg = (progress === 0 && total === 0) ? '初始化中...' : '处理中: ' + progress + '/' + total + ' - ' + message;
                    var progressText = document.getElementById(textId);
                    if (progressText) {
                        progressText.textContent = displayMsg;
                    }
                } else if (status.status === 'completed') {
                    clearInterval(checkInterval);
                    layer.close(loadingIndex);
                    layer.close(progressLayerIndex);
                    if (typeof onCompleted === 'function') {
                        onCompleted(taskId, status.result_data);
                        layer.msg('处理完成', {icon: 1});
                    } else {
                        layer.msg('处理完成，开始下载...', {icon: 1});
                        window.location.href = '/api/excel/async/download/' + taskId;
                    }
                } else if (status.status === 'failed') {
                    clearInterval(checkInterval);
                    fail('处理失败: ' + (status.error || '未知错误'));
                }
            })
            .catch(error => {
                clearInterval(checkInterval);
                fail('查询状态失败: ' + error.message);
            });
        }, 2000); // 每2秒查询一次
    }

    // ====== CRM异步处理函数 ======
    // onComplete 回调参数: (taskId, resultData)
    function handleCrmAsyncProcess(formData, loadingIndex, apiUrl, onComplete) {
        // 步骤1：提交异步任务
        fetch(apiUrl, {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(result => {
            if (result.code !== 0) {
                layer.close(loadingIndex);
                layer.msg('提交失败: ' + result.msg, {icon: 2});
                return;
            }

            var taskId = result.data.task_id;
            layer.msg('任务已提交，处理中...', {icon: 1});

            // 步骤2：轮询查询任务状态
            var progressLayerIndex = createProgressLayer('crmProgressContent', 'crmProgressText');
            pollExcelTask(taskId, loadingIndex, progressLayerIndex, 'crmProgressText', onComplete);
        })
        .catch(error => {
            layer.close(loadingIndex);
            layer.msg('提交失败: ' + error.message, {icon: 2});
        });
    }

    // ====== HTML 转义（表格单元格内容来自Excel，防止破坏页面结构） ======
    function escapeHtml(text) {
        return String(text == null ? '' : text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    // ====== 渲染匹配核对表格（阶段一完成后） ======
    function renderCrmCheckTable(data) {
        var items = data.items || [];
        var matchedCount = data.matched_count || 0;
        var unmatchedCount = data.unmatched_count || 0;
        var isThreeColumn = crmCheckMode === 'three_column';

        crmCheckItems = items;
        crmPendingCreateItems = [];
        var unmatchedBrandCount = 0;
        for (var i = 0; i < items.length; i++) {
            if (items[i].status === 'existed' && items[i].product_id) {
                // 已存在行：进入确认清单，阶段二对比品牌编码后按需更新
                crmPendingCreateItems.push({
                    _idx: i,
                    sheet_name: items[i].sheet_name,
                    oe: items[i].oe,
                    brand: items[i].brand,
                    brand_code: items[i].crm_brand_code || '',
                    status: 'existed',
                    product_id: items[i].product_id
                });
            } else if (items[i].status === 'to_create') {
                // 未匹配系统品牌的行不会新建（与原流程一致：没匹配到品牌ID就不新建），不进入清单
                if (items[i].brand_matched === false) {
                    unmatchedBrandCount++;
                } else {
                    crmPendingCreateItems.push({
                        _idx: i,
                        sheet_name: items[i].sheet_name,
                        oe: items[i].oe,
                        brand: items[i].brand,
                        brand_code: items[i].brand_code || '',
                        status: 'to_create',
                        product_id: ''
                    });
                }
            }
        }

        var html = '<table class="crm-check-table"><thead><tr>';
        html += '<th style="width:86px;">状态</th><th>OE号</th><th>品牌</th><th>系统品牌</th><th>匹配OE/品牌</th><th>CRM品牌编码</th>';
        if (isThreeColumn) {
            html += '<th>文件品牌号</th>';
        }
        html += '<th>实际更新品牌号</th>';
        html += '</tr></thead><tbody>';

        for (var j = 0; j < items.length; j++) {
            var it = items[j];
            var existed = it.status === 'existed';
            // 实际更新品牌号默认值：已存在行取CRM品牌编码，待新建行三列模式取文件品牌号
            var actualDefault = existed ? (it.crm_brand_code || '') : (isThreeColumn ? (it.brand_code || '') : '');
            html += '<tr>';
            html += '<td><span class="crm-check-tag ' + (existed ? 'existed' : 'to_create') + '">' + (existed ? '已存在' : '待新建') + '</span></td>';
            html += '<td>' + escapeHtml(it.oe) + '</td>';
            html += '<td>' + escapeHtml(it.brand) + '</td>';
            if (!existed && it.brand_matched === false) {
                html += '<td><span class="crm-brand-unmatched">未匹配品牌，不会新建</span></td>';
            } else {
                html += '<td>' + escapeHtml(it.system_brand || '—') + '</td>';
            }
            // 匹配OE/品牌：仅已存在行展示系统命中的号码/品牌
            html += '<td>' + (existed ? escapeHtml(it.matched_key || '') : '—') + '</td>';
            html += '<td>' + escapeHtml(it.crm_brand_code || '') + '</td>';
            if (isThreeColumn) {
                html += '<td>' + escapeHtml(it.brand_code || '') + '</td>';
            }
            html += '<td><input type="text" class="crm-actual-input" data-idx="' + j + '" value="' + escapeHtml(actualDefault) + '"></td>';
            html += '</tr>';
        }
        html += '</tbody></table>';

        var statsMsg = '匹配完成：已存在 ' + matchedCount + ' 条（对比品牌号后按需更新），需新建 ' + unmatchedCount + ' 条';
        if (unmatchedBrandCount > 0) {
            statsMsg += '（其中未匹配品牌 ' + unmatchedBrandCount + ' 条不会处理）';
        }
        statsMsg += '。实际更新品牌号可编辑，核对后点击右下角开始新建。';
        document.getElementById('crmCheckStats').textContent = statsMsg;
        document.getElementById('crmCheckTableWrap').innerHTML = html;

        // 进入核对阶段：底部按钮变红色"开始新建"，上传框隐藏（重置后恢复）
        crmStage = 'checked';
        updateConfirmBtnState();
        document.getElementById('crmCheckArea').style.display = 'block';
        setUploadZoneVisible('crm', false);
    }

    // ====== 阶段二：确认后开始处理（新建 + 已存在行品牌号对比更新） ======
    function startCrmConfirm() {
        var confirmBtn = document.getElementById('confirmProcessBtn');
        if (!crmCheckTaskId) {
            layer.msg('请先完成匹配检查', {icon: 2});
            return;
        }
        if (!crmPendingCreateItems.length) {
            layer.msg('没有需要处理的数据', {icon: 2});
            return;
        }

        // 从核对表格收集编辑后的实际更新品牌号（data-idx 对应 crmCheckItems 索引）
        var submitItems = crmPendingCreateItems.map(function (item) {
            var input = document.querySelector('.crm-actual-input[data-idx="' + item._idx + '"]');
            var actual = input ? input.value.trim() : '';
            return {
                sheet_name: item.sheet_name,
                oe: item.oe,
                brand: item.brand,
                brand_code: actual,
                status: item.status,
                product_id: item.product_id
            };
        });

        confirmBtn.disabled = true;
        var enableBtn = function () {
            confirmBtn.disabled = false;
            updateConfirmBtnState();
        };
        var loadingIndex = layer.load(1, { shade: [0.1, '#fff'] });
        fetch('/api/excel/async/product_archive_confirm', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                check_task_id: crmCheckTaskId,
                items: submitItems
            })
        })
        .then(response => response.json())
        .then(result => {
            if (result.code !== 0) {
                layer.close(loadingIndex);
                enableBtn();
                layer.msg('提交失败: ' + result.msg, {icon: 2});
                return;
            }

            var taskId = result.data.task_id;
            layer.msg('任务已提交，处理中...', {icon: 1});

            var progressLayerIndex = createProgressLayer('crmCreateProgressContent', 'crmCreateProgressText');
            pollExcelTask(taskId, loadingIndex, progressLayerIndex, 'crmCreateProgressText', function (tId, resultData) {
                currentTaskId = tId;
                currentTaskData = resultData || {};
                document.getElementById('crmCheckArea').style.display = 'none';
                // 处理完成：退出核对阶段，按钮恢复"开始处理"（需重置后重新走流程）
                crmStage = '';
                crmPendingCreateItems = [];
                enableBtn();
                var sc = currentTaskData.success_count || 0;
                var fc = currentTaskData.fail_count || 0;
                var msg = '处理完成：成功 ' + sc + ' 条，失败 ' + fc + ' 条';
                var uc = currentTaskData.unchanged_count || 0;
                if (uc > 0) {
                    msg += '，一致跳过 ' + uc + ' 条';
                }
                document.getElementById('crmResultMsg').textContent = msg;
                document.getElementById('crmResultArea').style.display = 'block';
            }, enableBtn);
        })
        .catch(error => {
            layer.close(loadingIndex);
            enableBtn();
            layer.msg('提交失败: ' + error.message, {icon: 2});
        });
    }

    // ====== 更新替换号处理函数 ======
    // direct: 直接添加，完成后展示结果区；compare: 阶段一匹配检查，完成后渲染核对表格
    function handleReplaceNumberProcess(formData, loadingIndex, mode) {
        fetch('/api/excel/async/replace_number', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(result => {
            if (result.code !== 0) {
                layer.close(loadingIndex);
                layer.msg('提交失败: ' + result.msg, {icon: 2});
                return;
            }

            var taskId = result.data.task_id;
            layer.msg('任务已提交，处理中...', {icon: 1});

            var progressLayerIndex = createProgressLayer('rnProgressContent', 'rnProgressText');
            pollExcelTask(taskId, loadingIndex, progressLayerIndex, 'rnProgressText', function (tId, resultData) {
                if (mode === 'compare') {
                    // 阶段一完成：渲染核对表格，等待用户编辑后点"开始更新"
                    rnCheckTaskId = tId;
                    renderRnCheckTable(resultData || {});
                } else {
                    // direct 直接添加完成：展示结果区
                    currentTaskId = tId;
                    document.getElementById('replaceNumberResultMsg').textContent = '处理完成，请下载结果文件';
                    document.getElementById('replaceNumberResultArea').style.display = 'block';
                    setUploadZoneVisible('replace_number', false);
                }
            });
        })
        .catch(error => {
            layer.close(loadingIndex);
            layer.msg('提交失败: ' + error.message, {icon: 2});
        });
    }

    // ====== 替换号输入拆分：兼容中英文逗号分隔 ======
    function splitNumbers(text) {
        if (!text) return [];
        return String(text).split(/[,，]/).map(function (s) { return s.trim(); }).filter(Boolean);
    }

    // ====== 渲染替换号核对表格（阶段一完成后） ======
    function renderRnCheckTable(data) {
        var items = data.items || [];
        var matchedCount = data.matched_count || 0;
        var unmatchedCount = data.unmatched_count || 0;

        rnCheckItems = items;

        var html = '<table class="crm-check-table"><thead><tr>';
        html += '<th style="width:86px;">状态</th><th>OE号</th><th>品牌</th><th>品牌号</th>';
        html += '<th>原厂号</th><th>其他号</th><th style="width:64px;">上传</th><th>将更新产品</th>';
        html += '</tr></thead><tbody>';

        for (var j = 0; j < items.length; j++) {
            var it = items[j];
            var pending = it.status === '待更新';
            html += '<tr>';
            html += '<td><span class="crm-check-tag ' + (pending ? 'to_create' : 'rn-blocked') + '">' + escapeHtml(pending ? '待更新' : it.status) + '</span></td>';
            html += '<td>' + escapeHtml(it.oe) + '</td>';
            html += '<td>' + escapeHtml(it.brand) + '</td>';
            html += '<td>' + escapeHtml(it.brand_number) + '</td>';
            html += '<td><textarea class="rn-num-input" data-idx="' + j + '" data-field="original"' + (pending ? '' : ' readonly') + '>' + escapeHtml(it.original_numbers || '') + '</textarea></td>';
            html += '<td><textarea class="rn-num-input" data-idx="' + j + '" data-field="other"' + (pending ? '' : ' readonly') + '>' + escapeHtml(it.other_numbers || '') + '</textarea></td>';
            html += '<td><select class="rn-upload-select" data-idx="' + j + '"' + (pending ? '' : ' disabled') + '>';
            html += '<option value="1"' + (parseInt(it.is_upload, 10) === 1 ? ' selected' : '') + '>1</option>';
            html += '<option value="0"' + (parseInt(it.is_upload, 10) !== 1 ? ' selected' : '') + '>0</option>';
            html += '</select></td>';
            var productLines = (it.products || []).map(function (p) {
                var line = p.number + '/' + p.brand_name;
                return '<div class="rn-product-line" title="' + escapeHtml(line) + '">' + escapeHtml(line) + '</div>';
            }).join('');
            html += '<td>' + (productLines || '—') + '</td>';
            html += '</tr>';
        }
        html += '</tbody></table>';

        var statsMsg = '匹配完成：待更新 ' + matchedCount + ' 行，未匹配/异常 ' + unmatchedCount + ' 行。';
        statsMsg += '原厂号与其他号可编辑，仅"上传=1"的行会更新，核对后点击右下角开始更新。';
        document.getElementById('rnCheckStats').textContent = statsMsg;
        document.getElementById('rnCheckTableWrap').innerHTML = html;

        // 进入核对阶段：底部按钮变红色"开始更新"，上传框隐藏（重置后恢复）
        rnStage = 'checked';
        updateConfirmBtnState();
        document.getElementById('rnCheckArea').style.display = 'block';
        setUploadZoneVisible('replace_number', false);
    }

    // ====== 阶段二：确认后批量更新替换号 ======
    function startReplaceNumberUpdate() {
        var confirmBtn = document.getElementById('confirmProcessBtn');
        if (!rnCheckTaskId) {
            layer.msg('请先完成匹配检查', {icon: 2});
            return;
        }

        // 从核对表格收集编辑后的替换号（data-idx 对应 rnCheckItems 索引）
        var submitItems = [];
        for (var i = 0; i < rnCheckItems.length; i++) {
            var it = rnCheckItems[i];
            if (it.status !== '待更新') continue;
            var select = document.querySelector('.rn-upload-select[data-idx="' + i + '"]');
            if (!select || parseInt(select.value, 10) !== 1) continue;

            var origInput = document.querySelector('.rn-num-input[data-idx="' + i + '"][data-field="original"]');
            var otherInput = document.querySelector('.rn-num-input[data-idx="' + i + '"][data-field="other"]');
            var newOriginal = splitNumbers(origInput ? origInput.value : '');
            var newOther = splitNumbers(otherInput ? otherInput.value : '');

            var products = [];
            (it.products || []).forEach(function (p) {
                // 原厂系品牌取原厂号，其他品牌取其他号，与产品已有替换号合并去重
                var base = (it.original_brands || []).indexOf(p.brand_name) >= 0 ? newOriginal : newOther;
                var finalNumbers = (p.display_numbers || []).slice();
                base.forEach(function (n) {
                    if (finalNumbers.indexOf(n) < 0) finalNumbers.push(n);
                });
                if (finalNumbers.length > 0) {
                    products.push({product_id: p.product_id, numbers: finalNumbers});
                }
            });
            if (products.length > 0) {
                submitItems.push({row_index: it.row_index, products: products});
            }
        }

        if (!submitItems.length) {
            layer.msg('没有可更新的数据，请勾选需要上传的行', {icon: 2});
            return;
        }

        confirmBtn.disabled = true;
        var enableBtn = function () {
            confirmBtn.disabled = false;
            updateConfirmBtnState();
        };
        var loadingIndex = layer.load(1, { shade: [0.1, '#fff'] });
        fetch('/api/excel/async/replace_number_confirm', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                check_task_id: rnCheckTaskId,
                items: submitItems
            })
        })
        .then(response => response.json())
        .then(result => {
            if (result.code !== 0) {
                layer.close(loadingIndex);
                enableBtn();
                layer.msg('提交失败: ' + result.msg, {icon: 2});
                return;
            }

            var taskId = result.data.task_id;
            layer.msg('任务已提交，处理中...', {icon: 1});

            var progressLayerIndex = createProgressLayer('rnUpdateProgressContent', 'rnUpdateProgressText');
            pollExcelTask(taskId, loadingIndex, progressLayerIndex, 'rnUpdateProgressText', function (tId, resultData) {
                currentTaskId = tId;
                currentTaskData = resultData || {};
                document.getElementById('rnCheckArea').style.display = 'none';
                // 处理完成：退出核对阶段，按钮恢复"开始处理"（需重置后重新走流程）
                rnStage = '';
                rnCheckItems = [];
                enableBtn();
                var sc = currentTaskData.success_count || 0;
                var fc = currentTaskData.fail_count || 0;
                document.getElementById('replaceNumberResultMsg').textContent = '处理完成：成功 ' + sc + ' 行，失败 ' + fc + ' 行';
                document.getElementById('replaceNumberResultArea').style.display = 'block';
            }, enableBtn);
        })
        .catch(error => {
            layer.close(loadingIndex);
            enableBtn();
            layer.msg('提交失败: ' + error.message, {icon: 2});
        });
    }

    // ====== 同步处理函数（对账/单据） ======
    function handleSyncProcess(formData, loadingIndex, processType, files) {
        var apiUrl = '/api/process_bill';

        fetch(apiUrl, {
            method: 'POST',
            body: formData
        })
        .then(response => response.blob())
        .then(blob => {
            layer.close(loadingIndex);

            var url = window.URL.createObjectURL(blob);
            var a = document.createElement('a');
            a.href = url;

            if (processType === 'order') {
                a.download = 'Processed_Orders_' + new Date().getTime() + '.zip';
            } else {
                if (files.length > 1) {
                    a.download = 'processed_bills.zip';
                } else {
                    a.download = files[0].name.replace(/\.[^/.]+$/, "") + '_已处理.xlsx';
                }
            }

            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);

            if (processType === 'order') {
                layer.msg('单据处理完成并已下载', {icon: 1});
            } else {
                layer.msg('对账单处理完成并已下载', {icon: 1});
            }
        })
        .catch(error => {
            layer.close(loadingIndex);
            layer.msg('处理失败: ' + error.message, {icon: 2});
        });
    }
});
