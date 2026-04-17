"""
开思商家平台接口客户端

提供三个接口的HTTP请求封装
"""

import requests
from typing import Dict, Any, Optional
from datetime import datetime

from .config import (
    BASE_URL,
    API_ENDPOINTS,
    DEFAULT_HEADERS,
    DEFAULT_BUSINESS_INDICATOR_PAYLOAD,
)


def _make_get_request(
    endpoint: str,
    headers: Optional[Dict[str, str]] = None,
    cookies: Optional[Dict[str, str]] = None
) -> Optional[Dict[str, Any]]:
    """
    发送GET请求
    
    Args:
        endpoint: API端点路径
        headers: 请求头（可选）
        cookies: Cookie（可选，用于认证）
        
    Returns:
        响应JSON数据，失败返回None
    """
    url = f"{BASE_URL}{endpoint}"
    request_headers = {**DEFAULT_HEADERS, **(headers or {})}
    
    # 将 cookie 字典转换为字符串并放入 headers
    if cookies:
        cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
        request_headers['Cookie'] = cookie_str
    
    try:
        response = requests.get(
            url,
            headers=request_headers,
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"请求失败: {url}, 错误: {e}")
        return None
    except Exception as e:
        print(f"解析响应失败: {url}, 错误: {e}")
        return None


def _make_post_request(
    endpoint: str,
    payload: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
    cookies: Optional[Dict[str, str]] = None
) -> Optional[Dict[str, Any]]:
    """
    发送POST请求
    
    Args:
        endpoint: API端点路径
        payload: 请求体数据
        headers: 请求头（可选）
        cookies: Cookie（可选，用于认证）
        
    Returns:
        响应JSON数据，失败返回None
    """
    url = f"{BASE_URL}{endpoint}"
    request_headers = {**DEFAULT_HEADERS, **(headers or {})}
    
    # 将 cookie 字典转换为字符串并放入 headers
    if cookies:
        cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
        request_headers['Cookie'] = cookie_str
    
    try:
        response = requests.post(
            url,
            json=payload,
            headers=request_headers,
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"请求失败: {url}, 错误: {e}")
        return None
    except Exception as e:
        print(f"解析响应失败: {url}, 错误: {e}")
        return None


def fetch_event_summary(
    cookies: Optional[Dict[str, str]] = None
) -> Optional[Dict[str, Any]]:
    """
    获取每日事件总数统计（接口1）
    
    获取最近7天的事件总数数据
    
    Args:
        cookies: Cookie（用于认证）
        
    Returns:
        响应数据格式:
        {
            "code": 200,
            "errorMessage": null,
            "data": [
                {"eventCount": 30, "eventDate": "04-09"},
                ...
            ]
        }
    """
    return _make_get_request(
        API_ENDPOINTS["event_summary"],
        cookies=cookies
    )


def fetch_event_detail(
    cookies: Optional[Dict[str, str]] = None
) -> Optional[Dict[str, Any]]:
    """
    获取每日事件详情（接口2）
    
    获取指定日期的事件详情列表
    
    Args:
        cookies: Cookie（用于认证）
        
    Returns:
        响应数据格式:
        {
            "code": 200,
            "errorMessage": null,
            "data": [
                {
                    "eventTypeKey": "QUOTATION_SUBMIT_OVERDUE",
                    "eventTypeName": "报价单超10分钟未报价",
                    "eventCount": 2,
                    "statisticsUnit": "单",
                    "eventDate": "2026-04-15",
                    "eventInfluence": "...",
                    "eventSuggest": "..."
                },
                ...
            ]
        }
    """
    return _make_get_request(
        API_ENDPOINTS["event_detail"],
        cookies=cookies
    )


def fetch_business_indicator(
    payload: Optional[Dict[str, Any]] = None,
    cookies: Optional[Dict[str, str]] = None
) -> Optional[Dict[str, Any]]:
    """
    获取经营分析概览数据（接口3）
    
    获取近7天的经营指标数据
    
    Args:
        payload: 请求体（可选，默认使用配置中的默认值）
        cookies: Cookie（用于认证）
        
    Returns:
        响应数据格式:
        {
            "code": 200,
            "errorMessage": null,
            "data": {
                "statisticsPeriodInfo": "近7天",
                "heads": [...],
                "rows": [...]
            }
        }
    """
    request_payload = payload or DEFAULT_BUSINESS_INDICATOR_PAYLOAD
    return _make_post_request(
        API_ENDPOINTS["business_indicator"],
        request_payload,
        cookies=cookies
    )


# 便捷函数：获取所有数据
def fetch_all_data(
    cookies: Optional[Dict[str, str]] = None
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    获取所有三个接口的数据
    
    Args:
        cookies: Cookie（用于认证）
        
    Returns:
        包含三个接口数据的字典
        {
            "event_summary": {...},
            "event_detail": {...},
            "business_indicator": {...}
        }
    """
    return {
        "event_summary": fetch_event_summary(cookies),
        "event_detail": fetch_event_detail(cookies),
        "business_indicator": fetch_business_indicator(cookies=cookies),
    }
