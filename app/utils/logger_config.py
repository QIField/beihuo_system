import logging
import os
import platform
from logging.handlers import RotatingFileHandler


# ============================================================================
# 日志使用规范（重要）
# ============================================================================
#
# 1. 禁止在日志中使用 emoji 或其他特殊 Unicode 字符
#    原因：
#    - emoji 会增加日志文件大小，且在不同编码环境下可能导致乱码
#    - Windows 记事本 / GBK 编码工具无法正确显示 emoji，下载查看时会变成乱码
#    - 宝塔面板读取大日志时，特殊字符可能增加渲染负担
#    建议：统一使用纯文本描述，例如 [成功]、[失败]、[警告]、[信息]
#
# 2. 如何避免 try/except 屎山代码
#    - 业务函数中尽量不要写 try/except，让异常自然向上冒泡
#    - 只在确实需要局部处理并继续执行的地方使用 try/except
#    - 如果内部捕获了异常但希望上层知道，必须重新 raise
#    - 整个任务的统一兜底 try/except 只写在任务入口函数中
#
# 3. 如何捕获所有异常但不做异常处理
#    - 任务入口函数用一层 try/except Exception 包裹全部业务逻辑
#    - 使用 logger.exception('任务失败') 记录完整堆栈
#    - 不要吞掉异常：需要让调度器/调用方感知时，记录后重新 raise
#    - 不要写 except Exception: pass 这种吞异常代码
#
# 4. 如何暴露完整问题
#    - 业务代码中不要 catch 后只打印简单文字，会丢失堆栈
#    - 统一使用 logger.exception()，它会自动记录 traceback
#    - 所有 ERROR 级别日志会自动汇总到 errors.log，崩溃时只看 errors.log 即可
#
# ============================================================================


# 环境判断：日志路径以 /www/ 开头的视为生产环境（宝塔 Linux 部署）
# 其余环境（Windows/Mac/Docker 开发等）视为开发环境
IS_PRODUCTION = platform.system() == 'Linux'

if IS_PRODUCTION:
    # 生产环境：/www/wwwlogs/python/beihuo_system
    #   - task_log/ 目录作为任务日志根目录
    #   - task_log/errors.log 直接暴露在 task_log 根目录，方便快速查看
    #   - task_log/{task_name}/{task_name}.log 为各任务详细日志
    BASE_LOG_DIR = '/www/wwwlogs/python/beihuo_system'
else:
    # 开发环境：项目根目录下的 logs/
    project_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    BASE_LOG_DIR = os.path.join(project_root, 'logs')

# 任务日志根目录（所有任务相关日志都在此目录下）
TASK_LOG_DIR = os.path.join(BASE_LOG_DIR, 'task_log')

# 统一的错误日志（直接暴露在 TASK_LOG_DIR 根目录，方便快速查看）
ERROR_LOG = os.path.join(TASK_LOG_DIR, 'errors.log')


# 需要按任务拆分日志的模块列表
# 使用规范：
# 1. 新任务先确认是否属于已有 TASK_LOGGERS 模块（如 qpl_auto_bill）
# 2. 如果属于，直接导入对应 logger：from app.utils.xxx import logger
# 3. 如果新建独立任务，把任务名加入 TASK_LOGGERS，并使用 get_task_logger(task_name)
# 4. 禁止在任务文件中使用 logging.getLogger(__name__)
# 新任务需要记录独立日志时，在此添加即可
TASK_LOGGERS = [
    'qpl_auto_bill',                # 汽配龙自动报价
    'btl_auto_bill',                # 巴图鲁自动报价
    'ks_auto_bill',                 # 开思自动对单
    'crm_warehouse_inventory_sync', # CRM 仓库库存同步
    'virtual_inventory',            # 虚拟库存同步
    'vin_vehicle_info_sync',        # VIN 车辆信息补全
    'crm_gzbbr',                    # CRM 爬虫公共模块默认日志
    'data_gzbbr',                   # data.gzbbr 报价接口日志
    'wms_order_push',               # WMS 订单推送
    'wms_return_items_detail',      # WMS 采购入库单明细同步（按指定字段）
    'wms_gzbbr',                    # WMS 爬虫公共模块日志
    'crm_price_sync',               # CRM 产品价格同步
    'replace_number',               # 更新替换号
    'quote_replace_number',         # 报价 OE 替换号自动同步
    'multi_channel_quote_adjust',   # 多渠道报价调价
]


def _create_error_handler():
    """创建统一的错误日志 handler，只记录 ERROR 及以上级别"""
    handler = RotatingFileHandler(
        ERROR_LOG,
        maxBytes=10 * 1024 * 1024,  # 10MB 自动切割
        backupCount=5,
        encoding='utf-8'
    )
    handler.setLevel(logging.ERROR)
    handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(name)s] [%(levelname)s] %(message)s'
    ))
    return handler


def _create_console_handler():
    """创建控制台输出 handler，仅在开发环境使用"""
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter(
        '[%(name)s] [%(levelname)s] %(message)s'
    ))
    return handler


def init_loggers():
    """初始化任务日志

    每个任务会生成两个日志输出：
    1. task_log/{task_name}/{task_name}.log  - 记录 INFO 及以上，用于查看任务完整执行过程
    2. task_log/errors.log                   - 记录 ERROR 及以上，用于快速定位所有任务崩溃
    """
    os.makedirs(TASK_LOG_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(ERROR_LOG), exist_ok=True)

    error_handler = _create_error_handler()

    for task_name in TASK_LOGGERS:
        logger = logging.getLogger(task_name)
        logger.setLevel(logging.INFO)

        # 避免重复添加 handler（Flask debug 重载时会重复执行）
        if logger.handlers:
            continue

        # 每个任务独立子目录
        task_dir = os.path.join(TASK_LOG_DIR, task_name)
        os.makedirs(task_dir, exist_ok=True)

        # 任务自己的日志文件
        log_path = os.path.join(task_dir, f'{task_name}.log')
        task_handler = RotatingFileHandler(
            log_path,
            maxBytes=10 * 1024 * 1024,  # 10MB 自动切割
            backupCount=5,
            encoding='utf-8'
        )
        task_handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s'
        ))

        logger.addHandler(task_handler)
        # 统一的错误汇总，ERROR 及以上会同时写入 errors.log
        logger.addHandler(error_handler)

        # 开发环境同时输出到控制台，效果和 print 一样
        if not IS_PRODUCTION:
            logger.addHandler(_create_console_handler())

        # 禁止向上传播，避免同时写入 uwsgi.log 或根 logger
        logger.propagate = False


def get_task_logger(task_name):
    """获取任务 logger，如果未注册会自动创建一个基础配置

    用法：
        logger = get_task_logger('qpl_auto_bill')
        logger.info('任务开始')
        try:
            do_something()
        except Exception:
            logger.exception('任务失败')  # 会自动记录完整 traceback
    """
    logger = logging.getLogger(task_name)

    if not logger.handlers:
        os.makedirs(TASK_LOG_DIR, exist_ok=True)
        os.makedirs(os.path.dirname(ERROR_LOG), exist_ok=True)

        task_dir = os.path.join(TASK_LOG_DIR, task_name)
        os.makedirs(task_dir, exist_ok=True)

        log_path = os.path.join(task_dir, f'{task_name}.log')
        handler = RotatingFileHandler(
            log_path,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8'
        )
        handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s'
        ))

        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
        logger.addHandler(_create_error_handler())

        # 开发环境同时输出到控制台
        if not IS_PRODUCTION:
            logger.addHandler(_create_console_handler())

        logger.propagate = False

    return logger
