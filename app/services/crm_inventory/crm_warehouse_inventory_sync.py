# -*- coding:utf-8 -*-
"""
CRM 仓库库存同步服务

职责：
1. 调用 getProductList 获取所有产品，按 sync_date 写入 warehouse_inventory_latest
   同一天覆盖，不同日期保留
2. 解析 kw_nos 得到每个仓位及库存数量
3. 对每个 (product_id, kw_no) 调用 inventoryRecordList（type=1）
   取最新若干条入库记录，按 stock_log_id 去重后保存到 inventory_record_latest
4. 按仓位统计今日/昨日 SKU 种类数，生成按仓位分 sheet 的 Excel 并发送通知

使用方式：
    from app.services.crm_inventory.crm_warehouse_inventory_sync import sync_company_inventory
    sync_company_inventory('fsbbr')
"""

import os
import re
from collections import defaultdict

import pandas as pd
from datetime import datetime, date, timedelta

from app.scripts.spiders.spider_entities.crm_gzbbr import CrmGzbbrSpider
from app.models.orm_models.warehouse_inventory_latest import WarehouseInventoryLatest
from app.models.orm_models.inventory_record_latest import InventoryRecordLatest
from app.utils.orm.session import orm_session
from app.utils.common_util_module.server_push import message_push
from app.utils.logger_config import get_task_logger


logger = get_task_logger('crm_warehouse_inventory_sync')


# 门店映射配置
SHOP_MAPPING = {
    'fsbbr': {'cookie_key': 'fs', 'warehouse_ids': [2]},
    # 后续扩展：
    # 'zsbbr': {'cookie_key': 'zs', 'warehouse_ids': [1]},
    # 'hfbbr': {'cookie_key': 'hf', 'warehouse_ids': [1]},
}

# getProductList 分页参数
PRODUCT_LIST_LIMIT = 400

# 每个 (product_id, kw_no) 拉取的入库记录条数上限
INVENTORY_RECORD_LIMIT = 20

# 入库记录批量保存阈值（累计多少条记录开一次 DB 会话）
INVENTORY_RECORD_BATCH_SIZE = 500

# 快照保留天数
SNAPSHOT_KEEP_DAYS = 30

# 特殊库位号列表
SPECIAL_KW_NOS = [
    '01-01-01-01-01', '01-09-09-09-08', '01-09-09-09-09',
    '01-09-09-09-10', '01-66-66-66-66', '08-08-08-08-08',
]

# 仓位备注映射（Excel 用）
KW_NO_REMARKS = {
    '01-01-01-01-01': '临时仓，已经清掉',
    '01-09-09-09-08': '菲尔次品，下一次退货货物还没退',
    '01-09-09-09-09': '问题，退不了',
    '01-09-09-09-10': '找不到',
    '01-66-66-66-66': '虚拟，已经清掉',
    '08-08-08-08-08': '中转仓，已经清掉',
    '01-09-09-09-11': '临时存放，暂时不卖（有库存，需要搞个固定货位）',
    '01-09-09-09-12': '索赔仓',
}


def _get_kw_no_remark(kw_no):
    """获取仓位备注，未配置的仓位返回空字符串"""
    return KW_NO_REMARKS.get(kw_no, '')


# kw_nos 解析正则，匹配 仓位号<span...>(数量)</span>
KW_NOS_PATTERN = re.compile(
    r"(\d{2}-\d{2}-\d{2}-\d{2}-\d{2})\s*<span[^>]*>\((\d+)\)</span>",
    re.IGNORECASE
)


def _parse_product_item_for_bin(item, company, kw_no, stock_quantity):
    """
    解析 getProductList 单条产品数据，按仓位拆行

    :param item: 接口返回的原始数据字典
    :param company: 门店代码
    :param kw_no: 单个仓位号
    :param stock_quantity: 该仓位库存数量
    :return: 标准化后的字典
    """
    return {
        'product_id': item.get('product_id'),
        'product_name': item.get('product_name', ''),
        'l_name_zh_default': item.get('l_name_zh_default', ''),
        'frey_no': item.get('frey_no', ''),
        'number': item.get('number', ''),
        'cass_oebrand_name': item.get('cass_oebrand_name', ''),
        'brand_name': item.get('brand_name', ''),
        'link_brand_code': item.get('link_brand_code', ''),
        'vehicle_model': item.get('vehicle_model', ''),
        'cost_price': float(item.get('cost_price', 0)) if item.get('cost_price') else 0.0,
        'stock_quantity': int(stock_quantity) if stock_quantity else 0,
        'cost_price_total': float(item.get('cost_price_total', 0)) if item.get('cost_price_total') else 0.0,
        'kw_nos': kw_no or '',
        'warehouse_name': item.get('warehouse_name', ''),
        'company': company,
        'sync_date': date.today(),
        'sync_time': datetime.now(),
    }


def _parse_kw_nos(kw_nos_str):
    """
    解析 kw_nos 字符串，提取每个仓位及库存数量

    示例：
        "07-01-01-10-03<span style='color:#FF9000'>(2)</span>、
         09-01-05-02-08<span style='color:#FF9000'>(3)</span>"
    返回：
        [('07-01-01-10-03', 2), ('09-01-05-02-08', 3)]

    :param kw_nos_str: 接口返回的 kw_nos 字段
    :return: [(kw_no, quantity), ...]
    """
    if not kw_nos_str:
        return []
    results = []
    for match in KW_NOS_PATTERN.finditer(kw_nos_str):
        kw_no = match.group(1)
        quantity = int(match.group(2))
        results.append((kw_no, quantity))
    return results


def _parse_inventory_record(item, product_id, record_type, company):
    """
    解析 inventoryRecordList 单条变动记录

    :param item: 接口返回的原始数据字典
    :param product_id: 产品ID
    :param record_type: 变动类型 1/-1
    :param company: 门店代码
    :return: 标准化后的字典
    """
    workdate_str = item.get('workdate', '')
    workdate = None
    if workdate_str:
        try:
            workdate = datetime.strptime(workdate_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            pass

    return {
        'stock_log_id': item.get('stock_log_id'),
        'product_id': product_id,
        'record_type': record_type,
        'user_id': item.get('user_id'),
        'kw_id': item.get('kw_id'),
        'batch_no': item.get('batch_no', ''),
        'create_log_date': item.get('create_log_date'),
        'change_number': item.get('change_number'),
        'original_number': item.get('original_number'),
        'note': item.get('note', ''),
        'orders_id': item.get('orders_id'),
        'process_type_id': item.get('process_type_id'),
        'pono': item.get('pono', ''),
        'device_type': item.get('device_type'),
        'warehouse_id': item.get('warehouse_id'),
        'frey_no': item.get('frey_no', ''),
        'product_name': item.get('product_name', ''),
        'number': item.get('number', ''),
        'brand_name': item.get('brand_name', ''),
        'operator_name': item.get('name', ''),
        'kw_no': item.get('kw_no', ''),
        'warehouse_name': item.get('warehouse_name', ''),
        'warehouse_no': item.get('warehouse_no', ''),
        'workdate': workdate,
        'names': item.get('names', ''),
        'common_order_id': item.get('common_order_id', ''),
        'company': company,
        'sync_time': datetime.now(),
    }


def _sync_product_list(spider, company, warehouse_ids):
    """
    同步产品列表（getProductList）

    :param spider: CrmGzbbrSpider 实例
    :param company: 门店代码
    :param warehouse_ids: 仓库ID列表
    :return: (product_kw_map, api_total)
             product_kw_map: {product_id: [(kw_no, quantity), ...]}
    """
    logger.info(f"\n{'=' * 60}")
    logger.info(f"[产品列表同步] 开始同步 {company}")
    logger.info(f"{'=' * 60}")

    all_product_ids = []
    product_kw_map = {}
    total_saved = 0
    api_total = 0

    for warehouse_id in warehouse_ids:
        logger.info(f"\n[仓库 {warehouse_id}] 开始拉取...")
        page = 1
        warehouse_total = 0

        while True:
            response = spider.get_product_list(
                page=page,
                limit=PRODUCT_LIST_LIMIT,
                warehouse_id=warehouse_id
            )

            if response is None:
                logger.info(f"[仓库 {warehouse_id}] 第{page}页请求失败")
                break

            try:
                result = response.json()
            except Exception as e:
                logger.info(f"[仓库 {warehouse_id}] 第{page}页解析失败: {e}")
                break

            if result.get('status') != 200:
                logger.info(f"[仓库 {warehouse_id}] 第{page}页接口错误: {result.get('msg')}")
                break

            data = result.get('data', {})
            items = data.get('data', [])

            # 记录接口返回的总数（取第一页即可）
            if page == 1:
                api_total = data.get('total', 0)

            if not items:
                logger.info(f"[仓库 {warehouse_id}] 第{page}页无数据，结束")
                break

            # 解析并收集 product_id 和仓位信息（按仓位拆行）
            parsed_items = []
            for item in items:
                product_id = item.get('product_id')
                all_product_ids.append(product_id)

                kw_nos_str = item.get('kw_nos', '')
                kw_list = _parse_kw_nos(kw_nos_str)

                if kw_list:
                    product_kw_map[product_id] = kw_list
                    for kw_no, quantity in kw_list:
                        parsed_items.append(
                            _parse_product_item_for_bin(item, company, kw_no, quantity)
                        )
                else:
                    # 解析不到仓位时，用原数据兜底保存一行
                    parsed_items.append(
                        _parse_product_item_for_bin(
                            item, company, '', item.get('stock_quantity', 0)
                        )
                    )

            # 批量写入数据库
            with orm_session() as session:
                count = WarehouseInventoryLatest.bulk_upsert(session, parsed_items)
                total_saved += count
                warehouse_total += count

            logger.info(f"[仓库 {warehouse_id}] 第{page}页: {len(items)} 条产品, 拆分为 {len(parsed_items)} 条仓位记录, 已保存")

            # 判断是否最后一页
            last_page = data.get('last_page', 1)
            if page >= last_page:
                logger.info(f"[仓库 {warehouse_id}] 已到最后一页 ({last_page})")
                break

            page += 1

        logger.info(f"[仓库 {warehouse_id}] 同步完成，本仓库共处理 {warehouse_total} 条")

    logger.info(f"\n[产品列表同步] {company} 完成，共 {len(all_product_ids)} 个产品，入库 {total_saved} 条")
    logger.info(f"{'=' * 60}\n")

    return product_kw_map, api_total


def _sync_inventory_records(spider, product_kw_map, company):
    """
    同步库存变动记录（inventoryRecordList）
    按 (product_id, kw_no) 拉取入库记录（type=1），只取第一页，按 stock_log_id 去重保存
    累计到一定数量后批量写入数据库，减少 orm_session 开销

    :param spider: CrmGzbbrSpider 实例
    :param product_kw_map: {product_id: [(kw_no, quantity), ...]}
    :param company: 门店代码
    :return: 实际插入的记录数
    """
    total_pairs = sum(len(kw_list) for kw_list in product_kw_map.values())
    logger.info(f"\n{'=' * 60}")
    logger.info(f"[入库记录同步] 开始同步 {company}，共 {len(product_kw_map)} 个产品，{total_pairs} 个仓位")
    logger.info(f"{'=' * 60}")

    total_inserted = 0
    skipped_count = 0
    no_data_count = 0
    processed = 0
    batch_records = []

    def _flush_batch():
        """把缓存的入库记录批量写入数据库"""
        nonlocal total_inserted, skipped_count, batch_records
        if not batch_records:
            return
        with orm_session() as session:
            inserted = InventoryRecordLatest.bulk_insert_ignore(session, batch_records)
            total_inserted += inserted
            skipped_count += len(batch_records) - inserted
        batch_records = []

    for product_id, kw_list in product_kw_map.items():
        for kw_no, _ in kw_list:
            response = spider.get_inventory_record_list(
                product_id=product_id,
                page=1,
                limit=INVENTORY_RECORD_LIMIT,
                record_type=1,
                kw_no=kw_no
            )

            processed += 1

            if response is None:
                continue

            try:
                result = response.json()
            except Exception:
                continue

            if result.get('status') != 200:
                if result.get('status') == 201:
                    no_data_count += 1
                continue

            data = result.get('data', {})
            items = data.get('data', [])

            if not items:
                no_data_count += 1
                continue

            records = [
                _parse_inventory_record(item, product_id, 1, company)
                for item in items
            ]
            batch_records.extend(records)

            # 累计达到阈值时批量写入
            if len(batch_records) >= INVENTORY_RECORD_BATCH_SIZE:
                _flush_batch()

            if processed % 100 == 0:
                logger.info(f"[进度] 已处理 {processed}/{total_pairs} 个仓位，插入 {total_inserted} 条，跳过 {skipped_count} 条")

    # 写入最后一批
    _flush_batch()

    logger.info(f"\n[入库记录同步] {company} 完成")
    logger.info(f"  - 插入新记录: {total_inserted} 条")
    logger.info(f"  - 跳过已存在: {skipped_count} 条")
    logger.info(f"  - 无变动数据: {no_data_count} 次")
    logger.info(f"{'=' * 60}\n")

    return total_inserted


def _sync_special_kw_records(spider, company):
    """
    同步特殊库位的库存变动记录（新流程）

    1. 用 kw_nos 参数调用 getProductList，获取特殊库位产品
    2. 保存产品快照到 warehouse_inventory_latest（含 sync_date）
    3. 解析 kw_nos，只保留 SPECIAL_KW_NOS 中的仓位
    4. 按 (product_id, kw_no) 拉取入库记录（type=1, limit=20）
    5. 全部保存到 inventory_record_latest，按 stock_log_id 去重

    :param spider: CrmGzbbrSpider 实例
    :param company: 门店代码
    :return: (special_product_ids, special_total)
             special_product_ids: 特殊库位产品ID列表
             special_total: 接口返回总数
    """
    kw_nos_str = ','.join(SPECIAL_KW_NOS)

    logger.info(f"\n{'=' * 60}")
    logger.info(f"[特殊库位变动同步] 开始同步 {company}")
    logger.info(f"[特殊库位] {SPECIAL_KW_NOS}")
    logger.info(f"{'=' * 60}")

    page = 1
    special_product_ids = []
    special_total = 0
    special_kw_map = {}

    # Step 1: 拉取并保存特殊库位产品
    while True:
        response = spider.get_product_list(
            page=page,
            limit=PRODUCT_LIST_LIMIT,
            kw_nos=kw_nos_str
        )

        if response is None:
            logger.info(f"[特殊库位] 第{page}页请求失败")
            break

        try:
            result = response.json()
        except Exception as e:
            logger.info(f"[特殊库位] 第{page}页解析失败: {e}")
            break

        if result.get('status') != 200:
            logger.info(f"[特殊库位] 第{page}页接口错误: {result.get('msg')}")
            break

        data = result.get('data', {})
        items = data.get('data', [])

        # 记录总数（取第一页）
        if page == 1:
            special_total = data.get('total', 0)

        if not items:
            logger.info(f"[特殊库位] 第{page}页无数据，结束")
            break

        # 解析并收集 product_id 和特殊仓位信息（按仓位拆行）
        parsed_items = []
        for item in items:
            product_id = item.get('product_id')
            special_product_ids.append(product_id)

            kw_list = _parse_kw_nos(item.get('kw_nos', ''))
            # 只保留 SPECIAL_KW_NOS 中的仓位
            filtered_kw_list = [
                (kw_no, qty) for kw_no, qty in kw_list
                if kw_no in SPECIAL_KW_NOS
            ]
            if filtered_kw_list:
                special_kw_map[product_id] = filtered_kw_list
                for kw_no, quantity in filtered_kw_list:
                    parsed_items.append(
                        _parse_product_item_for_bin(item, company, kw_no, quantity)
                    )
            else:
                # 兜底：保存一行空仓位
                parsed_items.append(
                    _parse_product_item_for_bin(
                        item, company, '', item.get('stock_quantity', 0)
                    )
                )

        # 写入产品列表（复用同一套表）
        with orm_session() as session:
            WarehouseInventoryLatest.bulk_upsert(session, parsed_items)

        logger.info(f"[特殊库位] 第{page}页: {len(items)} 条产品, 拆分为 {len(parsed_items)} 条仓位记录, 已保存")

        last_page = data.get('last_page', 1)
        if page >= last_page:
            logger.info(f"[特殊库位] 已到最后一页 ({last_page})")
            break

        page += 1

    logger.info(f"\n[特殊库位] 共 {len(special_product_ids)} 个产品，接口 total={special_total}")

    # Step 2: 按 (product_id, kw_no) 拉取入库记录并批量保存
    total_pairs = sum(len(kw_list) for kw_list in special_kw_map.values())
    logger.info(f"[特殊库位入库记录] 共 {len(special_kw_map)} 个产品，{total_pairs} 个特殊仓位")

    total_inserted = 0
    skipped_count = 0
    no_data_count = 0
    processed = 0
    batch_records = []

    def _flush_special_batch():
        """把缓存的特殊库位入库记录批量写入数据库"""
        nonlocal total_inserted, skipped_count, batch_records
        if not batch_records:
            return
        with orm_session() as session:
            inserted = InventoryRecordLatest.bulk_insert_ignore(session, batch_records)
            total_inserted += inserted
            skipped_count += len(batch_records) - inserted
        batch_records = []

    for product_id, kw_list in special_kw_map.items():
        for kw_no, _ in kw_list:
            response = spider.get_inventory_record_list(
                product_id=product_id,
                page=1,
                limit=INVENTORY_RECORD_LIMIT,
                record_type=1,
                kw_no=kw_no
            )

            processed += 1

            if response is None:
                continue

            try:
                result = response.json()
            except Exception:
                continue

            if result.get('status') != 200:
                if result.get('status') == 201:
                    no_data_count += 1
                continue

            data = result.get('data', {})
            items = data.get('data', [])

            if not items:
                no_data_count += 1
                continue

            records = [
                _parse_inventory_record(item, product_id, 1, company)
                for item in items
            ]
            batch_records.extend(records)

            if len(batch_records) >= INVENTORY_RECORD_BATCH_SIZE:
                _flush_special_batch()

            if processed % 100 == 0:
                logger.info(f"[特殊库位进度] 已处理 {processed}/{total_pairs} 个仓位，插入 {total_inserted} 条，跳过 {skipped_count} 条")

    _flush_special_batch()

    logger.info(f"\n[特殊库位变动同步] {company} 完成")
    logger.info(f"  - 插入新记录: {total_inserted} 条")
    logger.info(f"  - 跳过已存在: {skipped_count} 条")
    logger.info(f"  - 无变动数据: {no_data_count} 次")
    logger.info(f"{'=' * 60}\n")

    return special_product_ids, special_total


def _get_kw_no_sku_count(session, company, target_date):
    """
    按仓位统计指定日期的 SKU 种类数（仓位库存 > 0 才计入）

    :param session: SQLAlchemy Session
    :param company: 门店代码
    :param target_date: 目标日期
    :return: dict {kw_no: sku_count}
    """
    return WarehouseInventoryLatest.get_kw_no_sku_count(session, company, target_date)


def _get_inbound_records_for_bin(session, company, product_id, kw_no, needed_quantity):
    """
    获取指定仓位 + 产品的最新入库记录，累加数量直到满足 needed_quantity

    :param session: SQLAlchemy Session
    :param company: 门店代码
    :param product_id: 产品ID
    :param kw_no: 库位号
    :param needed_quantity: 需要凑够的库存数量
    :return: [(record, used_quantity), ...]
    """
    records = session.query(InventoryRecordLatest).filter(
        InventoryRecordLatest.company == company,
        InventoryRecordLatest.product_id == product_id,
        InventoryRecordLatest.kw_no == kw_no,
        InventoryRecordLatest.record_type == 1
    ).order_by(InventoryRecordLatest.workdate.desc()).all()

    if not records:
        return []

    result = []
    accumulated = 0
    for record in records:
        change_number = record.change_number or 0
        if change_number <= 0:
            continue

        remaining = needed_quantity - accumulated
        if remaining <= 0:
            break

        used = min(change_number, remaining)
        result.append((record, used))
        accumulated += used

    return result


def _build_excel_data(session, company):
    """
    构建按仓位分组的 Excel 数据

    直接从 warehouse_inventory_latest 查询今日仓位记录，
    再按 (product_id, kw_no) 匹配入库记录。

    :param session: SQLAlchemy Session
    :param company: 门店代码
    :return: dict {kw_no: [row_dict, ...]}
    """
    kw_no_rows = defaultdict(list)

    # 查询今日所有有库存的仓位记录
    rows = session.query(WarehouseInventoryLatest).filter(
        WarehouseInventoryLatest.company == company,
        WarehouseInventoryLatest.sync_date == date.today(),
        WarehouseInventoryLatest.stock_quantity > 0
    ).all()

    for row in rows:
        product_id = row.product_id
        kw_no = row.kw_nos or ''
        quantity = row.stock_quantity or 0

        if not kw_no or quantity <= 0:
            continue

        records = _get_inbound_records_for_bin(
            session, company, product_id, kw_no, quantity
        )

        if not records:
            # 没有入库记录，只展示产品基础信息
            kw_no_rows[kw_no].append({
                '产品ID': product_id,
                'OE号': row.number or '',
                '品牌': row.brand_name or '',
                '产品名称': row.product_name or '',
                '仓位库存': quantity,
                '入库数量': '',
                '累计入库': 0,
                '操作时间': '',
                '操作人': '',
                '备注': '未找到入库记录',
                '仓位备注': _get_kw_no_remark(kw_no),
            })
            continue

        accumulated = 0
        for record, used in records:
            accumulated += used
            kw_no_rows[kw_no].append({
                '产品ID': product_id,
                'OE号': record.number or '',
                '品牌': record.brand_name or '',
                '产品名称': record.product_name or '',
                '仓位库存': quantity,
                '入库数量': used,
                '累计入库': accumulated,
                '操作时间': record.workdate.strftime('%Y-%m-%d %H:%M') if record.workdate else '',
                '操作人': record.operator_name or '',
                '备注': record.note or '',
                '仓位备注': _get_kw_no_remark(kw_no),
            })
            if accumulated >= quantity:
                break

    return dict(kw_no_rows)


def _send_notification(company, sku_total):
    """
    按仓位统计 SKU 数，导出按仓位分 sheet 的 Excel，并发送微信通知

    :param company: 门店代码
    :param sku_total: getProductList 全部产品的总数
    """
    today = date.today()
    yesterday = today - timedelta(days=1)
    today_str = today.strftime('%Y-%m-%d')

    with orm_session() as session:
        # 今日 / 昨日 SKU 统计
        today_sku_count = _get_kw_no_sku_count(session, company, today)
        yesterday_sku_count = _get_kw_no_sku_count(session, company, yesterday)

        # 构建 Excel 数据
        kw_no_rows = _build_excel_data(session, company)

    # 汇总统计
    all_kw_nos = set(today_sku_count.keys()) | set(yesterday_sku_count.keys())
    summary_rows = []
    for kw_no in sorted(all_kw_nos):
        today_count = today_sku_count.get(kw_no, 0)
        yesterday_count = yesterday_sku_count.get(kw_no, 0)
        change = today_count - yesterday_count
        summary_rows.append({
            '库位号': kw_no,
            '昨日SKU数': yesterday_count,
            '今日SKU数': today_count,
            '增减': change,
            '仓位备注': _get_kw_no_remark(kw_no),
        })

    # 无库存数据时不生成 Excel，只发送通知
    if not summary_rows:
        message = (
            f"===【crm仓位库存业务汇报】===\n"
            f"日期：{today_str}\n"
            f"门店：{company}\n"
            f"今日无库存数据"
        )
        try:
            message_push("crm", message)
            logger.info(f"[通知] {company} 今日无库存数据，跳过Excel导出")
        except Exception as e:
            logger.error(f"[通知] 发送失败: {e}")
        return

    # 导出 Excel（按仓位分 sheet）
    export_dir = os.path.join('static', 'exports')
    os.makedirs(export_dir, exist_ok=True)
    file_path = os.path.join(export_dir, f'inventory_{company}_{today_str}.xlsx')

    with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
        # 第一个 sheet：汇总
        pd.DataFrame(summary_rows).to_excel(writer, sheet_name='SKU统计汇总', index=False)

        # 每个仓位一个 sheet
        for kw_no in sorted(kw_no_rows.keys()):
            rows = kw_no_rows[kw_no]
            sheet_name = kw_no[:31]  # Excel sheet 名最长 31 字符
            pd.DataFrame(rows).to_excel(writer, sheet_name=sheet_name, index=False)

    # 构建通知消息
    total_change = sum(row['增减'] for row in summary_rows)
    summary_text = '\n'.join(
        f"{row['库位号']}：{row['昨日SKU数']} → {row['今日SKU数']} ({row['增减']:+,})"
        for row in summary_rows[:10]
    )
    if len(summary_rows) > 10:
        summary_text += f"\n... 共 {len(summary_rows)} 个仓位"

    message = (
        f"===【crm仓位库存业务汇报】===\n"
        f"日期：{today_str}\n"
        f"门店：{company}\n"
        f"产品总数：{sku_total}\n"
        f"仓位总数：{len(summary_rows)}\n"
        f"整体增减：{total_change:+,}\n"
        f"\n仓位SKU变化（前10）：\n{summary_text}\n"
        f"\n详细记录下载：http://x.fsbbr.net/web/download_inventory/{company}/{today_str}"
    )

    try:
        message_push("crm", message)
        logger.info(f"[通知] 已发送 {company} 的业务汇报，仓位数 {len(summary_rows)}，总SKU {sku_total}")
    except Exception as e:
        logger.error(f"[通知] 发送失败: {e}")


def sync_company_inventory(company):
    """
    同步单个门店的库存数据

    :param company: 门店代码，如 'fsbbr'
    """
    config = SHOP_MAPPING.get(company)
    if not config:
        logger.error(f"[错误] 未知的门店代码: {company}")
        return

    cookie_key = config['cookie_key']
    warehouse_ids = config['warehouse_ids']

    logger.info(f"\n{'#' * 70}")
    logger.info(f"# 开始同步门店: {company} (cookie_key={cookie_key})")
    logger.info(f"{'#' * 70}")

    spider = CrmGzbbrSpider(cookies_key=cookie_key, logger=logger)
    sku_total = 0
    product_kw_map = {}

    try:
        # Step 1: 同步全部产品列表，同时收集每个产品的仓位分布
        product_kw_map, sku_total = _sync_product_list(spider, company, warehouse_ids)

        # Step 2: 同步入库记录（按 product_id + kw_no）
        if product_kw_map:
            _sync_inventory_records(spider, product_kw_map, company)
        else:
            logger.warning(f"[警告] {company} 未获取到任何产品，跳过入库记录同步")

        # Step 3: 同步特殊库位变动记录
        _sync_special_kw_records(spider, company)

    finally:
        spider.close()

    # Step 4: 清理旧快照
    with orm_session() as session:
        deleted = WarehouseInventoryLatest.delete_old_snapshots(
            session, company, keep_days=SNAPSHOT_KEEP_DAYS
        )
        logger.info(f"[清理] 已删除 {company} {deleted} 条超过 {SNAPSHOT_KEEP_DAYS} 天的旧快照")

    # Step 5: 发送通知
    _send_notification(company, sku_total)

    logger.info(f"\n{'#' * 70}")
    logger.info(f"# 门店同步完成: {company}")
    logger.info(f"{'#' * 70}\n")


def sync_all():
    """
    同步所有配置的门店
    """
    logger.info(f"\n{'#' * 80}")
    logger.info(f"# CRM 仓库库存全量同步开始")
    logger.info(f"# 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"{'#' * 80}")

    for company in SHOP_MAPPING.keys():
        sync_company_inventory(company)

    logger.info(f"\n{'#' * 80}")
    logger.info(f"# CRM 仓库库存全量同步完成")
    logger.info(f"# 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"{'#' * 80}\n")
