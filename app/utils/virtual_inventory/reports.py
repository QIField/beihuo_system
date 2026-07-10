# -*- coding: utf-8 -*-
"""
虚拟库存统计报表与推送模块

负责：
- 生成当天与昨天的虚拟库存对比 Excel
- 统计各供应商当天爬取量
- 组装并推送微信汇报消息
"""

import os
from datetime import datetime, timedelta

import pandas as pd

from .database import get_db_connection, get_business_time_range
from ..common_util_module.server_push import message_push
from app.routes.excel_download import DOWNLOAD_BASE_URL
from app.utils.logger_config import get_task_logger


logger = get_task_logger('virtual_inventory')


# 佛山总部表固定统计的 18 个供应商
FSBBR_SUPPLIER_NAMES = [
    '东莞佳配', '佛山万拓', '佛山巴博瑞', '佛山德孚', '佛山新奔裕汽配',
    '佳配', '宝翼隆', '广州佳配', '广州德之宝', '广州日昇',
    '广州昌盛', '广州犇宝', '广星', '沐博', '爱车贝母',
    '腾隆', '鑫峰', '盛旻'
]


def generate_virtual_inventory_compare_excel(business_date):
    """生成当天与昨天的虚拟库存对比Excel，返回下载URL"""
    # 与 excel_download.py 保持一致：使用相对路径，基于 Flask 启动目录
    export_dir = os.path.join('static', 'exports')
    os.makedirs(export_dir, exist_ok=True)

    today = datetime.strptime(business_date, '%Y-%m-%d').date()
    yesterday = today - timedelta(days=1)
    date_str = today.strftime('%Y%m%d')

    ranges = {
        'today': (
            datetime.combine(today, datetime.min.time()),
            datetime.combine(today, datetime.max.time().replace(microsecond=0))
        ),
        'yesterday': (
            datetime.combine(yesterday, datetime.min.time()),
            datetime.combine(yesterday, datetime.max.time().replace(microsecond=0))
        )
    }

    key_cols = ['supplier_name', 'oe_code', 'brand', 'warehouse']
    select_cols = key_cols + ['price', 'stock', 'remark']

    sql = f"""
        SELECT {', '.join(select_cols)}
        FROM virtual_inventory
        WHERE fetch_time >= %s AND fetch_time <= %s
    """

    db_manager = get_db_connection()
    try:
        today_rows = db_manager.execute_query(sql, ranges['today'])
        yesterday_rows = db_manager.execute_query(sql, ranges['yesterday'])
    finally:
        db_manager.close()

    df_today = pd.DataFrame(today_rows)[select_cols].drop_duplicates(subset=key_cols)
    df_yesterday = pd.DataFrame(yesterday_rows)[select_cols].drop_duplicates(subset=key_cols)

    for df in (df_today, df_yesterday):
        df['price'] = pd.to_numeric(df['price'], errors='coerce')
        df['stock'] = pd.to_numeric(df['stock'], errors='coerce').fillna(0).astype(int)

    # 新增OE
    merged_new = df_today.merge(df_yesterday[key_cols], on=key_cols, how='left', indicator=True)
    df_new = merged_new[merged_new['_merge'] == 'left_only'][select_cols].copy()
    df_new.rename(columns={
        'supplier_name': '供应商名称', 'oe_code': 'OE码', 'brand': '品牌',
        'price': '价格', 'stock': '库存', 'warehouse': '仓库', 'remark': '备注'
    }, inplace=True)

    # 价格变化
    df_price = df_today.merge(df_yesterday, on=key_cols, how='inner', suffixes=('_今天', '_昨天'))
    df_price = df_price[df_price['price_今天'] != df_price['price_昨天']].copy()
    df_price['变化量'] = df_price['price_今天'] - df_price['price_昨天']
    df_price = df_price[key_cols + ['price_昨天', 'price_今天', '变化量', 'remark_今天']]
    df_price.rename(columns={
        'supplier_name': '供应商名称', 'oe_code': 'OE码', 'brand': '品牌', 'warehouse': '仓库',
        'price_昨天': '昨天价格', 'price_今天': '今天价格', 'remark_今天': '备注'
    }, inplace=True)

    # 库存变化
    df_stock = df_today.merge(df_yesterday, on=key_cols, how='inner', suffixes=('_今天', '_昨天'))
    df_stock = df_stock[df_stock['stock_今天'] != df_stock['stock_昨天']].copy()
    df_stock['变化量'] = df_stock['stock_今天'] - df_stock['stock_昨天']
    df_stock = df_stock[key_cols + ['stock_昨天', 'stock_今天', '变化量', 'remark_今天']]
    df_stock.rename(columns={
        'supplier_name': '供应商名称', 'oe_code': 'OE码', 'brand': '品牌', 'warehouse': '仓库',
        'stock_昨天': '昨天库存', 'stock_今天': '今天库存', 'remark_今天': '备注'
    }, inplace=True)

    filename = f"virtual_inventory_compare_fsbbr_{date_str}.xlsx"
    filepath = os.path.join(export_dir, filename)

    with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
        df_new.to_excel(writer, sheet_name='新增OE', index=False)
        df_price.to_excel(writer, sheet_name='价格变化', index=False)
        df_stock.to_excel(writer, sheet_name='库存变化', index=False)

    # 清理7天前的旧文件
    for f in os.listdir(export_dir):
        fpath = os.path.join(export_dir, f)
        if os.path.isfile(fpath) and f.startswith('virtual_inventory_compare_fsbbr_'):
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
            if (datetime.now() - mtime).days > 7:
                try:
                    os.remove(fpath)
                except Exception:
                    pass

    return f"{DOWNLOAD_BASE_URL}/web/download_excel/virtual_inventory_compare/fsbbr/{date_str}"


def _build_supplier_summary_lines():
    """统计佛山总部表当天 18 个固定供应商的爬取总量，返回消息行列表"""
    placeholders = ','.join(['%s'] * len(FSBBR_SUPPLIER_NAMES))
    business_start, business_end = get_business_time_range(datetime.now())

    supplier_sql = f"""
        SELECT supplier_name, COUNT(*) as cnt
        FROM virtual_inventory
        WHERE supplier_name IN ({placeholders})
          AND fetch_time >= %s AND fetch_time <= %s
        GROUP BY supplier_name
    """

    db_manager = get_db_connection()
    try:
        supplier_rows = db_manager.execute_query(
            supplier_sql, FSBBR_SUPPLIER_NAMES + [business_start, business_end]
        )
    finally:
        db_manager.close()

    supplier_count_map = {row['supplier_name']: row['cnt'] for row in supplier_rows}

    lines = ['', '===【各供应商当天爬取量】===']
    for name in FSBBR_SUPPLIER_NAMES:
        lines.append(f'{name}：{supplier_count_map.get(name, 0)}条')
    return lines


def build_and_push_report(latest_business_date, latest_stats):
    """
    组装虚拟库存业务汇报消息并推送

    :param latest_business_date: 业务日期字符串，如 '2026-07-07'
    :param latest_stats: 当日各公司统计字典列表
    :return: 两次 message_push 的响应结果列表
    """
    company_order = ['fsbbr', 'zhbbr', 'zsbbr', 'dgby', 'dghf']
    stats_map = {item['company']: item for item in latest_stats}

    # 第一条：各公司业务汇总
    summary_lines = [
        '===【虚拟库存业务汇报】===',
        f'统计日期：{latest_business_date}'
    ]

    for company in company_order:
        item = stats_map.get(company)
        if not item:
            continue
        summary_lines.append(
            f"{company}：总数 {item['total_count']}，上传成功 {item['upload_success_count']}，"
            f"新建成功 {item['new_create_success_count']}，新建失败 {item['new_create_fail_count']}，"
            f"上传失败 {item['upload_fail_count']}，没有档案 {item['no_record_count']}"
        )

    # 第二条：供应商爬取量 + Excel 链接
    detail_lines = _build_supplier_summary_lines()
    try:
        excel_url = generate_virtual_inventory_compare_excel(latest_business_date)
        detail_lines.append('')
        detail_lines.append(f'对比Excel下载：{excel_url}')
    except Exception as e:
        logger.exception("[统计日志] 生成对比Excel失败")
        detail_lines.append('')
        detail_lines.append(f'对比Excel生成失败：{e}')

    results = []

    try:
        push_result = message_push('虚拟库存数据', '\n'.join(summary_lines))
        logger.info(f"[统计日志] 微信推送结果（汇总）: {push_result}")
        results.append(push_result)
    except Exception as push_error:
        logger.error(f"[统计日志] 微信推送失败（汇总）: {push_error}")

    try:
        push_result = message_push('虚拟库存数据', '\n'.join(detail_lines))
        logger.info(f"[统计日志] 微信推送结果（明细）: {push_result}")
        results.append(push_result)
    except Exception as push_error:
        logger.error(f"[统计日志] 微信推送失败（明细）: {push_error}")

    return results
