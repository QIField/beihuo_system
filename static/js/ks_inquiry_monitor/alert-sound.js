/**
 * 询价单报警声音提醒模块
 * 功能：数据更新后如果超出阈值，播放声音提醒
 */

(function(global) {
    'use strict';

    // 配置
    const CONFIG = {
        AUDIO_ID: 'alertSound',
        ALERT_TITLE: '⚠️ 紧急提醒',
        ALERT_MESSAGE: '询价单超过阈值！当前有 {count} 单待认领，请及时处理！',
        CONFIRM_BUTTON: '确定',
        SHADE: 0.8,
        CLOSE_BTN: 0
    };

    // 状态
    let state = {
        audio: null,
        isPlaying: false,
        currentAlertCount: 0
    };

    /**
     * 初始化音频
     */
    function initAudio() {
        state.audio = document.getElementById(CONFIG.AUDIO_ID);
        if (state.audio) {
            state.audio.loop = true;
        }
    }

    /**
     * 播放报警声音（循环）
     */
    function playAlertSound() {
        if (!state.audio) {
            initAudio();
        }

        if (state.isPlaying) {
            return;
        }

        state.isPlaying = true;
        
        const playPromise = state.audio.play();
        if (playPromise !== undefined) {
            playPromise.catch(function(error) {
                console.log('[AlertSound] 自动播放被阻止:', error);
            });
        }

        showConfirmDialog();
    }

    /**
     * 显示确认对话框
     */
    function showConfirmDialog() {
        const message = CONFIG.ALERT_MESSAGE.replace('{count}', state.currentAlertCount);
        
        layui.use('layer', function() {
            layui.layer.confirm(message, {
                title: CONFIG.ALERT_TITLE,
                btn: [CONFIG.CONFIRM_BUTTON],
                closeBtn: CONFIG.CLOSE_BTN,
                shade: CONFIG.SHADE,
                area: ['400px', '200px']
            }, function(index) {
                stopAlertSound();
                layui.layer.close(index);
            });
        });
    }

    /**
     * 停止报警声音
     */
    function stopAlertSound() {
        if (state.audio) {
            state.audio.pause();
            state.audio.currentTime = 0;
        }
        state.isPlaying = false;
    }

    /**
     * 触发报警
     */
    function triggerAlert(alertCount) {
        state.currentAlertCount = alertCount || 0;
        playAlertSound();
    }

    global.KsInquiryAlert = {
        play: triggerAlert,
        stop: stopAlertSound,
        getState: () => ({ ...state })
    };

})(window);
