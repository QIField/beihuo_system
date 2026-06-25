# -*- coding:utf-8 -*-
"""
任务管理器看门狗增强器 — 猴子补丁方式

作用：
    通过猴子补丁在 task_manager 对象上动态添加看门狗方法和属性，
    根据任务配置中的 enabled / demand_driven 状态自动启停调度器里的任务。

设计原则：
    1. 使用猴子补丁：在 task_manager 实例上动态添加方法和属性
    2. 保留 set_task_manager / get_task_manager 单例管理
    3. 配置存储在内存全局变量中（不再依赖数据库）

使用方式：
    from app.core.task_manager import task_manager
    task_manager.initialize()

    from app.core.task_enhancer import set_task_manager, install_enhancements, register_task_config
    set_task_manager(task_manager)
    
    # 手动注册需要看门狗管理的任务配置
    register_task_config(
        job_id='my_task',
        enabled=True,
        demand_driven=False,
        idle_timeout_minutes=30,
        description='我的任务'
    )
    
    install_enhancements()

猴子补丁添加的内容：
    - task_manager._watchdog_installed: 是否已安装看门狗
    - task_manager._watchdog_job_id: 看门狗任务 ID
    - task_manager._watchdog_task(): 看门狗核心逻辑（可调用）
    - task_manager.shutdown_watchdog(): 关闭看门狗
"""

from datetime import datetime


# ======================================================================
# 1. 单例引用管理（保持不变）
# ======================================================================

_TASK_MANAGER_SINGLETON = None


def set_task_manager(task_manager):
    """注入 task_manager 单例引用。"""
    global _TASK_MANAGER_SINGLETON
    _TASK_MANAGER_SINGLETON = task_manager


def get_task_manager():
    """获取 task_manager 实例。"""
    global _TASK_MANAGER_SINGLETON
    if _TASK_MANAGER_SINGLETON is None:
        raise ValueError("任务管理器单例未导入")
    return _TASK_MANAGER_SINGLETON


# ======================================================================
# 2. 任务配置管理（内存全局变量存储）
# ======================================================================
# 配置存储在内存字典中，通过 register_task_config() 手动注册

# 全局配置字典：{job_id: config_dict}
_TASK_CONFIGS = {}

# 默认配置模板
_DEFAULT_TASK_CONFIG = {
    "enabled": True,              # 任务是否启用
    "demand_driven": False,       # 是否按需执行
    "idle_timeout_seconds": 1800, # 按需模式下空闲多久后暂停（秒），默认30分钟
    "last_request_time": None,    # 最近一次请求时间（ISO 格式）
    "description": "",            # 任务描述
    "registered_at": None,        # 注册时间
}


def register_task_config(job_id, **kwargs):
    """手动注册任务配置到内存全局变量。
    
    Args:
        job_id: 任务唯一标识，必须与 task_manager.schedule() 的 job_id 一致
        **kwargs: 配置项，可选：
            - enabled: 是否启用，默认 True
            - demand_driven: 是否按需执行，默认 False
            - idle_timeout_seconds: 空闲超时时间（秒），默认 1800（30分钟）
            - description: 任务描述，默认 job_id
    
    Example:
        register_task_config(
            job_id='ks_auto_bill_task',
            enabled=True,
            demand_driven=False,
            description='开思自动对单任务'
        )
    """
    cfg = dict(_DEFAULT_TASK_CONFIG)
    cfg["enabled"] = kwargs.get("enabled", True)
    cfg["demand_driven"] = kwargs.get("demand_driven", False)
    cfg["idle_timeout_seconds"] = kwargs.get("idle_timeout_seconds", 1800)
    cfg["description"] = kwargs.get("description", job_id)
    cfg["registered_at"] = datetime.now().isoformat()
    
    _TASK_CONFIGS[job_id] = cfg
    print(f"[TaskEnhancer] 已注册任务配置 [{job_id}]")


def load_task_config(job_id):
    """读取单个任务配置（从内存全局变量）。
    
    Args:
        job_id: 任务唯一标识。
    
    Returns:
        配置字典，或 None（配置不存在）。
    """
    return _TASK_CONFIGS.get(job_id)


def save_task_config(job_id, config):
    """保存任务配置到内存全局变量。
    
    Args:
        job_id: 任务唯一标识。
        config: 配置字典。
    """
    _TASK_CONFIGS[job_id] = dict(config)
    print(f"[TaskEnhancer] 配置已保存 [{job_id}]")


def ensure_task_config(job_id, func_name=""):
    """确保任务配置存在；若不存在则创建默认配置。
    
    Args:
        job_id: 任务唯一标识。
        func_name: 任务函数名，用于生成 description。
    
    Returns:
        任务配置字典。
    """
    existing = load_task_config(job_id)
    if existing:
        return existing

    register_task_config(job_id, description=func_name or job_id)
    return _TASK_CONFIGS[job_id]


# ======================================================================
# 3. 调度器辅助函数（猴子补丁内部使用）
# ======================================================================

_WATCHDOG_JOB_ID = "task_enhancer_watchdog"


def _get_job(job_id):
    """从调度器获取 APScheduler 的 Job 对象。"""
    tm = get_task_manager()
    if tm and tm._scheduler:
        return tm._scheduler.get_job(job_id)
    return None


def _pause_job(job_id):
    """暂停指定任务。"""
    job = _get_job(job_id)
    if job:
        job.pause()
        return True
    return False


def _resume_job(job_id):
    """恢复指定任务。"""
    job = _get_job(job_id)
    if job:
        job.resume()
        return True
    return False


def _has_recent_request(cfg):
    """判断按需任务是否在最近收到过请求。"""
    last_request_time = cfg.get("last_request_time")
    if not last_request_time:
        return False

    idle_timeout = cfg.get("idle_timeout_seconds", 1800)
    try:
        elapsed = (datetime.now() - datetime.fromisoformat(last_request_time)).total_seconds()
        return elapsed < idle_timeout
    except (ValueError, TypeError):
        return False


# ======================================================================
# 4. 看门狗核心逻辑（通过猴子补丁绑定到 task_manager）
# ======================================================================

def _watchdog_task():
    """看门狗任务：扫描任务配置并动态调整任务启停状态。"""
    try:
        # 直接遍历内存配置字典
        for job_id, cfg in _TASK_CONFIGS.items():
            # 跳过看门狗自身
            if job_id == _WATCHDOG_JOB_ID:
                continue

            job = _get_job(job_id)
            if job is None:
                continue

            # --- 决策 1：任务被禁用，确保 pause ---
            if not cfg.get("enabled", True):
                if job.next_run_time is not None:
                    try:
                        job.pause()
                        print(f"[TaskEnhancer] 已暂停禁用任务 [{job_id}]")
                    except Exception:
                        pass
                continue

            # --- 决策 2：按需执行模式 ---
            if cfg.get("demand_driven", False):
                recent = _has_recent_request(cfg)
                if recent and job.next_run_time is None:
                    try:
                        job.resume()
                        print(f"[TaskEnhancer] 按需任务 [{job_id}] 恢复执行")
                        print("="*1000)
                    except Exception:
                        pass
                elif not recent and job.next_run_time is not None:
                    try:
                        job.pause()
                        print(f"[TaskEnhancer] 按需任务 [{job_id}] 空闲暂停")
                    except Exception:
                        pass
                continue

            # --- 决策 3：普通任务被意外 pause，自动恢复 ---
            if job.next_run_time is None:
                try:
                    job.resume()
                except Exception:
                    pass

    except Exception as e:
        print(f"[TaskEnhancer] 看门狗扫描失败: {e}")


def _shutdown_watchdog(self):
    """猴子补丁方法：移除看门狗定时任务。"""
    job = self._scheduler.get_job(_WATCHDOG_JOB_ID)
    if job:
        job.remove()
        print("[TaskEnhancer] 看门狗定时任务已移除")
    self._watchdog_installed = False


# ======================================================================
# 5. 安装（猴子补丁注入）
# ======================================================================

_INSTALLED = False
_INSTALL_LOCK = __import__('threading').Lock()


def install_enhancements():
    """通过猴子补丁在 task_manager 对象上安装看门狗。"""
    global _INSTALLED

    with _INSTALL_LOCK:
        if _INSTALLED:
            return

        tm = get_task_manager()

        # ===== 猴子补丁：在 task_manager 实例上动态添加属性和方法 =====

        # 属性：是否已安装看门狗
        tm._watchdog_installed = False

        # 属性：看门狗任务 ID
        tm._watchdog_job_id = _WATCHDOG_JOB_ID

        # 方法：看门狗核心逻辑
        tm._watchdog_task = _watchdog_task

        # 方法：关闭看门狗（绑定方法）
        tm.shutdown_watchdog = _shutdown_watchdog.__get__(tm, type(tm))

        # ===== 注册看门狗定时任务 =====

        # 通过 task_manager 的调度器注册看门狗任务（每5秒扫描一次）
        tm.schedule(
            tm._watchdog_task,
            trigger='interval',
            job_id=_WATCHDOG_JOB_ID,
            seconds=5,
            next_run_time=datetime.now(),
            replace_existing=True
        )

        # 标记已安装
        tm._watchdog_installed = True
        _INSTALLED = True

        print("[TaskEnhancer] 看门狗已通过猴子补丁安装到 task_manager")


def is_installed():
    """检查看门狗是否已安装。"""
    return _INSTALLED
