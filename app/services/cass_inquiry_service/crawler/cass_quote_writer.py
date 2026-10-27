"""
卡思商城报价数据入库

与原脚本 save_to_database 逐字段一致：
- 目标表 cass_inquiry_quote，唯一键(询单日期+询单ID+报价行ID)，重复行按最新数据更新
- 无报价行ID（如归档单）时按行内容生成 MD5 摘要
- crawl_date 仅记录最近一次运行日
- 连接走项目 db_cursor（跟随启动菜单选库，与修理厂询价单页面查询同源）
"""

import datetime
import hashlib

from app.utils.database_connection import db_cursor

INSERT_SQL = (
    "INSERT INTO cass_inquiry_quote "
    "(crawl_date, inquiry_date, inquiry_id, quote_id, num, vin, car_model, description, "
    "decode_num, merchant_parts_num, price_4s, parts_name, brand_name, quality_name, store_name, "
    "seller_price, remark, selling_point_tag, location_name, replacement) "
    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
    "ON DUPLICATE KEY UPDATE "
    "crawl_date=VALUES(crawl_date), num=VALUES(num), vin=VALUES(vin), "
    "car_model=VALUES(car_model), description=VALUES(description), "
    "decode_num=VALUES(decode_num), merchant_parts_num=VALUES(merchant_parts_num), "
    "price_4s=VALUES(price_4s), parts_name=VALUES(parts_name), brand_name=VALUES(brand_name), "
    "quality_name=VALUES(quality_name), "
    "store_name=VALUES(store_name), seller_price=VALUES(seller_price), remark=VALUES(remark), "
    "selling_point_tag=VALUES(selling_point_tag), location_name=VALUES(location_name), "
    "replacement=VALUES(replacement)"
)

CHUNK_SIZE = 500


def save_quote_rows(rows, on_saved=None):
    """
    批量入库报价行记录

    :param rows: 行记录列表（中文字段名，与解析层输出一致）
    :param on_saved: 可选回调 on_saved(saved_count)，每批入库后通知进度
    :return: 入库总行数
    """
    crawl_date = datetime.date.today().strftime('%Y-%m-%d')
    total = 0
    chunk = []
    with db_cursor(dict_cursor=False) as cursor:
        for rec in rows:
            iid = _s(rec['询单ID'])
            if not iid:
                continue
            qid = _s(rec['报价行ID'])
            if not qid:  # 无平台报价行ID（如归档单）时按行内容生成稳定摘要
                qid = hashlib.md5((_s(rec['译码']) + '|' + _s(rec['商家替换号']) + '|' + _s(rec['零件名称']) + '|'
                                   + _s(rec['品牌名称']) + '|' + _s(rec['供应商名称']) + '|' + _s(rec['卖家价格']) + '|'
                                   + _s(rec['发货地区'])).encode('utf-8')).hexdigest()
            chunk.append((
                crawl_date, _s(rec['日期']), iid, qid, _s(rec['数量']), _s(rec['vin']),
                _s(rec['车型']), _s(rec['描述']), _s(rec['译码']),
                _s(rec['商家替换号']), _s(rec['4S参考价']), _s(rec['零件名称']),
                _s(rec['品牌名称']), _s(rec['品质']), _s(rec['供应商名称']), _s(rec['卖家价格']),
                _s(rec['报价备注']), _s(rec['卖点标签']), _s(rec['发货地区']), _s(rec['替换']),
            ))
            if len(chunk) >= CHUNK_SIZE:
                cursor.executemany(INSERT_SQL, chunk)
                total += len(chunk)
                chunk = []
                if on_saved:
                    on_saved(total)
        if chunk:
            cursor.executemany(INSERT_SQL, chunk)
            total += len(chunk)
            if on_saved:
                on_saved(total)
    return total


def _s(v):
    """空值转空串（原脚本 s() 语义：None/NaN -> ''）"""
    return '' if v is None else str(v)
