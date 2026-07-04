"""
开思自动对单统一日志模块

所有开思自动对单相关日志都通过 ks_log() 输出，保证格式统一、便于 grep 提取。
"""
import threading
import logging

# 线程局部变量，存储当前公司代码
_ks_log_context = threading.local()

# 开思自动对单 logger
logger = logging.getLogger('ks_auto_bill')


def set_ks_log_company(company):
    """设置当前线程的公司代码"""
    _ks_log_context.company = company


def clear_ks_log_company():
    """清除当前线程的公司代码"""
    if hasattr(_ks_log_context, 'company'):
        delattr(_ks_log_context, 'company')


def ks_log(message, module=''):
    """
    输出统一格式的开思自动对单日志

    格式：[公司] [模块] 消息
    日志文件本身已按任务区分，且 logging 自带时间戳，因此不再重复输出。

    示例：
        [zhbbr] [订单] 第1页，共9条订单
    """
    company = getattr(_ks_log_context, 'company', None)
    parts = []
    if company:
        parts.append(f'[{company}]')
    if module:
        parts.append(f'[{module}]')
    parts.append(str(message))

    logger.info(' '.join(parts))
