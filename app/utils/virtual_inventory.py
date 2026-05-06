import json
import pandas as pd
import requests
import pymysql
import pyodbc
from datetime import datetime, timedelta
import time
from collections import defaultdict
import math
from .database_connection import get_db_connection as get_pooled_db_connection  # 导入统一的连接池实现并重命名
from .supplier_data_fetchers.changsheng_inventory import start as fetch_changsheng_data
from .supplier_data_fetchers.wantuo_inventory import start as fetch_wantuo_data


# 全局品牌缓存
_brand_cache = None


def load_crm_brand_list():
    """
    从 crm_brand_list 表加载品牌列表
    返回: {品牌名: type_cn, ...}
    """
    global _brand_cache
    
    if _brand_cache is not None:
        return _brand_cache
    
    conn = get_pooled_db_connection()
    brand_dict = {}
    
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            sql = "SELECT l_name_zh, type_cn FROM crm_brand_list"
            cursor.execute(sql)
            rows = cursor.fetchall()
            print(f"查询 crm_brand_list 返回 {len(rows)} 行数据")
            for row in rows:
                brand_name = row['l_name_zh'].strip() if row['l_name_zh'] else ''
                type_cn = row['type_cn'].strip() if row['type_cn'] else ''
                if brand_name:
                    brand_dict[brand_name] = type_cn
        
        _brand_cache = brand_dict
        print(f"已从 crm_brand_list 表加载 {len(brand_dict)} 个品牌")
        return brand_dict
    except Exception as e:
        import traceback
        print(f"加载 crm_brand_list 表失败: {e}")
        print(traceback.format_exc())
        _brand_cache = {}
        return {}
    finally:
        conn.close()


def clear_brand_cache():
    """清除品牌缓存"""
    global _brand_cache
    _brand_cache = None
    print("品牌缓存已清除")


def process_price_by_brand(price, brand, is_wantuo=False, is_changsheng_special=False, company='fsbbr'):
    """
    根据品牌精准匹配处理价格：
    - 佛山/中山/东莞：原厂+5%，品牌+6%，其他+8%
    - 珠海：原厂+8%，国际+12%，其他+20%
    - 万拓额外+15%，昌盛特殊产品额外+10%

    :param price: 原始价格
    :param brand: 品牌名称
    :param is_wantuo: 是否为万拓数据，如果是则额外加15%
    :param is_changsheng_special: 是否为昌盛特殊产品（尾号80结尾+原厂再制造），如果是则额外加10%
    :param company: 公司标识，'zhbbr'为珠海，其他为默认规则
    """
    if not price or price == '':
        return 0.0

    try:
        price_float = float(price)

        # 获取品牌缓存
        brand_dict = load_crm_brand_list()

        # 判断是否为珠海
        is_zhuhai = (company == 'zhbbr')

        # 基础加点
        base_multiplier = 1.0

        # 检查品牌是否在 crm_brand_list 中
        if brand in brand_dict:
            type_cn = brand_dict[brand]
            # 原厂品牌
            if type_cn == '原厂':
                base_multiplier = 1.08 if is_zhuhai else 1.05
            # type_cn='品牌'
            elif type_cn == '品牌':
                base_multiplier = 1.12 if is_zhuhai else 1.06
            # type_cn='其他品牌'
            else:
                base_multiplier = 1.20 if is_zhuhai else 1.08
        else:
            # 品牌不在 crm_brand_list 中
            base_multiplier = 1.20 if is_zhuhai else 1.08

        # 额外加点（万拓+15%，昌盛特殊+10%）
        extra_multiplier = 1.0
        if is_wantuo:
            extra_multiplier += 0.15
        elif is_changsheng_special:
            extra_multiplier += 0.10

        final_price = price_float * base_multiplier * extra_multiplier
        return round(final_price, 2)

    except (ValueError, TypeError):
        return 0.0


# 数据库配置
DB_CONFIG = {
    'host': '113.45.176.129',
    'port': 3306,
    'user': 'fsbbr_data',
    'password': 'wRCA8AGn3a568f4X',
    'database': 'fsbbr_data',
    'charset': 'utf8mb4'
}

def get_business_time_range(current_time):
    """
    计算给定时间所属的业务时间范围
    业务时间：当天00:00到23:59
    """
    business_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
    business_end = business_start.replace(hour=23, minute=59, second=59, microsecond=0)
    
    return business_start, business_end

def clean_business_time_data():
    """
    清理当前业务时间范围内的数据（所有公司表）
    """
    current_time = datetime.now()
    business_start, business_end = get_business_time_range(current_time)

    print(f"当前时间: {current_time}")
    print(f"业务时间范围: {business_start} 到 {business_end}")

    tables = [
        'virtual_inventory',
        'virtual_inventory_zhbbr',
        'virtual_inventory_zsbbr',
        'virtual_inventory_dgby',
        'virtual_inventory_dghf'
    ]

    db_manager = get_db_connection()
    try:
        for table in tables:
            # 检查是否存在该业务时间段的数据
            check_query = f"""
                SELECT COUNT(*) as count
                FROM {table}
                WHERE fetch_time >= %s AND fetch_time < %s
            """
            result = db_manager.execute_query(check_query, (business_start, business_end))
            count = result[0]['count']

            if count > 0:
                print(f"[{table}] 发现 {count} 条属于当前业务时间段的数据，正在删除...")

                delete_query = f"""
                    DELETE FROM {table}
                    WHERE fetch_time >= %s AND fetch_time < %s
                """
                deleted_count = db_manager.execute_update(delete_query, (business_start, business_end))
                print(f"[{table}] 已删除 {deleted_count} 条数据")
            else:
                print(f"[{table}] 当前业务时间段内没有数据")

    except Exception as e:
        print(f"清理业务时间数据时出错: {e}")
    finally:
        db_manager.close()

class DatabaseManager:
    def __init__(self, config):
        self.config = config
        self.connection = None
        self.connect()

    def connect(self):
        """建立数据库连接"""
        try:
            # 使用连接池获取连接
            self.connection = get_pooled_db_connection()
            return True
        except Exception as e:
            print(f"数据库连接失败: {e}")
            return False

    def check_connection(self):
        """检查数据库连接状态"""
        if self.connection is None:
            return False
        try:
            # 使用ping方法检查连接，自动重连
            self.connection.ping(reconnect=True)
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            return True
        except Exception:
            return False
    
    def ensure_connection(self):
        """确保数据库连接可用，否则重连"""
        if not self.check_connection():
            print("数据库连接已断开，正在尝试重连...")
            if self.connect():
                print("数据库重连成功")
                return True
            else:
                print("数据库重连失败")
                return False
        return True
    
    def execute_query(self, query, params=None):
        """执行查询，自动处理断连重连"""
        if not self.ensure_connection():
            raise Exception("数据库连接不可用")
        
        try:
            with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(query, params)
                result = cursor.fetchall()
                return result
        except Exception as e:
            # 如果查询失败，尝试重连后重试
            if self.ensure_connection():
                with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
                    cursor.execute(query, params)
                    result = cursor.fetchall()
                    return result
            else:
                raise e
    
    def execute_update(self, query, params=None):
        """执行更新操作，自动处理断连重连"""
        if not self.ensure_connection():
            raise Exception("数据库连接不可用")
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, params)
                self.connection.commit()
                return cursor.rowcount
        except Exception as e:
            # 如果更新失败，尝试重连后重试
            if self.ensure_connection():
                with self.connection.cursor() as cursor:
                    cursor.execute(query, params)
                    self.connection.commit()
                    return cursor.rowcount
            else:
                raise e
    
    def execute_many(self, query, data):
        """批量执行操作，自动处理断连重连"""
        if not self.ensure_connection():
            raise Exception("数据库连接不可用")
        
        try:
            with self.connection.cursor() as cursor:
                cursor.executemany(query, data)
                self.connection.commit()
                return cursor.rowcount
        except Exception as e:
            # 如果批量操作失败，尝试重连后重试
            if self.ensure_connection():
                with self.connection.cursor() as cursor:
                    cursor.executemany(query, data)
                    self.connection.commit()
                    return cursor.rowcount
            else:
                raise e
    
    def close(self):
        """关闭数据库连接"""
        if self.connection:
            self.connection.close()


def get_db_connection():
    """获取数据库连接管理器实例"""
    return DatabaseManager(DB_CONFIG)


def load_crm_aliases_mapping():
    """
    加载CRM可用别名映射关系
    从static/excel/crm可用别名.xlsx读取数据
    """
    try:
        import os
        # 获取当前脚本所在目录，向上两级到达项目根目录，然后进入static/excel目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))
        excel_path = os.path.join(project_root, "static", "excel", "crm可用别名.xlsx")
        
        # 检查文件是否存在
        if not os.path.exists(excel_path):
            print(f"警告: 未找到 {excel_path} 文件，将不进行品牌名称映射")
            return {}
        
        df = pd.read_excel(excel_path)
        brand_mapping = {}
        
        # 遍历每一行，解析pp_names字段
        for _, row in df.iterrows():
            pp_name = row['pp_name']
            pp_names_str = str(row['pp_names']) if pd.notna(row['pp_names']) else ""
            
            # 解析pp_names字段，通常是逗号分隔的多个可能的品牌名
            possible_names = [name.strip() for name in pp_names_str.split(',')]
            for name in possible_names:
                if name and name != "-":  # 忽略占位符"-"
                    brand_mapping[name] = pp_name
        
        print(f"加载了 {len(brand_mapping)} 个品牌别名映射")
        return brand_mapping
    except Exception as e:
        print(f"读取CRM可用别名文件时出错: {e}")
        return {}


def clear_all_tables():
    """清空所有表的数据并重置自动递增ID，但保留virtual_inventory表"""
    db_manager = get_db_connection()
    try:
        cursor = db_manager.connection.cursor()
        
        tables = [
            'tenglong_data', 
            'beiermale_data', 
            'aichebeimu_foshan_data', 
            'aichebeimu_dongguan_data', 
            'aichebeimu_zhongshan_data',
            'robot_data',
            'external_data'
            # 注意：这里不包括 'virtual_inventory' 表
        ]
        
        for table in tables:
            cursor.execute(f"DELETE FROM {table}")
            cursor.execute(f"ALTER TABLE {table} AUTO_INCREMENT = 1")
        
        db_manager.connection.commit()
    finally:
        db_manager.close()


def remove_trailing_numbers(code):
    """
    如果编码最后两位是特定序号（01-09），则去除这些序号
    """
    if not code or len(code) < 3:
        return code

    # 定义9个特定序号
    suffixes = ['01', '02', '03', '04', '05', '06', '07', '08', '09']

    # 检查编码末尾是否匹配这些序号
    for suffix in suffixes:
        if code.endswith(suffix):
            return code[:-2]

    return code


def load_brands_from_json():
    """
    从brands.json文件中加载品牌信息
    """
    try:
        with open('brands.json', 'r', encoding='utf-8') as f:
            brands_data = json.load(f)

        # 提取所有有效的中文品牌名称
        valid_brands = set()
        for brand in brands_data:
            brand_name = brand.get('l_name_zh', '').strip()
            if brand_name:
                valid_brands.add(brand_name)

        print(f"从brands.json加载了 {len(valid_brands)} 个有效品牌")
        return valid_brands

    except FileNotFoundError:
        print("警告: 未找到brands.json文件，将不过滤品牌数据")
        return None
    except Exception as e:
        print(f"读取brands.json文件时出错: {e}")
        return None


def process_supplier_data(all_data, valid_brands=None):
    """
    处理多家供应商数据：
    1. 去除编码末尾的特定序号
    2. 保留各自供应商名称（腾隆、宝翼隆、沐博分开显示）
    3. 只保留brands.json中存在的品牌
    4. 除了腾隆外，其他供应商只有库存大于等于2的才保留
    """
    print("处理供应商数据")

    # 如果提供了有效的品牌列表，则过滤数据
    if valid_brands is not None:
        filtered_data = []
        for item in all_data:
            if item['brand'] in valid_brands:
                filtered_data.append(item)
        print(f"品牌过滤: 从 {len(all_data)} 条数据过滤为 {len(filtered_data)} 条数据")
        all_data = filtered_data

    # 过滤其他供应商库存小于2的数据
    filtered_data = []
    for item in all_data:
        # 腾隆的数据不受限制
        if item['supplier'] == '腾隆':
            filtered_data.append(item)
        # 其他供应商只有库存大于等于2才保留
        elif int(item['stock']) >= 2:
            filtered_data.append(item)

    print(f"供应商库存过滤: 从 {len(all_data)} 条数据过滤为 {len(filtered_data)} 条数据")
    all_data = filtered_data

    # 按编码和品牌分组
    grouped_data = defaultdict(list)

    for item in all_data:
        # 去除编码末尾的特定序号
        original_code = item['code']
        processed_code = remove_trailing_numbers(original_code)
        item['code'] = processed_code

        # 按处理后的编码和品牌分组
        key = (processed_code, item['brand'])
        grouped_data[key].append(item)

    # 对每组数据进行处理：去重取中间值，但保留原始供应商名称
    final_data = []
    for key, items in grouped_data.items():
        if len(items) == 1:
            # 只有一个数据，直接使用
            final_data.append(items[0])
        else:
            # 多个数据，按库存数量排序，取中间值
            sorted_items = sorted(items, key=lambda x: int(x['stock']))
            middle_index = len(sorted_items) // 2
            selected_item = sorted_items[middle_index]
            # 保留原始供应商名称，不统一改为"腾隆"
            final_data.append(selected_item)

    return final_data


def fetch_supplier_data(supplier_name, server, database, username, password):
    """
    从数据库获取指定供应商的数据
    """
    # 定义连接字符串（Windows 版本）
    conn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={username};"
        f"PWD={password};"
        f"TrustServerCertificate=yes;"
        f"Encrypt=no"
    )

    try:
        # 建立连接
        conn = pyodbc.connect(conn_str)
        # 创建游标对象
        cursor = conn.cursor()

        # 执行查询 - 统一查询三家供应商数据
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN LEN(REPLACE(bianma, ' ', '')) = 13 
                         AND RIGHT(REPLACE(bianma, ' ', ''), 2) IN ('01', '02', '03', '04', '05', '06', '07', '08', '09') 
                    THEN LEFT(REPLACE(bianma, ' ', ''), LEN(REPLACE(bianma, ' ', '')) - 2) 
                    ELSE REPLACE(bianma, ' ', '') 
                END AS bianma, 
                CASE 
                    WHEN mingcheng LIKE '%下线%' THEN 'XX' 
                    WHEN REPLACE(fenleima, ' ', '') = '正厂' THEN '原厂' 
                    ELSE fenleima 
                END AS fenleima, 
                shuliang, 
                shoujia, 
                gs 
            FROM kucun 
            WHERE chexing != '奔驰' 
              AND gs IN ('腾隆', '沐博', '宝翼隆') 
              AND shuliang > 1 
              AND mingcheng NOT LIKE '%一比一%' 
              AND fenleima NOT LIKE '%一比一%'
        """)

        # 获取结果
        rows = cursor.fetchall()
        conn.close()

        # 处理数据
        current_time = datetime.now()
        processed_data = []

        for row in rows:
            # SQL查询结果：bianma, fenleima, shuliang, shoujia, gs
            bianma = row[0]      # 编码（已在SQL中处理）
            fenleima = row[1]    # 分类码/品牌（已在SQL中处理）
            shuliang = row[2]    # 数量
            shoujia = row[3]     # 售价
            gs = row[4]          # 供应商
            
            # 品牌过滤
            if not fenleima:
                continue

            # 根据品牌处理价格
            original_price = float(shoujia)
            price = process_price_by_brand(original_price, fenleima)
            if price < 1:
                continue

            stock = shuliang
            expiry_date = (current_time + timedelta(days=int(stock))).strftime("%Y-%m-%d %H:%M:%S")

            processed_data.append({
                'supplier': gs,
                'code': bianma,
                'brand': fenleima,
                'price': price,  # 处理后的价格
                'original_price': original_price,  # 原价格
                'expiry_date': expiry_date,
                'warehouse': '广州越秀仓',
                'stock': stock,
                'remark': '',
                'fetch_time': current_time.strftime("%Y-%m-%d %H:%M:%S")
            })

        return processed_data

    except Exception as e:
        print(f"获取{supplier_name}数据时出错: {e}")
        return []


def sql_sever_data():
    # 数据库连接信息
    server = "159.75.116.155,5399"
    database = "yyserver"
    username = "sa"
    password = "sql37365680."

    # 读取brands.json文件中的有效品牌
    valid_brands = load_brands_from_json()

    # 获取各供应商数据
    all_data = []

    print("获取腾隆数据...")
    tenglong_data = fetch_supplier_data('腾隆', server, database, username, password)
    all_data.extend(tenglong_data)

    print("获取宝翼隆数据...")
    baoyilong_data = fetch_supplier_data('宝翼隆', server, database, username, password)
    all_data.extend(baoyilong_data)

    print("获取沐博数据...")
    mubo_data = fetch_supplier_data('沐博', server, database, username, password)
    all_data.extend(mubo_data)

    print(f"总共获取到 {len(all_data)} 条原始数据")

    # 处理数据（去序号、去重、取中间值、品牌过滤、库存过滤）
    final_data = process_supplier_data(all_data, valid_brands)
    print(f"处理后剩余 {len(final_data)} 条数据")

    # 批量保存到数据库
    db_manager = get_db_connection()
    try:
        # 批量插入数据
        batch_size = 1000  # 批量处理大小
        for i in range(0, len(final_data), batch_size):
            batch = final_data[i:i + batch_size]
            
            # 准备批量插入数据
            batch_data = []
            for item in batch:
                batch_data.append((
                    item['supplier'],
                    item['code'],
                    item['brand'],
                    item['price'],
                    item['expiry_date'],
                    item['warehouse'],
                    item['stock'],
                    item['remark'],
                    item['fetch_time']
                ))
            
            # 批量插入
            sql = """
                INSERT INTO tenglong_data (supplier, code, brand, price, expiry_date, warehouse, stock, remark, fetch_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            db_manager.execute_many(sql, batch_data)
            print(f"已批量保存 {min(i + batch_size, len(final_data))} / {len(final_data)} 条腾隆数据")
        
    finally:
        db_manager.close()

    # 将处理后的数据保存到各公司整合表
    # 转换为DataFrame格式
    import pandas as pd
    df = pd.DataFrame(final_data)
    df = df.rename(columns={
        'supplier': '供应商名称',
        'code': '原厂OE码',
        'brand': '品牌',
        'price': '价格',
        'expiry_date': '失效时间',
        'warehouse': '仓库名称',
        'stock': '库存',
        'remark': '备注'
    })
    df['原价格'] = df.get('original_price', df['价格'])

    # 保存到各公司表（腾隆数据不是万拓也不是昌盛）
    save_to_company_tables(df, is_wantuo=False, is_changsheng=False)

    print("腾隆数据已批量保存到数据库")


def get_crm_cookies():
    url = "http://113.45.176.129:8001/get_crm_cookies?key=fs"
    payload = {}
    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36'
    }
    response = requests.request("GET", url, headers=headers, data=payload)
    cookies = json.loads(response.text)['cookie']
    headers = cookies

    return cookies, headers


def get_stock(cookies, headers):
    json_data = {
        'sale_start_time': None,
        'sale_end_time': None,
        'is_sub': None,
        'is_hot': None,
        'is_new': None,
        'product_type_id': None,
        'make_id': None,
        'series_id': None,
        'car_id': None,
        'chassis_id': None,
        'engine_id': None,
        'brand_id': '53,5,98,110',
        'sap_product_division': None,
        'material_type': None,
        'level_id': None,
        'product_grade': None,
        'currency_id': None,
        'language_code': None,
        'vin': None,
        'keyword': None,
        'aikeyword': None,
        'number': None,
        'numberlist': None,
        'is_stock': '1',
        'is_dangerstock': 0,
        'is_nostock': 0,
        'sale_type': 0,
        'is_zaitu': None,
        'customer_id': None,
        'price_exception': '',
        'is_third_party': None,
        'brand_type': None,
        'brand_type_map_id': None,
        'is_unsalable': None,
        'out_purchase_product': None,
        'page': 1,
        'limit': 20,
        'cass_oebrand_name': '',
        'warehouse_id': '',
    }
    page_max = 1
    page = 1

    brand_data = {
        '马勒': {},
        '贝洱': {},
        '纳铁福': {},
        '吉凯恩': {},
    }

    while page <= page_max:
        json_data['page'] = page
        try:
            response = requests.post(
                'https://crm.gzbbr.com/api/Product.Product/list',
                cookies=cookies,
                headers=headers,
                json=json_data,
                timeout=10
            ).json()['data']
        except (requests.RequestException, KeyError) as e:
            print(f"请求失败: {e}")
            return {}, {}, {}, {}

        page_max = response.get('last_page', 1)

        for item in response.get('data', [{}])[0].get('child', []):
            number = item.get('number')
            brand_name = item.get('brand_name')
            price = item.get('price')
            if not price:
                continue
            stock = item.get('stock', 0)

            if brand_name in brand_data:
                brand_data[brand_name][number] = {
                    'price': price,
                    'stock': stock
                }

        print(f'Page {page} / {page_max}')
        page += 1

    return (
        brand_data['马勒'],
        brand_data['贝洱'],
        brand_data['纳铁福'],
        brand_data['吉凯恩']
    )


def chuli_beiermale(male, beier, ntf, jky):
    print(beier)
    print('m')
    print(male)
    data = []

    # 马勒-贝洱对比组
    for number in male:
        if number not in beier:
            # 确保价格是数值类型后再进行计算
            price_value = male[number]['price']
            if isinstance(price_value, str):
                try:
                    price_value = float(price_value)
                except ValueError:
                    print(f"警告: 无法将价格 '{price_value}' 转换为数值，跳过此项")
                    continue
            adjusted_price = process_price_by_brand(price_value, '贝洱')
            data.append([
                number, '贝洱', adjusted_price, price_value, male[number]['stock']
            ])
    
    for number in beier:
        if number not in male:
            # 确保价格是数值类型后再进行计算
            price_value = beier[number]['price']
            if isinstance(price_value, str):
                try:
                    price_value = float(price_value)
                except ValueError:
                    print(f"警告: 无法将价格 '{price_value}' 转换为数值，跳过此项")
                    continue
            adjusted_price = process_price_by_brand(price_value, '马勒')
            data.append([
                number, '马勒', adjusted_price, price_value, beier[number]['stock']
            ])

    # 纳铁福-吉凯恩对比组
    for number in ntf:
        if number not in jky:
            # 确保价格是数值类型后再进行计算
            price_value = ntf[number]['price']
            if isinstance(price_value, str):
                try:
                    price_value = float(price_value)
                except ValueError:
                    print(f"警告: 无法将价格 '{price_value}' 转换为数值，跳过此项")
                    continue
            adjusted_price = process_price_by_brand(price_value, '吉凯恩')
            data.append([
                number, '吉凯恩', adjusted_price, price_value, ntf[number]['stock']
            ])
    
    for number in jky:
        if number not in ntf:
            # 确保价格是数值类型后再进行计算
            price_value = jky[number]['price']
            if isinstance(price_value, str):
                try:
                    price_value = float(price_value)
                except ValueError:
                    print(f"警告: 无法将价格 '{price_value}' 转换为数值，跳过此项")
                    continue
            adjusted_price = process_price_by_brand(price_value, '纳铁福')
            data.append([
                number, '纳铁福', adjusted_price, price_value, jky[number]['stock']
            ])

    return data


def save_beiermale_to_db(data):
    current_time = datetime.now()
    expiry_date = (current_time + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
    fetch_time_str = current_time.strftime('%Y-%m-%d %H:%M:%S')
    
    # 批量保存到数据库
    db_manager = get_db_connection()
    try:
        # 批量插入数据
        batch_size = 1000  # 批量处理大小
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            
            # 准备批量插入数据
            batch_data = []
            for row in batch:
                batch_data.append((
                    '佛山巴博瑞',  # 供应商
                    row[0],       # OE码
                    row[1],       # 品牌
                    row[2],       # 价格
                    expiry_date,  # 失效时间（当前时间+1天）
                    '佛山禅城仓', # 仓库
                    row[3],       # 库存
                    '',           # 备注
                    fetch_time_str  # 拉取时间
                ))
            
            # 批量插入
            sql = """
                INSERT INTO beiermale_data (supplier, oe_code, brand, price, expiry_date, warehouse, stock, remark, fetch_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            db_manager.execute_many(sql, batch_data)
            print(f"已批量保存 {min(i + batch_size, len(data))} / {len(data)} 条贝尔马勒数据")
        
    finally:
        db_manager.close()

    # 将数据保存到各公司整合表
    df = pd.DataFrame(data, columns=['原厂OE码', '品牌', '价格', '原价格', '库存'])
    df['供应商名称'] = '佛山巴博瑞'
    df['失效时间'] = expiry_date
    df['仓库名称'] = '佛山禅城仓'
    df['备注'] = ''

    # 保存到各公司表（贝尔马勒数据不是万拓也不是昌盛）
    save_to_company_tables(df, is_wantuo=False, is_changsheng=False)


def male_bier_start():
    cookies, headers = get_crm_cookies()
    male_data, beier_data, ntf_data, jky_data = get_stock(cookies, headers)
    diff_data = chuli_beiermale(male_data, beier_data, ntf_data, jky_data)
    save_beiermale_to_db(diff_data)


def gylqp_start():
    cookies = {
        'ASP.NET_SessionId': '2xjnyp1lnkpnqn53rl2ced4y',
        'b2bgylqp': 'ztname=KH020215&ztpwd=337704&ztper=&ztdpm=A&ztdpmname=%e5%b9%bf%e5%b7%9e%e6%80%bb%e9%83%a8',
    }

    headers = {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'Connection': 'keep-alive',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Origin': 'http://www.gylqp.com',
        'Referer': 'http://www.gylqp.com/New/index.aspx?mname=%E9%9B%B6%E4%BB%B6%E8%AF%A2%E4%BB%B7%E6%9C%8D%E5%8A%A1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0',
    }

    data = {
        'action': 'Getisto',
        'modulename': 'Getisto',
        'PageIndex': '1',
        'wdcp': 'false',
        'data': '{"Where":"","Nno":"","tabindex":"0"}',
    }
    page = 1
    d_ = []
    while True:
        data['PageIndex'] = str(page)
        for c in range(3):
            try:
                response = requests.post('http://www.gylqp.com/Handler/KHHandler.ashx', cookies=cookies, headers=headers, data=data,
                                         verify=False).json()
                c = len(response)
                break
            except:
                time.sleep(2)
        if page == 1:
            print(response[0])
            print()
        if c > 0:
            for item in response:
                d_.append([
                    item['v_nno'].strip(), item['na1'].strip(), item['ty'].strip(), item['fa'].strip(), item['oprc'],
                    item['kcamount'], item['areaname'].strip(), item['qq'].strip(), item['posi'].strip(),
                    item['sxnote'].strip(), item['hhm'].strip()
                ])
            print(f'\r以获取第{page}页，共{c}条数据')
            page += 1
        else:
            break

    current_time = datetime.now()
    fetch_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
    
    # 分类数据
    foshan_data = []
    dongguan_data = []
    zhongshan_data = []
    
    for i in d_:
        if '佛山' in i[6]:
            bm = i[0].replace(' ','')
            bm = bm.split('-')[0].replace('AM','')
            gys = '爱车贝母'
            pp = '巴博瑞'
            # 根据品牌处理价格
            original_price = i[4]
            price = process_price_by_brand(original_price, pp)
            kc = i[5]
            next_day_later = (current_time + timedelta(days=1)).strftime(
                "%Y-%m-%d %H:%M:%S")
            ck = '佛山禅城仓'
            foshan_data.append([
                gys, bm, pp, price, original_price, next_day_later, ck, kc, '', fetch_time
            ])
        if '东莞' in i[6]:
            bm = i[0].replace(' ','')
            bm = bm.split('-')[0].replace('AM','')
            gys = '爱车贝母'
            pp = '巴博瑞'
            # 根据品牌处理价格
            original_price = i[4]
            price = process_price_by_brand(original_price, pp)
            kc = i[5]
            next_day_later = (current_time + timedelta(days=1)).strftime(
                "%Y-%m-%d %H:%M:%S")
            ck = '东莞寮步仓'
            dongguan_data.append([
                gys, bm, pp, price, original_price, next_day_later, ck, kc, '', fetch_time
            ])
        if '中山' in i[6]:
            bm = i[0].replace(' ','')
            bm = bm.split('-')[0].replace('AM','')
            gys = '爱车贝母'
            pp = '巴博瑞'
            # 根据品牌处理价格
            original_price = i[4]
            price = process_price_by_brand(original_price, pp)
            kc = i[5]
            next_day_later = (current_time + timedelta(days=1)).strftime(
                "%Y-%m-%d %H:%M:%S")
            ck = '中山西区街道仓'
            zhongshan_data.append([
                gys, bm, pp, price, original_price, next_day_later, ck, kc, '', fetch_time
            ])

    # 批量保存到数据库
    db_manager = get_db_connection()
    try:
        # 保存佛山数据
        batch_size = 1000
        for i in range(0, len(foshan_data), batch_size):
            batch = foshan_data[i:i + batch_size]
            
            # 准备批量插入数据（跳过 original_price 字段）
            batch_data = []
            for row in batch:
                batch_data.append((row[0], row[1], row[2], row[3], row[5], row[6], row[7], row[8], row[9]))
            
            # 批量插入
            sql = """
                INSERT INTO aichebeimu_foshan_data (supplier, oe_code, brand, price, expiry_date, warehouse, stock, remark, fetch_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            db_manager.execute_many(sql, batch_data)
            print(f"已批量保存 {min(i + batch_size, len(foshan_data))} / {len(foshan_data)} 条爱车贝母佛山数据")
        
        # 保存东莞数据
        for i in range(0, len(dongguan_data), batch_size):
            batch = dongguan_data[i:i + batch_size]
            
            # 准备批量插入数据（跳过 original_price 字段）
            batch_data = []
            for row in batch:
                batch_data.append((row[0], row[1], row[2], row[3], row[5], row[6], row[7], row[8], row[9]))
            
            # 批量插入
            sql = """
                INSERT INTO aichebeimu_dongguan_data (supplier, oe_code, brand, price, expiry_date, warehouse, stock, remark, fetch_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            db_manager.execute_many(sql, batch_data)
            print(f"已批量保存 {min(i + batch_size, len(dongguan_data))} / {len(dongguan_data)} 条爱车贝母东莞数据")
        
        # 保存中山数据
        for i in range(0, len(zhongshan_data), batch_size):
            batch = zhongshan_data[i:i + batch_size]
            
            # 准备批量插入数据（跳过 original_price 字段）
            batch_data = []
            for row in batch:
                batch_data.append((row[0], row[1], row[2], row[3], row[5], row[6], row[7], row[8], row[9]))
            
            # 批量插入
            sql = """
                INSERT INTO aichebeimu_zhongshan_data (supplier, oe_code, brand, price, expiry_date, warehouse, stock, remark, fetch_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            db_manager.execute_many(sql, batch_data)
            print(f"已批量保存 {min(i + batch_size, len(zhongshan_data))} / {len(zhongshan_data)} 条爱车贝母中山数据")
        
    finally:
        db_manager.close()

    # 将数据保存到各公司整合表
    all_data = foshan_data + dongguan_data + zhongshan_data
    df = pd.DataFrame(all_data, columns=['供应商名称', '原厂OE码', '品牌', '价格', '原价格', '失效时间', '仓库名称', '库存', '备注', 'fetch_time'])

    # 保存到各公司表（爱车贝母数据不是万拓也不是昌盛）
    save_to_company_tables(df, is_wantuo=False, is_changsheng=False)


def get_zhuozhixing_multi():
    """
    获取鑫峰和广星库存
    :return:
    """
    suppliers = [
        {
            'name': '鑫峰',
            'gsign': 'B810A2A5ABAE10EAEE19B3BE563B24A9'
        },
        {
            'name': '广星',
            'gsign': '9F478C130BCD573232B129C5928F0B42'
        }
    ]
    
    all_dataframes = []
    
    for supplier_info in suppliers:
        supplier_name = supplier_info['name']
        gsign = supplier_info['gsign']
        
        # 一天只有3次
        url = f"http://api.inheartsoft.com/dw-api/kc2018?psign=7be06d54152d0bd916f09b0b055f76ad&gsign={gsign}&mode=allkckey"
        try:
            response = requests.request("GET", url)
            response.raise_for_status()  # 确保请求成功
        except requests.exceptions.RequestException as e:
            print(f"获取{supplier_name}数据时出错: {e}")
            continue
            
        try:
            allkckey = json.loads(response.text)['allkckey']
        except (json.JSONDecodeError, KeyError) as e:
            print(f"解析{supplier_name}初始响应失败: {e}")
            continue
            
        print(f"{supplier_name} allkckey: {allkckey}")
        pindex = 1
        res_list = []
        while True:
            url = f"http://api.inheartsoft.com/dw-api/kc2018?psign=7be06d54152d0bd916f09b0b055f76ad&gsign={gsign}&allkckey={allkckey}&mode=all_kc&pindex={pindex}"
            try:
                response = requests.request("GET", url)
                response.raise_for_status()
            except Exception as e:
                print(f"{supplier_name} 第{pindex}页请求失败: {e}")
                try:
                    response = requests.request("GET", url)
                    response.raise_for_status()
                except Exception as e:
                    print(f"{supplier_name} 第{pindex}页第二次请求失败: {e}")
                    try:
                        response = requests.request("GET", url)
                        response.raise_for_status()
                    except Exception as e:
                        print(f"{supplier_name} 第{pindex}页第三次请求失败，跳过: {e}")
                        break

            try:
                data_list = json.loads(response.text)['list']
            except (json.JSONDecodeError, KeyError) as e:
                print(f"{supplier_name} 解析第{pindex}页响应失败: {e}")
                break
                
            if len(data_list) == 0:
                break
            pindex = pindex + 1
            print(f"{supplier_name} 正在查询第{pindex}页")
            res_list.append(pd.DataFrame(data_list))

        if res_list:  # 如果有数据
            df = pd.concat(res_list, ignore_index=True)
            df = df.rename(columns={"pjid": "配件ID", "pjcode": "零件编码", "pjoemcode": "制造编码", "pjname": "零件名称",
                                    "pjename": "零件英文名称",
                                    "pjsize": "零件车型", "pjfactory": "产地", "xsprice": "价格", "kcamount": "库存数",
                                    'pjpp': '零件品牌',
                                    'pjbrand': '品牌', 'ppcode': '品牌编码', 'gxcode': '公会编码', 'pjgensize': '通用车型',
                                    'hhcode': '互换码', 'Isgx': '是否共享',
                                    'kcid': '商家库存表自增ID', 'kcdepot': '库号（仓库）'})

            df['oe_number1'] = df['零件编码'].str.replace(' ', '').str.replace('正厂', '').str.replace('-', '')
            df['ys_oe1'] = df['零件编码'].str.replace(' ', '').str.replace('正厂', '').str.replace('-', '')
            # 更新时间
            df['updateTime'] = str(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            df['update1'] = str(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            # 名称
            df['product_name1'] = df['零件名称']
            # 品牌
            df['brand_name1'] = df['产地'].str.replace(' ', '').replace('正厂', '原厂件')
            # 供应商
            df['seller_name1'] = supplier_name  # 使用当前供应商名称
            # 价格
            df['price1'] = df['价格']
            # 库存
            df['quantity1'] = df['库存数']
            # 地区
            df['city_name'] = '广州'
            # 备注
            df['make_vehicle1'] = df['通用车型']
            df['spider_date1'] = str(datetime.now().strftime('%Y-%m-%d'))
            df['make_name1'] = ''
            df = df[['spider_date1', 'oe_number1','ys_oe1','update1','product_name1','brand_name1','seller_name1','quantity1',
                     'price1','make_name1','make_vehicle1','city_name']]

            df = df[['seller_name1', 'oe_number1', 'brand_name1', 'price1', 'city_name', 'quantity1']]
            all_dataframes.append(df)
    
    if all_dataframes:
        return pd.concat(all_dataframes, ignore_index=True)
    else:
        return pd.DataFrame()  # 返回空DataFrame


def fetch_and_process_latest_data():
    host = '113.45.176.129'
    port = 3306
    user = 'fsbbr_data'
    password = 'wRCA8AGn3a568f4X'
    database = 'fsbbr_data'

    # 连接MySQL数据库
    conn = pymysql.connect(
        host=host,
        user=user,
        password=password,
        database=database,
        port=port,
        charset='utf8mb4'
    )

    try:
        # 先查询最新日期
        latest_date_query = """
        SELECT DATE(MAX(spider_date1)) as latest_date 
        FROM jqr_data
        """

        latest_date_result = pd.read_sql_query(latest_date_query, conn)
        latest_date = latest_date_result['latest_date'].iloc[0]

        if latest_date is None:
            print("数据库中没有数据")
            return None

        print(f"最新数据日期: {latest_date}")

        # 查询最新日期的所有数据
        data_query = f"""
        SELECT seller_name1, oe_number1, brand_name1, price1, city_name, quantity1
        FROM jqr_data 
        WHERE DATE(spider_date1) = '{latest_date}'
        """

        # 读取数据
        df = pd.read_sql_query(data_query, conn)
        df2 = get_zhuozhixing_multi()  # 使用新函数获取鑫峰和广星数据
        df = pd.concat([df, df2])

        if df.empty:
            print(f"在 {latest_date} 没有找到数据")
            return None

        # 品牌名称映射
        brand_mapping = {
            "下线": "XX",
            "原厂件": "原厂",
            "其它": "其他",
            "尼兰": "其他",
            "陆地卫士": "其他",
            "曼克马利": "巴博瑞",
            "伦福德": "伦福德(猫)",
            "VDO": "威迪欧",
            "科尔本施密特": "科尔本",
            "路爵士": "巴博瑞",
            "优宾": "巴博瑞",
            "卡玛伦": "巴博瑞",
            "汉科再生": "巴博瑞",
            "长虹": "巴博瑞",
            "都得利": "巴博瑞",
            "台湾提维西": "巴博瑞",
            "台湾维仑": "巴博瑞",
            "维轮AP": "巴博瑞",
            "亿升钣金": "巴博瑞",
            "ANHUO": "巴博瑞",
            "隆丰": "巴博瑞",
            "鹰眼": "巴博瑞",
        }

        # 应用品牌名称映射
        df['brand_name1'] = df['brand_name1'].replace(brand_mapping)

        # 仓库名称映射
        city_mapping = {
            "佛山": "佛山禅城仓",
            "广州": "广州越秀仓"
        }

        # 应用仓库名称映射
        df['city_name'] = df['city_name'].replace(city_mapping)
        # 直接使用 ys_oe1 作为 OE 码，不做处理
        df['oe_number1'] = df['ys_oe1']
        # 计算当前时间+1天作为失效时间
        expiry_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')

        # 创建新的DataFrame，匹配Excel表头
        result_df = pd.DataFrame({
            '供应商名称': df['seller_name1'],
            '原厂OE码': df['oe_number1'],  # 修改列名
            '品牌': df['brand_name1'],
            '价格': df['price1'],
            '失效时间': expiry_date,  # 当前时间+1天
            '仓库名称': df['city_name'],
            '库存': df['quantity1'],
            '备注': ''
        })

        # 按照'供应商名称', '原厂oe码', '品牌'去重，保留第一次出现的记录
        result_df = result_df.drop_duplicates(subset=['供应商名称', '原厂OE码', '品牌'], keep='first')

        # 批量保存到数据库
        db_manager = get_db_connection()
        try:
            # 批量插入数据
            batch_size = 1000  # 批量处理大小
            fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 保存原价格
            result_df['原价格'] = result_df['价格']

            # 根据品牌处理价格
            result_df['价格'] = result_df.apply(lambda row: process_price_by_brand(row['价格'], row['品牌']), axis=1)

            
            # 保存原始数据到机器人数据表
            for i in range(0, len(result_df), batch_size):
                batch = result_df.iloc[i:i + batch_size]
                
                # 准备批量插入数据
                batch_data = []
                for index, row in batch.iterrows():
                    batch_data.append((
                        row['供应商名称'],
                        row['原厂OE码'],
                        row['品牌'],
                        row['价格'],
                        row['失效时间'],
                        row['仓库名称'],
                        row['库存'],
                        row['备注'],
                        fetch_time  # 拉取时间
                    ))
                
                # 批量插入到机器人数据表
                sql = """
                    INSERT INTO robot_data (supplier_name, oe_number, brand_name, price, expiry_date, city_name, quantity, remark, fetch_time)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                db_manager.execute_many(sql, batch_data)
                print(f"已批量保存 {min(i + batch_size, len(result_df))} / {len(result_df)} 条机器人数据到机器人数据表")
            
        finally:
            db_manager.close()

        # 将数据保存到各公司整合表（机器人数据不是万拓也不是昌盛）
        save_to_company_tables(result_df, is_wantuo=False, is_changsheng=False)

        print(f"成功保存 {len(result_df)} 条机器人数据到数据库")
        return result_df

    except Exception as e:
        print(f"处理数据时发生错误: {e}")
        return None
    finally:
        conn.close()




def ggg2():
    url = "http://113.45.176.129:8001/get_xlsx_files"
    payload = {}
    headers = {
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
      'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
      'Cache-Control': 'max-age=0',
      'Connection': 'keep-alive',
      'Upgrade-Insecure-Requests': '1',
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36'
    }
    response = requests.request("GET", url, headers=headers, data=payload)
    
    # 添加错误处理
    try:
        response_data = json.loads(response.text)
    except json.JSONDecodeError:
        print(f"响应不是有效的JSON格式: {response.text}")
        return pd.DataFrame()  # 返回空DataFrame
    
    # 检查是否有'files'键
    if 'files' not in response_data:
        print(f"API响应中没有'files'键: {response_data}")
        return pd.DataFrame()  # 返回空DataFrame
    
    files = response_data['files']
    xs_df_list = []
    for file in files:
        url = "http://113.45.176.129:8001/download/" + file['filename']
        response = requests.request("GET", url, headers=headers)
        try:
            file_data = json.loads(response.text)['data']
            cdf = pd.DataFrame(file_data)
            xs_df_list.append(cdf)
        except json.JSONDecodeError:
            print(f"下载文件响应不是有效的JSON格式: {response.text}")
            continue
        except KeyError:
            print(f"下载文件响应中没有'data'键: {response.text}")
            continue

    if not xs_df_list:  # 如果没有有效数据
        return pd.DataFrame()
        
    fd_df = pd.concat(xs_df_list)
    fd_df['原厂OE码'] = fd_df['原厂oe码']
    fd_df = fd_df[['供应商名称','原厂OE码','品牌','价格','失效时间','仓库名称','库存','备注']]

    # 保存原价格
    fd_df['原价格'] = fd_df['价格']

    # 根据品牌处理价格
    fd_df['价格'] = fd_df.apply(
        lambda row: process_price_by_brand(row['价格'], row['品牌']) if row['价格'] != '' and pd.notna(row['价格']) and row['价格'] is not None else row['价格'],
        axis=1
    )

    # 替换nan值
    fd_df = fd_df.fillna('')
    
    # 添加拉取时间
    fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fd_df['fetch_time'] = fetch_time
    
    # 批量保存到数据库
    db_manager = get_db_connection()
    try:
        # 批量插入数据
        batch_size = 1000  # 批量处理大小
        for i in range(0, len(fd_df), batch_size):
            batch = fd_df.iloc[i:i + batch_size]
            
            # 准备批量插入数据
            batch_data = []
            for index, row in batch.iterrows():
                batch_data.append((
                    row['供应商名称'],
                    row['原厂OE码'],
                    row['品牌'],
                    row['价格'],
                    row['失效时间'],
                    row['仓库名称'],
                    row['库存'],
                    row['备注'],
                    row['fetch_time']
                ))
            
            # 批量插入到外部数据表
            sql = """
                INSERT INTO external_data (supplier_name, oe_code, brand, price, expiry_date, warehouse, stock, remark, fetch_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            db_manager.execute_many(sql, batch_data)
            print(f"已批量保存 {min(i + batch_size, len(fd_df))} / {len(fd_df)} 条外部数据到外部数据表")
        
    finally:
        db_manager.close()

    # 将数据保存到各公司整合表（外部数据不是万拓也不是昌盛）
    # 注意：ggg2函数已经对价格进行了处理，这里需要重新按各公司规则处理
    # 所以不使用save_to_company_tables，而是直接保存到各表（价格已在上面处理过）
    companies = ['fsbbr', 'zhbbr', 'zsbbr', 'dgby', 'dghf']
    table_map = {
        'fsbbr': 'virtual_inventory',
        'zhbbr': 'virtual_inventory_zhbbr',
        'zsbbr': 'virtual_inventory_zsbbr',
        'dgby': 'virtual_inventory_dgby',
        'dghf': 'virtual_inventory_dghf'
    }

    db_manager = get_db_connection()
    try:
        for company in companies:
            table_name = table_map[company]

            # 准备数据
            batch_data = []
            for _, row in fd_df.iterrows():
                batch_data.append((
                    row['供应商名称'],
                    row['原厂OE码'],
                    row['品牌'],
                    row['价格'],  # 已经处理过的价格
                    row['原价格'],
                    row['失效时间'],
                    row['仓库名称'],
                    row['库存'],
                    row['备注'],
                    row['fetch_time']
                ))

            # 批量插入
            batch_size = 1000
            for i in range(0, len(batch_data), batch_size):
                batch = batch_data[i:i + batch_size]
                sql = f"""
                    INSERT INTO {table_name} (supplier_name, oe_code, brand, price, original_price, expiry_date, warehouse, stock, remark, fetch_time)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                db_manager.execute_many(sql, batch)
                print(f"[{company}] 已批量保存 {min(i + batch_size, len(batch_data))} / {len(batch_data)} 条外部数据")

    finally:
        db_manager.close()

    return fd_df

def delete_old_data():
    """删除50天前的数据（所有公司汇总表）"""
    db_manager = get_db_connection()
    try:
        tables = [
            'virtual_inventory',
            'virtual_inventory_zhbbr',
            'virtual_inventory_zsbbr',
            'virtual_inventory_dgby',
            'virtual_inventory_dghf'
        ]

        for table in tables:
            delete_sql = f"""
                DELETE FROM {table}
                WHERE fetch_time < DATE_SUB(NOW(), INTERVAL 50 DAY)
            """
            deleted_count = db_manager.execute_update(delete_sql)
            print(f"[{table}] 已删除 {deleted_count} 条50天前的数据")
    finally:
        db_manager.close()


def save_to_company_tables(df, is_wantuo=False, is_changsheng=False, is_changsheng_special_fn=None):
    """
    保存数据到各公司虚拟库存表，按各公司价格规则处理

    :param df: 数据DataFrame
    :param is_wantuo: 是否为万拓数据
    :param is_changsheng: 是否为昌盛数据
    :param is_changsheng_special_fn: 判断是否为昌盛特殊产品的函数
    """
    if df is None or df.empty:
        return

    companies = ['fsbbr', 'zhbbr', 'zsbbr', 'dgby', 'dghf']
    table_map = {
        'fsbbr': 'virtual_inventory',
        'zhbbr': 'virtual_inventory_zhbbr',
        'zsbbr': 'virtual_inventory_zsbbr',
        'dgby': 'virtual_inventory_dgby',
        'dghf': 'virtual_inventory_dghf'
    }

    fetch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db_manager = get_db_connection()

    try:
        for company in companies:
            table_name = table_map[company]
            processed_data = []

            for _, row in df.iterrows():
                # 判断是否为昌盛特殊产品
                is_changsheng_special = False
                if is_changsheng_special_fn:
                    is_changsheng_special = is_changsheng_special_fn(row)

                # 按公司规则处理价格
                original_price = row['价格']
                processed_price = process_price_by_brand(
                    original_price,
                    row['品牌'],
                    is_wantuo=is_wantuo,
                    is_changsheng_special=is_changsheng_special,
                    company=company
                )

                processed_data.append((
                    row['供应商名称'],
                    row['原厂OE码'],
                    row['品牌'],
                    processed_price,
                    original_price,
                    row['失效时间'],
                    row['仓库名称'],
                    row['库存'],
                    row['备注'],
                    fetch_time
                ))

            # 批量插入
            batch_size = 1000
            for i in range(0, len(processed_data), batch_size):
                batch = processed_data[i:i + batch_size]
                sql = f"""
                    INSERT INTO {table_name} (supplier_name, oe_code, brand, price, original_price, expiry_date, warehouse, stock, remark, fetch_time)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                db_manager.execute_many(sql, batch)
                print(f"[{company}] 已保存 {min(i + batch_size, len(processed_data))} / {len(processed_data)} 条")

    finally:
        db_manager.close()


def save_supplier_to_virtual_inventory(df, supplier_name="供应商"):
    """
    保存供应商库存数据到各公司虚拟库存表
    """
    if df is None or df.empty:
        print(f"{supplier_name}库存数据为空，跳过保存")
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


def start_b2b_upload_with_brand_mapping(today_only=False):
    """
    上传数据到B2B系统，包含品牌映射和价格处理逻辑（优化版）
    today_only: 是否只上传今天的数据
    """
    import requests
    import json
    import decimal
    from datetime import datetime, date
    import time
    
    def convert_decimal_to_serializable(obj):
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        elif isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {key: convert_decimal_to_serializable(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [convert_decimal_to_serializable(item) for item in obj]
        elif isinstance(obj, tuple):
            return tuple(convert_decimal_to_serializable(item) for item in obj)
        else:
            return obj

    def login(company):
        config = {
            'fsbbr': {
                "AccessKeyId": "tdFsi8qAQVDz0PAotz56CNFJib3evY8H",
                "AccessKeySecret": "wHsV0V1Fk7MJBQ8tcy6XTd4VhLMxgtEr9vZhDjU9yxrtDwyBTFE8QI0WQY3c7Npp"
            },
            'zhbbr': {
                "AccessKeyId": "D6xZVa6tn3zK9vOxd7TGh6d5XLhHWoEe",
                "AccessKeySecret": "DOYRvIlOHVParozgWaS3I79BgKSs5cBz5ZBCaYAfUwWfDUGGmSryHdKBKxeuKYQ1"
            },
            'zsbbr': {
                "AccessKeyId": "4UjFNIabklprFwUtXVn4Rof4xeA2A79m",
                "AccessKeySecret": "UeJoyb6MeeXKBJmZBtTbgnazHujKDN2X4Xqi3kKZuCAVZdzWZT49V0UKX25D4i7F"
            },
            'dgby': {
                "AccessKeyId": "QChRLkBRG8iZTmmC4T3tRk9R1Xgn6EVr",
                "AccessKeySecret": "BfXAdzONLHKb1yoW2Eeuvb4ui7Z0W6GBjWegO4OZzahKQGzPmofhjOLekLxFhFyX"
            },
            'dghf': {
                "AccessKeyId": "p5yr2EjeLxY4MhmWNcTi9gS9mOJi7Unp",
                "AccessKeySecret": "nvnugyGdVwecdwdUbkUpHsLEDyKdYPXAfGL6aZx1rZnmjqDdyDt5JNYQGCKtRXEK"
            }
        }
        url = "https://openapi.gzbbr.com/login/index"
        data = config[company]
        
        for attempt in range(3):
            try:
                response = requests.post(url, data=data, timeout=(10, 30))
                break
            except requests.exceptions.ConnectTimeout:
                if attempt == 2:
                    raise
                time.sleep(5)
        re_js = json.loads(response.text)
        token = re_js['data']['token']
        return token

    def getAllCassWarehouse(token):
        url = "https://openapi.gzbbr.com/Product.Quote/getAllCassWarehouse"
        headers = {'token': token}
        for attempt in range(3):
            try:
                response = requests.request("GET", url, headers=headers, timeout=(10, 30))
                break
            except requests.exceptions.ConnectTimeout:
                if attempt == 2:
                    raise
                time.sleep(5)
        re_js = json.loads(response.text)
        data = pd.DataFrame(re_js['data'])
        del data['warehouse_no']
        return data

    def getAllSupplierChannel(token):
        url = "https://openapi.gzbbr.com/Product.Quote/getAllSupplierChannel"
        headers = {'token': token}
        for attempt in range(3):
            try:
                response = requests.request("GET", url, headers=headers, timeout=(10, 30))
                break
            except requests.exceptions.ConnectTimeout:
                if attempt == 2:
                    raise
                time.sleep(5)
        re_js = json.loads(response.text)
        data = pd.DataFrame(re_js['data'])
        del data['byname']
        return data

    def split_array_by_500_loop(arr):
        split_groups = []
        start = 0
        n = len(arr)
        while start < n:
            group = arr[start:start+500]
            split_groups.append(group)
            start += 500
        return split_groups

    def batchSave(records, original_rows, brand_mapping_info, reverse_brand_mapping, original_df, company='fsbbr'):
        # 转换所有记录中的不可序列化类型为可序列化类型
        serializable_records = [convert_decimal_to_serializable(record) for record in records]

        record_groups = split_array_by_500_loop(serializable_records)
        original_row_groups = split_array_by_500_loop(original_rows)

        for i, group in enumerate(record_groups):
            # 获取token，增加重试机制
            token = None
            for attempt in range(3):
                try:
                    token = login(company)
                    break
                except requests.exceptions.ConnectTimeout:
                    if attempt == 2:
                        print(f'[{company}] 获取token失败，跳过批次 {i+1}')
                        continue
                    time.sleep(5)
                except Exception as e:
                    if attempt == 2:
                        print(f'[{company}] 获取token失败，跳过批次 {i+1}')
                        continue
                    time.sleep(5)

            if token is None:
                print(f"[{company}] 无法获取token，跳过批次 {i+1}")
                continue

            url = "https://openapi.gzbbr.com/Product.Quote/batchSave"
            payload = json.dumps({
                "params": group
            })
            headers = {
                'token': token,
                'Content-Type': 'application/json'
            }
            
            # 发送请求，增加重试机制和更长的超时时间
            response = None
            for attempt in range(3):
                try:
                    response = requests.post(url, headers=headers, data=payload, timeout=(15, 180))
                    break
                except requests.exceptions.ConnectTimeout:
                    if attempt == 2:
                        print(f'[{company}] 批次 {i+1} 连接超时，跳过此批次')
                        continue
                    time.sleep(10)
                except requests.exceptions.ReadTimeout:
                    if attempt == 2:
                        print(f'[{company}] 批次 {i+1} 读取超时，跳过此批次')
                        continue
                    time.sleep(10)
                except requests.exceptions.ConnectionError as e:
                    if "Read timed out" in str(e):
                        if attempt == 2:
                            print(f'[{company}] 批次 {i+1} 读取超时，跳过此批次')
                            continue
                        time.sleep(10)
                    else:
                        if attempt == 2:
                            print(f'[{company}] 批次 {i+1} 连接错误，跳过此批次')
                            continue
                        time.sleep(10)
                except Exception as e:
                    if attempt == 2:
                        print(f'[{company}] 批次 {i+1} 发生未知错误，跳过此批次')
                        continue
                    time.sleep(10)

            if response is None:
                print(f"[{company}] 批次 {i+1} 响应为空，跳过")
                continue

            try:
                result = json.loads(response.text)
            except json.JSONDecodeError:
                print(f'[{company}] 批次 {i+1} 响应不是有效的JSON格式')
                continue
            except Exception as e:
                print(f'[{company}] 批次 {i+1} 解析响应时发生错误: {e}')
                continue

            # 更新数据库中的update_msg字段
            db_manager = get_db_connection()
            try:
                if 'data' in result and 'succes_data' in result['data'] and 'error_data' in result['data']:
                    # 获取成功和失败的数据
                    succes_data = result['data']['succes_data'] if result['data']['succes_data'] else []
                    error_data = result['data']['error_data'] if result['data']['error_data'] else []

                    # 将成功和失败的数据合并到一个列表，按no排序
                    all_results = succes_data + error_data
                    all_results.sort(key=lambda x: x['no'])

                    print(f'[{company}] 批次 {i+1}: 成功上传 {result["data"]["succes_num"]} 条, 失败 {result["data"]["error_num"]} 条')

                    # 根据公司确定要更新的表
                    table_map = {
                        'fsbbr': 'virtual_inventory',
                        'zhbbr': 'virtual_inventory_zhbbr',
                        'zsbbr': 'virtual_inventory_zsbbr',
                        'dgby': 'virtual_inventory_dgby',
                        'dghf': 'virtual_inventory_dghf'
                    }
                    table_name = table_map.get(company, 'virtual_inventory')

                    # 收集所有需要更新的数据
                    update_data = []
                    original_group = original_row_groups[i]
                    for j, result_item in enumerate(all_results):
                        if j < len(original_group):
                            # 获取原始记录的ID
                            original_row = original_group[j]

                            # 根据原始行的格式确定ID字段
                            # 如果是字典格式，则使用键访问
                            if isinstance(original_row, dict):
                                record_id = original_row['id']
                            else:  # 如果是元组或列表格式
                                record_id = original_row[0]

                            # 获取上传结果信息
                            if 'error_msg' in result_item:
                                update_msg = result_item['error_msg']
                            elif 'operation_name' in result_item:
                                operation_name = result_item['operation_name']
                                # 检查是否使用了品牌别名
                                if operation_name == 'update':
                                    # 获取原始品牌和映射后的品牌
                                    # 使用正确的列名 '品牌' 而不是 'brand'
                                    original_brand_values = original_df.loc[original_df['id'] == record_id, '品牌'].values
                                    mapped_brand_values = original_df.loc[original_df['id'] == record_id, 'temp_brand'].values

                                    original_brand = original_brand_values[0] if len(original_brand_values) > 0 else ''
                                    mapped_brand = mapped_brand_values[0] if len(mapped_brand_values) > 0 else ''

                                    if original_brand != mapped_brand and mapped_brand in reverse_brand_mapping:
                                        alias_used = reverse_brand_mapping[mapped_brand]
                                        update_msg = f"update，使用{alias_used}上传成功"
                                    else:
                                        update_msg = "update"
                                else:
                                    update_msg = operation_name
                            else:
                                update_msg = 'unknown'

                            # 检查是否有品牌映射，并更新update_msg
                            if record_id in brand_mapping_info:
                                if update_msg == 'unknown':  # 如果还没有设置过更新信息
                                    mapped_brand = brand_mapping_info[record_id]
                                    update_msg = f"update，使用{mapped_brand}上传"

                            update_data.append((update_msg, record_id))

                    # 批量更新数据库
                    if update_data:
                        update_sql = f"""
                            UPDATE {table_name}
                            SET update_msg = %s
                            WHERE id = %s
                        """
                        db_manager.execute_many(update_sql, update_data)
                        print(f"[{company}] 已更新 {len(update_data)} 条记录到 {table_name}")

            except Exception as e:
                print(f"[{company}] 更新数据库时出错: {e}")
                import traceback
                traceback.print_exc()  # 打印详细错误信息
            finally:
                db_manager.close()

        return result
    
    start_time = time.time()

    # 加载品牌映射
    brand_mapping = load_crm_aliases_mapping()

    # 创建反向映射：从真实品牌名到别名
    reverse_brand_mapping = {v: k for k, v in brand_mapping.items()}

    # 预加载API数据（使用 fsbbr 的 token，假设这些数据对所有公司相同）
    token = login('fsbbr')
    ck_data = getAllCassWarehouse(token)
    gys_data = getAllSupplierChannel(token)

    # 定义要推送的所有公司及对应表
    companies = ['fsbbr', 'zhbbr', 'zsbbr', 'dgby', 'dghf']
    table_map = {
        'fsbbr': 'virtual_inventory',
        'zhbbr': 'virtual_inventory_zhbbr',
        'zsbbr': 'virtual_inventory_zsbbr',
        'dgby': 'virtual_inventory_dgby',
        'dghf': 'virtual_inventory_dghf'
    }

    # 循环推送到各公司
    for company in companies:
        company_start_time = time.time()
        table_name = table_map[company]

        print(f"\n{'='*60}")
        print(f"开始向 [{company}] 推送数据...")
        print(f"从表 [{table_name}] 读取数据")
        print(f"{'='*60}")

        # 从对应公司表查询数据
        db_manager = get_db_connection()
        try:
            if today_only:
                query = f"""
                    SELECT id, supplier_name, oe_code, brand, price, expiry_date, warehouse, stock, remark, update_msg
                    FROM {table_name}
                    WHERE DATE(fetch_time) = CURDATE()
                """
            else:
                query = f"""
                    SELECT id, supplier_name, oe_code, brand, price, expiry_date, warehouse, stock, remark, update_msg
                    FROM {table_name}
                """
            rows = db_manager.execute_query(query)
        except Exception as e:
            print(f"[{company}] 查询数据时出错: {e}")
            continue
        finally:
            db_manager.close()

        if not rows:
            print(f"[{company}] 没有数据需要上传")
            continue

        # 👇 新增: 黑名单过滤
        print(f"[{company}] 开始黑名单过滤...")
        from .inventory_tasks import filter_by_blacklist
        rows_before_filter = len(rows)
        rows = filter_by_blacklist(rows)
        rows_after_filter = len(rows)
        removed_count = rows_before_filter - rows_after_filter
        print(f"[{company}] 黑名单过滤完成: 原始 {rows_before_filter} 条, 剔除 {removed_count} 条, 剩余 {rows_after_filter} 条")

        if not rows:
            print(f"[{company}] 过滤后没有数据需要上传")
            continue

        print(f"[{company}] 准备上传 {len(rows)} 条{'当天' if today_only else '全部'}数据")

        # 构建DataFrame
        df = pd.DataFrame(rows, columns=['id', 'supplier_name', 'oe_code', 'brand', 'price', 'expiry_date', 'warehouse', 'stock', 'remark', 'update_msg'])

        # 记录原始品牌用于判断是否使用了别名
        original_brand_series = df['brand'].copy()

        # 向量化品牌映射
        df['temp_brand'] = df['brand'].map(brand_mapping).fillna(df['brand'])

        # 重命名列
        df = df.rename(columns={
            'supplier_name': '供应商名称',
            'oe_code': '原厂OE码',
            'brand': '品牌',
            'price': '价格',
            'expiry_date': '失效时间',
            'warehouse': '仓库名称',
            'stock': '库存',
            'remark': '备注',
            'update_msg': '更新信息'
        })

        # 使用映射后的品牌
        df['品牌'] = df['temp_brand']

        # 供应商名称映射（用于B2B上传时匹配，不改变数据库中的名称）
        supplier_mapping = {
            '广州昌盛': '昌盛',
            '佛山万拓': '万拓'
        }
        df['供应商名称_映射'] = df['供应商名称'].map(supplier_mapping).fillna(df['供应商名称'])

        # 在合并前保存原始品牌信息
        df_with_original = df.copy()
        df_with_original['original_brand'] = original_brand_series.values

        # 合并数据（使用映射后的供应商名称进行匹配）
        df_merged = pd.merge(df_with_original, ck_data, left_on='仓库名称', right_on='warehouse_name', how='inner')
        df_merged = pd.merge(df_merged, gys_data, left_on='供应商名称_映射', right_on='name', how='inner')

        if df_merged.empty:
            print(f"[{company}] 没有匹配的仓库或供应商数据，无法上传")
            continue

        # 重命名和筛选
        df_final = df_merged.rename(columns={'supplier_channel_id': 'supplier_channel_id', '原厂OE码': 'number', '品牌': 'brand_name',
                                '价格': 'price', 'cass_warehouse_id': 'cass_warehouse_id', '库存': 'stock',
                                '失效时间': 'lose_date', '备注': 'remark'})
        df_final = df_final[['id', 'supplier_channel_id', 'number', 'brand_name', 'price', 'cass_warehouse_id', 'stock', 'lose_date', 'remark', 'original_brand']]
        df_final = df_final.fillna('')

        # 分离ID和数据
        ids = df_final['id'].tolist()
        df_data = df_final.drop(columns=['id', 'original_brand'])
        records = df_data.to_dict(orient='records')

        # 优化filtered_rows构建，包含原始品牌信息
        id_to_row = {row['id']: row for row in df_merged.to_dict('records')}
        filtered_rows = [id_to_row[record_id] for record_id in ids if record_id in id_to_row]

        # 品牌映射信息记录
        brand_mapping_info = dict(df[df['品牌'] != df['temp_brand']].set_index('id')['temp_brand'])

        # 上传数据
        try:
            result = batchSave(records, filtered_rows, brand_mapping_info, reverse_brand_mapping, df_with_original, company)
            print(f"[{company}] 推送完成，耗时: {time.time() - company_start_time:.2f}s")
        except Exception as e:
            print(f"[{company}] 推送失败: {e}")
            import traceback
            traceback.print_exc()
            continue

    print(f"\n{'='*60}")
    print(f"所有公司推送完成，总耗时: {time.time() - start_time:.2f}s")
    print(f"{'='*60}")
    return result



def main_process():
    """主处理流程"""
    # 清除品牌缓存，确保每次运行都重新加载
    clear_brand_cache()
    
    # 预加载 crm_brand_list 品牌列表到缓存
    print("正在加载 crm_brand_list 品牌列表...")
    load_crm_brand_list()
    
    # 清理当前业务时间范围内的数据
    clean_business_time_data()
    
    # 清空其他表的数据（除了virtual_inventory表）
    clear_all_tables()
    
    # 删除50天前的数据
    delete_old_data()
    
    # 获取所有供应商数据
    sql_sever_data()  # 腾隆数据
    male_bier_start()  # 马勒贝尔数据
    gylqp_start()  # 爱车贝母数据
    fetch_and_process_latest_data()  # 机器人数据
    
    # 获取外部数据
    df2 = ggg2()
    
    # 获取昌盛库存数据
    try:
        print("\n" + "="*60)
        print("开始获取昌盛库存数据")
        print("="*60)
        changsheng_df = fetch_changsheng_data()
        if changsheng_df is not None and not changsheng_df.empty:
            save_supplier_to_virtual_inventory(changsheng_df, "昌盛")
            print(f"昌盛库存数据获取完成，共 {len(changsheng_df)} 条")
        else:
            print("昌盛库存数据为空")
        print("="*60)
    except Exception as e:
        print(f"获取昌盛库存数据失败: {e}")
        import traceback
        traceback.print_exc()

    # 获取佛山万拓库存数据
    try:
        print("\n" + "="*60)
        print("开始获取佛山万拓库存数据")
        print("="*60)
        wantuo_df = fetch_wantuo_data()
        if wantuo_df is not None and not wantuo_df.empty:
            save_supplier_to_virtual_inventory(wantuo_df, "佛山万拓")
            print(f"佛山万拓库存数据获取完成，共 {len(wantuo_df)} 条")
        else:
            print("佛山万拓库存数据为空")
        print("="*60)
    except Exception as e:
        print(f"获取佛山万拓库存数据失败: {e}")
        import traceback
        traceback.print_exc()

    # 读取所有数据并整合到虚拟库存表（已通过各模块自动添加）
    db_manager = get_db_connection()
    try:
        # 统计各公司表的数据量
        tables = [
            ('virtual_inventory', '佛山'),
            ('virtual_inventory_zhbbr', '珠海'),
            ('virtual_inventory_zsbbr', '中山'),
            ('virtual_inventory_dgby', '东莞巴友'),
            ('virtual_inventory_dghf', '东莞恒发')
        ]
        for table, name in tables:
            count = db_manager.execute_query(f"SELECT COUNT(*) FROM {table}")[0]['COUNT(*)']
            print(f"[{name}] 虚拟库存表处理了 {count} 条数据")
    finally:
        db_manager.close()
    
    # 上传到B2B系统（使用品牌映射版本），只上传当天数据
    start_b2b_upload_with_brand_mapping(today_only=True)
    
    # 运行CRM产品新建（数据库模式）
    print("\n" + "="*60)
    print("开始运行CRM产品新建（数据库模式）")
    print("="*60)
    try:
        from app.utils.crm_product.crm_productAdd.main import process_database_mode_api
        process_database_mode_api()
        print("="*60)
        print("CRM产品新建完成")
        print("="*60)
    except Exception as e:
        print(f"CRM产品新建失败: {e}")
        import traceback
        traceback.print_exc()

    # ===== 保存当日统计数据到日志 =====
    print("\n" + "="*60)
    print("开始保存当日统计数据")
    print("="*60)
    try:
        from app.services.virtual_inventory_stats_service import save_daily_statistics

        # 获取业务日期范围（当天00:00到23:59）
        current_time = datetime.now()
        business_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
        business_end = business_start.replace(hour=23, minute=59, second=59, microsecond=0)

        result = save_daily_statistics(business_start, business_end)
        if result['code'] == 0:
            print(f"[统计日志] 保存成功: {result['data']['business_date']}")
        else:
            print(f"[统计日志] 保存失败: {result['msg']}")
    except Exception as e:
        print(f"[统计日志] 保存时出错: {e}")
    print("="*60)


if __name__ == '__main__':
    main_process()