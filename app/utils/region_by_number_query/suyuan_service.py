import requests
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

    response = requests.request("POST", url, headers=headers, data=payload)
    result = response.json()

    return result


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

if __name__ == '__main__':
    a=query_suyuan_data('fs','DS495579','DS498578')
    print(a)