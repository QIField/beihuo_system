"""
开思询价相关表
包含：询价明细表
"""

from app.utils.database_connection import get_db_connection


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
                brandName VARCHAR(100) NOT NULL COMMENT '品牌名称',
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
                INDEX idx_quote_date (quote_date),
                INDEX idx_company (company)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='开思询价明细表';
            """
            cursor.execute(create_table_sql)
    except Exception as e:
        print(f"  ✗ 开思询价明细表: {e}")
    finally:
        conn.close()
