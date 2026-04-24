"""
安全库存相关表定义
包含：安全库存计算结果表
"""

from app.utils.database_connection import get_db_connection


def init_safety_stock_calculation_table():
    """
    初始化安全库存计算结果表
    用于存储每天计算的安全库存参数和预警状态
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS crmapp_safety_stock_calculation (
                id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
                frey_no VARCHAR(100) NOT NULL COMMENT 'Frey编号/物料条码',
                product_name VARCHAR(255) DEFAULT NULL COMMENT '产品名称',
                abc_class VARCHAR(10) DEFAULT NULL COMMENT 'ABC分类(A/B/C)',
                avg_daily_sales DECIMAL(10,2) DEFAULT 0.00 COMMENT '平均日销量',
                sales_std DECIMAL(10,2) DEFAULT 0.00 COMMENT '销量标准差',
                seasonal_factor DECIMAL(3,2) DEFAULT 1.00 COMMENT '季节系数',
                base_safety_stock DECIMAL(10,2) DEFAULT 0.00 COMMENT '基础安全库存',
                safety_stock DECIMAL(10,2) DEFAULT 0.00 COMMENT '调整后安全库存',
                reorder_point DECIMAL(10,2) DEFAULT 0.00 COMMENT '库存下限(再订货点)',
                target_stock DECIMAL(10,2) DEFAULT 0.00 COMMENT '库存上限(目标库存)',
                current_stock DECIMAL(10,2) DEFAULT 0.00 COMMENT '当前库存',
                in_transit_qty DECIMAL(10,2) DEFAULT 0.00 COMMENT '在途数量',
                available_stock DECIMAL(10,2) DEFAULT 0.00 COMMENT '可用库存',
                inventory_amount DECIMAL(12,2) DEFAULT 0.00 COMMENT '库存金额',
                sellable_days DECIMAL(5,1) DEFAULT 0.0 COMMENT '可卖天数',
                stock_status VARCHAR(20) DEFAULT '正常' COMMENT '库存状态',
                calc_date DATE NOT NULL COMMENT '计算日期',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                
                UNIQUE KEY uk_frey_no_date (frey_no, calc_date),
                INDEX idx_abc_class (abc_class),
                INDEX idx_stock_status (stock_status),
                INDEX idx_calc_date (calc_date),
                INDEX idx_available_stock (available_stock)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='安全库存计算结果表';
            """
            cursor.execute(create_table_sql)
            conn.commit()
            print("✓ 安全库存计算结果表创建成功")
            
    except Exception as e:
        print(f"✗ 创建安全库存计算结果表失败: {e}")
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'conn' in locals():
            conn.close()
