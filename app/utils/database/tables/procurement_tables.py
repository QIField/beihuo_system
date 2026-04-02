"""
采购相关表
包含：采购历史表、采购历史明细表
"""

from app.utils.database_connection import get_db_connection


def init_procurement_history_table():
    """
    初始化采购历史表
    用于存储采购记录（按月汇总）
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS crmapp_procurement_history (
                id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
                `year_month` VARCHAR(7) NOT NULL COMMENT '年月，格式：YYYY-MM',
                purchase_date DATE NOT NULL COMMENT '采购日期',
                supplier_name VARCHAR(255) NOT NULL COMMENT '供应商名称',
                oe VARCHAR(100) NOT NULL COMMENT 'OE号',
                brand VARCHAR(100) NOT NULL COMMENT '品牌',
                unit_price DECIMAL(10,2) NOT NULL COMMENT '单价',
                company VARCHAR(50) DEFAULT 'fsbbr' COMMENT '公司代码',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                UNIQUE KEY uk_month_oe_brand_supplier_price (`year_month`, oe, brand, supplier_name, unit_price, company),
                KEY idx_year_month (`year_month`),
                KEY idx_oe_brand (oe, brand),
                KEY idx_purchase_date (purchase_date),
                KEY idx_company (company)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='采购历史表';
            """
            cursor.execute(create_table_sql)
    except Exception as e:
        print(f"  ✗ 采购历史表: {e}")
    finally:
        conn.close()


def init_procurement_history_detail_table():
    """
    初始化采购历史明细表
    用于存储采购订单明细数据
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS crmapp_procurement_history_detail (
                id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
                order_no VARCHAR(100) NOT NULL COMMENT '订单号',
                fullname VARCHAR(255) NOT NULL COMMENT '供应商全称',
                l_name_zh_default VARCHAR(255) COMMENT '产品中文名',
                frey_no VARCHAR(100) COMMENT 'Frey编号',
                number VARCHAR(100) NOT NULL COMMENT 'OE号/零件号',
                brand VARCHAR(100) NOT NULL COMMENT '品牌',
                l_model_zh VARCHAR(255) COMMENT '车型中文',
                purchase_quantity INT COMMENT '采购数量',
                unit_cost DECIMAL(10,2) COMMENT '单价',
                create_date DATETIME COMMENT '订单日期',
                expected_delivery_date DATETIME COMMENT '交货日期',
                year_month VARCHAR(7) COMMENT '年月YYYY-MM',
                company VARCHAR(50) DEFAULT 'fsbbr' COMMENT '公司代码',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                UNIQUE KEY uk_order_number_brand_company (order_no, number, brand, company),
                KEY idx_year_month (year_month),
                KEY idx_number_brand (number, brand),
                KEY idx_create_date (create_date),
                KEY idx_company (company)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='采购历史明细表';
            """
            cursor.execute(create_table_sql)
    except Exception as e:
        print(f"  ✗ 采购历史明细表: {e}")
    finally:
        conn.close()
