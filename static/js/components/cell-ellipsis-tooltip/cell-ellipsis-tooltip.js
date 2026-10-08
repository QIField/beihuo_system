/**
 * 单元格省略号原生 Tooltip
 *
 * 仅当单元格内容真实溢出（出现省略号 / 被裁切）时，
 * 通过 mouseover 事件委托按需设置原生 title 展示完整内容。
 *
 * 设计要点：
 * - 事件委托：只在容器上绑定一次，翻页 / 虚拟滚动 / 重渲染无需重绑；
 * - 每次悬停实时校正 title，虚拟滚动复用单元格 DOM 时不会残留旧值；
 * - 不接管已有自定义悬停浮窗（.hp-trigger）及按钮、输入框等交互元素；
 * - 水平溢出（scrollWidth）与垂直溢出（scrollHeight，如两行销量列）均支持。
 */
(function (global) {
    'use strict';

    var TOLERANCE = 1; // 溢出判定容差（px），避免边框/取整误差误判

    // 不接管的交互元素：按钮、输入控件等
    var INTERACTIVE_SELECTOR = [
        'button',
        'input',
        'a',
        'select',
        'textarea',
        'label',
        '.layui-form-checkbox',
        '.layui-form-switch'
    ].join(',');

    // 防止同一容器重复绑定
    var boundContainers = new WeakSet();

    /**
     * 判断元素内容是否被裁切
     * @param {HTMLElement} el
     * @returns {boolean}
     */
    function isOverflowing(el) {
        return el.scrollWidth > el.clientWidth + TOLERANCE ||
               el.scrollHeight > el.clientHeight + TOLERANCE;
    }

    /**
     * mouseover 委托处理：实时校正当前单元格的 title
     * @param {Event} e
     * @param {string} cellSelector 目标单元格选择器
     */
    function handleMouseOver(e, cellSelector) {
        var target = e.target;
        if (!(target instanceof Element)) return;

        // 命中按钮、输入控件等交互元素时不接管
        if (target.closest(INTERACTIVE_SELECTOR)) return;

        var cell = target.closest(cellSelector);
        if (!cell) return;

        // 该单元格已带自定义悬停浮窗（供应商、在途明细等 .hp-trigger 列）：
        // 触发器只是格内 span，鼠标可能停在内边距区，故按整格排除
        if (cell.classList.contains('hp-trigger') || cell.querySelector('.hp-trigger')) return;

        if (!isOverflowing(cell)) {
            // 未溢出：移除 title（含渲染器预置的无条件 title）
            cell.removeAttribute('title');
            return;
        }

        var text = (cell.innerText || cell.textContent || '').trim();
        if (!text) {
            cell.removeAttribute('title');
            return;
        }

        // 溢出：每次实时校正，避免虚拟滚动复用 DOM 后残留旧值
        if (cell.getAttribute('title') !== text) {
            cell.setAttribute('title', text);
        }
    }

    /**
     * 在表格容器上启用省略号原生 tooltip
     * @param {HTMLElement|string} container 容器元素或选择器
     * @param {string} cellSelector 目标单元格选择器（如 '.layui-table-cell'）
     */
    function bind(container, cellSelector) {
        var el = typeof container === 'string'
            ? document.querySelector(container)
            : container;
        if (!el || boundContainers.has(el)) return;

        boundContainers.add(el);
        el.addEventListener('mouseover', function (e) {
            handleMouseOver(e, cellSelector);
        });
    }

    global.CellEllipsisTooltip = {
        bind: bind
    };
})(window);
