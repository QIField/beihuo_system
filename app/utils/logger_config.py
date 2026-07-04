import logging
import os
import platform


# 根据运行环境选择日志目录
# Linux 生产环境使用宝塔日志目录，Windows/本地开发使用项目根目录下的 logs
if platform.system() == 'Linux' and os.path.exists('/www/wwwlogs'):
    LOG_DIR = '/www/wwwlogs/python/beihuo_system'
else:
    LOG_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        'logs'
    )


# 需要按任务拆分日志的模块列表
TASK_LOGGERS = [
    'qpl_auto_bill',      # 开思自动对单
    'ks_auto_bill',       # 快手自动对单
    'crm_data_sync',      # CRM 数据同步
]


def init_loggers():
    """初始化任务日志，每个任务一个独立文件"""
    os.makedirs(LOG_DIR, exist_ok=True)

    for task_name in TASK_LOGGERS:
        logger = logging.getLogger(task_name)
        logger.setLevel(logging.INFO)

        # 避免重复添加 handler（Flask debug 重载时会重复执行）
        if logger.handlers:
            continue

        log_path = os.path.join(LOG_DIR, f'{task_name}.log')
        handler = logging.FileHandler(log_path, encoding='utf-8')
        handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s'
        ))

        logger.addHandler(handler)
        # 禁止向上传播，避免同时写入 uwsgi.log 或根 logger
        logger.propagate = False


def get_task_logger(task_name):
    """获取任务 logger，如果未注册会自动创建一个基础配置"""
    logger = logging.getLogger(task_name)

    # 没有 handler 时自动初始化一个文件 handler
    if not logger.handlers:
        os.makedirs(LOG_DIR, exist_ok=True)
        log_path = os.path.join(LOG_DIR, f'{task_name}.log')
        handler = logging.FileHandler(log_path, encoding='utf-8')
        handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s'
        ))
        logger.addHandler(handler)
        logger.propagate = False

    return logger
