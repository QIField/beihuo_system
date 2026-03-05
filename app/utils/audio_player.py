import os
from pathlib import Path
# 直接导入全局通知函数
from app.sockets.notification_manager import send_websocket_notification


def play_audio(audio_file_path):
    """
    废弃函数 - 仅保留接口兼容性
    
    参数:
        audio_file_path: 音频文件的路径（已废弃）
    
    说明:
        此函数已废弃，改为发送WebSocket通知
        为了保持向后兼容性，仍然接受参数但不执行实际音频播放
    """
    print(f"[废弃] 本地音频播放已停用: {audio_file_path}")
    # 发送WebSocket通知替代音频播放
    send_websocket_notification(
        notification_type="info",
        message=f"音频提示触发: {os.path.basename(audio_file_path)}"
    )


def _play_with_system_command(audio_file_path):
    """
    废弃函数 - 仅保留接口兼容性
    
    参数:
        audio_file_path: 音频文件的路径（已废弃）
    
    说明:
        此函数已废弃，系统命令播放已停用
    """
    print(f"[废弃] 系统命令音频播放已停用: {audio_file_path}")


def play_notification_sound(sound_file="new_order_sound.wav"):
    """
    播放订单提示音（重构为WebSocket通知）
    
    参数:
        sound_file: 音频文件名（用于识别通知类型）
    
    说明:
        - 不再播放本地音频文件
        - 改为发送WebSocket通知到前端
        - 根据文件名确定通知类型和消息内容
    """
    # 获取项目根目录（保持原有路径解析逻辑）
    current_file_path = Path(__file__).resolve()
    project_root = current_file_path.parent.parent.parent
    
    # 构建音频文件的完整路径（仅用于日志记录）
    audio_path = project_root / "static" / "videos" / sound_file
    
    print(f"[WebSocket模式] 检测到音频提示请求: {sound_file}")
    
    # 根据音频文件名确定通知类型和消息
    notification_mapping = {
        "new_order_sound.wav": {
            "type": "success",
            "message": "检测到新订单，请及时处理！",
            "data": {"sound_type": "new_order"}
        },
        "error_sound.wav": {
            "type": "error", 
            "message": "操作出现错误，请检查！",
            "data": {"sound_type": "error"}
        },
        "warning_sound.wav": {
            "type": "warning",
            "message": "请注意重要提醒！",
            "data": {"sound_type": "warning"}
        }
    }
    
    # 获取对应的通知配置
    config = notification_mapping.get(sound_file, {
        "type": "info",
        "message": f"系统提示音触发: {sound_file}",
        "data": {"sound_type": "generic", "filename": sound_file}
    })
    
    # 发送WebSocket通知
    send_websocket_notification(
        notification_type=config["type"],
        message=config["message"],
        data=config["data"]
    )
    
    # 如果文件不存在，记录警告（但仍发送通知）
    if not audio_path.exists():
        print(f"[警告] 音频文件不存在: {audio_path}，但已发送WebSocket通知")
