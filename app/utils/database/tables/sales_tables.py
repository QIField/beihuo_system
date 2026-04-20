"""
销量相关表
包含：销量明细表、询价次数表
"""

from app.utils.database_connection import get_db_connection


def check_table_exists(cursor, table_name):
    """检查表是否存在"""
    cursor.execute("""
        SELECT COUNT(*) FROM information_schema.tables 
        WHERE table_schema = DATABASE() AND table_name = %s
    """, (table_name,))
    return cursor.fetchone()[0] > 0


def check_column_length(cursor, table_name, column_name):
    """检查字段长度"""
    cursor.execute("""
        SELECT CHARACTER_MAXIMUM_LENGTH 
        FROM information_schema.columns 
        WHERE table_schema = DATABASE() 
        AND table_name = %s 
        AND column_name = %s
    """, (table_name, column_name))
    result = cursor.fetchone()
    return result[0] if result else None


def init_sales_history_detail_table():
    """
    初始化销量明细表（新表）
    用于存储CRM销量明细数据（订单级）
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            table_name = 'crmapp_sales_history_detail'
            table_exists = check_table_exists(cursor, table_name)

            if not table_exists:
                # 表不存在，创建新表（使用200长度）
                create_table_sql = """
                CREATE TABLE IF NOT EXISTS crmapp_sales_history_detail (
                    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
                    ddno VARCHAR(50) NOT NULL COMMENT '订单号',
                    create_date DATETIME NOT NULL COMMENT '创建时间',
                    fullname VARCHAR(100) DEFAULT '' COMMENT '客户全称',
                    pdname VARCHAR(200) DEFAULT '' COMMENT '产品名称',
                    brand_name VARCHAR(50) DEFAULT '' COMMENT '品牌名称',
                    l_model_zh TEXT COMMENT '车型',
                    frey_no VARCHAR(200) DEFAULT '' COMMENT 'Frey编号',
                    number VARCHAR(200) DEFAULT '' COMMENT 'OE号',
                    quantity INT DEFAULT 0 COMMENT '销售数量',
                    sfqty INT DEFAULT 0 COMMENT '实发数量',
                    price DECIMAL(10,2) DEFAULT 0.00 COMMENT '单价',
                    total_price DECIMAL(12,2) DEFAULT 0.00 COMMENT '总价',
                    sfje DECIMAL(12,2) DEFAULT 0.00 COMMENT '实发金额',
                    remark TEXT COMMENT '备注',
                    warehouse VARCHAR(50) DEFAULT '' COMMENT '仓库',
                    return_policy VARCHAR(50) DEFAULT '' COMMENT '退货政策',
                    company VARCHAR(20) DEFAULT 'fsbbr' COMMENT '公司',
                    created_at DATETIME DEFAULT NOW() COMMENT '记录创建时间',
                    updated_time DATETIME DEFAULT NOW() ON UPDATE NOW() COMMENT '更新时间',
                    
                    UNIQUE KEY uk_ddno_frey_company (ddno, frey_no, company),
                    INDEX idx_create_date (create_date),
                    INDEX idx_ddno (ddno),
                    INDEX idx_number_brand (number, brand_name),
                    INDEX idx_company_date (company, create_date)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='销量明细表';
                """
                cursor.execute(create_table_sql)
                print(f"  ✓ 销量明细表: 创建成功")
            else:
                # 表已存在，检查并修改字段长度
                print(f"  ℹ 销量明细表: 已存在，检查字段长度...")
                
                # 检查 number 字段长度
                number_length = check_column_length(cursor, table_name, 'number')
                if number_length and number_length < 200:
                    cursor.execute(f"""
                        ALTER TABLE {table_name} 
                        MODIFY COLUMN number VARCHAR(200) DEFAULT '' COMMENT 'OE号'
                    """)
                    print(f"    ✓ number 字段: {number_length} → 200")
                else:
                    print(f"    ✓ number 字段: 已是 {number_length or '200'}")
                
                # 检查 frey_no 字段长度
                frey_no_length = check_column_length(cursor, table_name, 'frey_no')
                if frey_no_length and frey_no_length < 200:
                    cursor.execute(f"""
                        ALTER TABLE {table_name} 
                        MODIFY COLUMN frey_no VARCHAR(200) DEFAULT '' COMMENT 'Frey编号'
                    """)
                    print(f"    ✓ frey_no 字段: {frey_no_length} → 200")
                else:
                    print(f"    ✓ frey_no 字段: 已是 {frey_no_length or '200'}")
                
                print(f"  ✓ 销量明细表: 字段长度检查完成")
                
    except Exception as e:
        print(f"  ✗ 销量明细表: {e}")
    finally:
        conn.close()


def init_quote_count_ks_table():
    """
    初始化开思询价次数统计表
    用于存储按(年月, OE, 品牌)统计的询价次数
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            table_name = 'crmapp_quote_count_ks'
            table_exists = check_table_exists(cursor, table_name)

            if not table_exists:
                create_table_sql = """
                CREATE TABLE IF NOT EXISTS crmapp_quote_count_ks (
                    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键',
                    `year_month` VARCHAR(7) NOT NULL COMMENT '年月，格式：YYYY-MM',
                    oe VARCHAR(100) NOT NULL COMMENT 'OE号/零件号',
                    brand VARCHAR(100) NOT NULL COMMENT '品牌名称',
                    quote_count INT NOT NULL DEFAULT 0 COMMENT '询价次数',
                    company VARCHAR(50) NOT NULL DEFAULT 'fsbbr' COMMENT '公司代码',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                    UNIQUE KEY uk_year_month_oe_brand_company (`year_month`, oe, brand, company),
                    KEY idx_year_month (`year_month`),
                    KEY idx_company (company),
                    KEY idx_oe (oe),
                    KEY idx_brand (brand)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='开思询价次数统计表';
                """
                cursor.execute(create_table_sql)
                print(f"  ✓ 询价次数表: 创建成功")
            else:
                print(f"  ℹ 询价次数表: 已存在，跳过")
                
    except Exception as e:
        print(f"  ✗ 询价次数表: {e}")
    finally:
        conn.close()
