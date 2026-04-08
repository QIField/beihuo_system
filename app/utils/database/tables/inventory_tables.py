"""
库存相关表
包含：卓之星库存表、库存明细表
"""

from app.utils.database_connection import get_db_connection


def init_zhuozhixing_table():
    """
    初始化卓之星库存数据表
    用于存储从卓之星API同步的广星、鑫峰供应商库存数据
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS zhuozhixing_inventory (
                id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
                supplier_name VARCHAR(50) NOT NULL COMMENT '供应商名称：广星/鑫峰',
                配件ID VARCHAR(50) COMMENT '配件ID',
                零件编码 VARCHAR(100) COMMENT '零件编码',
                制造编码 VARCHAR(100) COMMENT '制造编码',
                零件名称 VARCHAR(255) COMMENT '零件名称',
                零件英文名称 VARCHAR(255) COMMENT '零件英文名称',
                零件车型 VARCHAR(255) COMMENT '零件车型',
                产地 VARCHAR(100) COMMENT '产地',
                价格 DECIMAL(10,2) COMMENT '价格',
                库存数 INT COMMENT '库存数',
                零件品牌 VARCHAR(100) COMMENT '零件品牌',
                品牌 VARCHAR(100) COMMENT '品牌',
                品牌编码 VARCHAR(50) COMMENT '品牌编码',
                公会编码 VARCHAR(50) COMMENT '公会编码',
                通用车型 VARCHAR(255) COMMENT '通用车型',
                互换码 TEXT COMMENT '互换码',
                是否共享 TINYINT COMMENT '是否共享：0-否，1-是',
                商家库存表自增ID VARCHAR(50) COMMENT '商家库存表自增ID',
                库号 VARCHAR(50) COMMENT '库号（仓库）',
                sync_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '同步时间',
                INDEX idx_supplier (supplier_name),
                INDEX idx_零件编码 (零件编码),
                INDEX idx_制造编码 (制造编码),
                INDEX idx_sync_time (sync_time),
                INDEX idx_零件名称 (零件名称)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='卓之星库存数据';
            """
            cursor.execute(create_table_sql)
    except Exception as e:
        print(f"  ✗ 卓之星库存表: {e}")
    finally:
        conn.close()


def init_inventory_detail_table():
    """
    初始化库存明细表
    用于存储CRM库存接口爬取的产品数据
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS crmapp_inventory_detail (
                id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
                product_id INT NOT NULL COMMENT '产品ID',
                product_name VARCHAR(255) COMMENT '产品名称',
                l_name_zh_default VARCHAR(255) COMMENT '默认中文名',
                frey_no VARCHAR(255) COMMENT 'Frey编号',
                brand_name VARCHAR(100) COMMENT '品牌名称',
                cass_oebrand_name VARCHAR(100) COMMENT '车辆品牌',
                number VARCHAR(100) COMMENT 'OE号',
                cost_price DECIMAL(10,2) DEFAULT 0.00 COMMENT '成本价',
                cost_price_total DECIMAL(10,2) DEFAULT 0.00 COMMENT '成本总价',
                kw_nos VARCHAR(255) COMMENT '关键字编号',
                link_brand_code VARCHAR(100) COMMENT '品牌关联码',
                stock_quantity INT DEFAULT 0 COMMENT '库存数量',
                vehicle_model VARCHAR(100) COMMENT '车型',
                warehouse_name VARCHAR(100) COMMENT '仓库名称',
                company VARCHAR(50) COMMENT '公司代码',
                INDEX idx_product_id (product_id),
                INDEX idx_brand_company_number (brand_name, company, number)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='库存明细表';
            """
            cursor.execute(create_table_sql)
    except Exception as e:
        print(f"  ✗ 库存明细表: {e}")
    finally:
        conn.close()
