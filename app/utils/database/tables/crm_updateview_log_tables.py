#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CRM updateView 接口调用日志表初始化
用于记录所有调用 https://crm.gzbbr.com/api/Product.Product/updateView 的请求参数、
组织（门店）来源以及接口响应结果，方便事后审计和统计修改量。
"""


# 先查后更流程中需要单独记录的 view 原始字段
# key: 数据库列名, value: 字段说明
ORIGINAL_COLUMNS = [
    ("original_cass_desc", "VARCHAR(500) NULL COMMENT '原开思描述'"),
    ("original_brand_code", "VARCHAR(255) NULL COMMENT '原品牌号'"),
    ("original_l_name_zh_store", "VARCHAR(255) NULL COMMENT '原门店产品名称'"),
    ("original_brand_barcode", "VARCHAR(255) NULL COMMENT '原品牌条码'"),
    ("original_store_cass_price", "VARCHAR(50) NULL COMMENT '原开思价'"),
    ("original_store_peer_price", "VARCHAR(50) NULL COMMENT '原同行价'"),
    ("original_qpl_price", "VARCHAR(50) NULL COMMENT '原汽配龙价格'"),
    ("original_cost_price", "VARCHAR(50) NULL COMMENT '原成本价'"),
    ("original_manufacturer_price", "VARCHAR(50) NULL COMMENT '原厂家价'"),
]


def _get_existing_columns(cursor):
    """获取当前表已存在的字段名"""
    cursor.execute("""
        SELECT COLUMN_NAME FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'crm_updateview_log'
    """)
    return {row[0] for row in cursor.fetchall()}


def _add_original_columns_if_missing(cursor):
    """为已存在的表补齐原始字段列"""
    existing = _get_existing_columns(cursor)
    for column_name, column_def in ORIGINAL_COLUMNS:
        if column_name not in existing:
            cursor.execute(
                f"ALTER TABLE crm_updateview_log ADD COLUMN {column_name} {column_def}"
            )


def init_crm_updateview_log_table():
    """初始化 CRM updateView 调用日志表"""
    from app.utils.database_connection import get_db_connection

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            original_columns_sql = ",\n".join(
                f"                {name} {definition}" for name, definition in ORIGINAL_COLUMNS
            )

            create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS crm_updateview_log (
                id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
                source VARCHAR(100) NOT NULL COMMENT '调用来源，如 crm_price_sync / updateview_service / batch_update_view / crm_updateView',
                store_code VARCHAR(50) NOT NULL COMMENT '门店/组织代码，如 fsbbr',
                product_id VARCHAR(50) NOT NULL COMMENT '产品ID',
                request_payload JSON NOT NULL COMMENT '请求参数（product_id 及待更新字段）',
{original_columns_sql},
                response_status VARCHAR(20) COMMENT '响应状态：success / failed / error',
                response_msg TEXT COMMENT '接口返回消息或异常信息',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '请求时间',
                INDEX idx_source (source),
                INDEX idx_store_code (store_code),
                INDEX idx_product_id (product_id),
                INDEX idx_created_at (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='CRM updateView 接口调用日志';
            """
            cursor.execute(create_table_sql)
            _add_original_columns_if_missing(cursor)
            conn.commit()
            print("[数据库] crm_updateview_log 表初始化完成")
    finally:
        conn.close()


if __name__ == '__main__':
    init_crm_updateview_log_table()
