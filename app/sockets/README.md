# WebSocket通信模块

## 模块概述

该模块提供统一的WebSocket实时通信功能，支持各种业务场景的通知需求。

## 目录结构

```
app/sockets/
├── __init__.py              # 模块初始化文件
├── notification_manager.py  # 通知管理器核心类
├── event_handlers.py        # SocketIO事件处理器
└── README.md               # 使用说明文档
```

## 核心组件

### 1. NotificationManager（通知管理器）

提供统一的通知发送接口，支持多种通知类型：

```python
from app.sockets import notification_manager

# 发送普通通知
notification_manager.send_notification(
    notification_type='success',
    message='操作成功',
    data={'order_id': 12345}
)

# 发送音频通知（兼容原有接口）
notification_manager.send_audio_notification(
    sound_type='new_order',
    custom_message='您有新的订单待处理'
)

# 发送任务进度通知
notification_manager.send_task_progress(
    task_id='task_001',
    progress=75,
    message='数据处理中...'
)

# 发送数据变更通知
notification_manager.send_data_update(
    data_type='order',
    action='create',
    record_id='ORD001',
    data={'customer': '张三'}
)
```

### 2. 事件处理器

处理客户端连接、房间管理等SocketIO事件，在主应用中注册：

```python
from app.sockets import register_socket_events

# 在Flask应用初始化时注册事件
socketio = SocketIO(app)
register_socket_events(socketio)
```

## 前端集成示例

### JavaScript客户端连接

```javascript
// 建立WebSocket连接
const socket = io('/notifications');

// 监听连接成功
socket.on('connected', function(data) {
    console.log('WebSocket连接成功:', data);
});

// 监听通知消息
socket.on('notification', function(data) {
    console.log('收到通知:', data);
    
    // 根据通知类型处理
    switch(data.type) {
        case 'success':
            showSuccessMessage(data.message);
            break;
        case 'error':
            showErrorMessage(data.message);
            break;
        case 'warning':
            showWarningMessage(data.message);
            break;
        case 'info':
            showInfoMessage(data.message);
            break;
    }
    
    // 播放提示音（如果需要）
    if (data.data && data.data.sound_type) {
        playNotificationSound(data.data.sound_type);
    }
});

// 订阅特定类型的通知
socket.emit('subscribe_notifications', {
    types: ['success', 'error', 'warning'],
    user_id: 'current_user_id'
});
```

## 通知类型说明

| 类型 | 用途 | 示例场景 |
|------|------|----------|
| `success` | 成功操作通知 | 订单创建成功、数据导入完成 |
| `error` | 错误通知 | 操作失败、系统异常 |
| `warning` | 警告通知 | 库存不足、数据异常 |
| `info` | 信息通知 | 系统消息、进度更新 |

## 房间机制

支持按需订阅不同类型的房间：

- `notifications_success` - 成功通知房间
- `notifications_error` - 错误通知房间  
- `notifications_warning` - 警告通知房间
- `notifications_info` - 信息通知房间
- `task_{task_id}` - 特定任务进度房间

## 兼容性说明

该模块完全兼容原有的 `audio_player.py` 接口，只需在主应用中替换 `send_websocket_notification` 函数的实现即可。

## 后续扩展

可根据业务需求扩展更多功能：
- 用户私信功能
- 实时聊天室
- 数据同步推送
- 系统状态监控
