"""
子进程管理器
用于管理后台任务子进程，实现进程隔离和崩溃自愈
"""

import multiprocessing
import time
import os
from datetime import datetime
from typing import Callable, Optional, Dict, Any


class SubProcessManager:
    """
    子进程管理器
    
    功能：
    1. 启动/停止子进程
    2. 监控子进程状态
    3. 自动重启（可配置）
    4. 记录重启历史
    
    使用示例：
        manager = SubProcessManager("ks_auto_bill")
        manager.start(target_function)
        
        # 检查状态
        if manager.is_running():
            print(f"进程运行中，PID: {manager.get_pid()}")
        
        # 获取详细状态
        status = manager.get_status()
    """
    
    def __init__(self, process_name: str = "subprocess"):
        """
        初始化子进程管理器
        
        :param process_name: 进程名称，用于日志标识
        """
        self.process_name = process_name
        self._process: Optional[multiprocessing.Process] = None
        self._start_time: Optional[datetime] = None
        self._restart_count = 0
        self._max_restarts = 5  # 最大重启次数，防止无限重启
        self._history: list = []  # 启动/停止历史
        
    def start(self, target_func: Callable, *args, **kwargs) -> bool:
        """
        启动子进程
        
        :param target_func: 要在子进程中执行的函数
        :param args: 传递给目标函数的位置参数
        :param kwargs: 传递给目标函数的关键字参数
        :return: 是否成功启动
        """
        # 检查是否已在运行
        if self._process and self._process.is_alive():
            print(f"[{self.process_name}] 进程已在运行中，PID: {self._process.pid}")
            return False
        
        # 检查重启次数限制
        if self._restart_count >= self._max_restarts:
            print(f"[{self.process_name}] 已达到最大重启次数({self._max_restarts})，不再自动重启")
            return False
        
        try:
            # 创建新进程
            # 使用 spawn 模式，确保子进程是干净的（不继承父进程的资源）
            multiprocessing.set_start_method('spawn', force=True)
            
            self._process = multiprocessing.Process(
                target=target_func,
                args=args,
                kwargs=kwargs,
                name=self.process_name,
                daemon=False  # 非守护进程，方便管理和监控
            )
            
            self._process.start()
            self._start_time = datetime.now()
            
            # 记录历史
            self._history.append({
                'action': 'start',
                'time': self._start_time.isoformat(),
                'pid': self._process.pid
            })
            
            print(f"[{self.process_name}] 进程已启动，PID: {self._process.pid}")
            return True
            
        except Exception as e:
            print(f"[{self.process_name}] 启动进程失败: {e}")
            return False
    
    def stop(self, timeout: int = 10) -> bool:
        """
        停止子进程
        
        :param timeout: 等待进程优雅退出的超时时间（秒）
        :return: 是否成功停止
        """
        if not self._process or not self._process.is_alive():
            print(f"[{self.process_name}] 进程未在运行")
            return True
        
        pid = self._process.pid
        print(f"[{self.process_name}] 正在停止进程 {pid}...")
        
        try:
            # 等待进程自然退出（通过信号通知）
            self._process.join(timeout=timeout)
            
            # 如果还在运行，强制终止
            if self._process.is_alive():
                print(f"[{self.process_name}] 进程未在 {timeout} 秒内退出，强制终止")
                self._process.terminate()
                self._process.join(timeout=2)
                
                # 如果还在运行，强制杀死
                if self._process.is_alive():
                    print(f"[{self.process_name}] 强制终止失败，使用 kill")
                    self._process.kill()
                    self._process.join()
            
            # 记录历史
            self._history.append({
                'action': 'stop',
                'time': datetime.now().isoformat(),
                'pid': pid
            })
            
            print(f"[{self.process_name}] 进程 {pid} 已停止")
            return True
            
        except Exception as e:
            print(f"[{self.process_name}] 停止进程时出错: {e}")
            return False
    
    def restart(self, target_func: Callable, *args, **kwargs) -> bool:
        """
        重启子进程
        
        :param target_func: 要在子进程中执行的函数
        :return: 是否成功重启
        """
        print(f"[{self.process_name}] 正在重启进程...")
        self.stop()
        time.sleep(1)  # 等待资源释放
        self._restart_count += 1
        return self.start(target_func, *args, **kwargs)
    
    def is_running(self) -> bool:
        """
        检查进程是否在运行
        
        :return: True 表示正在运行
        """
        return self._process is not None and self._process.is_alive()
    
    def get_pid(self) -> Optional[int]:
        """
        获取进程 PID
        
        :return: 进程ID，如果未启动则返回 None
        """
        if self._process and self._process.is_alive():
            return self._process.pid
        return None
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取进程详细状态
        
        :return: 包含状态信息的字典
        """
        if self._process is None:
            return {
                'status': 'not_started',
                'process_name': self.process_name
            }
        
        is_alive = self._process.is_alive()
        
        status = {
            'status': 'running' if is_alive else 'stopped',
            'process_name': self.process_name,
            'pid': self._process.pid,
            'start_time': self._start_time.isoformat() if self._start_time else None,
            'restart_count': self._restart_count,
            'max_restarts': self._max_restarts
        }
        
        # 如果进程已停止，添加退出码
        if not is_alive and self._process.exitcode is not None:
            status['exit_code'] = self._process.exitcode
            # 解释退出码
            if self._process.exitcode == 0:
                status['exit_reason'] = '正常退出'
            elif self._process.exitcode < 0:
                status['exit_reason'] = f'被信号终止 ({self._process.exitcode})'
            else:
                status['exit_reason'] = f'异常退出 (code: {self._process.exitcode})'
        
        return status
    
    def get_history(self, limit: int = 10) -> list:
        """
        获取启动/停止历史
        
        :param limit: 返回最近多少条记录
        :return: 历史记录列表
        """
        return self._history[-limit:]
    
    def reset_restart_count(self):
        """重置重启计数器"""
        self._restart_count = 0
        print(f"[{self.process_name}] 重启计数器已重置")


# 全局进程管理器实例
# 用于管理开思自动对单子进程
ks_bill_process_manager = SubProcessManager("ks_auto_bill")
