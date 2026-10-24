/**
 * 修理厂询价单 · CRM 产品开思价修改弹窗
 *
 * 入口：商家替换号列蓝色链接（供应商为佛山巴博瑞汽配的行）点击触发
 * 流程：按替换号调 /api/cass_inquiry/crm_products 搜索 → 弹窗表格
 *       （勾选 / OE号 / 品牌 / 产品名 / 开思价可编辑 / 成本价只读）
 *       → 保存时仅提交"勾选且改价"的行 → 逐行回显更新结果
 * product_id 仅存于本模块数据缓存，不渲染到表格
 */
var CassPriceEditDialog = (function () {
    'use strict';

    var products = [];      // 弹窗数据缓存（含 product_id）
    var layerIndex = null;
    var submitting = false;

    function escapeHtml(text) {
        return String(text === null || text === undefined ? '' : text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    /** 价格规范化：剥离货币符号/千分位/空白，须为大于0的数字，非法返回 null */
    function normalizePrice(value) {
        var text = String(value === null || value === undefined ? '' : value)
            .replace(/[¥￥\s,，]/g, '');
        if (!text) return null;
        var num = Number(text);
        return (isFinite(num) && num > 0) ? num : null;
    }

    function findByPid(pid) {
        for (var i = 0; i < products.length; i++) {
            if (String(products[i].product_id) === String(pid)) return products[i];
        }
        return null;
    }

    function fetchProducts(replacement, onDone, onFail) {
        fetch('/api/cass_inquiry/crm_products?replacement=' + encodeURIComponent(replacement), {
            method: 'GET',
            credentials: 'same-origin'
        })
            .then(function (resp) { return resp.json(); })
            .then(function (result) {
                if (result && result.code === 0) onDone(result.data.list || []);
                else onFail((result && result.msg) || 'CRM 搜索失败');
            })
            .catch(function () { onFail('网络异常，CRM 搜索失败'); });
    }

    function buildRowHtml(p) {
        var price = (p.store_cass_price === null || p.store_cass_price === undefined) ? '' : p.store_cass_price;
        var cost = (p.cost_price === null || p.cost_price === undefined) ? '' : p.cost_price;
        return '<tr data-pid="' + escapeHtml(p.product_id) + '">' +
            '<td class="cass-col-check"><input type="checkbox" class="cass-row-check"></td>' +
            '<td class="cass-col-oe" title="' + escapeHtml(p.number) + '">' + escapeHtml(p.number) + '</td>' +
            '<td class="cass-col-brand" title="' + escapeHtml(p.brand_name) + '">' + escapeHtml(p.brand_name) + '</td>' +
            '<td class="cass-col-name" title="' + escapeHtml(p.l_name_zh) + '">' + escapeHtml(p.l_name_zh) + '</td>' +
            '<td class="cass-col-input"><input type="text" class="cass-price-input" value="' + escapeHtml(price) + '"></td>' +
            '<td class="cass-col-cost">' + escapeHtml(cost) + '</td>' +
            '<td class="cass-col-status">—</td>' +
            '</tr>';
    }

    function buildContentHtml() {
        var rows = products.map(buildRowHtml).join('');
        return '<div class="cass-price-dialog">' +
            '<div class="cass-price-tip">勾选要修改的产品并改动开思价，再点"保存修改"；只勾选未改价的行不会提交。</div>' +
            '<table class="cass-price-table">' +
            '<thead><tr>' +
            '<th class="cass-col-check"><input type="checkbox" id="cassCheckAll"></th>' +
            '<th class="cass-col-oe">OE号</th>' +
            '<th class="cass-col-brand">品牌</th>' +
            '<th class="cass-col-name">产品名</th>' +
            '<th class="cass-col-input">开思价</th>' +
            '<th class="cass-col-cost">成本价</th>' +
            '<th class="cass-col-status">更新结果</th>' +
            '</tr></thead>' +
            '<tbody>' + rows + '</tbody>' +
            '</table>' +
            '<div class="cass-price-actions">' +
            '<button type="button" class="cass-save-btn" id="cassSaveBtn">保存修改</button>' +
            '</div>' +
            '</div>';
    }

    function setRowStatus(tr, type, text) {
        var cell = tr.querySelector('.cass-col-status');
        if (!cell) return;
        cell.textContent = text || '—';
        cell.className = 'cass-col-status' + (type ? ' cass-status-' + type : '');
    }

    function renderDialog(replacement) {
        if (layerIndex !== null) layui.layer.close(layerIndex);
        layerIndex = layui.layer.open({
            type: 1,
            title: 'CRM 产品开思价修改（替换号：' + escapeHtml(replacement) + '）',
            area: ['960px'],
            shade: 0.3,
            content: buildContentHtml()
        });
        bindDialogEvents();
    }

    function bindDialogEvents() {
        var root = document.querySelector('.cass-price-dialog');
        if (!root) return;

        var checkAll = root.querySelector('#cassCheckAll');
        checkAll.addEventListener('change', function () {
            var boxes = root.querySelectorAll('.cass-row-check');
            Array.prototype.forEach.call(boxes, function (box) { box.checked = checkAll.checked; });
        });

        root.querySelector('#cassSaveBtn').addEventListener('click', function () { save(root); });
    }

    /** 收集"勾选且改价"的行；未勾选或未改价（含改回原值）的行不提交 */
    function collectPending(root) {
        var pending = [];
        var rows = root.querySelectorAll('tbody tr');
        Array.prototype.forEach.call(rows, function (tr) {
            var box = tr.querySelector('.cass-row-check');
            if (!box || !box.checked) return;

            var product = findByPid(tr.getAttribute('data-pid'));
            var input = tr.querySelector('.cass-price-input');
            var newValue = normalizePrice(input.value);
            var originalValue = product ? normalizePrice(product.store_cass_price) : null;

            if (newValue === null) {
                setRowStatus(tr, 'failed', '开思价须为大于0的数字');
                return;
            }
            if (originalValue !== null && newValue === originalValue) {
                setRowStatus(tr, 'skipped', '未修改，跳过');
                return;
            }
            pending.push({
                item: { product_id: tr.getAttribute('data-pid'), store_cass_price: newValue },
                row: tr,
                newValue: newValue
            });
        });
        return pending;
    }

    function save(root) {
        if (submitting) return;

        var pending = collectPending(root);
        if (!pending.length) {
            layui.layer.msg('没有需要更新的行（仅提交勾选且改了价的行）', { icon: 0 });
            return;
        }

        var saveBtn = root.querySelector('#cassSaveBtn');
        submitting = true;
        saveBtn.disabled = true;
        pending.forEach(function (p) { setRowStatus(p.row, 'skipped', '提交中...'); });

        fetch('/api/cass_inquiry/update_price', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(pending.map(function (p) { return p.item; }))
        })
            .then(function (resp) { return resp.json(); })
            .then(function (result) {
                submitting = false;
                saveBtn.disabled = false;
                if (!result || result.code !== 0) {
                    layui.layer.msg((result && result.msg) || '更新失败', { icon: 2 });
                    pending.forEach(function (p) { setRowStatus(p.row, 'failed', '更新失败'); });
                    return;
                }
                applyResults(pending, result.data ? (result.data.results || []) : []);
            })
            .catch(function () {
                submitting = false;
                saveBtn.disabled = false;
                pending.forEach(function (p) { setRowStatus(p.row, 'failed', '网络异常，更新失败'); });
            });
    }

    /** 逐行回显更新结果（results 与提交 items 顺序一致），成功后同步数据缓存 */
    function applyResults(pending, results) {
        var updated = 0, failed = 0;
        pending.forEach(function (p, i) {
            var r = results[i];
            if (r && r.success) {
                updated++;
                setRowStatus(p.row, 'updated', r.msg || '开思价已更新');
                var product = findByPid(p.item.product_id);
                if (product) product.store_cass_price = p.newValue;
            } else {
                failed++;
                setRowStatus(p.row, 'failed', (r && r.msg) || '更新失败');
            }
        });
        layui.layer.msg('更新完成：成功 ' + updated + ' 行，失败 ' + failed + ' 行', { icon: failed ? 0 : 1 });
    }

    function open(replacement) {
        var loading = layui.layer.msg('正在查询 CRM 产品...', { icon: 16, shade: 0.3, time: 0 });
        fetchProducts(replacement, function (list) {
            layui.layer.close(loading);
            if (!list.length) {
                layui.layer.msg('替换号 ' + replacement + ' 未匹配到 CRM 产品', { icon: 0 });
                return;
            }
            products = list;
            renderDialog(replacement);
        }, function (msg) {
            layui.layer.close(loading);
            layui.layer.msg(msg, { icon: 2 });
        });
    }

    // 商家替换号蓝色链接点击（document 级事件委托，表格侧无需重复绑定）
    document.addEventListener('click', function (e) {
        var link = e.target && e.target.closest ? e.target.closest('.cass-replacement-link') : null;
        if (!link) return;
        var replacement = (link.getAttribute('data-replacement') || '').trim();
        if (replacement) open(replacement);
    });

    return { open: open };
})();
