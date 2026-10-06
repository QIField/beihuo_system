# -*- coding: utf-8 -*-
"""
虚拟库存 B2B 上传模块

负责将各公司虚拟库存表的数据批量推送到 B2B 系统。
"""

import gc
import json
import decimal
import time
from datetime import datetime, date

import requests
import pandas as pd

from .database import get_db_connection
from .brands import load_crm_aliases_mapping
from ..inventory_tasks import filter_by_blacklist
from backend.virtual_inventory_api import get_update_status
from app.utils.logger_config import get_task_logger


logger = get_task_logger('virtual_inventory')


COMPANY_TABLE_MAP = {
    'fsbbr': 'virtual_inventory',
    'zhbbr': 'virtual_inventory_zhbbr',
    'zsbbr': 'virtual_inventory_zsbbr',
    # 'dgby': 'virtual_inventory_dgby',   # 东莞巴友：暂不参与定时上传
    # 'dghf': 'virtual_inventory_dghf'    # 东莞恒发：暂不参与定时上传
}

COMPANY_TOKEN_MAP = {
    'fsbbr': 'openapi_gzbbr_com_fs',
    'zhbbr': 'openapi_gzbbr_com_zh',
    'zsbbr': 'openapi_gzbbr_com_zs',
    # 'dgby': 'openapi_gzbbr_com_by',     # 东莞巴友：暂不参与定时上传
    # 'dghf': 'openapi_gzbbr_com_hf'      # 东莞恒发：暂不参与定时上传
}


def _convert_decimal_to_serializable(obj):
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: _convert_decimal_to_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [_convert_decimal_to_serializable(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(_convert_decimal_to_serializable(item) for item in obj)
    else:
        return obj


def _login(company):
    """从数据库获取 B2B token"""
    from config.config_list_manager.config_cache import get_config_value

    config_key = COMPANY_TOKEN_MAP.get(company)
    if not config_key:
        raise KeyError(f"未知的公司代码: {company}")

    # 添加重试机制，处理连接超时问题
    for attempt in range(3):
        try:
            token = get_config_value(config_key)
            if token:
                return token
            else:
                raise Exception(f"[{company}] 数据库中未找到 token")
        except Exception as e:
            if "Lost connection" in str(e) or "10060" in str(e):
                if attempt == 2:
                    raise Exception(f"[{company}] 获取token失败，数据库连接超时: {e}")
                logger.info(f"[{company}] 数据库连接超时，第{attempt + 1}次重试...")
                time.sleep(2)
            else:
                raise


def _get_all_cass_warehouse(token):
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


def _get_all_supplier_channel(token):
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


def _split_array_by_500_loop(arr):
    split_groups = []
    start = 0
    n = len(arr)
    while start < n:
        group = arr[start:start+500]
        split_groups.append(group)
        start += 500
    return split_groups


def _batch_save(records, original_rows, brand_mapping_info, reverse_brand_mapping, original_df, company='fsbbr', token=None):
    # 转换所有记录中的不可序列化类型为可序列化类型
    serializable_records = [_convert_decimal_to_serializable(record) for record in records]

    record_groups = _split_array_by_500_loop(serializable_records)
    original_row_groups = _split_array_by_500_loop(original_rows)
    total_groups = len(record_groups)

    # 预构造 id -> 品牌 / temp_brand 字典，避免后续在循环里对 DataFrame 做 O(N) 的 boolean 索引
    try:
        id_to_orig_brand = dict(zip(original_df['id'].tolist(), original_df['品牌'].tolist()))
        id_to_temp_brand = dict(zip(original_df['id'].tolist(), original_df['temp_brand'].tolist()))
    except Exception:
        id_to_orig_brand = {}
        id_to_temp_brand = {}

    for i, group in enumerate(record_groups):
        # 使用传入的token，不再重复获取
        if token is None:
            logger.info(f"[{company}] 未提供token，跳过批次 {i+1}")
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
                    logger.info(f'[{company}] 批次 {i+1} 连接超时，跳过此批次')
                    continue
                time.sleep(10)
            except requests.exceptions.ReadTimeout:
                if attempt == 2:
                    logger.info(f'[{company}] 批次 {i+1} 读取超时，跳过此批次')
                    continue
                time.sleep(10)
            except requests.exceptions.ConnectionError as e:
                if "Read timed out" in str(e):
                    if attempt == 2:
                        logger.info(f'[{company}] 批次 {i+1} 读取超时，跳过此批次')
                        continue
                    time.sleep(10)
                else:
                    if attempt == 2:
                        logger.info(f'[{company}] 批次 {i+1} 连接错误，跳过此批次')
                        continue
                    time.sleep(10)
            except Exception as e:
                if attempt == 2:
                    logger.info(f'[{company}] 批次 {i+1} 发生未知错误，跳过此批次')
                    continue
                time.sleep(10)

        if response is None:
            logger.info(f"[{company}] 批次 {i+1} 响应为空，跳过")
            continue

        try:
            result = json.loads(response.text)
        except json.JSONDecodeError:
            logger.info(f'[{company}] 批次 {i+1} 响应不是有效的JSON格式')
            continue
        except Exception as e:
            logger.exception(f'[{company}] 批次 {i+1} 解析响应时发生错误')
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

                logger.info(f'[{company}] 批次 {i+1}/{total_groups}: 成功上传 {result["data"]["succes_num"]} 条, 失败 {result["data"]["error_num"]} 条')

                table_name = COMPANY_TABLE_MAP.get(company, 'virtual_inventory')

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
                                # 使用预构造的字典做 O(1) 查询，避免对 DataFrame 做 boolean 索引
                                original_brand = id_to_orig_brand.get(record_id, '')
                                mapped_brand = id_to_temp_brand.get(record_id, '')

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

                        update_data.append((update_msg, get_update_status(update_msg), record_id))

                # 批量更新数据库
                if update_data:
                    update_sql = f"""
                        UPDATE {table_name}
                        SET update_msg = %s, update_status = %s
                        WHERE id = %s
                    """
                    db_manager.execute_many(update_sql, update_data)
                    logger.info(f"[{company}] 已更新 {len(update_data)} 条记录到 {table_name}")

        except Exception as e:
            logger.exception(f"[{company}] 更新数据库时出错")
        finally:
            db_manager.close()

    return result


def start_b2b_upload_with_brand_mapping(today_only=False, companies=None):
    """
    上传数据到B2B系统，包含品牌映射和价格处理逻辑（优化版）
    today_only: 是否只上传今天的数据
    companies: 要推送的公司列表，默认全部
    """
    start_time = time.time()
    result = None  # 兼容函数末尾 return result：即使所有公司都跳过也不会抛 NameError

    # 加载品牌映射
    brand_mapping = load_crm_aliases_mapping()

    # 创建反向映射：从真实品牌名到别名
    reverse_brand_mapping = {v: k for k, v in brand_mapping.items()}

    # 定义要推送的公司
    if companies is None:
        companies = list(COMPANY_TABLE_MAP.keys())

    # 一次性获取所有公司的 token
    logger.info("\n" + "="*60)
    logger.info("开始预获取所有公司 token...")
    logger.info("="*60)
    company_tokens = {}
    for company in companies:
        try:
            token = _login(company)
            if token:
                company_tokens[company] = token
                logger.info(f"[{company}] 成功获取 token")
            else:
                logger.error(f"[{company}] 获取 token 失败: 返回空值")
                company_tokens[company] = None
        except Exception as e:
            logger.exception(f"[{company}] 获取 token 失败")
            company_tokens[company] = None
    logger.info("="*60)

    # 循环推送到各公司
    for company in companies:
        # 检查是否有可用 token
        if not company_tokens.get(company):
            logger.info(f"\n[{company}] 没有可用 token，跳过")
            continue
        company_start_time = time.time()
        table_name = COMPANY_TABLE_MAP[company]

        logger.info(f"\n{'='*60}")
        logger.info(f"开始向 [{company}] 推送数据...")
        logger.info(f"从表 [{table_name}] 读取数据")
        logger.info(f"{'='*60}")

        # 使用预获取的token
        token = company_tokens[company]
        logger.info(f"[{company}] 使用预获取的token...")

        ck_data = _get_all_cass_warehouse(token)
        if ck_data is None or ck_data.empty:
            logger.error(f"[{company}] 获取仓库数据失败，跳过")
            continue

        gys_data = _get_all_supplier_channel(token)
        if gys_data is None or gys_data.empty:
            logger.error(f"[{company}] 获取供应商数据失败，跳过")
            continue

        logger.info(f"[{company}] 成功获取token和仓库/供应商数据")

        # ========== 游标分页处理（按 id 升序逐页拉取并上传，避免一次性把全表数据装入内存导致 OOM） ==========
        PAGE_SIZE = 5000  # 单页拉取行数，过小会增加 SQL 次数，过大会失去内存优化效果

        # 1) 先查 id 范围 + 总数（一次轻量 SQL），锁定上界，避免上传期间漏读未来插入
        db_manager = get_db_connection()
        try:
            if today_only:
                range_sql = f"""
                    SELECT MIN(id) AS min_id, MAX(id) AS max_id, COUNT(*) AS cnt
                    FROM {table_name}
                    WHERE DATE(fetch_time) = CURDATE()
                """
            else:
                range_sql = f"""
                    SELECT MIN(id) AS min_id, MAX(id) AS max_id, COUNT(*) AS cnt
                    FROM {table_name}
                """
            range_rows = db_manager.execute_query(range_sql)
        except Exception as e:
            logger.exception(f"[{company}] 查询 id 范围失败")
            db_manager.close()
            continue
        finally:
            try:
                db_manager.close()
            except Exception:
                pass

        if not range_rows or range_rows[0].get('cnt') in (None, 0) or range_rows[0].get('max_id') is None:
            logger.info(f"[{company}] 没有数据需要上传")
            continue

        min_id = range_rows[0]['min_id']
        max_id_lock = range_rows[0]['max_id']
        total_count = range_rows[0]['cnt']
        logger.info(f"[{company}] 待上传 {total_count} 条，id 范围 [{min_id}, {max_id_lock}]，分页大小 {PAGE_SIZE}")

        # 2) 游标分页：用 WHERE id > last_id AND id <= max_id_lock 的 keyset pagination
        #    - 主键索引扫描，毫秒级
        #    - 不依赖 id 是否连续，空洞自动跳过
        #    - 不重复、不遗漏
        last_id = (min_id - 1) if min_id is not None else 0
        page_no = 0
        processed_total = 0
        result = None  # 保留最后一页的 result 用于函数返回值兼容

        while True:
            page_no += 1
            page_start_time = time.time()

            # 拉取一页
            db_manager = get_db_connection()
            try:
                if today_only:
                    page_sql = f"""
                        SELECT id, supplier_name, oe_code, brand, price, expiry_date,
                               warehouse, stock, remark, update_msg, upload_supplier_name
                        FROM {table_name}
                        WHERE id > %s AND id <= %s
                          AND DATE(fetch_time) = CURDATE()
                        ORDER BY id ASC
                        LIMIT %s
                    """
                else:
                    page_sql = f"""
                        SELECT id, supplier_name, oe_code, brand, price, expiry_date,
                               warehouse, stock, remark, update_msg, upload_supplier_name
                        FROM {table_name}
                        WHERE id > %s AND id <= %s
                        ORDER BY id ASC
                        LIMIT %s
                    """
                rows = db_manager.execute_query(page_sql, (last_id, max_id_lock, PAGE_SIZE))
            except Exception as e:
                logger.exception(f"[{company}] 页 {page_no} 查询失败")
                rows = None
            finally:
                try:
                    db_manager.close()
                except Exception:
                    pass

            if not rows:
                break

            # 推进游标
            last_id = rows[-1]['id']
            page_row_count = len(rows)

            # ---------- 单页内独立完成：黑名单过滤 → 菲尔过滤 → DataFrame → merge → 上传 → 回写 ----------
            try:
                # 黑名单过滤
                rows_before_filter = len(rows)
                rows = filter_by_blacklist(rows)
                removed_count = rows_before_filter - len(rows)
                if removed_count > 0:
                    logger.info(f"[{company}] 页 {page_no} 黑名单剔除 {removed_count} 条")

                # 非佛山公司过滤掉菲尔品牌
                if company != 'fsbbr':
                    rows_before_feier = len(rows)
                    rows = [row for row in rows if row.get('brand') != '菲尔']
                    feier_removed = rows_before_feier - len(rows)
                    if feier_removed > 0:
                        logger.info(f"[{company}] 页 {page_no} 菲尔品牌剔除 {feier_removed} 条")

                # 过滤沐博/宝翼隆的指定品牌数据
                rows_before_special = len(rows)
                rows = [
                    row for row in rows
                    if not (row.get('supplier_name') in ('沐博', '宝翼隆') and row.get('brand') in ('菲比', 'FEBI', '费比'))
                ]
                special_removed = rows_before_special - len(rows)
                if special_removed > 0:
                    logger.info(f"[{company}] 页 {page_no} 沐博/宝翼隆菲比/FEBI/费比品牌剔除 {special_removed} 条")

                if not rows:
                    logger.info(f"[{company}] 页 {page_no} 过滤后无数据，跳过")
                    processed_total += page_row_count
                    continue

                # 构建 DataFrame
                df = pd.DataFrame(rows, columns=['id', 'supplier_name', 'oe_code', 'brand', 'price', 'expiry_date',
                                                 'warehouse', 'stock', 'remark', 'update_msg', 'upload_supplier_name'])

                # 记录原始品牌（用于判断是否使用了别名）
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
                    'update_msg': '更新信息',
                    'upload_supplier_name': '上传供应商名称'
                })

                # 使用映射后的品牌
                df['品牌'] = df['temp_brand']

                # 上传供应商名称（NULL 回退到 supplier_name）
                df['供应商名称_映射'] = df['上传供应商名称'].fillna(df['供应商名称'])
                df['供应商名称_映射'] = df['供应商名称_映射'].astype(str).str.strip()

                # 直接在 df 上添加 original_brand 列（不再 df.copy() 节省内存）
                df['original_brand'] = original_brand_series.values

                # 合并仓库 / 供应商映射
                df_merged = pd.merge(df, ck_data, left_on='仓库名称', right_on='warehouse_name', how='inner')
                df_merged = pd.merge(df_merged, gys_data, left_on='供应商名称_映射', right_on='name', how='inner')

                if df_merged.empty:
                    logger.info(f"[{company}] 页 {page_no} 没有匹配的仓库或供应商数据，跳过")
                    processed_total += page_row_count
                    # 释放
                    del df, df_merged, rows, original_brand_series
                    gc.collect()
                    continue

                # 重命名和筛选上传需要的列
                df_final = df_merged.rename(columns={
                    'supplier_channel_id': 'supplier_channel_id', '原厂OE码': 'number', '品牌': 'brand_name',
                    '价格': 'price', 'cass_warehouse_id': 'cass_warehouse_id', '库存': 'stock',
                    '失效时间': 'lose_date', '备注': 'remark'
                })
                df_final = df_final[['id', 'supplier_channel_id', 'number', 'brand_name', 'price',
                                     'cass_warehouse_id', 'stock', 'lose_date', 'remark', 'original_brand']]
                df_final = df_final.fillna('')

                # 分离 ID 和上传数据
                ids = df_final['id'].tolist()
                df_data = df_final.drop(columns=['id', 'original_brand'])
                records = df_data.to_dict(orient='records')

                # 构建 id -> 合并后行的字典（用于 batchSave 内部回写 update_msg 时确定记录 id）
                id_to_row = {row_dict['id']: row_dict for row_dict in df_merged.to_dict('records')}
                filtered_rows = [id_to_row[record_id] for record_id in ids if record_id in id_to_row]

                # 品牌映射信息（用于 batchSave 内部识别使用了别名的记录）
                brand_mapping_info = dict(df[df['品牌'] != df['temp_brand']].set_index('id')['temp_brand'])

                # 调用批量上传（内部仍按 500 条/批分组）
                result = _batch_save(records, filtered_rows, brand_mapping_info, reverse_brand_mapping, df, company, token=token)

                processed_total += page_row_count
                logger.info(f"[{company}] 页 {page_no} 完成（本页 {page_row_count} 条，累计 {processed_total}/{total_count}），耗时 {time.time() - page_start_time:.2f}s")

                # 显式释放本页对象
                del df, df_merged, df_final, df_data, records, filtered_rows, id_to_row
                del ids, brand_mapping_info, original_brand_series, rows
                gc.collect()

            except Exception as e:
                logger.exception(f"[{company}] 页 {page_no} 处理异常，跳过本页")
                # 异常时也要释放可能存在的局部变量
                try:
                    del df, df_merged, df_final, df_data, records, filtered_rows, id_to_row
                    del ids, brand_mapping_info, original_brand_series, rows
                except Exception:
                    pass
                gc.collect()
                continue

        logger.info(f"[{company}] 推送完成：应处理 {total_count} 条，累计扫描 {processed_total} 条，耗时 {time.time() - company_start_time:.2f}s")

    logger.info(f"\n{'='*60}")
    logger.info(f"所有公司推送完成，总耗时: {time.time() - start_time:.2f}s")
    logger.info(f"{'='*60}")
    return result
