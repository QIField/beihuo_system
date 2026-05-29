/**
 * 一键置顶按钮组件
 * 支持多种表格类型：Handsontable、AG Grid、LayUI Table 等
 */

(function(global) {
    'use strict';

    class ScrollToTop {
        constructor(options = {}) {
            this.options = {
                container: options.container || null,           // 表格容器选择器
                threshold: options.threshold || 200,            // 显示按钮的滚动阈值（px）
                position: options.position || 'bottom-right',   // 按钮位置
                offsetBottom: options.offsetBottom || 30,       // 距底部距离
                offsetRight: options.offsetRight || 30,         // 距右侧距离
                smooth: options.smooth !== false,               // 是否平滑滚动
                duration: options.duration || 300,              // 动画持续时间（ms）
                zIndex: options.zIndex || 9999                // 按钮层级
            };

            this.scrollElement = null;  // 实际滚动的元素
            this.button = null;         // 置顶按钮元素
            this.isVisible = false;     // 按钮是否可见
            this.isScrolling = false;   // 是否正在滚动

            this.init();
        }

        /**
         * 初始化组件
         */
        init() {
            this.detectScrollElement();
            this.createButton();
            this.bindEvents();
        }

        /**
         * 检测滚动元素
         * 自动识别多种表格类型的滚动容器
         */
        detectScrollElement() {
            // 如果指定了容器，优先使用
            if (this.options.container) {
                const container = document.querySelector(this.options.container);
                if (container) {
                    // 针对 AG Grid 特殊处理
                    const agGridViewport = container.querySelector('.ag-body-viewport');
                    if (agGridViewport) {
                        this.scrollElement = agGridViewport;
                        console.log('[ScrollToTop] 检测到 AG Grid 滚动元素:', this.options.container + ' .ag-body-viewport');
                        return;
                    }

                    // 针对 Handsontable 特殊处理
                    const hotHolder = container.querySelector('.wtHolder') ||
                                      container.querySelector('.ht_master .wtHolder');
                    if (hotHolder) {
                        this.scrollElement = hotHolder;
                        console.log('[ScrollToTop] 检测到 Handsontable 滚动元素');
                        return;
                    }

                    // 通用处理：查找可滚动子元素
                    const scrollableChild = this.findScrollableChild(container);
                    if (scrollableChild) {
                        this.scrollElement = scrollableChild;
                        console.log('[ScrollToTop] 检测到容器内滚动元素');
                        return;
                    }

                    // 如果容器本身可滚动
                    if (this.isScrollable(container)) {
                        this.scrollElement = container;
                        console.log('[ScrollToTop] 使用容器作为滚动元素');
                        return;
                    }
                }
            }

            // 自动检测常见表格类型的滚动容器
            const selectors = [
                // Handsontable
                '.handsontable .wtHolder',
                '.handsontable .ht_master .wtHolder',
                '.handsontable .htCore',

                // AG Grid
                '.ag-body-viewport',
                '.ag-grid .ag-body-viewport',
                '.ag-theme-alpine .ag-body-viewport',
                '#myGrid .ag-body-viewport',

                // LayUI Table
                '.layui-table-view .layui-table-body',
                '.layui-table-body.layui-table-main',

                // 通用表格容器
                '.table-container',
                '#table-container'
            ];

            for (const selector of selectors) {
                const element = document.querySelector(selector);
                if (element && this.isScrollable(element)) {
                    this.scrollElement = element;
                    console.log('[ScrollToTop] 检测到滚动元素:', selector);
                    return;
                }
            }

            // 默认使用 window
            this.scrollElement = window;
            console.log('[ScrollToTop] 使用默认滚动元素: window');
        }

        /**
         * 查找可滚动的子元素
         */
        findScrollableChild(container) {
            const children = container.querySelectorAll('*');
            for (const child of children) {
                if (this.isScrollable(child)) {
                    return child;
                }
            }
            return null;
        }

        /**
         * 判断元素是否可滚动
         */
        isScrollable(element) {
            if (!element) return false;

            const style = window.getComputedStyle(element);
            const overflowY = style.overflowY;
            const overflow = style.overflow;

            // 检查是否有滚动条（高度差大于 2px 才认为有滚动条）
            const hasScrollBar = element.scrollHeight > element.clientHeight + 2;

            // AG Grid 的 body-viewport 通常 overflow 是 hidden 或 auto
            // 所以只要有高度差就认为可滚动
            if (hasScrollBar) {
                return true;
            }

            // 检查 overflow 属性
            return (overflowY === 'auto' || overflowY === 'scroll' ||
                    overflow === 'auto' || overflow === 'scroll') && hasScrollBar;
        }

        /**
         * 创建置顶按钮
         */
        createButton() {
            this.button = document.createElement('button');
            this.button.className = 'scroll-to-top-btn';
            this.button.setAttribute('type', 'button');
            this.button.setAttribute('title', '回到顶部');
            this.button.innerHTML = `
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 19V5M5 12l7-7 7 7"/>
                </svg>
            `;

            // 设置位置
            this.updatePosition();

            // 初始隐藏
            this.button.style.opacity = '0';
            this.button.style.visibility = 'hidden';
            this.button.style.transform = 'scale(0.8)';

            document.body.appendChild(this.button);
        }

        /**
         * 更新按钮位置
         */
        updatePosition() {
            const { offsetBottom, offsetRight, zIndex } = this.options;

            this.button.style.cssText = `
                position: fixed;
                bottom: ${offsetBottom}px;
                right: ${offsetRight}px;
                z-index: ${zIndex};
                width: 48px;
                height: 48px;
                border-radius: 50%;
                background: linear-gradient(135deg, #1890ff 0%, #40a9ff 100%);
                border: none;
                box-shadow: 0 4px 12px rgba(24, 144, 255, 0.4);
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                transition: all 0.3s ease;
                opacity: 0;
                visibility: hidden;
                transform: scale(0.8);
            `;
        }

        /**
         * 绑定事件
         */
        bindEvents() {
            // 滚动事件
            const scrollTarget = this.scrollElement === window ? window : this.scrollElement;
            scrollTarget.addEventListener('scroll', this.handleScroll.bind(this), { passive: true });

            // 点击事件
            this.button.addEventListener('click', this.scrollToTop.bind(this));

            // 鼠标悬停效果
            this.button.addEventListener('mouseenter', () => {
                if (this.isVisible) {
                    this.button.style.transform = 'scale(1.1)';
                    this.button.style.boxShadow = '0 6px 16px rgba(24, 144, 255, 0.5)';
                }
            });

            this.button.addEventListener('mouseleave', () => {
                if (this.isVisible) {
                    this.button.style.transform = 'scale(1)';
                    this.button.style.boxShadow = '0 4px 12px rgba(24, 144, 255, 0.4)';
                }
            });
        }

        /**
         * 处理滚动事件
         */
        handleScroll() {
            const scrollTop = this.getScrollTop();
            const shouldShow = scrollTop > this.options.threshold;

            if (shouldShow && !this.isVisible) {
                this.showButton();
            } else if (!shouldShow && this.isVisible) {
                this.hideButton();
            }
        }

        /**
         * 获取当前滚动位置
         */
        getScrollTop() {
            if (this.scrollElement === window) {
                return window.pageYOffset || document.documentElement.scrollTop;
            }
            return this.scrollElement.scrollTop;
        }

        /**
         * 显示按钮
         */
        showButton() {
            this.isVisible = true;
            this.button.style.opacity = '1';
            this.button.style.visibility = 'visible';
            this.button.style.transform = 'scale(1)';
        }

        /**
         * 隐藏按钮
         */
        hideButton() {
            this.isVisible = false;
            this.button.style.opacity = '0';
            this.button.style.visibility = 'hidden';
            this.button.style.transform = 'scale(0.8)';
        }

        /**
         * 滚动到顶部
         */
        scrollToTop() {
            if (this.isScrolling) return;

            this.isScrolling = true;

            if (this.options.smooth) {
                this.smoothScrollToTop();
            } else {
                this.instantScrollToTop();
            }
        }

        /**
         * 平滑滚动到顶部
         */
        smoothScrollToTop() {
            const startPosition = this.getScrollTop();
            const duration = this.options.duration;
            const startTime = performance.now();

            const animate = (currentTime) => {
                const elapsed = currentTime - startTime;
                const progress = Math.min(elapsed / duration, 1);

                // 使用 easeOutQuart 缓动函数 - 更丝滑的减速效果
                const easeProgress = 1 - Math.pow(1 - progress, 4);
                const currentPosition = startPosition * (1 - easeProgress);

                this.setScrollTop(currentPosition);

                if (progress < 1) {
                    requestAnimationFrame(animate);
                } else {
                    this.isScrolling = false;
                    this.setScrollTop(0);
                }
            };

            requestAnimationFrame(animate);
        }

        /**
         * 立即滚动到顶部
         */
        instantScrollToTop() {
            this.setScrollTop(0);
            this.isScrolling = false;
        }

        /**
         * 设置滚动位置
         */
        setScrollTop(value) {
            if (this.scrollElement === window) {
                window.scrollTo(0, value);
            } else {
                this.scrollElement.scrollTop = value;
            }
        }

        /**
         * 销毁组件
         */
        destroy() {
            if (this.button && this.button.parentNode) {
                this.button.parentNode.removeChild(this.button);
            }
            this.button = null;
            this.scrollElement = null;
        }

        /**
         * 更新配置
         */
        updateOptions(newOptions) {
            this.options = { ...this.options, ...newOptions };
            this.updatePosition();
        }
    }

    // 静态方法：快速初始化
    ScrollToTop.init = function(options = {}) {
        return new ScrollToTop(options);
    };

    // 导出到全局
    global.ScrollToTop = ScrollToTop;

})(window);
