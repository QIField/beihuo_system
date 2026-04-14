/**
 * 询价单报警声音提醒模块
 * 功能：循环播放声音，直到用户确认
 */

(function(global) {
    'use strict';

    // 配置
    const CONFIG = {
        AUDIO_ID: 'alertSound',
        ALERT_TITLE: '⚠️ 紧急提醒',
        ALERT_MESSAGE: '询价单超过阈值！当前有 {count} 单待认领，请及时处理！',
        CONFIRM_BUTTON: '已处理，停止提醒',
        SHADE: 0.8,
        CLOSE_BTN: 0
    };

    // 状态
    let state = {
        audio: null,
        isPlaying: false,
        isConfirmed: false,
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

        if (state.isPlaying || state.isConfirmed) {
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
                state.isConfirmed = true;
                layui.layer.close(index);
                notifyBackendConfirmed();
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
     * 重置报警状态
     */
    function resetAlertState() {
        state.isConfirmed = false;
        state.isPlaying = false;
        console.log('[AlertSound] 报警状态已重置');
    }

    /**
     * 通知后端用户已确认报警
     */
    function notifyBackendConfirmed() {
        fetch('/api/ks_inquiry/confirm_alert', {
            method: 'POST',
            credentials: 'same-origin'
        }).catch(err => console.log('[AlertSound] 确认通知失败:', err));
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
        reset: resetAlertState,
        getState: () => ({ ...state })
    };

})(window);
