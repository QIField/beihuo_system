# -*- coding:utf-8 -*-
"""
CRM 仓库库存同步服务

职责：
1. 调用 getProductList 获取所有产品，覆盖写入 warehouse_inventory_latest
2. 对每个 product_id 调用两次 inventoryRecordList（type=1 和 type=-1）
   取第一条记录，查重后插入 inventory_record_latest

使用方式：
    from app.services.crm_inventory.crm_warehouse_inventory_sync import sync_company_inventory
    sync_company_inventory('fsbbr')
"""

from datetime import datetime, date, timedelta

from app.scripts.spiders.spider_entities.crm_gzbbr import CrmGzbbrSpider
from app.models.orm_models.warehouse_inventory_latest import WarehouseInventoryLatest
from app.models.orm_models.inventory_record_latest import InventoryRecordLatest
from app.utils.orm.session import orm_session
from app.utils.common_util_module.server_push import message_push


# 门店映射配置
SHOP_MAPPING = {
    'fsbbr': {'cookie_key': 'fs', 'warehouse_ids': [2]},
    # 后续扩展：
    # 'zsbbr': {'cookie_key': 'zs', 'warehouse_ids': [1]},
    # 'hfbbr': {'cookie_key': 'hf', 'warehouse_ids': [1]},
}

# getProductList 分页参数
PRODUCT_LIST_LIMIT = 400


def _parse_product_item(item, company):
    """
    解析 getProductList 单条产品数据

    :param item: 接口返回的原始数据字典
    :param company: 门店代码
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
        'stock_quantity': int(item.get('stock_quantity', 0)) if item.get('stock_quantity') else 0,
        'cost_price_total': float(item.get('cost_price_total', 0)) if item.get('cost_price_total') else 0.0,
        'kw_nos': item.get('kw_nos', ''),
        'warehouse_name': item.get('warehouse_name', ''),
        'company': company,
        'sync_time': datetime.now(),
    }


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
    :return: (product_ids, total) 产品ID列表 和 接口返回的总数
    """
    print(f"\n{'=' * 60}")
    print(f"[产品列表同步] 开始同步 {company}")
    print(f"{'=' * 60}")

    all_product_ids = []
    total_saved = 0
    api_total = 0

    for warehouse_id in warehouse_ids:
        print(f"\n[仓库 {warehouse_id}] 开始拉取...")
        page = 1
        warehouse_total = 0

        while True:
            response = spider.get_product_list(
                page=page,
                limit=PRODUCT_LIST_LIMIT,
                warehouse_id=warehouse_id
            )

            if response is None:
                print(f"[仓库 {warehouse_id}] 第{page}页请求失败")
                break

            try:
                result = response.json()
            except Exception as e:
                print(f"[仓库 {warehouse_id}] 第{page}页解析失败: {e}")
                break

            if result.get('status') != 200:
                print(f"[仓库 {warehouse_id}] 第{page}页接口错误: {result.get('msg')}")
                break

            data = result.get('data', {})
            items = data.get('data', [])

            # 记录接口返回的总数（取第一页即可）
            if page == 1:
                api_total = data.get('total', 0)

            if not items:
                print(f"[仓库 {warehouse_id}] 第{page}页无数据，结束")
                break

            # 解析并收集 product_id
            parsed_items = []
            for item in items:
                parsed_items.append(_parse_product_item(item, company))
                all_product_ids.append(item.get('product_id'))

            # 批量写入数据库
            with orm_session() as session:
                count = WarehouseInventoryLatest.bulk_upsert(session, parsed_items)
                total_saved += count
                warehouse_total += count

            print(f"[仓库 {warehouse_id}] 第{page}页: {len(items)} 条产品, 已保存")

            # 判断是否最后一页
            last_page = data.get('last_page', 1)
            if page >= last_page:
                print(f"[仓库 {warehouse_id}] 已到最后一页 ({last_page})")
                break

            page += 1

        print(f"[仓库 {warehouse_id}] 同步完成，本仓库共处理 {warehouse_total} 条")

    print(f"\n[产品列表同步] {company} 完成，共 {len(all_product_ids)} 个产品，入库 {total_saved} 条")
    print(f"{'=' * 60}\n")

    return all_product_ids, api_total


def _sync_inventory_records(spider, product_ids, company):
    """
    同步库存变动记录（inventoryRecordList）
    每个 product_id 发两次请求：type=1 和 type=-1，取第一条记录

    :param spider: CrmGzbbrSpider 实例
    :param product_ids: 产品ID列表
    :param company: 门店代码
    """
    print(f"\n{'=' * 60}")
    print(f"[变动记录同步] 开始同步 {company}，共 {len(product_ids)} 个产品")
    print(f"{'=' * 60}")

    total_inserted = 0
    skipped_count = 0
    no_data_count = 0

    for idx, product_id in enumerate(product_ids, start=1):
        for record_type in (1, -1):
            response = spider.get_inventory_record_list(
                product_id=product_id,
                page=1,
                limit=1,
                record_type=record_type
            )

            if response is None:
                continue

            try:
                result = response.json()
            except Exception:
                continue

            if result.get('status') != 200:
                # 产品不存在或无记录
                if result.get('status') == 201:
                    no_data_count += 1
                continue

            data = result.get('data', {})
            items = data.get('data', [])

            if not items:
                no_data_count += 1
                continue

            # 只取第一条（最新变动）
            record = _parse_inventory_record(items[0], product_id, record_type, company)

            # 查重后插入
            with orm_session() as session:
                exists = InventoryRecordLatest.exists_by_stock_log(
                    session,
                    record['stock_log_id'],
                    company
                )
                if exists:
                    skipped_count += 1
                else:
                    session.add(InventoryRecordLatest(**record))
                    total_inserted += 1

        # 每100个产品打印一次进度
        if idx % 100 == 0:
            print(f"[进度] 已处理 {idx}/{len(product_ids)} 个产品，插入 {total_inserted} 条，跳过 {skipped_count} 条")

    print(f"\n[变动记录同步] {company} 完成")
    print(f"  - 插入新记录: {total_inserted} 条")
    print(f"  - 跳过已存在: {skipped_count} 条")
    print(f"  - 无变动数据: {no_data_count} 次")
    print(f"{'=' * 60}\n")


def _send_notification(company, sku_total):
    """
    查询当天变动记录并发送微信通知

    :param company: 门店代码
    :param sku_total: getProductList 接口返回的产品总数
    """
    today = date.today()
    tomorrow = today + timedelta(days=1)

    with orm_session() as session:
        records = session.query(InventoryRecordLatest).filter(
            InventoryRecordLatest.company == company,
            InventoryRecordLatest.workdate >= today,
            InventoryRecordLatest.workdate < tomorrow,
        ).order_by(InventoryRecordLatest.workdate.desc()).all()

    # 构建消息
    lines = [
        "===【crm特殊仓位库存变化业务汇报】===",
        f"统计时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"sku：{sku_total}",
    ]

    if records:
        for r in records:
            workdate_str = r.workdate.strftime('%Y-%m-%d %H:%M') if r.workdate else ''
            lines.append(
                f"{r.number or ''}+{r.brand_name or ''}+{r.change_number or ''}+"
                f"{r.kw_no or ''}+{r.operator_name or ''}+{workdate_str}"
            )
    else:
        lines.append("今日无变动记录")

    message = "\n".join(lines)

    try:
        message_push("crm", message)
        print(f"[通知] 已发送 {company} 的业务汇报，共 {len(records)} 条变动记录")
    except Exception as e:
        print(f"[通知] 发送失败: {e}")


def sync_company_inventory(company):
    """
    同步单个门店的库存数据

    :param company: 门店代码，如 'fsbbr'
    """
    config = SHOP_MAPPING.get(company)
    if not config:
        print(f"[错误] 未知的门店代码: {company}")
        return

    cookie_key = config['cookie_key']
    warehouse_ids = config['warehouse_ids']

    print(f"\n{'#' * 70}")
    print(f"# 开始同步门店: {company} (cookie_key={cookie_key})")
    print(f"{'#' * 70}")

    spider = CrmGzbbrSpider(cookies_key=cookie_key)
    sku_total = 0

    try:
        # Step 1: 同步产品列表
        product_ids, sku_total = _sync_product_list(spider, company, warehouse_ids)

        # Step 2: 同步变动记录
        if product_ids:
            _sync_inventory_records(spider, product_ids, company)
        else:
            print(f"[警告] {company} 未获取到任何产品，跳过变动记录同步")

    finally:
        spider.close()

    # Step 3: 发送通知
    _send_notification(company, sku_total)

    print(f"\n{'#' * 70}")
    print(f"# 门店同步完成: {company}")
    print(f"{'#' * 70}\n")


def sync_all():
    """
    同步所有配置的门店
    """
    print(f"\n{'#' * 80}")
    print(f"# CRM 仓库库存全量同步开始")
    print(f"# 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#' * 80}")

    for company in SHOP_MAPPING.keys():
        sync_company_inventory(company)

    print(f"\n{'#' * 80}")
    print(f"# CRM 仓库库存全量同步完成")
    print(f"# 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#' * 80}\n")
