# -*- coding: utf-8 -*-
"""
虚拟库存数据持久化模块

负责将供应商数据保存到各公司虚拟库存表。
"""

from datetime import datetime

import pandas as pd

from .database import get_db_connection
from .brands import process_price_by_brand
from app.utils.logger_config import get_task_logger


logger = get_task_logger('virtual_inventory')


# 供应商名称映射（用于非佛山表）
SUPPLIER_MAPPING = {
    '东莞佳配': '佛山1',
    '佛山万拓': '佛山2',
    '佛山巴博瑞': '佛山3',
    '佛山德孚': '佛山4',
    '佛山新奔裕汽配': '佛山5',
    '佳配': '佛山6',
    '宝翼隆': '佛山7',
    '广州佳配': '佛山8',
    '广州德之宝': '佛山9',
    '广州日昇': '佛山10',
    '广州昌盛': '佛山11',
    '广州犇宝': '佛山12',
    '广星': '佛山13',
    '沐博': '佛山14',
    '爱车贝母': '佛山15',
    '腾隆': '佛山16',
    '鑫峰': '佛山17',
    '盛旻': '佛山18'
}

# 佛山表上传用供应商名称映射
FSBBR_UPLOAD_MAPPING = {
    '广州昌盛': '昌盛',
    '佛山万拓': '万拓'
}

# 仓库名称映射（用于非佛山表）
WAREHOUSE_MAPPING = {
    'zsbbr': {
        '佛山禅城仓': '广州越秀仓'
    },
    'dgby': {
        '佛山禅城仓': '广州越秀仓'
    },
    'dghf': {
        '佛山禅城仓': '广州越秀仓'
    },
    'zhbbr': {
        '佛山禅城仓': '广州越秀1仓',
        '广州越秀仓': '广州越秀1仓'
    }
}

COMPANIES = ['fsbbr', 'zhbbr', 'zsbbr', 'dgby', 'dghf']
TABLE_MAP = {
    'fsbbr': 'virtual_inventory',
    'zhbbr': 'virtual_inventory_zhbbr',
    'zsbbr': 'virtual_inventory_zsbbr',
    'dgby': 'virtual_inventory_dgby',
    'dghf': 'virtual_inventory_dghf'
}


def save_to_company_tables(df, is_wantuo=False, is_changsheng=False, is_changsheng_special_fn=None, companies=None):
    """
    保存数据到各公司虚拟库存表，按各公司价格规则处理
    非佛山表的供应商名称会映射为佛山X格式
    新增 upload_supplier_name 列用于上传时的供应商名称

    :param df: 数据DataFrame
    :param is_wantuo: 是否为万拓数据
    :param is_changsheng: 是否为昌盛数据
    :param is_changsheng_special_fn: 判断是否为昌盛特殊产品的函数
    :param companies: 要保存的公司列表，默认全部
    """
    if df is None or df.empty:
        return

    if companies is None:
        companies = COMPANIES

    fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db_manager = get_db_connection()

    # 统一去除所有字符串字段的前后空格
    string_columns = ['供应商名称', '原厂OE码', '品牌', '仓库名称', '备注']
    for col in string_columns:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    try:
        for company in companies:
            table_name = TABLE_MAP[company]
            processed_data = []

            for _, row in df.iterrows():
                # 判断是否为昌盛特殊产品
                is_changsheng_special = False
                if is_changsheng_special_fn:
                    is_changsheng_special = is_changsheng_special_fn(row)

                # 按公司规则处理价格
                # 使用原价格进行计算，避免重复加点
                original_price = row.get('原价格', row['价格'])
                processed_price = process_price_by_brand(
                    original_price,
                    row['品牌'],
                    is_wantuo=is_wantuo,
                    is_changsheng_special=is_changsheng_special,
                    company=company
                )

                # 处理供应商名称和上传用供应商名称
                original_supplier = row['供应商名称']
                if company == 'fsbbr':
                    # 佛山表：supplier_name保持原名称，upload_supplier_name使用映射
                    supplier_name = original_supplier
                    upload_supplier_name = FSBBR_UPLOAD_MAPPING.get(original_supplier, original_supplier)
                else:
                    # 其他表：supplier_name保持原名称，upload_supplier_name使用佛山X映射
                    supplier_name = original_supplier
                    upload_supplier_name = SUPPLIER_MAPPING.get(original_supplier, original_supplier)

                # 处理仓库名称映射
                original_warehouse = row['仓库名称']
                if company in WAREHOUSE_MAPPING:
                    warehouse_name = WAREHOUSE_MAPPING[company].get(original_warehouse, original_warehouse)
                else:
                    warehouse_name = original_warehouse

                processed_data.append((
                    supplier_name,
                    row['原厂OE码'],
                    row['品牌'],
                    processed_price,
                    original_price,
                    row['失效时间'],
                    warehouse_name,
                    row['库存'],
                    row['备注'],
                    fetch_time,
                    upload_supplier_name
                ))

            # 批量插入
            batch_size = 1000
            for i in range(0, len(processed_data), batch_size):
                batch = processed_data[i:i + batch_size]
                sql = f"""
                    INSERT INTO {table_name} (supplier_name, oe_code, brand, price, original_price, expiry_date, warehouse, stock, remark, fetch_time, upload_supplier_name)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                db_manager.execute_many(sql, batch)
                logger.info(f"[{company}] 已保存 {min(i + batch_size, len(processed_data))} / {len(processed_data)} 条")

    finally:
        db_manager.close()


def save_supplier_to_virtual_inventory(df, supplier_name="供应商"):
    """
    保存供应商库存数据到各公司虚拟库存表
    """
    if df is None or df.empty:
        logger.info(f"{supplier_name}库存数据为空，跳过保存")
        return

    is_wantuo = supplier_name == "佛山万拓"
    is_changsheng = supplier_name == "昌盛" or supplier_name == "广州昌盛"

    # 昌盛特殊产品判断函数
    def is_changsheng_special_fn(row):
        if is_changsheng:
            oe_code = str(row.get('原厂OE码', ''))
            remark = str(row.get('备注', ''))
            return oe_code.endswith('80') and '是惠选件' in remark
        return False

    # 保存到各公司表
    save_to_company_tables(df, is_wantuo, is_changsheng, is_changsheng_special_fn)


# 昌盛原始数据字段映射（API字段 -> 数据库字段）
CHANGSHENG_RAW_COLUMNS = [
    ('part_id', 'INT'),
    ('part_name', 'VARCHAR(255)'),
    ('part_number', 'VARCHAR(100)'),
    ('oe_number', 'VARCHAR(100)'),
    ('part_spec', 'VARCHAR(100)'),
    ('brand_name', 'VARCHAR(100)'),
    ('part_quality_name', 'VARCHAR(100)'),
    ('unit', 'VARCHAR(20)'),
    ('sale_price', 'VARCHAR(50)'),
    ('min_sale_price', 'VARCHAR(50)'),
    ('max_sale_price', 'VARCHAR(50)'),
    ('wholesale_price', 'VARCHAR(50)'),
    ('sale_price1', 'VARCHAR(50)'),
    ('sale_price2', 'VARCHAR(50)'),
    ('last_sale_price', 'VARCHAR(50)'),
    ('cost_price', 'VARCHAR(50)'),
    ('stock_amount', 'VARCHAR(50)'),
    ('remark', 'TEXT'),
    ('car_series', 'VARCHAR(255)'),
    ('part_engine', 'VARCHAR(50)'),
    ('part_standard', 'VARCHAR(50)'),
    ('goods_class', 'VARCHAR(100)'),
    ('custom_class', 'VARCHAR(100)'),
    ('manufacturer_number', 'VARCHAR(100)'),
    ('prices', 'TEXT'),
]


def _ensure_changsheng_raw_table(db_manager):
    """确保昌盛原始数据表存在"""
    columns_def = ",\n        ".join([f"{db_col} {db_type}" for api_col, db_type, db_col in
                           [(c[0], c[1], c[0]) for c in CHANGSHENG_RAW_COLUMNS]])
    create_sql = f"""
        CREATE TABLE IF NOT EXISTS changsheng_raw_inventory (
            id INT AUTO_INCREMENT PRIMARY KEY,
            {columns_def},
            fetch_time DATETIME NOT NULL,
            INDEX idx_fetch_time (fetch_time),
            INDEX idx_oe_number (oe_number),
            INDEX idx_part_number (part_number)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """
    db_manager.execute_update(create_sql)


def save_changsheng_raw_data(df):
    """
    保存昌盛原始数据到 changsheng_raw_inventory 表
    与现有清洗流程并行执行，失败不影响主流程
    """
    if df is None or df.empty:
        logger.info("昌盛原始数据为空，跳过原始保存")
        return

    fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db_manager = get_db_connection()

    try:
        _ensure_changsheng_raw_table(db_manager)

        # 准备数据
        api_columns = [c[0] for c in CHANGSHENG_RAW_COLUMNS]
        columns_str = ", ".join(api_columns + ['fetch_time'])
        placeholders = ", ".join(["%s"] * (len(api_columns) + 1))

        data = []
        for _, row in df.iterrows():
            row_data = []
            for col in api_columns:
                val = row.get(col)
                if col == 'prices' and val is not None:
                    # 嵌套对象转JSON字符串
                    import json
                    val = json.dumps(val, ensure_ascii=False) if not isinstance(val, str) else val
                row_data.append(val)
            row_data.append(fetch_time)
            data.append(tuple(row_data))

        # 批量插入
        batch_size = 1000
        total_inserted = 0
        sql = f"INSERT INTO changsheng_raw_inventory ({columns_str}) VALUES ({placeholders})"
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            db_manager.execute_many(sql, batch)
            total_inserted += len(batch)

        logger.info(f"[changsheng_raw_inventory] 已保存 {total_inserted} 条原始数据")

    except Exception:
        logger.exception("[changsheng_raw_inventory] 保存昌盛原始数据失败")
        # 失败不抛出，不影响主流程
    finally:
        db_manager.close()
