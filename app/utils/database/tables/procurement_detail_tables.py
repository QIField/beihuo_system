"""
采购历史明细表
用于存储采购订单明细数据
"""

from app.utils.database_connection import get_db_connection


def init_procurement_history_detail_table():
    """
    初始化采购历史明细表
    用于存储采购订单明细数据

    如果需要手动修改已存在表的字段类型，请执行以下 SQL：

    ALTER TABLE crmapp_procurement_history_detail
    MODIFY COLUMN l_model_zh TEXT COMMENT '车型中文';

    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 检查表是否已存在
            cursor.execute("""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_schema = DATABASE()
                AND table_name = 'crmapp_procurement_history_detail'
            """)
            table_exists = cursor.fetchone()[0] > 0

            if table_exists:
                print("  [信息]  采购历史明细表已存在，检查字段类型...")

                # 检查 l_model_zh 字段类型
                cursor.execute("""
                    SELECT DATA_TYPE FROM information_schema.columns
                    WHERE table_schema = DATABASE()
                    AND table_name = 'crmapp_procurement_history_detail'
                    AND column_name = 'l_model_zh'
                """)
                result = cursor.fetchone()

                if result and result[0].upper() != 'TEXT':
                    print("  [编辑] 修改 l_model_zh 字段类型为 TEXT...")
                    cursor.execute("""
                        ALTER TABLE crmapp_procurement_history_detail
                        MODIFY COLUMN l_model_zh TEXT COMMENT '车型中文'
                    """)
                    print("  [成功] l_model_zh 字段类型修改完成")
                else:
                    print("  [成功] l_model_zh 字段类型已是 TEXT，无需修改")

                return

            # 表不存在，创建新表
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS crmapp_procurement_history_detail (
                id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
                order_no VARCHAR(100) NOT NULL COMMENT '订单号',
                fullname VARCHAR(255) NOT NULL COMMENT '供应商全称',
                l_name_zh_default VARCHAR(255) COMMENT '产品中文名',
                frey_no VARCHAR(100) COMMENT 'Frey编号',
                number VARCHAR(100) NOT NULL COMMENT 'OE号/零件号',
                brand VARCHAR(100) NOT NULL COMMENT '品牌',
                l_model_zh TEXT COMMENT '车型中文',
                purchase_quantity INT COMMENT '采购数量',
                unit_cost DECIMAL(10,2) COMMENT '单价',
                create_date DATETIME COMMENT '订单日期',
                expected_delivery_date DATETIME COMMENT '交货日期',
                `year_month` VARCHAR(7) COMMENT '年月YYYY-MM',
                company VARCHAR(50) DEFAULT 'fsbbr' COMMENT '公司代码',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                UNIQUE KEY uk_order_number_brand_company (order_no, number, brand, company),
                KEY idx_year_month (`year_month`),
                KEY idx_number_brand (number, brand),
                KEY idx_create_date (create_date),
                KEY idx_company (company)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='采购历史明细表';
            """
            cursor.execute(create_table_sql)
            print("  [成功] 采购历史明细表初始化完成")
    except Exception as e:
        print(f"  [失败] 采购历史明细表: {e}")
        raise
    finally:
        conn.close()
