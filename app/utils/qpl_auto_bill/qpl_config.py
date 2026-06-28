#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""配置"""

from datetime import datetime

# 基础URL
BASE_URL = 'https://qpl-gateway.qipeilong.cn'

# Token缓存（按组织缓存）
_token_cache = {}

# 支持的组织列表
SUPPORTED_COMPANIES = ['fsbbr']

# 宝马自动报价价格系数（后续可改为配置表/前端按钮调整）
BMW_TAX_RATE = 1.13   # 税率
BMW_DISCOUNT = 0.9    # 折扣
BMW_PRICE_FORMULA = lambda net_price: net_price * BMW_TAX_RATE * BMW_DISCOUNT


def qpl_log(message, order_no=None, detail=False, debug=False):
    """
    统一汽配龙自动报价日志格式

    输出格式:
        [2026-06-25 10:17:46] [QPL-QUOTE] [SIQRxxx] [明细] 消息内容
        [2026-06-25 10:17:46] [QPL-QUOTE] [调试] [SIQRxxx] 消息内容

    这样即使多任务日志穿插，也能通过 grep [QPL-QUOTE] 或 [SIQRxxx] 提取。
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    parts = [f"[{timestamp}] [QPL-QUOTE]"]
    if debug:
        parts.append("[调试]")
    if order_no:
        parts.append(f"[{order_no}]")
    if detail:
        parts.append("[明细]")
    parts.append(str(message))
    print(" ".join(parts))


# 组织代码到配置键名的映射
COMPANY_TOKEN_KEY_MAP = {
    'fsbbr': 'QPL_AUTH_TOKEN_fs',
    # 未来可添加更多组织映射
    # 'gzbbr': 'QPL_AUTH_TOKEN_gz',
}

# 组织代码到组织名称的映射
COMPANY_NAME_MAP = {
    'fsbbr': '佛山巴博瑞',
}


def get_qpl_token(company='fsbbr'):
    """
    获取指定组织的Token（延迟加载，从数据库配置获取）
    
    Args:
        company: 组织代码，默认fsbbr
    
    Returns:
        str: Token字符串
    """
    global _token_cache
    
    # 检查缓存
    if company in _token_cache:
        return _token_cache[company]
    
    # 从映射获取配置键名
    config_key = COMPANY_TOKEN_KEY_MAP.get(company)
    if not config_key:
        print(f"[汽配龙配置] 未找到组织 {company} 的Token配置映射")
        return None
    
    # 从数据库获取配置
    from config.config_list_manager.config_cache import get_config_value
    token = get_config_value(config_key)
    
    # 缓存token
    if token:
        _token_cache[company] = token
    
    return token


def get_headers(company='fsbbr'):
    """
    获取指定组织的Headers（延迟加载token）
    
    Args:
        company: 组织代码，默认fsbbr
    
    Returns:
        dict: Headers字典
    """
    token = get_qpl_token(company)
    return {
        'Content-Type': 'application/json',
        'Authorization': token,
        'authtype': 'qpl_merchant',
        'origin': 'https://s.qipeilong.cn',
        'referer': 'https://s.qipeilong.cn/',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'qpl-info': 'QPL/WEB-BIZ',
        'accept': '*/*',
        'accept-language': 'zh-CN,zh;q=0.9'
    }


def clear_token_cache(company=None):
    """
    清除Token缓存
    
    Args:
        company: 组织代码，不传则清除所有缓存
    """
    global _token_cache
    if company:
        _token_cache.pop(company, None)
    else:
        _token_cache = {}


def notify_token_invalid(company='fsbbr'):
    """推送汽配龙Token失效预警"""
    company_name = COMPANY_NAME_MAP.get(company, company)
    remind_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    message = (
        "===【汽配龙业务预警】===\n"
        f"组织：{company_name}\n"
        "汽配龙cookie失效！\n"
        f"提醒时间：{remind_time}\n"
        "请及时核对处理！"
    )
    try:
        from app.utils.common_util_module.server_push import message_push
        return message_push("汽配龙", message)
    except Exception as e:
        print(f"[汽配龙配置][{company}] Token失效预警推送失败: {e}")
        return None


def is_token_invalid_response(resp):
    """判断汽配龙响应是否为Token失效"""
    return resp.status_code == 401 or resp.text.strip() == 'token无效'


def handle_qpl_response(resp, company='fsbbr'):
    """解析汽配龙响应，Token失效时推送预警"""
    if is_token_invalid_response(resp):
        notify_token_invalid(company)
        return {
            'code': 401,
            'message': '汽配龙cookie失效',
            'data': None
        }
    return resp.json()


def get_supported_companies():
    """获取支持的组织列表"""
    return SUPPORTED_COMPANIES.copy()