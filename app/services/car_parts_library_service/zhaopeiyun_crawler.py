import json
from app.exceptions.crawler_exceptions import CrawlerTokenError
from app.scripts.spiders.spider_entities.zhaopeiyun import ZhaoPeiYunSpider
from app.scripts.spiders.pipeline_clean.zhaopeiyun_clean import clean_all
from app.utils.orm.session import orm_session
from app.models.orm_models.external_system_models.zpy_token import ZpyToken


def get_zpy_token() -> str:
    """
    从数据库获取Zhaopeiyun访问令牌
    :return: token字符串（包含bearer前缀）
    """
    with orm_session() as session:
        token_record = session.query(ZpyToken).order_by(ZpyToken.update_date.desc()).first()
        if token_record and token_record.access_token:  # pyright: ignore[reportGeneralTypeIssues]
            return token_record.access_token  # pyright: ignore[reportReturnType]
    return ""


def get_zhaopeiyun_part_detail(part_code: str):
    """
    从Zhaopeiyun获取配件详情（含数据清洗）
    """
    token = get_zpy_token()
    if not token:
        print("Zhaopeiyun访问令牌为空")
        return None

    spider = ZhaoPeiYunSpider(token=token)

    response = spider.get_oe_detail(brand_code='bmw', part_code=part_code)
    if response is None:
        raise CrawlerTokenError("Zhaopeiyun API返回空响应，请查看token是否过期")
    
   
    # if response.status_code != 200:
    #    print(f"Zhaopeiyun API返回错误状态码: {response.status_code}")
    #    return None

    raw_json = response.json()

   

    data = raw_json.get('data')
    if not data:
        return None

    cleaned_data = clean_all(data)

    spider.close()
    return cleaned_data


# if __name__ == '__main__':
#     cleaned_data = get_zhaopeiyun_part_detail('16117363072')
#     print(json.dumps(cleaned_data, ensure_ascii=False, indent=2))

# 定义装饰器
def zhaopeiyun_decorator(func):
    # 内层包装函数，接收原函数所有参数
    def wrapper(*args, **kwargs):
        part_code = args[0] if args else kwargs.get('oe', None)

        try:
            res = func(*args, **kwargs)
        except Exception:
           
            return get_zhaopeiyun_part_detail(part_code)  # pyright: ignore[reportArgumentType]ata
        
        if not isinstance(res, dict):
            
            return get_zhaopeiyun_part_detail(part_code)  # pyright: ignore[reportArgumentType]ata

        stock_data = res.get('stock')
        detail_data = res.get('detail')

        stock_valid = bool(stock_data) and isinstance(stock_data, dict) and len(stock_data) > 0
        detail_valid = bool(detail_data) and isinstance(detail_data, dict) and len(detail_data) > 0

        if not stock_valid and not detail_valid:
            return get_zhaopeiyun_part_detail(part_code)  # pyright: ignore[reportArgumentType]

        return res
    return wrapper





# if __name__ == '__main__':

#     cleaned_data = get_zhaopeiyun_part_detail('16117363072')
#     print('清洗后的数据（可直接入库）:')
#     print(json.dumps(cleaned_data, ensure_ascii=False, indent=2))
