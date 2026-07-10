import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from app.models.orm_models.ks_suyuanma import KsSuyuanma
from app.utils.orm import orm_session


def query_suyuan_data(md, b1, b2):
    """
    查询溯源数据

    Args:
        md: 组织编码，默认为 'fs' (佛山)
        b1: 开始溯源码，默认为 '11'
        b2: 结束溯源码，默认为 '11'

    Returns:
        dict: 接口返回的JSON数据
    """
    url = "http://113.45.176.129:8001/md_ks.start_suyuan"

    payload = f"md={md}&b1={b1}&b2={b2}"

    headers = {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Origin': 'http://113.45.176.129:8001',
        'Pragma': 'no-cache',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest'
    }

    try:
        # 创建 session 并配置重试策略
        session = requests.Session()
        retry_strategy = Retry(
            total=1,  # 最多重试3次
            backoff_factor=1,  # 重试间隔时间因子（1秒、2秒、4秒...）
            status_forcelist=[500, 502, 503, 504],  # 对这些状态码进行重试
            allowed_methods=["POST"]  # 允许重试 POST 请求
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        response = session.request("POST", url, headers=headers, data=payload)

        # 检查响应状态码
        if response.status_code >= 400:
            # 如果是 4xx 或 5xx 错误，返回完整的错误信息
            return {
                'success': False,
                'status_code': response.status_code,
                'data': response.text,
                'headers': dict(response.headers)
            }

        # 尝试解析 JSON
        try:
            result = response.json()
            return {
                'success': True,
                'status_code': response.status_code,
                'data': result,
                'headers': dict(response.headers)
            }
        except ValueError:
            # 如果不是 JSON 格式，返回原始内容
            return {
                'success': False,
                'status_code': response.status_code,
                'data': response.text,
                'headers': dict(response.headers)
            }
    except Exception as e:
        # 捕获所有可能的异常，包括网络错误、连接超时等
        return {
            'success': False,
            'status_code': None,
            'data': str(e),
            'headers':None
        }


def get_suyuan_statistics(md=None):
    """
    获取溯源码统计数据

    Args:
        md: 组织编码，可选，不传则查询所有组织

    Returns:
        list: 统计数据列表，每个元素包含 start_m, end_m, count
    """
    with orm_session() as session:
        results = KsSuyuanma.get_suyuan_statistics(session, md=md)
        dict_list = KsSuyuanma.list_to_dict_list(results)
        return dict_list

# if __name__ == '__main__':

#     a=query_suyuan_data('fs','','')
#     print(a)