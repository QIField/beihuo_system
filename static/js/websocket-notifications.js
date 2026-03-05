/**
 * WebSocket实时通知模块
 * 提供统一的WebSocket连接和通知处理功能
 */

(function(global) {
    'use strict';
    
    // 模块配置
    const CONFIG = {
        SOCKET_PATH: '/notifications',
        AUDIO_FILES: {
            'new_order': '/static/videos/new_order_sound.wav',  // 使用你现有的WAV文件
            'error': '/static/videos/new_order_sound.wav',
            'warning': '/static/videos/new_order_sound.wav',
            'generic': '/static/videos/new_order_sound.wav'
        },
        HEARTBEAT_INTERVAL: 30000, // 30秒心跳间隔
        RECONNECT_DELAY: 5000,     // 重连延迟5秒
        MAX_RECONNECT_ATTEMPTS: 5  // 最大重连次数
    };
    
    // WebSocket通知类
    class WebSocketNotifier {
        constructor() {
            this.socket = null;
            this.isConnected = false;
            this.reconnectAttempts = 0;
            this.heartbeatTimer = null;
            this.userId = 'web_client_' + Date.now();
        }
        
        // 初始化连接
        init() {
            this.connect();
            this.setupGlobalAccess();
        }
        
        // 建立WebSocket连接
        connect() {
            try {
                this.socket = io(CONFIG.SOCKET_PATH);
                this.bindEvents();
                console.log('[WebSocket] 尝试连接...');
            } catch (error) {
                console.error('[WebSocket] 连接初始化失败:', error);
                this.scheduleReconnect();
            }
        }
        
        // 绑定事件处理
        bindEvents() {
            // 连接成功
            this.socket.on('connected', (data) => {
                console.log('[WebSocket] 连接成功:', data);
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.startHeartbeat();
                this.subscribeToNotifications();
                
                // 添加明显的连接成功提示
                this.showConnectionSuccess();
            });
            
            // 连接断开
            this.socket.on('disconnect', () => {
                console.log('[WebSocket] 连接断开');
                this.isConnected = false;
                this.stopHeartbeat();
                this.scheduleReconnect();
            });
            
            // 接收通知
            this.socket.on('notification', (data) => {
                console.log('[WebSocket] 收到通知:', data);
                this.handleNotification(data);
            });
            
            // 订阅确认
            this.socket.on('subscription_confirmed', (data) => {
                console.log('[WebSocket] 通知订阅成功:', data);
            });
            
            // 心跳响应
            this.socket.on('pong', (data) => {
                console.log('[WebSocket] 心跳响应:', data.timestamp);
            });
            
            // 连接错误
            this.socket.on('connect_error', (error) => {
                console.error('[WebSocket] 连接错误:', error);
                this.scheduleReconnect();
            });
            
            // 测试通知处理
            this.socket.on('test_notification', (data) => {
                console.log('[WebSocket] 收到测试通知:', data);
                this.handleTestNotification(data);
            });
        }
        
        // 处理测试通知
        handleTestNotification(data) {
            // 显示测试通知
            this.showVisualNotification({
                type: data.type || 'info',
                message: data.message || '测试通知',
                data: data.data || {}
            });
            
            // 播放测试音频
            this.playNotificationSound('new_order');
            
            // 显示测试成功提示
            layui.use('layer', function(){
                layui.layer.msg('✅ WebSocket测试通知接收成功！', {
                    icon: 1,
                    time: 2000
                });
            });
        }

        // 订阅通知
        subscribeToNotifications() {
            if (this.socket) {
                this.socket.emit('subscribe_notifications', {
                    types: ['success', 'error', 'warning', 'info'],
                    user_id: this.userId
                });
            }
        }
        
        // 处理收到的通知
        handleNotification(data) {
            // 显示视觉通知
            this.showVisualNotification(data);
            
            // 播放音频提示
            if (data.data && data.data.sound_type) {
                this.playNotificationSound(data.data.sound_type);
            }
        }
        
        // 显示视觉通知（使用Layui）
        showVisualNotification(data) {
            layui.use('layer', function(){
                var layer = layui.layer;
                layer.msg(data.message, {
                    icon: this.getMessageIcon(data.type),
                    time: 3000,
                    shade: 0.1,
                    anim: 5 // 弹出动画
                });
            }.bind(this));
        }
        
        // 获取消息图标
        getMessageIcon(type) {
            switch(type) {
                case 'success': return 1; // 对勾图标
                case 'error': return 2;   // 叉号图标
                case 'warning': return 0; // 感叹号图标
                case 'info': return 6;    // 信息图标
                default: return 6;
            }
        }
        
        // 播放提示音
        playNotificationSound(soundType) {
            try {
                const audioFile = CONFIG.AUDIO_FILES[soundType] || CONFIG.AUDIO_FILES['generic'];
                const audio = new Audio(audioFile);
                
                // 设置音频属性
                audio.volume = 0.8; // 音量80%
                
                // 播放音频
                const playPromise = audio.play();
                
                if (playPromise !== undefined) {
                    playPromise.catch(function(error) {
                        console.log('[Audio] 自动播放被阻止，需要用户交互:', error);
                        // 可以在这里显示一个按钮让用户手动播放
                    });
                }
            } catch (error) {
                console.log('[Audio] 音频播放异常:', error);
            }
        }
        
        // 开始心跳检测
        startHeartbeat() {
            this.stopHeartbeat(); // 先清除已有的定时器
            this.heartbeatTimer = setInterval(() => {
                if (this.isConnected && this.socket) {
                    this.socket.emit('ping');
                }
            }, CONFIG.HEARTBEAT_INTERVAL);
        }
        
        // 停止心跳检测
        stopHeartbeat() {
            if (this.heartbeatTimer) {
                clearInterval(this.heartbeatTimer);
                this.heartbeatTimer = null;
            }
        }
        
        // 安排重连
        scheduleReconnect() {
            if (this.reconnectAttempts < CONFIG.MAX_RECONNECT_ATTEMPTS) {
                this.reconnectAttempts++;
                console.log(`[WebSocket] ${CONFIG.RECONNECT_DELAY/1000}秒后尝试第${this.reconnectAttempts}次重连...`);
                
                setTimeout(() => {
                    if (!this.isConnected) {
                        this.connect();
                    }
                }, CONFIG.RECONNECT_DELAY);
            } else {
                console.error('[WebSocket] 达到最大重连次数，停止重连');
            }
        }
        
        // 设置全局访问
        setupGlobalAccess() {
            // 将实例暴露到全局，便于调试和外部调用
            global.WebSocketNotifier = this;
            
            // 提供便捷的全局函数
            global.sendTestNotification = (type = 'info', message = '测试消息') => {
                if (this.socket) {
                    this.socket.emit('test_notification', { type, message });
                }
            };
        }
        
        // 发送自定义消息（供外部调用）
        sendMessage(event, data) {
            if (this.socket && this.isConnected) {
                this.socket.emit(event, data);
                return true;
            }
            return false;
        }
        
        // 加入房间
        joinRoom(roomName) {
            if (this.socket && this.isConnected) {
                this.socket.emit('join_room', { room: roomName });
                return true;
            }
            return false;
        }
        
        // 离开房间
        leaveRoom(roomName) {
            if (this.socket && this.isConnected) {
                this.socket.emit('leave_room', { room: roomName });
                return true;
            }
            return false;
        }
        
        // 获取连接状态
        getStatus() {
            return {
                connected: this.isConnected,
                userId: this.userId,
                reconnectAttempts: this.reconnectAttempts
            };
        }
    }
    
    // 创建全局实例
    const notifier = new WebSocketNotifier();
    
    // 页面加载完成后自动初始化
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            notifier.init();
        });
    } else {
        notifier.init();
    }
    
    // 导出模块（如果支持ES6模块）
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = WebSocketNotifier;
    }
    
})(typeof window !== 'undefined' ? window : global);
