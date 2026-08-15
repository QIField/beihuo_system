import json

from app.scripts.independent_script_handler.logs import create_logger
from app.scripts.spiders.spider_entities.crm_gzbbr import CrmGzbbrSpider
from app.utils.orm.session import orm_session
from app.models.orm_models.crm.sales_order_history_proto import SalesOrderHistoryProto
from sqlalchemy.dialects.mysql import insert







def time_to_ms(time_str: str):
    """
    时间字符串转换为毫秒级时间戳
    """
    import time

    start_time = int(time.mktime(time.strptime(time_str, '%Y-%m-%d')) * 1000)
    end_time = start_time + 86399000

    return start_time, end_time


def get_sales_order_history_by_page_service(start_str, end_str, spider,logger):
    """
    分页爬取CRM销售订单历史（while 循环版本）

    page_num 控制方式：
    - None = 自动爬取到最后一页
    - 数字 = 只爬取指定页数

    流程：
    1. while True 循环，current_page 从 1 开始累加
    2. 调用 get_sales_order_history 取当前页数据
    3. 无数据直接 break；数据少于 limit，也视为最后一页
    4. 指定了 page_num 时，爬够页数就退出
    5. 不入库、不清洗，返回原始数据列表

    :param start_str: 开始日期字符串，格式 'YYYY-MM-DD'
    :param end_str: 结束日期字符串，格式 'YYYY-MM-DD'
    :param spider: 外部传入的爬虫实例
    :param logger: 日志器
    :param page_num: 爬取页数，None=自动全部，数字=指定页数，默认 None
    :param limit: 每页数量，默认 200
    :return: list[dict] 原始数据列表
    """
   
   

    limit=3000
    create_date_start, _ = time_to_ms(start_str)
    _,create_date_end = time_to_ms(end_str)

    str_date_flag=f"爬取批次: {start_str} 至 {end_str}  "

    all_data = []
    current_page = 1
    while True:
        logger.info(f"{str_date_flag} 正在爬取第 {current_page} 页")
        response = spider.get_sales_order_history(
            page=current_page,
            limit=limit,
            create_date_start=create_date_start,
            create_date_end=create_date_end,
        )

        if response is None:
            logger.error(f"{str_date_flag} 第 {current_page} 页请求失败（网络异常），爬取终止")
            continue

        if response.status_code != 200:
            logger.error(f"{str_date_flag} 第 {current_page} 页请求失败，状态码: {response.status_code}，响应: {response.text[:200]}")
            continue

        try:
            json_data = response.json()
        except ValueError as e:
            logger.error(f"{str_date_flag} 第 {current_page} 页JSON解析失败: {str(e)}，响应内容: {response.text[:200]}")
            continue

        if not isinstance(json_data, dict):
            logger.error(f"{str_date_flag} 第 {current_page} 页返回数据格式异常，不是字典类型")
            continue

        page_data = json_data.get("data", {}).get("data", [])

        if not isinstance(page_data, list):
            logger.error(f"{str_date_flag} 第 {current_page} 页data.data格式异常，不是列表类型")
            continue

        if not page_data:
            logger.info(f"{str_date_flag} 第 {current_page} 页无数据，爬取结束")
            break



        all_data.extend(page_data)





        logger.info(f"{str_date_flag} 第 {current_page} 页获取 {len(page_data)} 条，累计 {len(all_data)} 条")



        if len(page_data) < limit:
            logger.info(f"{str_date_flag} 第 {current_page} 页数量不足 {limit} 条，已到最后一页，爬取结束")
            break

        current_page += 1

    logger.info(f"{str_date_flag} 共爬取 {len(all_data)} 条数据")

    return all_data


   






def batch_store_sales_order_history(data_list, batch_id, time_batch_id, logger):
    """
    批量存储销售订单历史原始数据到数据库

    使用 on_duplicate_key_update 实现 upsert，以 sales_order_id 为唯一键

    :param data_list: list[dict] 原始数据列表，每个元素为一条销售订单历史记录
    :param batch_id: 批次ID
    :param time_batch_id: 时间批次ID
    :param logger: 可选日志器
    :return: int 成功入库的记录数
    """
    if not data_list:
        raise ValueError(f"数据列表不能为空，批次ID: {batch_id}，时间批次ID: {time_batch_id}")

    db_data = []
    for item in data_list:
        sales_order_id = str(item.get('ddno') or item.get('ddsapno') or '')
        if not sales_order_id:
            logger.warning(f"批次ID: {batch_id}，时间批次ID: {time_batch_id}  ==  销售订单ID为空，跳过数据: {item}")
            continue
        db_data.append({
            'time_batch_id': time_batch_id,
            'batch_id': batch_id,
            'sales_order_id': sales_order_id,
            'json_text': json.dumps(item, ensure_ascii=False),
            'orders_items_id': item.get('orders_items_id') or '',

        })

    if not db_data:
        logger.warning(f"批次ID: {batch_id}，时间批次ID: {time_batch_id}  ==  过滤后无有效数据，跳入库")
        return 0

    with orm_session() as session:
        insert_stmt = insert(SalesOrderHistoryProto.__table__).values(db_data)

        skip_cols = {'id', 'create_time', 'update_time'}
        all_cols = SalesOrderHistoryProto.__table__.columns.keys()
        update_dict = {
            k: insert_stmt.inserted[k]
            for k in all_cols
            if k not in skip_cols
        }

        update_stmt = insert_stmt.on_duplicate_key_update(**update_dict)
        result = session.execute(update_stmt)
        affected = result.rowcount  # pyright: ignore[reportAttributeAccessIssue]
        
        if affected == len(db_data):
            # 有数据入库成功
            logger.info(f"批次ID: {batch_id}，时间批次ID: {time_batch_id}   ==入库成功   共 {affected} 条数据成功入库")
        else:
            # 0条入库，区分两种场景：正常无数据 / 异常
            logger.warning(f"批次ID: {batch_id}，时间批次ID: {time_batch_id} ==入库失败 共 {affected} 条数据成功入库")




    
    logger.info(f"批次ID: {batch_id}，时间批次ID: {time_batch_id}  ==  销售订单历史原始数据入库完成，共 {affected} 条")

    return affected




def get_sales_order_history_for(start_date,batch_id):
    from datetime import datetime, timedelta

    logger = create_logger()
    spider = CrmGzbbrSpider()

    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    all_data = 0
    current_start = start_dt
    batch_days = 4
    logger.info("="*100)
    logger.info("="*100)
    logger.info("="*100)
    logger.info(f"==========批次ID: {batch_id}================")
    logger.warning(f"==========批次ID: {batch_id}================")
    logger.info("开始爬取CRM销售订单历史")
    logger.info(f"开始日期: {start_date}")
    logger.info(f"结束日期: {today.strftime('%Y-%m-%d')}")
    
   

    while current_start <= today:  # pyright: ignore[reportOperatorIssue]
        try:
            current_end = current_start + timedelta(days=batch_days - 1)
            if current_end > today:  # pyright: ignore[reportOperatorIssue]
                current_end = today

            start_str = current_start.strftime('%Y-%m-%d')  # pyright: ignore[reportAttributeAccessIssue]
            end_str = current_end.strftime('%Y-%m-%d')  # pyright: ignore[reportAttributeAccessIssue]
            logger.info("*"*50)
            logger.info(f"正在爬取批次: {start_str} 至 {end_str}")
            time_batch_id =f"{start_str}_{end_str}"
            batch_data = get_sales_order_history_by_page_service(
                start_str=start_str,
                end_str=end_str,
                spider=spider,
                logger=logger,
            )


            batch_store_sales_order_history(batch_data, batch_id, time_batch_id, logger=logger)

            all_data += len(batch_data)




            logger.info(f"批次 {start_str} ~ {end_str} 完成，累计 {all_data} 条")
            logger.info("*"*50)
            current_start = current_end + timedelta(days=1)
            
            







        except Exception as e:
            logger.error(f"批次 {start_str} ~ {end_str} 爬取失败: {str(e)}")
            current_start = current_end + timedelta(days=1)
            continue




    logger.info(f"全部批次爬取完成，共 {all_data} 条数据")

    logger.info("="*100)
    logger.info("="*100)
    logger.info("="*100)

  

    return all_data


if __name__ == "__main__":
    import time
    start_date = "2024-01-01"
    start_time = int(time.time())
    get_sales_order_history_for(start_date,f"{start_date}+{start_time}")
    