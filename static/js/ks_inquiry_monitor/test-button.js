/**
 * 询价单监控测试按钮模块
 * 提供手动测试声音提醒功能
 */

(function(global) {
    'use strict';

    /**
     * 创建测试按钮
     */
    function createTestButton() {
        const container = document.querySelector('.header');
        if (!container) return;

        const btnContainer = document.createElement('div');
        btnContainer.className = 'test-btn-container';
        btnContainer.style.cssText = 'display: flex; gap: 10px; align-items: center;';

        const testBtn = document.createElement('button');
        testBtn.className = 'layui-btn layui-btn-normal layui-btn-sm';
        testBtn.innerHTML = '<i class="layui-icon">&#xe6fc;</i> 测试声音提醒';
        testBtn.onclick = testAlertSound;

        btnContainer.appendChild(testBtn);

        const titleEl = container.querySelector('.title');
        if (titleEl) {
            titleEl.after(btnContainer);
        } else {
            container.appendChild(btnContainer);
        }
    }

    /**
     * 测试声音提醒
     */
    function testAlertSound() {
        console.log('[TestButton] 手动触发测试报警');
        
        if (global.KsInquiryAlert) {
            global.KsInquiryAlert.stop();
            global.KsInquiryAlert.play(99);
        } else {
            layui.use('layer', function() {
                layui.layer.msg('报警模块未加载', { icon: 2 });
            });
        }
    }

    /**
     * 初始化
     */
    function init() {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', createTestButton);
        } else {
            createTestButton();
        }
    }

    init();

})(window);
