/**
 * TabNav 通用标签导航组件
 *
 * 使用方式：
 * 1. 引入 tab-nav.css 和 tab-nav.js
 * 2. HTML结构：
 *    <div class="tab-nav" id="myTabNav">
 *        <div class="tab-title">页面标题</div>
 *        <button class="tab-btn active" data-tab="tab1">标签1</button>
 *        <button class="tab-btn" data-tab="tab2">标签2</button>
 *    </div>
 *    <div class="tab-content">
 *        <div id="tab-tab1" class="tab-pane active">内容1</div>
 *        <div id="tab-tab2" class="tab-pane">内容2</div>
 *    </div>
 * 3. JS初始化：
 *    const tabNav = TabNav.init({
 *        navSelector: '#myTabNav',
 *        contentSelector: '.tab-content',
 *        onSwitch: function(tabId, prevTabId) { console.log(tabId); }
 *    });
 */
const TabNav = {
    /**
     * 初始化标签导航
     * @param {Object} options 配置选项
     * @param {string} options.navSelector 标签导航容器选择器
     * @param {string} options.contentSelector 内容容器选择器
     * @param {string} [options.activeClass='active'] 激活状态类名
     * @param {string} [options.tabPrefix='tab-'] 内容面板ID前缀
     * @param {Function} [options.onSwitch] 切换回调 (tabId, prevTabId) => void
     * @returns {Object|null} 组件实例
     */
    init: function(options) {
        const navContainer = document.querySelector(options.navSelector);
        const contentContainer = document.querySelector(options.contentSelector);

        if (!navContainer) {
            console.error('[TabNav] 导航容器未找到:', options.navSelector);
            return null;
        }

        const activeClass = options.activeClass || 'active';
        const tabPrefix = options.tabPrefix || 'tab-';

        const instance = {
            navContainer: navContainer,
            contentContainer: contentContainer,
            currentTab: null,
            activeClass: activeClass,

            /**
             * 切换到指定标签
             * @param {string} tabId 标签ID
             */
            switchTo: function(tabId) {
                const prevTab = this.currentTab;

                // 更新按钮状态
                const buttons = this.navContainer.querySelectorAll('.tab-btn');
                buttons.forEach(function(btn) {
                    const isTarget = btn.dataset.tab === tabId;
                    btn.classList.toggle(activeClass, isTarget);
                });

                // 更新内容显示
                if (this.contentContainer) {
                    const panes = this.contentContainer.querySelectorAll('.tab-pane');
                    panes.forEach(function(pane) {
                        pane.classList.remove(activeClass);
                    });

                    const targetPane = document.getElementById(tabPrefix + tabId);
                    if (targetPane) {
                        targetPane.classList.add(activeClass);
                    }
                }

                this.currentTab = tabId;

                // 触发回调
                if (typeof options.onSwitch === 'function') {
                    options.onSwitch(tabId, prevTab);
                }
            },

            /**
             * 获取当前激活的标签ID
             * @returns {string|null}
             */
            getActiveTab: function() {
                return this.currentTab;
            },

            /**
             * 获取所有标签按钮
             * @returns {NodeList}
             */
            getTabs: function() {
                return this.navContainer.querySelectorAll('.tab-btn');
            },

            /**
             * 销毁组件（移除事件监听）
             */
            destroy: function() {
                const buttons = this.navContainer.querySelectorAll('.tab-btn');
                buttons.forEach(function(btn) {
                    btn.onclick = null;
                });
            }
        };

        // 绑定点击事件
        const buttons = navContainer.querySelectorAll('.tab-btn');
        buttons.forEach(function(btn) {
            btn.addEventListener('click', function() {
                const tabId = this.dataset.tab;
                if (tabId && tabId !== instance.currentTab) {
                    instance.switchTo(tabId);
                }
            });
        });

        // 默认激活当前带有 active 类的标签
        const activeBtn = navContainer.querySelector('.' + activeClass);
        if (activeBtn && activeBtn.dataset.tab) {
            instance.switchTo(activeBtn.dataset.tab);
        } else if (buttons.length > 0) {
            instance.switchTo(buttons[0].dataset.tab);
        }

        return instance;
    }
};
