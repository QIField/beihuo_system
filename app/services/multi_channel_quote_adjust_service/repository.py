"""
多渠道报价调价 - 数据访问层

职责：
- supplier_info 表查询
- qq_msg 表写入
- multi_channel_quote_import 表写入/查询

表结构变更：
ALTER TABLE `multi_channel_quote_import`
ADD COLUMN `stock` INT NOT NULL DEFAULT 0 COMMENT '库存数量' AFTER `barcode`;
"""

from typing import List, Dict, Any, Tuple

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
              product_id, barcode, stock 等字段
        create_by: 导入人
    """
    if not rows:
        return

    insert_sql = """
        INSERT INTO `multi_channel_quote_import`
        (`oe`, `brand`, `car_brand`, `inquiry_supplier`, `system_oe`,
         `sell_price`, `cost_price`, `profit_rate`, `profit_amount`,
         `product_id`, `barcode`, `stock`, `create_by`, `create_time`)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
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
                    row.get("stock") or 0,
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
               `product_id`, `barcode`, `stock`
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
            "stock": row["stock"] or "",
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
    `chat_message_id` BIGINT NULL COMMENT '关联 qq_chat_message.序号，接口数据匹配时可为 NULL',
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


def batch_update_qq_chat_message_status(updates: List[Dict[str, Any]]) -> None:
    """
    批量更新 qq_chat_message 转换状态

    Args:
        updates: 每个元素包含 message_id, status
    """
    if not updates:
        return

    status_groups: Dict[str, List[int]] = {}
    for u in updates:
        status = u["status"]
        status_groups.setdefault(status, []).append(u["message_id"])

    with db_cursor(dict_cursor=False) as cursor:
        for status, ids in status_groups.items():
            for i in range(0, len(ids), 500):
                batch = ids[i:i + 500]
                placeholders = ",".join(["%s"] * len(batch))
                sql = f"""
                    UPDATE `qq_chat_message`
                    SET `转换状态` = %s
                    WHERE `序号` IN ({placeholders})
                """
                cursor.execute(sql, (status, *batch))


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
        ON DUPLICATE KEY UPDATE
            `price` = VALUES(`price`),
            `conversion_time` = NOW()
    """

    params = [
        (
            row.get("chat_message_id") if row.get("chat_message_id") is not None else None,
            row.get("supplier", ""),
            row.get("supplier_name", ""),
            row.get("search_oe", ""),
            row.get("result_oe", ""),
            row.get("price", 0),
            row.get("brand", ""),
        )
        for row in rows
    ]

    with db_cursor(dict_cursor=False) as cursor:
        cursor.executemany(insert_sql, params)


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


def fetch_qq_chat_message_results_by_oe(oe: str, hours: int = 36) -> List[Dict[str, Any]]:
    """
    根据单个 OE 查询最近 N 小时内的 QQ 消息转换结果（不过滤品牌）

    Args:
        oe: 搜索 OE
        hours: 时间窗口（小时），默认 36 小时

    Returns:
        结果列表，包含 供应商, brand, price, search_oe
    """
    if not oe:
        return []

    sql = """
        SELECT `search_oe`, `result_oe`, `供应商`, `brand`, `price`
        FROM `qq_chat_message_result`
        WHERE `search_oe` = %s
          AND `conversion_time` >= DATE_SUB(NOW(), INTERVAL %s HOUR)
        ORDER BY `conversion_time` DESC
    """

    with db_cursor(dict_cursor=True) as cursor:
        cursor.execute(sql, (oe, hours))
        return cursor.fetchall()


def fetch_recent_import_oes(hours: int = 36) -> List[str]:
    """
    查询最近 N 小时内 multi_channel_quote_import 表中的 distinct oe

    Args:
        hours: 时间窗口（小时）

    Returns:
        去重并去除首尾空格的 OE 列表
    """
    sql = """
        SELECT DISTINCT `oe`
        FROM `multi_channel_quote_import`
        WHERE `create_time` >= DATE_SUB(NOW(), INTERVAL %s HOUR)
          AND `oe` IS NOT NULL AND `oe` != ''
        ORDER BY `oe`
    """
    with db_cursor(dict_cursor=False) as cursor:
        cursor.execute(sql, (hours,))
        return [row[0].strip() for row in cursor.fetchall()]


def fetch_replace_numbers() -> List[Dict[str, Any]]:
    """
    查询 crmapp_compare_summary 表中所有非空替换号

    Returns:
        每条包含 oe, replace_number
    """
    sql = """
        SELECT `oe`, `replace_number`, `company`
        FROM `crmapp_compare_summary`
        WHERE `replace_number` IS NOT NULL AND `replace_number` != ''
    """
    with db_cursor(dict_cursor=True) as cursor:
        cursor.execute(sql)
        return cursor.fetchall()


def fetch_virtual_inventory_by_oes(oe_list: List[str]) -> List[Dict[str, Any]]:
    """
    根据 OE 列表精确查询虚拟库存

    Args:
        oe_list: OE 码列表

    Returns:
        每条包含 oe_code, supplier_name, brand, original_price
    """
    if not oe_list:
        return []

    sql = """
        SELECT `oe_code`, `supplier_name`, `brand`, `original_price`
        FROM `virtual_inventory`
        WHERE `oe_code` IN (%s)
          AND `fetch_time` >= DATE_SUB(CURDATE(), INTERVAL 1 DAY)
    """ % ",".join(["%s"] * len(oe_list))

    with db_cursor(dict_cursor=True) as cursor:
        cursor.execute(sql, tuple(oe_list))
        return cursor.fetchall()


def fetch_unmatched_import_oes(hours: int = 36) -> List[str]:
    """
    查询最近 N 小时内、且未做过库存匹配的 distinct oe

    Args:
        hours: 时间窗口（小时）

    Returns:
        去重并去除首尾空格的 OE 列表
    """
    sql = """
        SELECT DISTINCT `oe`
        FROM `multi_channel_quote_import`
        WHERE `create_time` >= DATE_SUB(NOW(), INTERVAL %s HOUR)
          AND `oe` IS NOT NULL AND `oe` != ''
          AND `oe_inventory_matched_at` IS NULL
        ORDER BY `oe`
    """
    with db_cursor(dict_cursor=False) as cursor:
        cursor.execute(sql, (hours,))
        return [row[0].strip() for row in cursor.fetchall()]


def mark_import_oes_matched(oe_list: List[str]) -> None:
    """
    标记指定 OE 列表已完成库存匹配

    Args:
        oe_list: 已匹配的 OE 列表
    """
    if not oe_list:
        return

    placeholders = ",".join(["%s"] * len(oe_list))
    sql = f"""
        UPDATE `multi_channel_quote_import`
        SET `oe_inventory_matched_at` = NOW()
        WHERE `oe` IN ({placeholders})
          AND `oe_inventory_matched_at` IS NULL
    """
    with db_cursor(dict_cursor=False) as cursor:
        cursor.execute(sql, tuple(oe_list))


def init_replace_number_index_table() -> None:
    """
    初始化 replace_number_index 预处理表
    """
    sql = """
        CREATE TABLE IF NOT EXISTS `replace_number_index` (
            `id` BIGINT AUTO_INCREMENT PRIMARY KEY,
            `normalized_key` VARCHAR(255) NOT NULL COMMENT '归一化后的替换号',
            `oe` VARCHAR(255) NOT NULL COMMENT '对应的OE号',
            `company` VARCHAR(255) NOT NULL DEFAULT '' COMMENT '门店/公司代码',
            INDEX `idx_normalized_key_company` (`normalized_key`, `company`),
            INDEX `idx_oe` (`oe`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='替换号反向索引表'
    """
    with db_cursor(dict_cursor=False) as cursor:
        cursor.execute(sql)


def clear_replace_number_index() -> None:
    """清空 replace_number_index 表"""
    with db_cursor(dict_cursor=False) as cursor:
        cursor.execute("TRUNCATE TABLE `replace_number_index`")


def batch_insert_replace_number_index(rows: List[tuple]) -> None:
    """
    批量插入 replace_number_index 数据

    Args:
        rows: [(normalized_key, oe, company), ...]
    """
    if not rows:
        return
    sql = """
        INSERT INTO `replace_number_index` (`normalized_key`, `oe`, `company`)
        VALUES (%s, %s, %s)
    """
    with db_cursor(dict_cursor=False) as cursor:
        cursor.executemany(sql, rows)


def fetch_replace_index_by_keys(keys: List[str], company: str = "") -> List[Dict[str, Any]]:
    """
    根据归一化 key 列表和门店查询 replace_number_index

    Args:
        keys: 归一化后的替换号列表
        company: 门店/公司代码

    Returns:
        每条包含 normalized_key, oe
    """
    if not keys:
        return []
    placeholders = ",".join(["%s"] * len(keys))
    sql = """
        SELECT DISTINCT `normalized_key`, `oe`
        FROM `replace_number_index`
        WHERE `normalized_key` IN (%s)
          AND `company` = %s
    """ % (placeholders, "%s")
    with db_cursor(dict_cursor=True) as cursor:
        cursor.execute(sql, tuple(keys) + (company,))
        return cursor.fetchall()


def check_replace_number_index_empty() -> bool:
    """
    检查 replace_number_index 表是否为空

    Returns:
        True 为空，False 非空
    """
    sql = "SELECT COUNT(*) as cnt FROM `replace_number_index`"
    with db_cursor(dict_cursor=True) as cursor:
        cursor.execute(sql)
        row = cursor.fetchone()
        return row["cnt"] == 0 if row else True
