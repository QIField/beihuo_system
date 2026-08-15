#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
汽配龙报价记录表初始化
"""


def init_qpl_quote_record_table():
    """初始化报价记录表"""
    from app.utils.database_connection import get_db_connection

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS qpl_quote_record (
                id INT AUTO_INCREMENT PRIMARY KEY,
                supplier_enquiry_no VARCHAR(100) NOT NULL COMMENT '询价单号',
                supplier_demand_id VARCHAR(100) COMMENT '需求ID',
                enquiry_item_id VARCHAR(100) COMMENT '询价产品ID',
                item_oe VARCHAR(100) COMMENT 'OE号码',
                item_name VARCHAR(255) COMMENT '产品名称',
                item_description TEXT COMMENT '产品描述',
                brand_id VARCHAR(100) COMMENT '品牌ID',
                brand_name VARCHAR(100) COMMENT '品牌名称',
                item_sell_price DECIMAL(10,2) COMMENT '销售价格',
                delivery_aging INT COMMENT '交货周期(天)',
                item_quality VARCHAR(50) COMMENT '产品品质',
                parts_no VARCHAR(100) COMMENT '零件号',
                quote_status VARCHAR(50) COMMENT '报价状态',
                submit_result VARCHAR(255) COMMENT '提交结果',
                order_submit_status VARCHAR(20) COMMENT '订单整体提交状态：success/failure',
                crm_flow_status VARCHAR(50) COMMENT 'CRM流程状态',
                bc_flow_status VARCHAR(50) COMMENT 'B/C接口流程状态',
                result_source VARCHAR(50) COMMENT '报价来源/结果分类',
                submit_time DATETIME COMMENT '提交时间',
                company VARCHAR(100) COMMENT '组织代码',
                created_time DATETIME COMMENT '询价单创建时间',
                vin_code VARCHAR(100) COMMENT 'VIN码',
                car_type TEXT COMMENT '车型信息',
                order_status VARCHAR(50) COMMENT '汽配龙产品报价状态（quoteStatusStr），如：已下单、已报价',
                retry_count INT DEFAULT 0 COMMENT '失败重试次数',
                failure_category VARCHAR(50) COMMENT '失败分类：business/temporary/retry_exhausted',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                INDEX idx_supplier_enquiry_no (supplier_enquiry_no),
                INDEX idx_item_oe (item_oe),
                INDEX idx_brand_name (brand_name),
                INDEX idx_submit_time (submit_time),
                INDEX idx_company (company),
                UNIQUE INDEX uk_company_order_item (company, supplier_enquiry_no, enquiry_item_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='汽配龙报价记录表';
            """
            cursor.execute(create_table_sql)
            conn.commit()

            # 检查并添加可能缺失的字段
            from app.utils.database.table_manager import check_and_add_fields
            qpl_fields = [
                {'name': 'created_time', 'definition': "DATETIME COMMENT '询价单创建时间'"},
                {'name': 'vin_code', 'definition': "VARCHAR(100) COMMENT 'VIN码'"},
                {'name': 'car_type', 'definition': "TEXT COMMENT '车型信息'"},
                {'name': 'result_source', 'definition': "VARCHAR(50) COMMENT '报价来源/结果分类'"},
                {'name': 'order_submit_status', 'definition': "VARCHAR(20) COMMENT '订单整体提交状态：success/failure'"},
                {'name': 'crm_flow_status', 'definition': "VARCHAR(50) COMMENT 'CRM流程状态'"},
                {'name': 'bc_flow_status', 'definition': "VARCHAR(50) COMMENT 'B/C接口流程状态'"},
                {'name': 'order_status', 'definition': "VARCHAR(50) COMMENT '汽配龙产品报价状态（quoteStatusStr），如：已下单、已报价'"},
                {'name': 'retry_count', 'definition': "INT DEFAULT 0 COMMENT '失败重试次数'"},
                {'name': 'failure_category', 'definition': "VARCHAR(50) COMMENT '失败分类：business/temporary/retry_exhausted'"}
            ]
            check_and_add_fields('qpl_quote_record', qpl_fields)

            print("[数据库] qpl_quote_record 表初始化完成")
    finally:
        conn.close()


def init_qpl_quote_result_v2_table():
    """初始化报价结果明细表v2"""
    from app.utils.database_connection import get_db_connection

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS qpl_quote_result_v2 (
                id INT AUTO_INCREMENT PRIMARY KEY,
                supplier_enquiry_no VARCHAR(100) NOT NULL COMMENT '询价单号',
                company VARCHAR(100) NOT NULL COMMENT '组织代码',
                enquiry_item_id VARCHAR(100) NOT NULL COMMENT '询价产品ID',
                supplier_demand_id VARCHAR(100) COMMENT '需求ID',
                item_oe VARCHAR(100) COMMENT 'OE号码',
                item_name VARCHAR(255) COMMENT '产品名称',
                item_description TEXT COMMENT '产品描述',
                brand_id VARCHAR(100) COMMENT '品牌ID',
                brand_name VARCHAR(100) COMMENT '品牌名称',
                item_sell_price DECIMAL(10,2) COMMENT '销售价格',
                delivery_aging INT COMMENT '交货周期(天)',
                item_quality VARCHAR(50) COMMENT '产品品质',
                parts_no VARCHAR(100) COMMENT '零件号',
                quote_source VARCHAR(50) COMMENT '来源: 已有报价/CRM现货/奔驰接口/宝马接口',
                is_quoted TINYINT DEFAULT 0 COMMENT '是否报价成功: 1是 0否',
                fail_stage VARCHAR(50) COMMENT '失败环节: 品牌匹配/partNo匹配/价格校验/库存检查/priceCheck/无',
                fail_reason VARCHAR(500) COMMENT '具体失败原因',
                fail_type VARCHAR(50) COMMENT '分类: 成功/业务错误/临时错误/重试耗尽',
                retry_count INT DEFAULT 0 COMMENT '重试次数',
                submit_status VARCHAR(50) COMMENT '提交状态: 未提交/提交成功/提交失败/cannot_quote成功/cannot_quote失败',
                submit_message TEXT COMMENT 'API原始响应',
                order_status VARCHAR(50) COMMENT '汽配龙产品报价状态（quoteStatusStr），如：已下单、已报价',
                created_time DATETIME COMMENT '询价单创建时间',
                vin_code VARCHAR(100) COMMENT 'VIN码',
                submit_time DATETIME COMMENT '提交时间',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                UNIQUE INDEX uk_company_order_item_brand (company, supplier_enquiry_no, enquiry_item_id, brand_name),
                INDEX idx_enquiry_no (company, supplier_enquiry_no),
                INDEX idx_item_oe (company, item_oe),
                INDEX idx_submit_status (company, submit_status)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='汽配龙报价结果明细表v2';
            """
            cursor.execute(create_table_sql)
            conn.commit()
            print("[数据库] qpl_quote_result_v2 表初始化完成")
    finally:
        conn.close()


def init_qpl_quote_flow_trace_table():
    """初始化报价流程备查日志表"""
    from app.utils.database_connection import get_db_connection

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS qpl_quote_flow_trace (
                id INT AUTO_INCREMENT PRIMARY KEY,
                supplier_enquiry_no VARCHAR(100) NOT NULL COMMENT '询价单号',
                company VARCHAR(100) NOT NULL COMMENT '组织代码',
                enquiry_item_id VARCHAR(100) NOT NULL COMMENT '询价产品ID',
                item_oe VARCHAR(100) COMMENT 'OE号码',
                item_name VARCHAR(255) COMMENT '产品名称',
                flow_name VARCHAR(50) COMMENT '流程: CRM现货/奔驰接口/宝马接口',
                flow_status VARCHAR(50) COMMENT '状态: 成功/失败/跳过',
                fail_stage VARCHAR(50) COMMENT '失败环节: 品牌匹配/partNo匹配/价格校验/库存检查/priceCheck/无',
                fail_reason VARCHAR(500) COMMENT '具体失败原因',
                stage_detail JSON COMMENT '各阶段明细',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                INDEX idx_enquiry_item (company, supplier_enquiry_no, enquiry_item_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='报价流程备查日志';
            """
            cursor.execute(create_table_sql)
            conn.commit()
            print("[数据库] qpl_quote_flow_trace 表初始化完成")
    finally:
        conn.close()


if __name__ == '__main__':
    init_qpl_quote_record_table()
    init_qpl_quote_result_v2_table()
    init_qpl_quote_flow_trace_table()
