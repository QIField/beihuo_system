/**
 * 修理厂询价单 · 数据采集弹窗
 *
 * 流程：选择日期 + 粘贴 cookie -> 提交后台爬取任务 -> 轮询进度 -> 展示结果
 * cookie 仅随请求提交，不在前端保存
 */
(function () {
    'use strict';

    var pollTimer = null;
    var taskId = null;

    function $(id) { return document.getElementById(id); }

    function open() {
        $('crawlMask').style.display = 'flex';
    }

    function close() {
        $('crawlMask').style.display = 'none';
        stopPolling();
    }

    function stopPolling() {
        if (pollTimer) {
            clearInterval(pollTimer);
            pollTimer = null;
        }
    }

    function startCrawl() {
        var startDate = $('crawlStartDate').value.trim();
        var endDate = $('crawlEndDate').value.trim();
        var cookie = $('crawlCookie').value.trim();
        if (!startDate || !endDate || !cookie) {
            showResult('请填写开始日期、结束日期与 Cookie', 'error');
            return;
        }

        $('crawlStartBtn').disabled = true;
        hideResult();
        $('crawlProgress').style.display = 'block';
        $('crawlProgressText').textContent = '任务提交中...';
        $('crawlProgressBar').style.width = '0';
        $('crawlFailedList').innerHTML = '';

        fetch('/api/cass_inquiry/crawl/start', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ start_date: startDate, end_date: endDate, cookie: cookie })
        })
            .then(function (resp) { return resp.json(); })
            .then(function (result) {
                if (result.code !== 0) {
                    throw new Error(result.msg || '任务启动失败');
                }
                taskId = result.data.task_id;
                pollTimer = setInterval(pollStatus, 1500);
            })
            .catch(function (err) {
                $('crawlStartBtn').disabled = false;
                $('crawlProgress').style.display = 'none';
                showResult('启动失败：' + err.message, 'error');
            });
    }

    function pollStatus() {
        fetch('/api/cass_inquiry/crawl/status?task_id=' + encodeURIComponent(taskId), {
            credentials: 'same-origin'
        })
            .then(function (resp) { return resp.json(); })
            .then(function (result) {
                if (result.code !== 0) {
                    throw new Error(result.msg || '查询进度失败');
                }
                renderProgress(result.data);
                if (result.data.status === 'done') {
                    stopPolling();
                    $('crawlStartBtn').disabled = false;
                    renderDoneResult(result.data);
                } else if (result.data.status === 'failed') {
                    stopPolling();
                    $('crawlStartBtn').disabled = false;
                    showResult('采集失败：' + (result.data.error || '未知错误'), 'error');
                }
            })
            .catch(function (err) {
                stopPolling();
                $('crawlStartBtn').disabled = false;
                showResult('进度查询失败：' + err.message, 'error');
            });
    }

    function renderProgress(job) {
        var parts = ['状态：采集中'];
        if (job.total_pages > 0) {
            parts.push('第 ' + job.page + '/' + job.total_pages + ' 页');
        }
        parts.push('已处理询单 ' + job.inquiry_done + ' 个');
        parts.push('已解析报价行 ' + job.rows_collected + ' 条');
        if (job.rows_saved > 0) {
            parts.push('已入库 ' + job.rows_saved + ' 条');
        }
        if (job.failed && job.failed.length > 0) {
            parts.push('异常 ' + job.failed.length + ' 个');
        }
        $('crawlProgressText').textContent = parts.join('，');

        var percent = 0;
        if (job.total_pages > 0 && job.page > 0) {
            percent = Math.min(100, Math.round(job.page / job.total_pages * 100));
        }
        $('crawlProgressBar').style.width = percent + '%';

        renderFailedList(job);
    }

    function renderFailedList(job) {
        if (!job.failed || job.failed.length === 0) {
            $('crawlFailedList').innerHTML = '';
            return;
        }
        var lines = job.failed.slice(0, 20).map(function (item) {
            return '询单 ' + item.inquiryid + '：' + item.error;
        });
        if (job.failed.length > 20) {
            lines.push('...等共 ' + job.failed.length + ' 条');
        }
        $('crawlFailedList').innerHTML = lines.join('<br>');
    }

    function renderDoneResult(job) {
        var result = job.result || {};
        var text = '采集完成：解析报价行 ' + result.rows_collected + ' 条，入库 ' +
            result.rows_saved + ' 条（重复行已按最新数据更新）';
        if (result.failed_count > 0) {
            text += '；异常询单 ' + result.failed_count + ' 个（明细见上方列表）';
        }
        showResult(text, 'success');
        renderFailedList(job);
    }

    function showResult(text, type) {
        var el = $('crawlResult');
        el.style.display = 'block';
        el.className = 'crawl-result ' + (type === 'error' ? 'error' : 'success');
        el.textContent = text;
    }

    function hideResult() {
        $('crawlResult').style.display = 'none';
    }

    document.addEventListener('DOMContentLoaded', function () {
        $('crawlDialogBtn').addEventListener('click', open);
        $('crawlCloseBtn').addEventListener('click', close);
        $('crawlStartBtn').addEventListener('click', startCrawl);
        $('crawlMask').addEventListener('click', function (e) {
            if (e.target === this) { close(); }  // 点击遮罩关闭
        });
    });
})();
