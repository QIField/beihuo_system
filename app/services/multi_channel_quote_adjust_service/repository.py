"""
多渠道报价调价 - 数据访问层

职责：
- supplier_info 表查询
- qq_msg 表写入
- multi_channel_quote_import 表写入/查询
"""

from typing import List, Dict, Any

from app.utils.database_connection import db_cursor


def fetch_suppliers_by_car_brand(car_brand: str) -> List[Dict[str, Any]]:
    """
    根据车辆品牌从 supplier_info 表查询匹配的供应商

    匹配规则：supplier_info.car_brand 包含输入的车辆品牌即匹配
    （如车辆品牌为'宝马'，可匹配 '宝马'、'奔驰/宝马' 等记录）
    """
    if not car_brand:
        return []

    sql = """
        SELECT `id`, `supplier`, `car_brand`, `main_business`
        FROM `supplier_info`
        WHERE `car_brand` LIKE %s
    """
    with db_cursor(dict_cursor=True) as cursor:
        cursor.execute(sql, (f"%{car_brand}%",))
        return cursor.fetchall()


def save_to_qq_msg(rows: List[Dict[str, Any]]) -> None:
    """
    将 OE / 供应商 / QQ 保存到 qq_msg 表

    Args:
        rows: 展开后的行，每个元素包含 oe, supplier_text, qq
    """
    if not rows:
        return

    insert_sql = """
        INSERT INTO `qq_msg` (`OE`, `供应商`, `QQ`)
        VALUES (%s, %s, %s)
    """

    with db_cursor(dict_cursor=False) as cursor:
        for row in rows:
            cursor.execute(
                insert_sql,
                (
                    row.get("oe", ""),
                    row.get("supplier_text", ""),
                    row.get("qq", ""),
                ),
            )


def save_import_records(rows: List[Dict[str, Any]], create_by: str = "") -> None:
    """
    将导入并匹配 CRM 后的完整行保存到 multi_channel_quote_import 表

    Args:
        rows: 组装后的前端行，包含 oe, brand, car_brand, supplier, system_oe,
              sell_price, cost_price, profit_rate, profit_amount,
              product_id, barcode 等字段
        create_by: 导入人
    """
    if not rows:
        return

    insert_sql = """
        INSERT INTO `multi_channel_quote_import`
        (`oe`, `brand`, `car_brand`, `inquiry_supplier`, `system_oe`,
         `sell_price`, `cost_price`, `profit_rate`, `profit_amount`,
         `product_id`, `barcode`, `create_by`, `create_time`)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
    """

    with db_cursor(dict_cursor=False) as cursor:
        for row in rows:
            cursor.execute(
                insert_sql,
                (
                    row.get("oe", ""),
                    row.get("brand", ""),
                    row.get("car_brand", ""),
                    row.get("supplier", ""),
                    row.get("system_oe", ""),
                    row.get("sell_price", ""),
                    row.get("cost_price", ""),
                    row.get("profit_rate", ""),
                    row.get("profit_amount", ""),
                    row.get("product_id", ""),
                    row.get("barcode", ""),
                    create_by,
                ),
            )


def fetch_recent_imports(hours: int = 36) -> List[Dict[str, Any]]:
    """
    查询最近 N 小时内导入的完整报价数据

    Args:
        hours: 时间窗口（小时），默认 36 小时

    Returns:
        可直接返回给前端的行列表
    """
    sql = """
        SELECT `oe`, `brand`, `car_brand`, `inquiry_supplier`, `system_oe`,
               `sell_price`, `cost_price`, `profit_rate`, `profit_amount`,
               `product_id`, `barcode`
        FROM `multi_channel_quote_import`
        WHERE `create_time` >= DATE_SUB(NOW(), INTERVAL %s HOUR)
        ORDER BY `create_time` DESC, `id` DESC
    """

    with db_cursor(dict_cursor=True) as cursor:
        cursor.execute(sql, (hours,))
        rows = cursor.fetchall()

    return [
        {
            "oe": row["oe"],
            "brand": row["brand"],
            "car_brand": row["car_brand"],
            "system_oe": row["system_oe"] or "",
            "supplier": row["inquiry_supplier"] or "",
            "sell_price": row["sell_price"] or "",
            "cost_price": row["cost_price"] or "",
            "profit_rate": row["profit_rate"] or "",
            "profit_amount": row["profit_amount"] or "",
            "supplier_selected": "",
            "cass_price": "",
            "peer_price": "",
            "qpl_price": "",
            "new_profit_rate": "",
            "new_profit_amount": "",
            "product_id": row["product_id"] or "",
            "barcode": row["barcode"] or "",
            "modify": "是",
            "qq": row["inquiry_supplier"] or "",
        }
        for row in rows
    ]


def save_update_log(log_item: Dict[str, Any]) -> None:
    """
    将批量更新价格日志写入 multi_channel_quote_update_log 表

    Args:
        log_item: 单条更新日志字典
    """
    insert_sql = """
        INSERT INTO `multi_channel_quote_update_log`
        (`company`, `oe`, `product_id`, `sell_price`, `company_price_id`,
         `index_product_id`, `company_id`, `company_name`, `original_price`,
         `original_peer_price`, `min_quantity`, `start_date`, `end_date`,
         `price_status`, `update_request_params`, `update_response`, `status`,
         `error_msg`, `create_by`, `create_time`)
        VALUES
        (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
    """

    with db_cursor(dict_cursor=False) as cursor:
        cursor.execute(
            insert_sql,
            (
                log_item.get("company", ""),
                log_item.get("oe", ""),
                log_item.get("product_id", ""),
                log_item.get("sell_price", ""),
                log_item.get("company_price_id", ""),
                log_item.get("index_product_id", ""),
                log_item.get("company_id", ""),
                log_item.get("company_name", ""),
                log_item.get("original_price", ""),
                log_item.get("original_peer_price", ""),
                log_item.get("min_quantity", 1),
                log_item.get("start_date", ""),
                log_item.get("end_date", ""),
                log_item.get("price_status", 1),
                log_item.get("update_request_params", ""),
                log_item.get("update_response", ""),
                log_item.get("status", ""),
                log_item.get("error_msg", ""),
                log_item.get("create_by", ""),
            ),
        )


def delete_import_record(company: str, oe: str, product_id: str) -> None:
    """
    根据公司、OE、产品ID删除导入记录

    Args:
        company: 公司代码
        oe: OE号
        product_id: 产品ID
    """
    sql = """
        DELETE FROM `multi_channel_quote_import`
        WHERE `oe` = %s AND `product_id` = %s
    """

    with db_cursor(dict_cursor=False) as cursor:
        cursor.execute(sql, (oe, product_id))


# ====================== QQ 聊天消息转换 ======================
"""
结果表建表语句（请在数据库执行一次）：

CREATE TABLE IF NOT EXISTS `qq_chat_message_result` (
    `id` BIGINT NOT NULL AUTO_INCREMENT,
    `chat_message_id` BIGINT NOT NULL COMMENT '关联 qq_chat_message.序号',
    `supplier` VARCHAR(255) NOT NULL DEFAULT '' COMMENT '发送对象',
    `供应商` VARCHAR(100) NOT NULL DEFAULT '' COMMENT '供应商简称',
    `search_oe` VARCHAR(100) NOT NULL DEFAULT '' COMMENT '搜索OE',
    `result_oe` VARCHAR(100) NOT NULL DEFAULT '' COMMENT '结果OE',
    `price` DECIMAL(12, 2) NOT NULL DEFAULT 0 COMMENT '价格',
    `brand` VARCHAR(100) NOT NULL DEFAULT '' COMMENT '品牌',
    `conversion_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '转换时间',
    PRIMARY KEY (`id`),
    KEY `idx_chat_message_id` (`chat_message_id`),
    KEY `idx_search_oe` (`search_oe`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='QQ聊天消息转换结果';

已建表后新增字段请执行：
ALTER TABLE `qq_chat_message_result`
ADD COLUMN `供应商` VARCHAR(100) NOT NULL DEFAULT '' COMMENT '供应商简称'
AFTER `supplier`;
"""


def fetch_unconverted_qq_chat_messages(limit: int = 100) -> List[Dict[str, Any]]:
    """
    查询 qq_chat_message 表中转换状态为空的记录

    Args:
        limit: 单次处理条数上限

    Returns:
        消息记录列表，包含 序号, 发送对象, 发送内容, 回复内容
    """
    sql = """
        SELECT `序号`, `发送对象`, `发送内容`, `回复内容`
        FROM `qq_chat_message`
        WHERE `转换状态` IS NULL OR `转换状态` = ''
        ORDER BY `序号` ASC
        LIMIT %s
    """
    with db_cursor(dict_cursor=True) as cursor:
        cursor.execute(sql, (limit,))
        return cursor.fetchall()


def update_qq_chat_message_status(message_id: int, status: str) -> None:
    """
    更新 qq_chat_message 转换状态

    Args:
        message_id: 消息序号（主键）
        status: 转换状态，如 '已转换'、'转换对象不符合'
    """
    sql = """
        UPDATE `qq_chat_message`
        SET `转换状态` = %s
        WHERE `序号` = %s
    """
    with db_cursor(dict_cursor=False) as cursor:
        cursor.execute(sql, (status, message_id))


def save_qq_chat_message_results(rows: List[Dict[str, Any]]) -> None:
    """
    将转换结果批量写入 qq_chat_message_result 表

    Args:
        rows: 每条包含 chat_message_id, supplier, search_oe, result_oe, price, brand
    """
    if not rows:
        return

    insert_sql = """
        INSERT INTO `qq_chat_message_result`
        (`chat_message_id`, `supplier`, `供应商`, `search_oe`, `result_oe`, `price`, `brand`, `conversion_time`)
        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
    """

    with db_cursor(dict_cursor=False) as cursor:
        for row in rows:
            cursor.execute(
                insert_sql,
                (
                    row.get("chat_message_id", 0),
                    row.get("supplier", ""),
                    row.get("supplier_name", ""),
                    row.get("search_oe", ""),
                    row.get("result_oe", ""),
                    row.get("price", 0),
                    row.get("brand", ""),
                ),
            )


def fetch_qq_chat_message_results_by_oes(oe_list: List[str], hours: int = 36) -> List[Dict[str, Any]]:
    """
    根据 OE 列表查询最近 N 小时内的 QQ 消息转换结果

    Args:
        oe_list: 搜索 OE 列表
        hours: 时间窗口（小时），默认 36 小时

    Returns:
        结果列表，包含 供应商, brand, price, search_oe
    """
    if not oe_list:
        return []

    sql = """
        SELECT `search_oe`, `result_oe`, `供应商`, `brand`, `price`
        FROM `qq_chat_message_result`
        WHERE `search_oe` IN (%s)
          AND `conversion_time` >= DATE_SUB(NOW(), INTERVAL %%s HOUR)
        ORDER BY `conversion_time` DESC
    """ % ",".join(["%s"] * len(oe_list))

    with db_cursor(dict_cursor=True) as cursor:
        cursor.execute(sql, tuple(oe_list) + (hours,))
        return cursor.fetchall()
