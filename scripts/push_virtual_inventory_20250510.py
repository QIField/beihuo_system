#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
虚拟库存推送脚本 - 2026.5.11数据
功能：
1. 对2026.5.11的数据进行虚拟库存推送
2. 五个组织并行推送（最大3线程，剩余排队）
3. 推送后直接更新数据库的update_msg状态
4. 不调用新建产品功能
"""

import json
import pandas as pd
import requests
import pymysql
import decimal
import time
import threading
from datetime import datetime, date, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue

# 数据库配置
DB_CONFIG = {
    'host': '113.45.176.129',
    'port': 3306,
    'user': 'fsbbr_data',
    'password': 'wRCA8AGn3a568f4X',
    'database': 'fsbbr_data',
    'charset': 'utf8mb4'
}

# 公司配置
COMPANIES = ['fsbbr', 'zhbbr', 'zsbbr', 'dgby', 'dghf']
TABLE_MAP = {
    'fsbbr': 'virtual_inventory',
    'zhbbr': 'virtual_inventory_zhbbr',
    'zsbbr': 'virtual_inventory_zsbbr',
    'dgby': 'virtual_inventory_dgby',
    'dghf': 'virtual_inventory_dghf'
}

# API配置
API_CONFIG = {
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


class DatabaseManager:
    """数据库管理器"""
    def __init__(self):
        self.connection = None
        self.connect()

    def connect(self):
        """建立数据库连接"""
        try:
            self.connection = pymysql.connect(**DB_CONFIG)
            return True
        except Exception as e:
            print(f"数据库连接失败: {e}")
            return False

    def ensure_connection(self):
        """确保数据库连接可用"""
        try:
            self.connection.ping(reconnect=True)
            return True
        except Exception:
            return self.connect()

    def execute_query(self, query, params=None):
        """执行查询"""
        self.ensure_connection()
        with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()

    def execute_update(self, query, params=None):
        """执行更新"""
        self.ensure_connection()
        with self.connection.cursor() as cursor:
            cursor.execute(query, params)
            self.connection.commit()
            return cursor.rowcount

    def execute_many(self, query, data):
        """批量执行"""
        self.ensure_connection()
        with self.connection.cursor() as cursor:
            cursor.executemany(query, data)
            self.connection.commit()
            return cursor.rowcount

    def close(self):
        """关闭连接"""
        if self.connection:
            self.connection.close()


def get_db_connection():
    """获取数据库连接"""
    return DatabaseManager()


def convert_decimal_to_serializable(obj):
    """转换Decimal为可序列化类型"""
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
    """登录获取token"""
    url = "https://openapi.gzbbr.com/login/index"
    data = API_CONFIG[company]
    
    for attempt in range(3):
        try:
            response = requests.post(url, data=data, timeout=(10, 30))
            result = json.loads(response.text)
            return result['data']['token']
        except requests.exceptions.ConnectTimeout:
            if attempt == 2:
                raise
            time.sleep(5)
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(5)
    return None


def get_all_cass_warehouse(token):
    """获取仓库列表"""
    url = "https://openapi.gzbbr.com/Product.Quote/getAllCassWarehouse"
    headers = {'token': token}
    for attempt in range(3):
        try:
            response = requests.get(url, headers=headers, timeout=(10, 30))
            result = json.loads(response.text)
            df = pd.DataFrame(result['data'])
            if 'warehouse_no' in df.columns:
                del df['warehouse_no']
            return df
        except requests.exceptions.ConnectTimeout:
            if attempt == 2:
                raise
            time.sleep(5)
    return None


def get_all_supplier_channel(token):
    """获取供应商渠道列表"""
    url = "https://openapi.gzbbr.com/Product.Quote/getAllSupplierChannel"
    headers = {'token': token}
    for attempt in range(3):
        try:
            response = requests.get(url, headers=headers, timeout=(10, 30))
            result = json.loads(response.text)
            df = pd.DataFrame(result['data'])
            if 'byname' in df.columns:
                del df['byname']
            return df
        except requests.exceptions.ConnectTimeout:
            if attempt == 2:
                raise
            time.sleep(5)
    return None


def split_array_by_500(arr):
    """将数组按500分割"""
    groups = []
    start = 0
    n = len(arr)
    while start < n:
        group = arr[start:start+500]
        groups.append(group)
        start += 500
    return groups


def batch_save_to_api(records, company, table_name, original_rows):
    """
    批量保存到API并更新数据库状态
    """
    if not records:
        return {'success': True, 'msg': '没有数据需要上传'}

    # 转换记录为可序列化类型
    serializable_records = [convert_decimal_to_serializable(record) for record in records]
    record_groups = split_array_by_500(serializable_records)
    original_row_groups = split_array_by_500(original_rows)

    total_success = 0
    total_error = 0
    db_manager = get_db_connection()

    try:
        for i, group in enumerate(record_groups):
            # 获取token
            token = None
            for attempt in range(3):
                try:
                    token = login(company)
                    break
                except Exception as e:
                    if attempt == 2:
                        print(f'[{company}] 批次 {i+1} 获取token失败: {e}')
                        continue
                    time.sleep(5)

            if token is None:
                print(f"[{company}] 批次 {i+1} 无法获取token，跳过")
                continue

            # 发送请求
            url = "https://openapi.gzbbr.com/Product.Quote/batchSave"
            payload = json.dumps({"params": group})
            headers = {
                'token': token,
                'Content-Type': 'application/json'
            }

            response = None
            for attempt in range(3):
                try:
                    response = requests.post(url, headers=headers, data=payload, timeout=(15, 180))
                    break
                except requests.exceptions.Timeout:
                    if attempt == 2:
                        print(f'[{company}] 批次 {i+1} 超时')
                        continue
                    time.sleep(10)
                except Exception as e:
                    if attempt == 2:
                        print(f'[{company}] 批次 {i+1} 请求失败: {e}')
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

            # 更新数据库状态
            if 'data' in result and 'succes_data' in result['data'] and 'error_data' in result['data']:
                succes_data = result['data']['succes_data'] if result['data']['succes_data'] else []
                error_data = result['data']['error_data'] if result['data']['error_data'] else []

                total_success += len(succes_data)
                total_error += len(error_data)

                # 合并结果并按no排序
                all_results = succes_data + error_data
                all_results.sort(key=lambda x: x['no'])

                print(f'[{company}] 批次 {i+1}/{len(record_groups)}: 成功 {len(succes_data)} 条, 失败 {len(error_data)} 条')

                # 准备更新数据
                update_data = []
                original_group = original_row_groups[i] if i < len(original_row_groups) else []

                for j, result_item in enumerate(all_results):
                    if j < len(original_group):
                        original_row = original_group[j]
                        record_id = original_row['id'] if isinstance(original_row, dict) else original_row[0]

                        # 确定更新消息
                        if 'error_msg' in result_item and result_item['error_msg']:
                            update_msg = result_item['error_msg']
                        elif 'operation_name' in result_item:
                            update_msg = result_item['operation_name']
                        else:
                            update_msg = 'unknown'

                        update_data.append((update_msg, record_id))

                # 批量更新数据库
                if update_data:
                    update_sql = f"""
                        UPDATE {table_name}
                        SET update_msg = %s
                        WHERE id = %s
                    """
                    try:
                        db_manager.execute_many(update_sql, update_data)
                        print(f"[{company}] 已更新 {len(update_data)} 条记录状态")
                    except Exception as e:
                        print(f"[{company}] 更新数据库时出错: {e}")

    except Exception as e:
        print(f"[{company}] batch_save_to_api 出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db_manager.close()

    return {
        'success': True,
        'total_success': total_success,
        'total_error': total_error
    }


def load_crm_aliases_mapping():
    """加载CRM品牌别名映射"""
    try:
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        excel_path = os.path.join(project_root, "static", "excel", "crm可用别名.xlsx")

        if not os.path.exists(excel_path):
            print(f"警告: 未找到 {excel_path} 文件")
            return {}

        df = pd.read_excel(excel_path, dtype=str)
        brand_mapping = {}

        for _, row in df.iterrows():
            pp_name = row['pp_name']
            pp_names_str = str(row['pp_names']) if pd.notna(row['pp_names']) else ""
            possible_names = [name.strip() for name in pp_names_str.split(',')]
            for name in possible_names:
                if name and name != "-":
                    brand_mapping[name] = pp_name

        print(f"加载了 {len(brand_mapping)} 个品牌别名映射")
        return brand_mapping
    except Exception as e:
        print(f"读取CRM可用别名文件时出错: {e}")
        return {}


def get_blacklist():
    """获取黑名单"""
    try:
        db_manager = get_db_connection()
        sql = "SELECT supplier_name, oe_code, brand FROM virtual_inventory_blacklist"
        rows = db_manager.execute_query(sql)
        db_manager.close()
        # 转换为集合以便快速查找
        blacklist_set = set()
        for row in rows:
            key = (row['supplier_name'], row['oe_code'], row['brand'])
            blacklist_set.add(key)
        return blacklist_set
    except Exception as e:
        print(f"获取黑名单失败: {e}")
        return set()


def push_company_inventory(company, target_date='2026-05-10'):
    """
    推送指定公司的虚拟库存数据
    """
    print(f"\n{'='*60}")
    print(f"开始推送 [{company}] 的 {target_date} 数据")
    print(f"{'='*60}")

    start_time = time.time()
    table_name = TABLE_MAP[company]

    # 获取token和仓库/供应商数据
    try:
        print(f"[{company}] 正在获取token...")
        token = login(company)
        if not token:
            print(f"[{company}] 获取token失败")
            return {'success': False, 'msg': '获取token失败'}

        print(f"[{company}] 正在获取仓库和供应商数据...")
        ck_data = get_all_cass_warehouse(token)
        gys_data = get_all_supplier_channel(token)

        if ck_data is None or ck_data.empty:
            print(f"[{company}] 获取仓库数据失败")
            return {'success': False, 'msg': '获取仓库数据失败'}

        if gys_data is None or gys_data.empty:
            print(f"[{company}] 获取供应商数据失败")
            return {'success': False, 'msg': '获取供应商数据失败'}

    except Exception as e:
        print(f"[{company}] 初始化失败: {e}")
        return {'success': False, 'msg': f'初始化失败: {e}'}

    # 查询指定日期的数据
    db_manager = get_db_connection()
    try:
        query = f"""
            SELECT id, supplier_name, oe_code, brand, price, expiry_date, warehouse, stock, remark, update_msg, upload_supplier_name
            FROM {table_name}
            WHERE DATE(fetch_time) = %s
        """
        rows = db_manager.execute_query(query, (target_date,))
    except Exception as e:
        print(f"[{company}] 查询数据时出错: {e}")
        db_manager.close()
        return {'success': False, 'msg': f'查询数据失败: {e}'}
    finally:
        db_manager.close()

    if not rows:
        print(f"[{company}] {target_date} 没有数据需要上传")
        return {'success': True, 'msg': '没有数据需要上传', 'count': 0}

    print(f"[{company}] 查询到 {len(rows)} 条数据")

    # 黑名单过滤
    blacklist = get_blacklist()
    rows_before = len(rows)
    rows = [row for row in rows if (row['supplier_name'], row['oe_code'], row['brand']) not in blacklist]
    removed_count = rows_before - len(rows)
    if removed_count > 0:
        print(f"[{company}] 黑名单过滤: 剔除 {removed_count} 条, 剩余 {len(rows)} 条")

    # 非佛山公司过滤菲尔品牌
    if company != 'fsbbr':
        rows_before = len(rows)
        rows = [row for row in rows if row.get('brand') != '菲尔']
        feier_removed = rows_before - len(rows)
        if feier_removed > 0:
            print(f"[{company}] 菲尔品牌过滤: 剔除 {feier_removed} 条, 剩余 {len(rows)} 条")

    if not rows:
        print(f"[{company}] 过滤后没有数据需要上传")
        return {'success': True, 'msg': '过滤后没有数据需要上传', 'count': 0}

    # 加载品牌映射
    brand_mapping = load_crm_aliases_mapping()

    # 构建DataFrame
    df = pd.DataFrame(rows)
    original_brand_series = df['brand'].copy()

    # 品牌映射
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
        'update_msg': '更新信息',
        'upload_supplier_name': '上传供应商名称'
    })

    # 使用映射后的品牌
    df['品牌'] = df['temp_brand']

    # 处理供应商名称
    df['供应商名称_映射'] = df['上传供应商名称'].fillna(df['供应商名称'])
    df['供应商名称_映射'] = df['供应商名称_映射'].astype(str).str.strip()

    # 保存原始品牌信息
    df_with_original = df.copy()
    df_with_original['original_brand'] = original_brand_series.values

    # 合并仓库和供应商数据
    df_merged = pd.merge(df_with_original, ck_data, left_on='仓库名称', right_on='warehouse_name', how='inner')
    df_merged = pd.merge(df_merged, gys_data, left_on='供应商名称_映射', right_on='name', how='inner')

    if df_merged.empty:
        print(f"[{company}] 没有匹配的仓库或供应商数据，无法上传")
        return {'success': False, 'msg': '没有匹配的仓库或供应商数据'}

    # 准备上传数据
    df_final = df_merged.rename(columns={
        'supplier_channel_id': 'supplier_channel_id',
        '原厂OE码': 'number',
        '品牌': 'brand_name',
        '价格': 'price',
        'cass_warehouse_id': 'cass_warehouse_id',
        '库存': 'stock',
        '失效时间': 'lose_date',
        '备注': 'remark'
    })

    df_final = df_final[['id', 'supplier_channel_id', 'number', 'brand_name', 'price', 
                         'cass_warehouse_id', 'stock', 'lose_date', 'remark', 'original_brand']]
    df_final = df_final.fillna('')

    # 分离ID和数据
    ids = df_final['id'].tolist()
    df_data = df_final.drop(columns=['id', 'original_brand'])
    records = df_data.to_dict(orient='records')

    # 构建原始行数据（用于更新数据库）
    id_to_row = {row['id']: row for row in df_merged.to_dict('records')}
    filtered_rows = [id_to_row[record_id] for record_id in ids if record_id in id_to_row]

    print(f"[{company}] 准备上传 {len(records)} 条数据")

    # 上传到API并更新数据库
    result = batch_save_to_api(records, company, table_name, filtered_rows)

    elapsed_time = time.time() - start_time
    print(f"[{company}] 推送完成，耗时: {elapsed_time:.2f}s")
    print(f"[{company}] 结果: 成功 {result.get('total_success', 0)} 条, 失败 {result.get('total_error', 0)} 条")

    return {
        'success': True,
        'company': company,
        'count': len(records),
        'success_count': result.get('total_success', 0),
        'error_count': result.get('total_error', 0),
        'elapsed_time': elapsed_time
    }


class PushWorker:
    """推送工作器，用于控制并发"""
    def __init__(self, max_workers=3):
        self.max_workers = max_workers
        self.queue = Queue()
        self.results = {}
        self.lock = threading.Lock()

    def add_task(self, company, target_date):
        """添加任务到队列"""
        self.queue.put((company, target_date))

    def worker(self):
        """工作线程"""
        while True:
            try:
                company, target_date = self.queue.get(timeout=1)
                if company is None:  # 结束信号
                    break

                print(f"\n[队列] 开始处理 [{company}]，剩余队列长度: {self.queue.qsize()}")

                try:
                    result = push_company_inventory(company, target_date)
                    with self.lock:
                        self.results[company] = result
                except Exception as e:
                    print(f"[{company}] 推送失败: {e}")
                    import traceback
                    traceback.print_exc()
                    with self.lock:
                        self.results[company] = {'success': False, 'error': str(e)}

                self.queue.task_done()

            except Exception as e:
                break

    def run(self, target_date='2026-05-11'):
        """运行推送任务"""
        print(f"\n{'='*60}")
        print(f"开始推送 2026.5.11 虚拟库存数据")
        print(f"最大并发数: {self.max_workers}")
        print(f"{'='*60}\n")

        # 添加所有任务到队列
        for company in COMPANIES:
            self.add_task(company, target_date)

        # 创建工作线程
        threads = []
        for i in range(self.max_workers):
            t = threading.Thread(target=self.worker)
            t.daemon = True
            t.start()
            threads.append(t)

        # 等待所有任务完成
        self.queue.join()

        # 发送结束信号
        for _ in range(self.max_workers):
            self.queue.put((None, None))

        # 等待线程结束
        for t in threads:
            t.join(timeout=5)

        return self.results


def main():
    """主函数"""
    start_time = time.time()

    print("="*60)
    print("虚拟库存推送脚本 - 2026.5.11数据")
    print("="*60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    # 创建推送工作器（最大3线程）
    worker = PushWorker(max_workers=3)
    results = worker.run(target_date='2026-05-11')

    # 打印汇总结果
    print("\n" + "="*60)
    print("推送结果汇总")
    print("="*60)

    total_count = 0
    total_success = 0
    total_error = 0

    for company in COMPANIES:
        result = results.get(company, {})
        if result.get('success'):
            count = result.get('count', 0)
            success = result.get('success_count', 0)
            error = result.get('error_count', 0)
            elapsed = result.get('elapsed_time', 0)

            total_count += count
            total_success += success
            total_error += error

            print(f"[{company}] 数据: {count} 条 | 成功: {success} 条 | 失败: {error} 条 | 耗时: {elapsed:.2f}s")
        else:
            print(f"[{company}] 推送失败: {result.get('error', '未知错误')}")

    total_time = time.time() - start_time
    print("="*60)
    print(f"总计: 数据 {total_count} 条 | 成功 {total_success} 条 | 失败 {total_error} 条")
    print(f"总耗时: {total_time:.2f}s")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)


if __name__ == '__main__':
    main()
