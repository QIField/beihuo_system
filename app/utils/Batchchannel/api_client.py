import requests
from typing import Dict, Any, List, Union

API_URL = "https://data.gzbbr.com/admin/Cass.ChannelPrice/BatchChannel"


def batch_channel_request(product_ids: Union[str, List[str], int, List[int]], cookie: str) -> Dict[str, Any]:
    """
    批量推送渠道价格信息

    Args:
        product_ids: 产品ID，可以是单个ID、ID列表、逗号分隔的字符串
        cookie: Cookie字符串（从逻辑层通过 get_config_value 获取）

    Returns:
        {
            'success': bool,
            'status': str,
            'msg': str
        }
    """
    # 格式化 product_id
    if isinstance(product_ids, (list, tuple)):
        product_id_str = ','.join(str(pid) for pid in product_ids)
    else:
        product_id_str = str(product_ids)

    # 准备请求数据
    payload = {'product_id': product_id_str}

    # 设置请求头（与浏览器完全一致）
    headers = {
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
        'Origin': 'https://data.gzbbr.com',
        'Referer': 'https://data.gzbbr.com/admin/Cass.ChannelPrice/index.html',
        'Sec-Ch-Ua': '"Microsoft Edge";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.0 Edg/147.0.0.0',
        'X-Requested-With': 'XMLHttpRequest',
        'Cookie': cookie
    }

    try:
        response = requests.post(
            API_URL,
            headers=headers,
            data=payload,
            timeout=30
        )
        response.raise_for_status()

        result = response.json()
        return {
            'success': result.get('status') == '00',
            'status': result.get('status', ''),
            'msg': result.get('msg', '')
        }

    except requests.exceptions.RequestException as e:
        return {'success': False, 'status': '01', 'msg': f'请求失败: {str(e)}'}
    except Exception as e:
        return {'success': False, 'status': '01', 'msg': f'错误: {str(e)}'}
