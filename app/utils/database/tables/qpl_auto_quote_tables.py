#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
汽配龙自动报价重构 · 三层表初始化

qpl_order         订单表（一单一行，uk: company + supplier_enquiry_no）
qpl_order_item    明细表（一明细一行，状态机落点，uk: company + enquiry_item_id）
qpl_quote_attempt 尝试流水表（append-only 只插不改）

均为幂等建表，跟随启动菜单选库连接（PyMySQL 同源），无需手动执行 SQL。
"""


def _init_table(conn, create_sql, table_name):
    """执行单表 DDL 并提交"""
    with conn.cursor() as cursor:
        cursor.execute(create_sql)
    conn.commit()
    print(f"[数据库] {table_name} 表初始化完成")


def init_qpl_order_table():
    """初始化订单表"""
    from app.utils.database_connection import get_db_connection

    conn = get_db_connection()
    try:
        _init_table(conn, """
            CREATE TABLE IF NOT EXISTS qpl_order (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                company VARCHAR(20) NOT NULL COMMENT '组织代码',
                supplier_enquiry_no VARCHAR(50) NOT NULL COMMENT '供应商询价单号 SIQRxxx',
                qpl_enquiry_no VARCHAR(50) COMMENT '平台询价单号 IQRxxx',
                tid VARCHAR(20) COMMENT '车型ID',
                car_brand VARCHAR(50) COMMENT '车辆品牌(奔驰/宝马)',
                car_type5 VARCHAR(255) COMMENT '车型全称',
                vin_code VARCHAR(50) COMMENT 'VIN码',
                shop_name VARCHAR(100) COMMENT '门店名称',
                trader_name VARCHAR(100) COMMENT '需求方',
                user_name VARCHAR(50) COMMENT '联系人',
                user_phone VARCHAR(20) COMMENT '联系电话',
                demand_status VARCHAR(20) COMMENT '汽配龙单状态: PART/ALL/NEVER',
                accept_status VARCHAR(20) COMMENT '接单状态',
                multi_quote_gray TINYINT DEFAULT 0 COMMENT '是否新报价灰度',
                item_total INT DEFAULT 0 COMMENT '明细总数',
                item_quoted INT DEFAULT 0 COMMENT '已报价明细数',
                enquiry_time DATETIME COMMENT '询价时间',
                first_handle_time DATETIME COMMENT '首轮处理时间',
                last_handle_time DATETIME COMMENT '末轮处理时间',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                UNIQUE KEY uk_company_enquiry (company, supplier_enquiry_no)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
              COMMENT='汽配龙报价订单表';
        """, 'qpl_order')
    finally:
        conn.close()


def init_qpl_order_item_table():
    """初始化明细表（状态机落点）"""
    from app.utils.database_connection import get_db_connection

    conn = get_db_connection()
    try:
        _init_table(conn, """
            CREATE TABLE IF NOT EXISTS qpl_order_item (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                company VARCHAR(20) NOT NULL COMMENT '组织代码',
                supplier_enquiry_no VARCHAR(50) NOT NULL COMMENT '供应商询价单号',
                supplier_demand_id BIGINT COMMENT '需求组ID',
                enquiry_item_id BIGINT NOT NULL COMMENT '明细ID(汽配龙全局唯一)',
                item_name VARCHAR(255) COMMENT '品名',
                item_nick_names VARCHAR(255) COMMENT '别名(逗号拼接)',
                item_oe VARCHAR(100) COMMENT 'OE号',
                item_amount INT DEFAULT 1 COMMENT '数量',
                assembly_quantity INT DEFAULT 1 COMMENT '装配数量',
                item_quality_list VARCHAR(50) COMMENT '可报品质档位,如1,2',
                sale_category_name VARCHAR(50) COMMENT '品类',
                car_brand VARCHAR(50) COMMENT '车辆品牌(冗余,便于查询)',
                status VARCHAR(20) NOT NULL DEFAULT 'pending'
                    COMMENT '状态机: pending/quoted/failed_biz/failed_temp',
                quote_source VARCHAR(30) COMMENT '报价来源: CRM现货/奔驰接口/宝马接口',
                matched_brand VARCHAR(100) COMMENT '匹配品牌',
                item_sell_price DECIMAL(10,2) COMMENT '报价',
                delivery_aging INT COMMENT '时效(天)',
                parts_no VARCHAR(100) COMMENT '零件号',
                item_quality TINYINT COMMENT '实际品质档位',
                fail_stage VARCHAR(30) COMMENT '失败环节',
                fail_reason VARCHAR(500) COMMENT '失败原因',
                retry_count INT DEFAULT 0 COMMENT '临时失败重试次数',
                next_retry_time DATETIME COMMENT '下次重试时间(冷却)',
                last_attempt_time DATETIME COMMENT '末次尝试时间',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                UNIQUE KEY uk_company_item (company, enquiry_item_id),
                INDEX idx_status_retry (company, status, next_retry_time),
                INDEX idx_enquiry_no (company, supplier_enquiry_no)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
              COMMENT='汽配龙报价明细表';
        """, 'qpl_order_item')
    finally:
        conn.close()


def init_qpl_quote_attempt_table():
    """初始化尝试流水表（append-only）"""
    from app.utils.database_connection import get_db_connection

    conn = get_db_connection()
    try:
        _init_table(conn, """
            CREATE TABLE IF NOT EXISTS qpl_quote_attempt (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                company VARCHAR(20) NOT NULL COMMENT '组织代码',
                supplier_enquiry_no VARCHAR(50) NOT NULL COMMENT '供应商询价单号',
                enquiry_item_id BIGINT NOT NULL COMMENT '明细ID',
                round_id VARCHAR(32) COMMENT '轮次标识(YYYYMMDDHHMMSS_company)',
                action VARCHAR(30) COMMENT '动作: match/price_check/submit/fetch_list/fetch_detail/manual_retry',
                result VARCHAR(20) COMMENT '结果: 成功/失败/跳过',
                quote_source VARCHAR(30) COMMENT '报价来源',
                fail_stage VARCHAR(30) COMMENT '失败环节',
                fail_reason VARCHAR(500) COMMENT '失败原因',
                request_snapshot JSON COMMENT '请求快照',
                response_snapshot JSON COMMENT '响应快照(priceCheck快照/提交回执)',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                INDEX idx_item_time (company, enquiry_item_id, created_at),
                INDEX idx_round (company, round_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
              COMMENT='汽配龙报价尝试流水表';
        """, 'qpl_quote_attempt')
    finally:
        conn.close()


def init_qpl_auto_quote_tables():
    """三表初始化统一入口（幂等，可重复调用）"""
    init_qpl_order_table()
    init_qpl_order_item_table()
    init_qpl_quote_attempt_table()


if __name__ == '__main__':
    init_qpl_auto_quote_tables()
