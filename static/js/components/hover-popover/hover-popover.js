/**
 * HoverPopover 通用悬停浮窗（全局单例）
 *
 * 设计原则：
 * - 机制与业务分离：本文件只管单例互斥、定位、延迟、事件委托；
 *   浮窗内容由通过 register() 注册的 Provider 生成（可同步或异步）。
 * - 物理单例：body 下只有一个浮层元素，任何 show() 先执行 hide()，
 *   因此全局同一时刻最多只能存在一个浮窗，无需各页面自行互斥。
 * - 触发元素只打标记（class="hp-trigger" data-popover="类型" data-*），
 *   document 级事件委托只绑定一次，表格翻页 / 重渲染无需重新绑定。
 *
 * Provider 契约：{ content(anchor): string | Promise<string> }
 */
(function (global) {
    'use strict';

    var SHOW_DELAY = 150;   // 悬停多久后显示（防快速划动误触）
    var HIDE_DELAY = 200;   // 离开后延迟隐藏（允许鼠标移入浮窗）
    var GAP = 5;            // 浮窗与单元格间距
    var MARGIN = 10;        // 浮窗与视口边缘最小间距

    var el = null;          // 单例浮层 DOM
    var contentEl = null;   // 内容容器
    var providers = {};     // type -> provider
    var initialized = false;

    // 当前浮窗状态；token 用于丢弃过期的异步内容
    var state = {
        anchor: null,
        showTimer: null,
        hideTimer: null,
        token: 0
    };

    /**
     * 创建全局唯一浮层（只创建一次）
     */
    function ensureElement() {
        if (el) return el;

        el = document.createElement('div');
        el.className = 'hp-popover';
        el.setAttribute('role', 'tooltip');
        contentEl = document.createElement('div');
        contentEl.className = 'hp-popover-content';
        el.appendChild(contentEl);
        document.body.appendChild(el);
        return el;
    }

    /**
     * 注册内容提供者
     * @param {string} type 浮窗类型，对应 data-popover
     * @param {{content: function(HTMLElement): (string|Promise<string>)}} provider
     */
    function register(type, provider) {
        providers[type] = provider;
    }

    function clearTimers() {
        if (state.showTimer) {
            clearTimeout(state.showTimer);
            state.showTimer = null;
        }
        if (state.hideTimer) {
            clearTimeout(state.hideTimer);
            state.hideTimer = null;
        }
    }

    /**
     * 立即隐藏浮窗并作废进行中的异步内容
     */
    function hide() {
        clearTimers();
        state.token++;
        state.anchor = null;
        if (el) {
            el.style.display = 'none';
            contentEl.innerHTML = '';
        }
    }

    function scheduleHide() {
        if (state.showTimer) {
            clearTimeout(state.showTimer);
            state.showTimer = null;
        }
        if (state.hideTimer) clearTimeout(state.hideTimer);
        state.hideTimer = setTimeout(hide, HIDE_DELAY);
    }

    /**
     * 视口边界检测：下方优先，空间不足翻上方，水平方向夹紧
     */
    function position(anchor) {
        var rect = anchor.getBoundingClientRect();
        var width = el.offsetWidth;
        var height = el.offsetHeight;
        var viewportWidth = global.innerWidth || document.documentElement.clientWidth;
        var viewportHeight = global.innerHeight || document.documentElement.clientHeight;

        var left = rect.left;
        if (left + width > viewportWidth - MARGIN) {
            left = viewportWidth - width - MARGIN;
        }
        if (left < MARGIN) left = MARGIN;

        var top;
        if (rect.bottom + GAP + height <= viewportHeight - MARGIN) {
            top = rect.bottom + GAP;                 // 下方放得下
        } else if (rect.top - GAP - height >= MARGIN) {
            top = rect.top - GAP - height;           // 下方放不下、上方放得下
        } else {
            top = Math.max(MARGIN, viewportHeight - height - MARGIN); // 两侧都紧张
        }

        el.style.left = left + 'px';
        el.style.top = top + 'px';
    }

    /**
     * 在指定锚点单元格上显示浮窗
     */
    function show(anchor) {
        var type = anchor.getAttribute('data-popover');
        var provider = providers[type];
        if (!provider) return;

        ensureElement();
        hide();                          // 单例互斥：先关闭任何已显示的浮窗

        state.anchor = anchor;
        var token = state.token;

        // 同步 / 异步内容统一走 Promise；异步返回时校验 token 防止串内容
        Promise.resolve()
            .then(function () {
                return provider.content(anchor);
            })
            .then(function (html) {
                if (state.token !== token || state.anchor !== anchor) return;
                contentEl.innerHTML = html || '<div class="hp-empty">暂无信息</div>';
                el.style.visibility = 'hidden';
                el.style.display = 'block';
                position(anchor);
                el.style.visibility = '';
            })
            .catch(function () {
                if (state.token !== token || state.anchor !== anchor) return;
                contentEl.innerHTML = '<div class="hp-empty">加载失败</div>';
                el.style.display = 'block';
                position(anchor);
            });
    }

    function scheduleShow(anchor) {
        if (state.hideTimer) {
            clearTimeout(state.hideTimer);
            state.hideTimer = null;
        }
        if (state.showTimer) clearTimeout(state.showTimer);
        state.showTimer = setTimeout(function () {
            state.showTimer = null;
            show(anchor);
        }, SHOW_DELAY);
    }

    /**
     * 事件委托：mouseover/mouseout 冒泡，配合 relatedTarget 判定悬停去向
     */
    function onMouseOver(e) {
        var trigger = e.target.closest ? e.target.closest('.hp-trigger') : null;

        if (trigger) {
            // 已在显示同一单元格 / 正在其上方移动：不重启定时器
            if (state.anchor === trigger && el && el.style.display === 'block') return;
            scheduleShow(trigger);
            return;
        }

        // 鼠标移入浮窗本身：取消关闭
        if (el && el.contains(e.target)) {
            if (state.hideTimer) {
                clearTimeout(state.hideTimer);
                state.hideTimer = null;
            }
        }
    }

    function onMouseOut(e) {
        var related = e.relatedTarget;

        // 移向浮窗内部或仍在当前触发单元格内：不关闭
        if (related && el && el.contains(related)) return;
        if (related && state.anchor && state.anchor.contains(related)) return;
        if (related && related.closest && related.closest('.hp-trigger') === state.anchor) return;

        scheduleHide();
    }

    function init() {
        if (initialized) return;
        initialized = true;
        ensureElement();

        document.addEventListener('mouseover', onMouseOver, false);
        document.addEventListener('mouseout', onMouseOut, false);

        // 任意容器滚动（事件不冒泡，用捕获阶段）、窗口缩放、ESC 均关闭，避免浮层悬空
        document.addEventListener('scroll', hide, true);
        global.addEventListener('resize', hide);
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') hide();
        });
    }

    /* ---------------- 触发元素构建工具（供各表格框架使用） ---------------- */

    function escapeHtml(value) {
        return String(value == null ? '' : value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    /**
     * 构建触发单元格 HTML（Layui templet 等返回 HTML 字符串的场景）
     * @param {string} type 浮窗类型
     * @param {Object} attrs 数据属性（自动加 data- 前缀），值会做 HTML 转义
     * @param {string} text 单元格显示文本
     * @returns {string} 空文本返回空字符串（无浮窗）
     */
    function triggerHtml(type, attrs, text) {
        if (!text) return '';
        var html = '<span class="hp-trigger" data-popover="' + escapeHtml(type) + '"';
        for (var key in attrs) {
            if (attrs[key] === undefined || attrs[key] === null || attrs[key] === '') continue;
            html += ' data-' + key + '="' + escapeHtml(attrs[key]) + '"';
        }
        return html + '>' + escapeHtml(text) + '</span>';
    }

    /**
     * 构建触发单元格 DOM（ag-grid cellRenderer 等需要 DOM 节点的场景）
     */
    function createTrigger(type, attrs, text) {
        var wrapper = document.createElement('div');
        wrapper.innerHTML = triggerHtml(type, attrs, text);
        return wrapper.firstChild || document.createTextNode('');
    }

    // 暴露 API
    global.HoverPopover = {
        init: init,
        register: register,
        show: show,
        hide: hide,
        triggerHtml: triggerHtml,
        createTrigger: createTrigger,
        escapeHtml: escapeHtml
    };

    // 脚本加载即初始化（DOM 未就绪时等待）
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})(window);
