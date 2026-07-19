"""
虚拟库存相关表
包含：虚拟库存主表、腾隆数据表、贝尔马勒数据表、爱车贝母数据表、机器人数据表、外部数据表
"""

from app.utils.database_connection import get_db_connection


def init_virtual_inventory_table():
    """
    初始化虚拟库存主表
    用于整合所有供应商的库存数据
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS virtual_inventory (
                id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
                supplier_name VARCHAR(100) COMMENT '供应商名称',
                oe_code VARCHAR(100) COMMENT 'OE码',
                brand VARCHAR(255) DEFAULT NULL COMMENT '品牌',
                price DECIMAL(10,2) COMMENT '价格',
                original_price DECIMAL(10,2) COMMENT '原价格',
                expiry_date DATETIME COMMENT '过期时间',
                warehouse VARCHAR(255) COMMENT '仓库',
                stock INT DEFAULT 0 COMMENT '库存',
                remark TEXT COMMENT '备注',
                fetch_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '获取时间',
                update_msg TEXT COMMENT '更新信息',
                update_status VARCHAR(50) DEFAULT NULL COMMENT '更新状态',
                INDEX idx_brand (brand),
                INDEX idx_warehouse (warehouse),
                INDEX idx_expiry_date (expiry_date),
                INDEX idx_fetch_time (fetch_time),
                INDEX idx_oe_code (oe_code),
                INDEX idx_supplier_name (supplier_name),
                INDEX idx_update_status (update_status),
                FULLTEXT INDEX idx_update_msg_fulltext (update_msg)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='虚拟库存表';
            """
            cursor.execute(create_table_sql)
            
            # 检查并添加缺失的字段（兼容旧表）
            columns_to_check = [
                ('original_price', "DECIMAL(10,2) COMMENT '原价格'"),
                ('update_status', "VARCHAR(50) DEFAULT NULL COMMENT '更新状态'"),
            ]
            
            for col_name, col_def in columns_to_check:
                try:
                    cursor.execute(f"ALTER TABLE virtual_inventory ADD COLUMN {col_name} {col_def}")
                    print(f"已添加字段 {col_name} 到 virtual_inventory 表")
                except Exception as e:
                    if "Duplicate column name" not in str(e):
                        print(f"添加字段 {col_name} 时出错: {str(e)}")
                        
    except Exception as e:
        print(f"  [失败] 虚拟库存表: {e}")
    finally:
        conn.close()


def init_tenglong_data_table():
    """
    初始化腾隆数据表
    用于存储腾隆、宝翼隆、沐博三家供应商的原始数据
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS tenglong_data (
                id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
                supplier VARCHAR(100) COMMENT '供应商名称',
                code VARCHAR(100) COMMENT 'OE码',
                brand VARCHAR(100) COMMENT '品牌',
                price DECIMAL(10,2) COMMENT '价格',
                expiry_date DATETIME COMMENT '过期时间',
                warehouse VARCHAR(100) COMMENT '仓库',
                stock INT COMMENT '库存',
                remark TEXT COMMENT '备注',
                fetch_time DATETIME COMMENT '获取时间'
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='腾隆数据表';
            """
            cursor.execute(create_table_sql)
    except Exception as e:
        print(f"  [失败] 腾隆数据表: {e}")
    finally:
        conn.close()


def init_beiermale_data_table():
    """
    初始化贝尔马勒数据表
    用于存储马勒、贝洱等品牌对比数据
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS beiermale_data (
                id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
                supplier VARCHAR(100) COMMENT '供应商名称',
                oe_code VARCHAR(100) COMMENT 'OE码',
                brand VARCHAR(100) COMMENT '品牌',
                price DECIMAL(10,2) COMMENT '价格',
                expiry_date DATETIME COMMENT '过期时间',
                warehouse VARCHAR(100) COMMENT '仓库',
                stock INT COMMENT '库存',
                remark TEXT COMMENT '备注',
                fetch_time DATETIME COMMENT '获取时间'
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='贝尔马勒数据表';
            """
            cursor.execute(create_table_sql)
    except Exception as e:
        print(f"  [失败] 贝尔马勒数据表: {e}")
    finally:
        conn.close()


def init_aichebeimu_data_tables():
    """
    初始化爱车贝母数据表（按地区分表）
    包含：佛山、东莞、中山三个地区
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 佛山数据表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS aichebeimu_foshan_data (
                    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
                    supplier VARCHAR(100) COMMENT '供应商名称',
                    oe_code VARCHAR(100) COMMENT 'OE码',
                    brand VARCHAR(100) COMMENT '品牌',
                    price DECIMAL(10,2) COMMENT '价格',
                    expiry_date DATETIME COMMENT '过期时间',
                    warehouse VARCHAR(100) COMMENT '仓库',
                    stock INT COMMENT '库存',
                    remark TEXT COMMENT '备注',
                    fetch_time DATETIME COMMENT '获取时间'
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='爱车贝母佛山数据表';
            """)
            
            # 东莞数据表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS aichebeimu_dongguan_data (
                    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
                    supplier VARCHAR(100) COMMENT '供应商名称',
                    oe_code VARCHAR(100) COMMENT 'OE码',
                    brand VARCHAR(100) COMMENT '品牌',
                    price DECIMAL(10,2) COMMENT '价格',
                    expiry_date DATETIME COMMENT '过期时间',
                    warehouse VARCHAR(100) COMMENT '仓库',
                    stock INT COMMENT '库存',
                    remark TEXT COMMENT '备注',
                    fetch_time DATETIME COMMENT '获取时间'
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='爱车贝母东莞数据表';
            """)
            
            # 中山数据表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS aichebeimu_zhongshan_data (
                    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
                    supplier VARCHAR(100) COMMENT '供应商名称',
                    oe_code VARCHAR(100) COMMENT 'OE码',
                    brand VARCHAR(100) COMMENT '品牌',
                    price DECIMAL(10,2) COMMENT '价格',
                    expiry_date DATETIME COMMENT '过期时间',
                    warehouse VARCHAR(100) COMMENT '仓库',
                    stock INT COMMENT '库存',
                    remark TEXT COMMENT '备注',
                    fetch_time DATETIME COMMENT '获取时间'
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='爱车贝母中山数据表';
            """)
    except Exception as e:
        print(f"  [失败] 爱车贝母数据表: {e}")
    finally:
        conn.close()


def init_robot_data_table():
    """
    初始化机器人数据表
    用于存储从CRM系统爬取的库存数据
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS robot_data (
                id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
                supplier_name VARCHAR(100) COMMENT '供应商名称',
                oe_number VARCHAR(100) COMMENT 'OE码',
                brand_name VARCHAR(100) COMMENT '品牌名称',
                price DECIMAL(10,2) COMMENT '价格',
                expiry_date DATETIME COMMENT '过期时间',
                city_name VARCHAR(100) COMMENT '城市/仓库名称',
                quantity INT COMMENT '库存数量',
                remark TEXT COMMENT '备注',
                fetch_time DATETIME COMMENT '获取时间'
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='机器人数据表';
            """
            cursor.execute(create_table_sql)
    except Exception as e:
        print(f"  [失败] 机器人数据表: {e}")
    finally:
        conn.close()


def init_external_data_table():
    """
    初始化外部数据表
    用于存储从Excel文件导入的外部供应商数据
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS external_data (
                id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
                supplier_name VARCHAR(100) COMMENT '供应商名称',
                oe_code VARCHAR(100) COMMENT 'OE码',
                brand VARCHAR(100) COMMENT '品牌',
                price DECIMAL(10,2) COMMENT '价格',
                expiry_date DATETIME COMMENT '过期时间',
                warehouse VARCHAR(100) COMMENT '仓库',
                stock INT COMMENT '库存',
                remark TEXT COMMENT '备注',
                fetch_time DATETIME COMMENT '获取时间'
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='外部数据表';
            """
            cursor.execute(create_table_sql)
    except Exception as e:
        print(f"  [失败] 外部数据表: {e}")
    finally:
        conn.close()


def init_jiapei_data_table():
    """
    初始化佳配原始数据表
    用于存储从 113.45.176.129:8001 接口拉取的原始 Excel JSON 数据
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS jiapei_data (
                id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
                supplier_name VARCHAR(100) COMMENT '供应商名称',
                oe_code VARCHAR(100) COMMENT 'OE码',
                brand VARCHAR(100) COMMENT '品牌',
                price DECIMAL(10,2) COMMENT '价格',
                expiry_date DATETIME COMMENT '过期时间',
                warehouse VARCHAR(100) COMMENT '仓库',
                stock INT COMMENT '库存',
                remark TEXT COMMENT '备注',
                source_filename VARCHAR(255) COMMENT '来源文件名',
                fetch_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '获取时间'
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='佳配原始数据表';
            """
            cursor.execute(create_table_sql)
    except Exception as e:
        print(f"  [失败] 佳配数据表: {e}")
    finally:
        conn.close()


def init_all_virtual_inventory_tables():
    """初始化所有虚拟库存相关表"""
    init_virtual_inventory_table()
    init_tenglong_data_table()
    init_beiermale_data_table()
    init_aichebeimu_data_tables()
    init_robot_data_table()
    init_external_data_table()
    init_jiapei_data_table()
