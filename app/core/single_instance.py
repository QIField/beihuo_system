"""
单例检测模块 - 极简版
单 worker 环境下无需复杂锁机制
"""

import os
import tempfile

# 获取系统临时目录
TEMP_DIR = tempfile.gettempdir()


class SimpleFileLock:
    """
    简单文件锁（兼容旧代码）
    单 worker 环境下仅作标记用
    """
    
    def __init__(self, lock_name: str, lock_dir: str = None):
        self.lock_name = lock_name
        if lock_dir is None:
            lock_dir = TEMP_DIR
        self.lock_path = os.path.join(lock_dir, f"{lock_name}.lock")
        self._acquired = False
    
    def acquire(self) -> bool:
        """获取锁"""
        try:
            fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            self._acquired = True
            return True
        except FileExistsError:
            return False
        except Exception:
            return False
    
    def release(self):
        """释放锁"""
        if self._acquired:
            try:
                if os.path.exists(self.lock_path):
                    os.unlink(self.lock_path)
                self._acquired = False
            except Exception:
                pass
    
    def __enter__(self):
        return self.acquire()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False
