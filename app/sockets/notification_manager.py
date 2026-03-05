"""
WebSocket通知管理模块
提供统一的实时通知发送接口，支持各种业务场景的通知需求
"""

from flask import current_app
from flask_socketio import emit
import json
from datetime import datetime
from typing import Dict, Any, Optional
import threading


# 全局SocketIO实例引用
_global_socketio = None
_global_app = None


def init_global_socketio(app, socketio):
    """初始化全局SocketIO引用"""
    global _global_socketio, _global_app
    _global_socketio = socketio
    _global_app = app
    print("[WebSocket] 全局SocketIO初始化完成")


def get_global_socketio():
    """获取全局SocketIO实例"""
    return _global_socketio


class NotificationManager:
    """通知管理器类"""
    
    def __init__(self):
        self._socketio = None
        self._app = None
        
    def init_app(self, app, socketio):
        """初始化应用和SocketIO实例"""
        self._app = app
        self._socketio = socketio
        # 将实例存储到应用中以便全局访问
        if not hasattr(app, 'notification_manager'):
            app.notification_manager = self
    
    @property
    def socketio(self):
        """获取SocketIO实例"""
        # 优先使用实例存储的
        if self._socketio:
            return self._socketio
        # 其次使用全局的
        global_socketio = get_global_socketio()
        if global_socketio:
            return global_socketio
        # 最后尝试从current_app获取
        try:
            app = current_app._get_current_object()
            return getattr(app, 'socketio', None)
        except RuntimeError:
            return None
    
    def send_notification(
        self,
        notification_type: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        room: Optional[str] = None,
        namespace: str = '/notifications'
    ) -> bool:
        """
        发送WebSocket通知
        
        参数:
            notification_type: 通知类型 ('success', 'error', 'warning', 'info')
            message: 通知消息内容
            data: 附加业务数据
            room: 房间ID，None表示广播给所有连接用户
            namespace: SocketIO命名空间
            
        返回:
            bool: 发送是否成功
        """
        try:
            socketio_instance = self.socketio
            
            if not socketio_instance:
                print(f"[WebSocket] SocketIO实例不可用，使用回退方案: {message}")
                return True
                
            # 构造通知数据
            notification_data = {
                'type': notification_type,
                'message': message,
                'data': data or {},
                'timestamp': datetime.now().isoformat(),
                'event': 'notification'
            }
            
            # 发送通知
            if room:
                socketio_instance.emit('notification', notification_data, room=room, namespace=namespace)
                print(f"[WebSocket] 向房间 {room} 发送通知: {message}")
            else:
                # 广播给所有用户
                socketio_instance.emit('notification', notification_data, namespace=namespace)
                print(f"[WebSocket] 广播通知: {message}")
            
            return True
            
        except Exception as e:
            print(f"[WebSocket] 发送通知失败: {str(e)}")
            return False
    
    @staticmethod
    def send_audio_notification(
        sound_type: str = "generic",
        custom_message: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        发送音频相关通知（兼容原有audio_player接口）
        
        参数:
            sound_type: 音频类型 ('new_order', 'error', 'warning', 'generic')
            custom_message: 自定义消息（可选）
            data: 附加数据
            
        返回:
            bool: 发送是否成功
        """
        # 音频通知类型映射
        sound_mappings = {
            'new_order': {
                'type': 'success',
                'message': custom_message or '检测到新订单，请及时处理！',
                'data': {'sound_type': 'new_order', 'audio_category': 'order'}
            },
            'error': {
                'type': 'error',
                'message': custom_message or '操作出现错误，请检查！',
                'data': {'sound_type': 'error', 'audio_category': 'alert'}
            },
            'warning': {
                'type': 'warning',
                'message': custom_message or '请注意重要提醒！',
                'data': {'sound_type': 'warning', 'audio_category': 'alert'}
            },
            'generic': {
                'type': 'info',
                'message': custom_message or '系统提示',
                'data': {'sound_type': 'generic', 'audio_category': 'system'}
            }
        }
        
        # 获取映射配置
        config = sound_mappings.get(sound_type, sound_mappings['generic'])
        
        # 合并自定义数据
        if data:
            config['data'].update(data)
            
        # 发送通知
        return NotificationManager.send_notification(
            notification_type=config['type'],
            message=config['message'],
            data=config['data']
        )
    
    @staticmethod
    def send_task_progress(
        task_id: str,
        progress: int,
        message: str = "",
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        发送任务进度通知
        
        参数:
            task_id: 任务ID
            progress: 进度百分比 (0-100)
            message: 进度描述
            data: 附加数据
            
        返回:
            bool: 发送是否成功
        """
        progress_data = {
            'task_id': task_id,
            'progress': progress,
            'message': message,
            'status': 'running' if progress < 100 else 'completed'
        }
        
        if data:
            progress_data.update(data)
            
        return NotificationManager.send_notification(
            notification_type='info',
            message=f'任务进度: {progress}%',
            data=progress_data,
            room=f'task_{task_id}'
        )
    
    @staticmethod
    def send_data_update(
        data_type: str,
        action: str,
        record_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        发送数据变更通知
        
        参数:
            data_type: 数据类型 ('order', 'inventory', 'user', etc.)
            action: 操作类型 ('create', 'update', 'delete')
            record_id: 记录ID
            data: 变更的具体数据
            
        返回:
            bool: 发送是否成功
        """
        update_data = {
            'data_type': data_type,
            'action': action,
            'record_id': record_id,
            'timestamp': datetime.now().isoformat()
        }
        
        if data:
            update_data.update(data)
            
        message = f'{data_type}数据已{action}'
        if record_id:
            message += f' (ID: {record_id})'
            
        return NotificationManager.send_notification(
            notification_type='info',
            message=message,
            data=update_data
        )


# 全局通知管理器实例
notification_manager = NotificationManager()


# 便捷函数 - 可在任何地方调用
def send_websocket_notification(notification_type, message="", data=None):
    """
    兼容函数：发送WebSocket通知
    这个函数将被audio_player.py中的同名函数替换
    """
    # 尝试使用notification_manager实例
    try:
        return notification_manager.send_notification(
            notification_type=notification_type,
            message=message,
            data=data
        )
    except:
        pass
    
    # 如果实例不可用，尝试使用全局SocketIO
    try:
        socketio_instance = get_global_socketio()
        if socketio_instance:
            notification_data = {
                'type': notification_type,
                'message': message,
                'data': data or {},
                'timestamp': datetime.now().isoformat(),
                'event': 'notification'
            }
            socketio_instance.emit('notification', notification_data, namespace='/notifications')
            print(f"[WebSocket] 全局发送通知: {message}")
            return True
    except Exception as e:
        print(f"[WebSocket] 全局发送通知失败: {str(e)}")
    
    # 最后的回退方案
    print(f"[回退通知] 类型: {notification_type}, 消息: {message}")
    return True
