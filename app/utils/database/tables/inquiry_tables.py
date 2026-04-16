"""
开思询价相关表
包含：开思询价明细表、微信询价明细表、询价单监控数据表、询价直接入库数据表
"""

from app.utils.database_connection import get_db_connection


def init_ks_inquiry_monitor_table():
    """
    初始化开思询价单监控数据表
    用于存储各门店的询价单实时统计数据（每次更新清空后插入新数据）
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS crmapp_ks_inquiry_monitor (
                id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
                store_code VARCHAR(10) NOT NULL COMMENT '门店代码(fs/zs/zh/hf/by)',
                store_name VARCHAR(50) NOT NULL COMMENT '门店名称',
                unclaimed_count INT DEFAULT 0 COMMENT '待认领询价单数量',
                quoted_count INT DEFAULT 0 COMMENT '已报价数量',
                unquoted_count INT DEFAULT 0 COMMENT '未报价数量',
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                UNIQUE KEY uk_store (store_code),
                INDEX idx_updated_at (updated_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='开思询价单监控数据表';
            """
            cursor.execute(create_table_sql)
            print("  ✓ 开思询价单监控数据表")
    except Exception as e:
        print(f"  ✗ 开思询价单监控数据表: {e}")
    finally:
        conn.close()


def init_ks_inquiry_detail_table():
    """
    初始化开思询价明细表
    用于存储从开思平台爬取的询价明细数据
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS crmapp_ks_inquiry_detail (
                id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
                inquiryId VARCHAR(50) NOT NULL COMMENT '询价单ID',
                partsNum VARCHAR(100) NOT NULL COMMENT 'OE号/零件号',
                partsName VARCHAR(255) DEFAULT NULL COMMENT '零件名称',
                brandName VARCHAR(100) NOT NULL COMMENT '品牌名称（原始）',
                brandNormalized VARCHAR(100) DEFAULT NULL COMMENT '品牌名称（标准化，处理宝马/奔驰品质映射后）',
                brandId VARCHAR(50) DEFAULT NULL COMMENT '品牌ID',
                partType VARCHAR(50) DEFAULT NULL COMMENT '零件类型',
                partsBrandQuality VARCHAR(50) DEFAULT NULL COMMENT '配件品质',
                remark TEXT DEFAULT NULL COMMENT '备注',
                company VARCHAR(50) NOT NULL COMMENT '公司标识',
                quote_date DATE NOT NULL COMMENT '询价日期',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                UNIQUE KEY uk_inquiry_detail (inquiryId, brandName, partsNum, company),
                INDEX idx_parts_num (partsNum),
                INDEX idx_brand_name (brandName),
                INDEX idx_brand_normalized (brandNormalized),
                INDEX idx_quote_date (quote_date),
                INDEX idx_company (company)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='开思询价明细表';
            """
            cursor.execute(create_table_sql)
    except Exception as e:
        print(f"  ✗ 开思询价明细表: {e}")
    finally:
        conn.close()


def init_weixin_inquiry_detail_table():
    """
    初始化微信询价明细表
    用于存储从 weixin_decoding_result 表解析的询价明细数据
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS crmapp_weixin_inquiry_detail (
                id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
                oe VARCHAR(100) NOT NULL COMMENT 'OE号/零件号',
                brand VARCHAR(100) NOT NULL COMMENT '品牌名称',
                creation_date DATETIME NOT NULL COMMENT '询价时间（原始记录的完整时间）',
                company VARCHAR(50) NOT NULL COMMENT '公司标识',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录更新时间',
                UNIQUE KEY uk_weixin_inquiry (oe, brand, creation_date, company),
                INDEX idx_oe (oe),
                INDEX idx_brand (brand),
                INDEX idx_creation_date (creation_date),
                INDEX idx_company (company)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='微信询价明细表';
            """
            cursor.execute(create_table_sql)
    except Exception as e:
        print(f"  ✗ 微信询价明细表: {e}")
    finally:
        conn.close()


def init_price_inquiry_direct_table():
    """
    初始化询价直接入库数据表
    用于存储跳过B2B推送直接入库的询价数据
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS crmapp_price_inquiry_direct (
                id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
                oe VARCHAR(50) NOT NULL COMMENT 'OE号',
                brand VARCHAR(100) DEFAULT NULL COMMENT '品牌',
                supplier VARCHAR(200) DEFAULT NULL COMMENT '供应商',
                price DECIMAL(10,2) DEFAULT NULL COMMENT '价格（加价后）',
                original_price DECIMAL(10,2) DEFAULT NULL COMMENT '原始价格',
                warehouse VARCHAR(200) DEFAULT NULL COMMENT '仓库',
                expire_time DATETIME DEFAULT NULL COMMENT '失效时间',
                remark TEXT COMMENT '备注',
                stock_quantity INT DEFAULT 0 COMMENT '库存数量',
                common_number VARCHAR(500) DEFAULT NULL COMMENT '通用号',
                ks_sync TINYINT DEFAULT 0 COMMENT '是否同步开思 0-否 1-是',
                company VARCHAR(50) DEFAULT NULL COMMENT '公司',
                import_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '导入时间',
                creator VARCHAR(100) DEFAULT NULL COMMENT '导入人',
                source_file VARCHAR(255) DEFAULT NULL COMMENT '来源文件名',
                INDEX idx_oe (oe),
                INDEX idx_brand (brand),
                INDEX idx_company (company),
                INDEX idx_import_time (import_time)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='询价直接入库数据表';
            """
            cursor.execute(create_table_sql)
            print("  ✓ 询价直接入库数据表")
    except Exception as e:
        print(f"  ✗ 询价直接入库数据表: {e}")
    finally:
        conn.close()
