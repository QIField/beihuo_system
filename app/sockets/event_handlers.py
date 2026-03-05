"""
SocketIO事件处理器
处理客户端连接、断开连接以及各种实时通信事件
"""

from flask import request
from flask_socketio import join_room, leave_room
from datetime import datetime
import json


def register_socket_events(socketio):
    """
    注册所有SocketIO事件处理函数
    
    参数:
        socketio: Flask-SocketIO实例
    """
    
    @socketio.on('connect', namespace='/notifications')
    def handle_connect():
        """处理客户端连接"""
        client_ip = request.environ.get('REMOTE_ADDR')
        print(f"[WebSocket] 客户端连接: {request.sid} (IP: {client_ip})")
        
        # 发送连接成功的欢迎消息
        socketio.emit('connected', {
            'message': '连接成功',
            'client_id': request.sid,
            'server_time': datetime.now().isoformat()
        }, room=request.sid)
    
    @socketio.on('disconnect', namespace='/notifications')
    def handle_disconnect():
        """处理客户端断开连接"""
        print(f"[WebSocket] 客户端断开连接: {request.sid}")
    
    @socketio.on('join_room', namespace='/notifications')
    def handle_join_room(data):
        """
        处理客户端加入房间请求
        
        参数:
            data: {'room': '房间名称'}
        """
        room_name = data.get('room')
        if room_name:
            join_room(room_name)
            print(f"[WebSocket] 客户端 {request.sid} 加入房间: {room_name}")
            
            socketio.emit('room_joined', {
                'room': room_name,
                'message': f'已加入房间 {room_name}'
            }, room=request.sid)
    
    @socketio.on('leave_room', namespace='/notifications')
    def handle_leave_room(data):
        """
        处理客户端离开房间请求
        
        参数:
            data: {'room': '房间名称'}
        """
        room_name = data.get('room')
        if room_name:
            leave_room(room_name)
            print(f"[WebSocket] 客户端 {request.sid} 离开房间: {room_name}")
            
            socketio.emit('room_left', {
                'room': room_name,
                'message': f'已离开房间 {room_name}'
            }, room=request.sid)
    
    @socketio.on('subscribe_notifications', namespace='/notifications')
    def handle_subscribe(data):
        """
        处理通知订阅请求
        
        参数:
            data: {'types': ['success', 'error', 'warning']} 订阅的通知类型
        """
        notification_types = data.get('types', ['success', 'error', 'warning', 'info'])
        user_id = data.get('user_id', 'anonymous')
        
        # 将用户加入对应的通知房间
        for notify_type in notification_types:
            room_name = f'notifications_{notify_type}'
            join_room(room_name)
        
        print(f"[WebSocket] 用户 {user_id} 订阅通知类型: {notification_types}")
        
        socketio.emit('subscription_confirmed', {
            'types': notification_types,
            'user_id': user_id,
            'message': '通知订阅成功'
        }, room=request.sid)
    
    @socketio.on('ping', namespace='/notifications')
    def handle_ping():
        """处理心跳检测"""
        socketio.emit('pong', {
            'timestamp': datetime.now().isoformat(),
            'message': 'pong'
        }, room=request.sid)
    
    @socketio.on('error', namespace='/notifications')
    def handle_error(error):
        """处理SocketIO错误"""
        print(f"[WebSocket] 客户端错误: {error}")
