# -*- coding:utf-8 -*-
# @Time    : 2026/07/24
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : order_history_clean.py
# @Software: trae-cn

import json
import numpy as np
import pandas as pd
from typing import List, Dict

from sqlalchemy.dialects.mysql import insert

from app.scripts.independent_script_handler.logs import create_logger
from app.utils.orm.session import orm_session
from app.models.orm_models.crm.sales_order_history_proto import SalesOrderHistoryProto
from app.models.orm_models.crm.sales_order_history import SalesOrderHistory


def clean_sales_order_history(data_list: List[Dict], store: str) -> List[Dict]:
    """
    销售订单历史数据清洗函数

    该函数执行以下操作：
    1. 将原始数据列表转换为 DataFrame
    2. 按 model_fields 过滤保留字段
    3. 添加门店标识 store
    4. 数字字段空值处理：空字符串/空格/None/NaN → -1，并转为 int
    5. 数量字段处理：转为 int，空值填 0
    6. 金额字段处理：转为 float，空值填 0
    7. 将清洗后的数据转换回字典列表

    :param data_list: 原始数据字典列表
    :param store: 仓库/门店标识
    :return: 清洗后的销售订单历史数据列表
    """
    # 空数据直接返回
    if not data_list:
        return []

    # 将数据列表转换为 DataFrame
    df = pd.DataFrame(data_list)

    # 要保留的字段（与 sales_order_history 模型一致）
    model_fields = [
        # 人员相关
        'handler',                  # 处理人ID
        'user_id',                  # 用户ID（经收人）
        'seller_id',                # 销售员ID
        'customer_id',              # 客户ID
        # 订单类型与时间
        'order_type_id',            # 订单类型ID
        'create_date',              # 创建时间戳
        'send_date',                # 发货时间戳
        # 订单标识
        'orders_id',                # 订单ID
        'ddno',                     # 订单号
        'ddsapno',                  # 订单金蝶号
        # 状态
        'status',                   # 订单状态（中文）
        'origin_status',            # 原始状态码
        # 客户信息
        'fullname',                 # 客户全称
        # 数量
        'quantity',                 # 数量
        'sfqty',                    # 实发数量
        # 金额
        'price',                    # 单价
        'cost_price',               # 成本价
        'total_price',              # 总价
        'sfje',                     # 实付金额
        # 产品信息
        'product_id',               # 产品ID
        'orders_items_id',          # 订单明细ID（主键）
        'brand_id',                 # 品牌ID
        'pdname',                   # 产品名称
        'frey_no',                  # 菲尔号
        'l_model_zh',               # 车型（中文）
        'number',                   # OE号
        # WMS与发货
        'is_wms',                   # 是否WMS订单
        'delivery_status',          # 发货状态
        'logistics_name',           # 物流公司名称
        'kingdee_status',           # 金蝶状态
        'logistics_user_id',        # 物流用户ID
        # 仓库与品牌
        'warehouse_no',             # 仓库编号
        'brand_name',               # 品牌名称
        # 订单类型与人员名称
        'order_type_name',          # 订单类型名称
        'user_name',                # 用户名
        'creater',                  # 创建人
        'seller_name',              # 销售员名称
        # 发货单号
        'deliverysapno',            # 发货金蝶号
        'deliveryordersno'          # 发货单号
    ]

    # 只保留存在的字段，避免字段缺失报错
    available_fields = [field for field in model_fields if field in df.columns]
    df = df[available_fields].copy()

    # 添加门店标识
    df['store'] = store

    # 数字字段空值处理：空字符串/空格/None/NaN → -1，并转为 int
    numeric_cols = [
        'handler', 'user_id', 'seller_id', 'customer_id',
        'order_type_id', 'orders_id', 'origin_status',
        'product_id', 'orders_items_id', 'brand_id', 'is_wms',
        'delivery_status', 'kingdee_status', 'logistics_user_id'
    ]
    available_numeric_cols = [col for col in numeric_cols if col in df.columns]

    for col in available_numeric_cols:
        # 替换各种空值形式为 -1
        df[col] = df[col].replace(['', r'^\s*$', None, np.nan], -1, regex=True)  # pyright: ignore[reportAttributeAccessIssue]
        try:
            # 转为数值类型，失败的填 -1，最终转成 int
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(-1).astype(int)  # pyright: ignore[reportAttributeAccessIssue]
        except:
            pass

    # 数量字段处理：转为 int，空值填 0
    quantity_cols = ['quantity', 'sfqty']
    available_quantity_cols = [col for col in quantity_cols if col in df.columns]

    for col in available_quantity_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)  # pyright: ignore[reportAttributeAccessIssue]

    # 金额字段处理：转为 float，空值填 0
    amount_cols = [
        'price', 'cost_price', 'total_price', 'sfje'
    ]
    available_amount_cols = [col for col in amount_cols if col in df.columns]

    for col in available_amount_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)  # pyright: ignore[reportAttributeAccessIssue]

    # 将清洗后的 DataFrame 转换为字典列表
    clean_data_list = df.to_dict('records')  # pyright: ignore[reportArgumentType]

    return clean_data_list  # pyright: ignore[reportReturnType]


def fetch_proto_data(
    batch_id: str = None,  # pyright: ignore[reportArgumentType]
    time_batch_id: str = None,  # pyright: ignore[reportArgumentType]
    offset: int = 0,
    limit: int = 2000,
    logger=None
) -> List[Dict]:  # pyright: ignore[reportArgumentType]
    """
    从 sales_order_history_proto 表分页读取原始 JSON 数据并解析

    支持按 batch_id 或 time_batch_id 筛选数据，
    解析每条记录的 json_text 字段为字典。
    支持分页参数 offset 和 limit，用于分批读取。

    :param batch_id: 批次ID，可选
    :param time_batch_id: 时间批次ID，可选
    :param offset: 分页偏移量，默认 0
    :param limit: 每页读取条数，默认 2000
    :param logger: 日志器，可选
    :return: 解析后的原始数据字典列表
    """
    with orm_session() as session:
        # 构建查询
        query = session.query(SalesOrderHistoryProto)

        # 按批次ID筛选
        if batch_id:
            query = query.filter(SalesOrderHistoryProto.batch_id == batch_id)
        # 按时间批次ID筛选
        if time_batch_id:
            query = query.filter(SalesOrderHistoryProto.time_batch_id == time_batch_id)

        # 按 id 排序，保证分页顺序一致
        query = query.order_by(SalesOrderHistoryProto.id)

        # 分页
        proto_list = query.offset(offset).limit(limit).all()

        result = []
        for proto in proto_list:
            # 跳过空的 json_text
            if not proto.json_text:  # pyright: ignore[reportGeneralTypeIssues]
                continue
            try:
                # 解析 JSON 字符串为字典
                item = json.loads(proto.json_text)  # pyright: ignore[reportArgumentType]
                result.append(item)
            except (json.JSONDecodeError, TypeError) as e:
                # 解析失败记录日志，继续下一条
                if logger:
                    logger.warning(f"解析JSON失败，proto id={proto.id}, error: {str(e)}")
                continue

        if logger:
            logger.info(
                f"从 sales_order_history_proto 读取 {len(proto_list)} 条 "
                f"(offset={offset}, limit={limit})，成功解析 {len(result)} 条"
            )

        return result


def batch_upsert_sales_order_history(clean_data_list: List[Dict], logger=None) -> int:
    """
    批量 upsert 销售订单历史数据到 sales_order_history 表

    使用 on_duplicate_key_update 实现幂等入库，
    以 orders_items_id 为唯一键，冲突时更新其他字段。

    :param clean_data_list: 清洗后的数据字典列表
    :param logger: 日志器，可选
    :return: 受影响的行数（含插入和更新）
    """
    # 空数据直接返回
    if not clean_data_list:
        if logger:
            logger.warning("清洗后无数据，跳过入库")
        return 0

    with orm_session() as session:
        # 构建批量 insert 语句
        insert_stmt = insert(SalesOrderHistory.__table__).values(clean_data_list)

        # 主键和自动更新字段不参与更新
        skip_cols = {'orders_items_id', 'created_at', 'updated_at'}
        all_cols = SalesOrderHistory.__table__.columns.keys()
        # 构建需更新的字段字典
        update_dict = {
            k: insert_stmt.inserted[k]
            for k in all_cols
            if k not in skip_cols
        }

        # on duplicate key update 实现 upsert
        update_stmt = insert_stmt.on_duplicate_key_update(**update_dict)
        result = session.execute(update_stmt)
        affected = result.rowcount  # pyright: ignore[reportAttributeAccessIssue]

        if logger:
            logger.info(f"sales_order_history 入库完成，共 {affected} 条（含更新）")

        return affected


def clean_and_store_sales_order_history(
    store: str = "fs",
    batch_id: str = None,  # pyright: ignore[reportArgumentType]
    time_batch_id: str = None,  # pyright: ignore[reportArgumentType]
    batch_size: int = 2000
) -> int:  # pyright: ignore[reportArgumentType]
    """
    销售订单历史数据清洗入库主入口（分批处理）

    执行流程：
    循环执行以下步骤，直到读取完所有数据：
    1. 从 sales_order_history_proto 表分批读取原始 JSON 数据
    2. 调用 clean_sales_order_history 清洗数据
    3. 调用 batch_upsert_sales_order_history 批量入库

    :param store: 门店标识，默认 "fs"
    :param batch_id: 批次ID，可选，None 表示全量
    :param time_batch_id: 时间批次ID，可选
    :param batch_size: 每批处理的数据条数，默认 2000
    :return: 成功入库的总记录数
    """
    # 创建日志器
    logger = create_logger()

    logger.info("=" * 80)
    logger.info("开始销售订单历史数据清洗入库（分批处理）")
    logger.info(f"store={store}, batch_id={batch_id}, time_batch_id={time_batch_id}, batch_size={batch_size}")

    offset = 0
    total_affected = 0
    batch_num = 0

    while True:
        # 第一步：从 proto 表分批读取原始数据
        proto_data_list = fetch_proto_data(
            batch_id=batch_id,
            time_batch_id=time_batch_id,
            offset=offset,
            limit=batch_size,
            logger=logger
        )

        # 无数据则结束循环
        if not proto_data_list:
            logger.info("已读取完所有数据，结束分批处理")
            break

        batch_num += 1

        # 第二步：数据清洗
        clean_data_list = clean_sales_order_history(proto_data_list, store)

        logger.info(
            f"第 {batch_num} 批：原始数据 {len(proto_data_list)} 条，"
            f"清洗后 {len(clean_data_list)} 条"
        )

        # 第三步：批量入库
        affected = batch_upsert_sales_order_history(clean_data_list, logger=logger)
        total_affected += affected

        # 偏移量累加
        offset += len(proto_data_list)

        # 如果读取的数量小于 batch_size，说明已经是最后一批
        if len(proto_data_list) < batch_size:
            logger.info("已读取完所有数据，结束分批处理")
            break

    logger.info(f"销售订单历史数据清洗入库完成，共 {batch_num} 批，总计 {total_affected} 条")
    logger.info("=" * 80)

    return total_affected


if __name__ == "__main__":
    # 直接运行脚本时，全量清洗 fos 门店的数据
    clean_and_store_sales_order_history(store="fs")
