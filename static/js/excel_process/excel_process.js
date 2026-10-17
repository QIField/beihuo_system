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

    // ====== 重置：清空当前功能已选文件并隐藏结果区 ======
    document.getElementById('epResetBtn').addEventListener('click', function () {
        tabFiles[currentTab] = [];
        var input = document.getElementById(getFileInputId(currentTab));
        if (input) {
            input.value = '';
        }
        document.getElementById('crmResultArea').style.display = 'none';
        document.getElementById('replaceNumberResultArea').style.display = 'none';
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

        // 隐藏上次 CRM 结果
        document.getElementById('crmResultArea').style.display = 'none';
        document.getElementById('replaceNumberResultArea').style.display = 'none';
        currentTaskId = null;
        currentTaskData = null;

        // 显示处理进度
        var processLoading = layer.load(1, { shade: [0.1, '#fff'] });

        if (currentTab === 'crm') {
            handleCrmAsyncProcess(formData, processLoading, '/api/excel/async/product_archive', function (taskId, resultData) {
                currentTaskId = taskId;
                currentTaskData = resultData || {};
                var sc = currentTaskData.success_count || 0;
                var fc = currentTaskData.fail_count || 0;
                document.getElementById('crmResultMsg').textContent = '处理完成：成功 ' + sc + ' 条，失败 ' + fc + ' 条';
                document.getElementById('crmResultArea').style.display = 'block';
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

    // 查看替换号差异：将新建成功或已存在的 OE+品牌 传入替换号编辑页面
    document.getElementById('crmDiffBtn').addEventListener('click', function () {
        var oeBrandList = currentTaskData && currentTaskData.oe_brand_list;
        if (oeBrandList && oeBrandList.length > 0) {
            sessionStorage.setItem('replace_number_oe_brand_list', JSON.stringify(oeBrandList));
            window.open('/replace_number_edit', '_blank');
        } else {
            layer.msg('没有可查看替换号的成功/已存在数据', {icon: 2});
        }
    });

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

            // 创建进度提示层（使用固定 DOM，避免闪烁）
            var progressLayerIndex = layer.open({
                type: 1,
                title: false,
                closeBtn: 0,
                shade: 0.3,
                area: ['280px', '100px'],
                content: '<div id="crmProgressContent" style="padding: 28px 0; text-align: center; font-size: 14px;"><i class="layui-icon layui-icon-loading layui-anim layui-anim-rotate layui-anim-loop"></i> <span id="crmProgressText">初始化中...</span></div>'
            });

            // 步骤2：轮询查询任务状态
            var pollCount = 0;
            var maxPollCount = 900; // 最多轮询 900 次，约 30 分钟
            var checkInterval = setInterval(function () {
                pollCount++;
                if (pollCount > maxPollCount) {
                    clearInterval(checkInterval);
                    layer.close(loadingIndex);
                    layer.close(progressLayerIndex);
                    layer.msg('处理超时，请稍后重试', {icon: 2});
                    return;
                }

                fetch('/api/excel/async/status/' + taskId)
                .then(response => response.json())
                .then(statusResult => {
                    if (statusResult.code !== 0) {
                        clearInterval(checkInterval);
                        layer.close(loadingIndex);
                        layer.close(progressLayerIndex);
                        layer.msg('查询状态失败: ' + statusResult.msg, {icon: 2});
                        return;
                    }

                    var status = statusResult.data;

                    if (status.status === 'running') {
                        // 更新进度提示
                        var progress = status.progress || 0;
                        var total = status.total || 0;
                        var message = status.message || '处理中...';

                        var displayMsg;
                        if (progress === 0 && total === 0) {
                            displayMsg = '初始化中...';
                        } else {
                            displayMsg = '处理中: ' + progress + '/' + total + ' - ' + message;
                        }

                        var progressText = document.getElementById('crmProgressText');
                        if (progressText) {
                            progressText.textContent = displayMsg;
                        }
                    } else if (status.status === 'completed') {
                        // 任务完成
                        clearInterval(checkInterval);
                        layer.close(loadingIndex);
                        layer.close(progressLayerIndex);

                        // 如果有完成回调，把 taskId 和 result_data 传出去
                        if (typeof onComplete === 'function') {
                            onComplete(taskId, status.result_data);
                            layer.msg('处理完成', {icon: 1});
                        } else {
                            layer.msg('处理完成，开始下载...', {icon: 1});
                            // 下载结果文件
                            window.location.href = '/api/excel/async/download/' + taskId;
                        }
                    } else if (status.status === 'failed') {
                        // 任务失败
                        clearInterval(checkInterval);
                        layer.close(loadingIndex);
                        layer.close(progressLayerIndex);
                        layer.msg('处理失败: ' + (status.error || '未知错误'), {icon: 2});
                    }
                })
                .catch(error => {
                    clearInterval(checkInterval);
                    layer.close(loadingIndex);
                    layer.close(progressLayerIndex);
                    layer.msg('查询状态失败: ' + error.message, {icon: 2});
                });
            }, 2000); // 每2秒查询一次
        })
        .catch(error => {
            layer.close(loadingIndex);
            layer.msg('提交失败: ' + error.message, {icon: 2});
        });
    }

    // ====== 更新替换号处理函数 ======
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

            if (mode === 'compare') {
                layer.close(loadingIndex);
                if (result.data && result.data.oe_brand_list) {
                    sessionStorage.setItem('replace_number_oe_brand_list', JSON.stringify(result.data.oe_brand_list));
                }
                layer.msg('已跳转到替换号编辑页面', {icon: 1});
                window.open('/replace_number_edit', '_blank');
                return;
            }

            // direct 模式：轮询下载
            var taskId = result.data.task_id;
            currentTaskId = taskId;
            layer.msg('任务已提交，处理中...', {icon: 1});

            var progressLayerIndex = layer.open({
                type: 1,
                title: false,
                closeBtn: 0,
                shade: 0.3,
                area: ['280px', '100px'],
                content: '<div id="rnProgressContent" style="padding: 28px 0; text-align: center; font-size: 14px;"><i class="layui-icon layui-icon-loading layui-anim layui-anim-rotate layui-anim-loop"></i> <span id="rnProgressText">初始化中...</span></div>'
            });

            var pollCount = 0;
            var maxPollCount = 900;
            var checkInterval = setInterval(function () {
                pollCount++;
                if (pollCount > maxPollCount) {
                    clearInterval(checkInterval);
                    layer.close(progressLayerIndex);
                    layer.msg('处理超时，请稍后重试', {icon: 2});
                    return;
                }

                fetch('/api/excel/async/status/' + taskId)
                .then(response => response.json())
                .then(statusResult => {
                    if (statusResult.code !== 0) {
                        clearInterval(checkInterval);
                        layer.close(progressLayerIndex);
                        layer.msg('查询状态失败: ' + statusResult.msg, {icon: 2});
                        return;
                    }

                    var status = statusResult.data;
                    if (status.status === 'running') {
                        var progress = status.progress || 0;
                        var total = status.total || 0;
                        var message = status.message || '处理中...';
                        var displayMsg = (progress === 0 && total === 0) ? '初始化中...' : '处理中: ' + progress + '/' + total + ' - ' + message;
                        var progressText = document.getElementById('rnProgressText');
                        if (progressText) {
                            progressText.textContent = displayMsg;
                        }
                    } else if (status.status === 'completed') {
                        clearInterval(checkInterval);
                        layer.close(progressLayerIndex);
                        layer.close(loadingIndex);
                        document.getElementById('replaceNumberResultMsg').textContent = '处理完成，请下载结果文件';
                        document.getElementById('replaceNumberResultArea').style.display = 'block';
                        layer.msg('处理完成', {icon: 1});
                    } else if (status.status === 'failed') {
                        clearInterval(checkInterval);
                        layer.close(progressLayerIndex);
                        layer.close(loadingIndex);
                        layer.msg('处理失败: ' + (status.error || '未知错误'), {icon: 2});
                    }
                })
                .catch(error => {
                    clearInterval(checkInterval);
                    layer.close(progressLayerIndex);
                    layer.close(loadingIndex);
                    layer.msg('查询状态失败: ' + error.message, {icon: 2});
                });
            }, 2000);
        })
        .catch(error => {
            layer.close(loadingIndex);
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
