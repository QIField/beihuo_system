"""
店铺事件相关表
包含：每日事件汇总表、事件明细表、经营指标表
"""

from app.utils.database_connection import get_db_connection


def init_shop_event_summary_table():
    """
    初始化每日事件汇总表
    存储接口1的每日总错误数
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS crmapp_shop_event_summary (
                id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
                event_date DATE NOT NULL COMMENT '事件日期',
                total_event_count INT DEFAULT 0 COMMENT '每日总错误数',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                UNIQUE KEY uk_event_date (event_date),
                INDEX idx_event_date (event_date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='每日事件汇总表';
            """
            cursor.execute(create_table_sql)
    except Exception as e:
        print(f"  [失败] 每日事件汇总表: {e}")
    finally:
        conn.close()


def init_shop_event_detail_table():
    """
    初始化事件明细表
    存储接口2的事件详情列表
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS crmapp_shop_event_detail (
                id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
                event_date DATE NOT NULL COMMENT '事件日期',
                event_type_key VARCHAR(100) NOT NULL COMMENT '事件类型标识',
                event_type_name VARCHAR(200) COMMENT '事件类型名称',
                event_count INT DEFAULT 0 COMMENT '事件数量',
                statistics_unit VARCHAR(50) COMMENT '统计单位',
                event_influence TEXT COMMENT '事件影响说明',
                event_suggest TEXT COMMENT '处理建议',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                UNIQUE KEY uk_date_type (event_date, event_type_key),
                INDEX idx_event_date (event_date),
                INDEX idx_event_type_key (event_type_key)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='事件明细表';
            """
            cursor.execute(create_table_sql)
    except Exception as e:
        print(f"  [失败] 事件明细表: {e}")
    finally:
        conn.close()


def init_shop_business_indicator_table():
    """
    初始化经营指标表
    存储接口3的经营指标数据
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS crmapp_shop_business_indicator (
                id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
                indicator_date DATE NOT NULL COMMENT '指标日期',
                sales_amount DECIMAL(15,2) DEFAULT 0.00 COMMENT '销售额(元)',
                system_quote_rate VARCHAR(20) COMMENT '系统报价成交额比例(%)',
                order_customer_count INT DEFAULT 0 COMMENT '下单客户数(个)',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                UNIQUE KEY uk_indicator_date (indicator_date),
                INDEX idx_indicator_date (indicator_date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='经营指标表';
            """
            cursor.execute(create_table_sql)
            
            # 检查并添加缺失的字段（兼容旧表）
            alter_columns = [
                ("sales_amount", "DECIMAL(15,2) DEFAULT 0.00 COMMENT '销售额(元)'"),
                ("system_quote_rate", "VARCHAR(20) COMMENT '系统报价成交额比例(%)'"),
                ("order_customer_count", "INT DEFAULT 0 COMMENT '下单客户数(个)'"),
                ("total_quote_rate", "VARCHAR(20) COMMENT '总报出率(%)'"),
                ("system_quote_rate_detail", "VARCHAR(20) COMMENT '系统报出率(%)'"),
                ("manual_quote_rate", "VARCHAR(20) COMMENT '人工报出率(%)'"),
                ("whole_order_quote_rate", "VARCHAR(20) COMMENT '整单报出率(%)'"),
                ("spot_quote_rate", "VARCHAR(20) COMMENT '现货报出率(%)'"),
                ("quote_conversion_rate", "VARCHAR(20) COMMENT '报出转化率(%)'"),
                ("system_quote_conversion_rate", "VARCHAR(20) COMMENT '系统报出转化率(%)'"),
                ("avg_quote_quality_count", "DECIMAL(10,2) DEFAULT 0.00 COMMENT '平均报出品质数(个)'"),
                ("return_sku_count", "INT DEFAULT 0 COMMENT '退货SKU数(个)'"),
                ("sku_return_rate", "VARCHAR(20) COMMENT 'SKU退货率(%)'"),
                ("return_amount", "DECIMAL(15,2) DEFAULT 0.00 COMMENT '退货金额(元)'"),
                ("amount_return_rate", "VARCHAR(20) COMMENT '金额退货率(%)'"),
            ]
            
            for col_name, col_def in alter_columns:
                try:
                    cursor.execute(f"ALTER TABLE crmapp_shop_business_indicator ADD COLUMN {col_name} {col_def}")
                except Exception as e:
                    if "Duplicate column name" not in str(e):
                        print(f"添加字段 {col_name} 时出错: {str(e)}")
                        
    except Exception as e:
        print(f"  [失败] 经营指标表: {e}")
    finally:
        conn.close()
