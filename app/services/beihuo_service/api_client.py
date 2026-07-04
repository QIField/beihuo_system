"""
备货数据 API 客户端

封装对 BI 系统的 API 调用，包括更新和拉取两个接口。
"""

import json
import requests
from typing import Dict, Any, Optional

from .config import UPDATE_API_URL, FETCH_API_URL, DEFAULT_HEADERS, UPDATE_TIMEOUT, FETCH_TIMEOUT


def update_company(company: str) -> Dict[str, Any]:
    """
    调用更新 API，触发后台数据更新
    
    Args:
        company: 门店代码，如 'fsbbr'
        
    Returns:
        {
            'success': bool,
            'message': str,
            'raw_response': Optional[dict/str]
        }
    """
    try:
        response = requests.post(
            UPDATE_API_URL,
            headers=DEFAULT_HEADERS,
            data={"company": company},
            timeout=UPDATE_TIMEOUT
        )
        
        print(f"[统计] [{company}] 更新API响应状态码: {response.status_code}")
        
        if response.status_code != 200:
            return {
                'success': False,
                'message': f'HTTP错误 {response.status_code}',
                'raw_response': response.text[:500]
            }
        
        # 尝试解析JSON
        try:
            result = response.json()
            if isinstance(result, dict):
                if result.get('code') == 0:
                    return {
                        'success': True,
                        'message': '更新请求发送成功',
                        'raw_response': result
                    }
                else:
                    # 检查是否包含成功提示
                    response_text = str(result)
                    if '正在' in response_text or '处理' in response_text:
                        return {
                            'success': True,
                            'message': '更新请求已发送（正在后台处理）',
                            'raw_response': result
                        }
                    return {
                        'success': False,
                        'message': result.get('msg', '未知错误'),
                        'raw_response': result
                    }
            else:
                return {
                    'success': False,
                    'message': '响应格式异常',
                    'raw_response': result
                }
                
        except json.JSONDecodeError:
            # 非JSON响应，检查文本内容
            response_text = response.text
            if '正在' in response_text or '处理' in response_text or 'start' in response_text:
                return {
                    'success': True,
                    'message': '更新请求已发送（正在后台处理）',
                    'raw_response': response_text[:500]
                }
            return {
                'success': False,
                'message': '无法解析响应',
                'raw_response': response_text[:500]
            }
            
    except requests.exceptions.Timeout:
        return {
            'success': True,  # 超时可能意味着请求已发送
            'message': '请求超时（可能仍在后台处理）',
            'raw_response': None
        }
    except requests.exceptions.RequestException as e:
        return {
            'success': False,
            'message': f'网络请求错误: {str(e)}',
            'raw_response': None
        }
    except Exception as e:
        return {
            'success': False,
            'message': f'未知错误: {str(e)}',
            'raw_response': None
        }


def fetch_company(company: str) -> Dict[str, Any]:
    """
    调用拉取 API，获取备货数据
    
    Args:
        company: 门店代码，如 'fsbbr'
        
    Returns:
        {
            'success': bool,
            'message': str,
            'data': List[dict],  # 成功时返回数据列表
            'gx_date': Optional[str],  # 数据更新时间
            'raw_response': Any
        }
    """
    try:
        response = requests.post(
            FETCH_API_URL,
            headers=DEFAULT_HEADERS,
            data={"company": company},
            timeout=FETCH_TIMEOUT
        )
        
        print(f"[统计] [{company}] 拉取API响应状态码: {response.status_code}")
        
        if response.status_code != 200:
            return {
                'success': False,
                'message': f'HTTP错误 {response.status_code}',
                'data': [],
                'gx_date': None,
                'raw_response': response.text[:500]
            }
        
        # 尝试解析JSON
        try:
            result = response.json()
            print(f"[统计] [{company}] 拉取API响应内容类型: {type(result)}")
            
            if not isinstance(result, dict):
                return {
                    'success': False,
                    'message': f'响应格式错误: {type(result)}',
                    'data': [],
                    'gx_date': None,
                    'raw_response': result
                }
            
            # 检查是否包含 data 字段
            if 'data' not in result:
                return {
                    'success': False,
                    'message': '响应中缺少 data 字段',
                    'data': [],
                    'gx_date': None,
                    'raw_response': result
                }
            
            data_list = result.get("data", [])
            if not isinstance(data_list, list):
                return {
                    'success': False,
                    'message': 'data 字段格式异常',
                    'data': [],
                    'gx_date': None,
                    'raw_response': result
                }
            
            gx_date = result.get("gx_date")
            
            return {
                'success': True,
                'message': f'成功获取 {len(data_list)} 条数据',
                'data': data_list,
                'gx_date': gx_date,
                'raw_response': result
            }
            
        except json.JSONDecodeError:
            # 非JSON响应
            response_text = response.text
            if '正在' in response_text or '处理' in response_text:
                return {
                    'success': True,
                    'message': '请求已发送（正在后台处理）',
                    'data': [],
                    'gx_date': None,
                    'raw_response': response_text[:500]
                }
            return {
                'success': False,
                'message': '无法解析JSON响应',
                'data': [],
                'gx_date': None,
                'raw_response': response_text[:500]
            }
            
    except requests.exceptions.Timeout:
        return {
            'success': True,  # 超时可能意味着请求已发送
            'message': '请求超时（可能仍在后台处理）',
            'data': [],
            'gx_date': None,
            'raw_response': None
        }
    except requests.exceptions.RequestException as e:
        return {
            'success': False,
            'message': f'网络请求错误: {str(e)}',
            'data': [],
            'gx_date': None,
            'raw_response': None
        }
    except Exception as e:
        return {
            'success': False,
            'message': f'未知错误: {str(e)}',
            'data': [],
            'gx_date': None,
            'raw_response': None
        }
