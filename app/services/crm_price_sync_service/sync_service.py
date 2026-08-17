# -*- coding: utf-8 -*-
"""
CRM 产品价格同步业务编排

主流程：比对佛山/珠海库存 → 珠海 view → 计算价格 → 珠海 updateView → 输出 Excel 报告。
"""

import os
import time
from datetime import datetime

import pandas as pd

from app.utils.crm_price_sync import (
    CrmPriceSyncApiClient,
    extract_stock_items,
    match_stock_items,
    calculate_update_payload,
    is_valid_fs_price,
)
from app.utils.logger_config import get_task_logger, BASE_LOG_DIR


logger = get_task_logger('crm_price_sync')

FS_STORE_CODE = "fsbbr"
ZH_STORE_CODE = "zhbbr"
REQUEST_DELAY = 0.3


def _pull_stock_products(store_code):
    """拉取指定门店有库存产品列表。"""
    logger.info(f"[{store_code}] 开始拉取库存产品列表...")
    client = CrmPriceSyncApiClient(store_code)
    products = client.list_stock_products()
    items = extract_stock_items(products)
    logger.info(f"[{store_code}] 共拉取 {len(items)} 条库存产品")
    return client, items


def _get_view_data(client, product_id):
    """获取产品完整视图数据。"""
    return client.get_product_view(product_id)


def _build_report_path():
    """构建报告文件路径。"""
    report_dir = os.path.join(BASE_LOG_DIR, "task_log", "crm_price_sync")
    os.makedirs(report_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(report_dir, f"crm_price_sync_report_{timestamp}.xlsx")


def sync_crm_prices():
    """
    执行 CRM 产品价格同步，并输出 Excel 报告。

    :return: dict 统计结果
    """
    logger.info("=" * 80)
    logger.info("[CRM价格同步] 任务开始")
    logger.info("=" * 80)

    # 1. 拉取佛山、珠海库存
    fs_client, fs_items = _pull_stock_products(FS_STORE_CODE)
    zh_client, zh_items = _pull_stock_products(ZH_STORE_CODE)

    # 2. 匹配与过滤
    match_result = match_stock_items(fs_items, zh_items)
    both = match_result["both"]
    only_zhuhai = match_result["only_zhuhai"]
    only_foshan = match_result["only_foshan"]

    # 3. 按佛山开思价有效性拆分
    valid_items = []
    low_price_items = []
    for item in both:
        if is_valid_fs_price(item["fs_store_cass_price"]):
            valid_items.append(item)
        else:
            low_price_items.append(item)

    logger.info(f"[CRM价格同步] 两店都有库存: {len(both)} 条")
    logger.info(f"[CRM价格同步] 佛山开思价有效: {len(valid_items)} 条")
    logger.info(f"[CRM价格同步] 佛山开思价无效: {len(low_price_items)} 条（跳过）")
    logger.info(f"[CRM价格同步] 仅珠海有库存: {len(only_zhuhai)} 条")
    logger.info(f"[CRM价格同步] 仅佛山有库存: {len(only_foshan)} 条（已过滤）")

    # 4. 逐个处理有效产品，记录结果
    both_records = []
    success_count = 0
    fail_count = 0

    for idx, item in enumerate(both, start=1):
        product_id = item["product_id"]
        brand_name = item["brand_name"]
        number = item["number"]
        fs_price = item["fs_store_cass_price"]

        record = {
            "brand_name": brand_name,
            "number": number,
            "product_id": product_id,
            "fs_store_cass_price": fs_price,
            "before_store_cass_price": None,
            "before_qpl_price": None,
            "after_store_cass_price": None,
            "after_qpl_price": None,
            "update_status": "",
            "msg": "",
        }

        try:
            view_data = _get_view_data(zh_client, product_id)
            record["before_store_cass_price"] = view_data.get("store_cass_price")
            record["before_qpl_price"] = view_data.get("qpl_price")
        except Exception:
            logger.exception(f"[{idx}/{len(both)}] product_id={product_id} 查询 view 失败")
            record["update_status"] = "失败"
            record["msg"] = "查询 view 失败"
            fail_count += 1
            both_records.append(record)
            continue

        if not is_valid_fs_price(fs_price):
            record["after_store_cass_price"] = view_data.get("store_cass_price")
            record["after_qpl_price"] = view_data.get("qpl_price")
            record["update_status"] = "价格为0跳过"
            record["msg"] = f"佛山开思价无效: {fs_price}"
            both_records.append(record)
            continue

        try:
            payload = calculate_update_payload(fs_price, brand_name, view_data)

            if payload is None:
                record["after_store_cass_price"] = view_data.get("store_cass_price")
                record["after_qpl_price"] = view_data.get("qpl_price")
                record["update_status"] = "计算失败跳过"
                record["msg"] = "价格计算失败"
                both_records.append(record)
                continue

            ok, msg = zh_client.update_product_view(payload, original_values=view_data)
            record["msg"] = msg

            time.sleep(REQUEST_DELAY)
            view_after = _get_view_data(zh_client, product_id)
            record["after_store_cass_price"] = view_after.get("store_cass_price")
            record["after_qpl_price"] = view_after.get("qpl_price")

            if ok:
                record["update_status"] = "成功"
                success_count += 1
                logger.info(
                    f"[{idx}/{len(both)}] product_id={product_id}, number={number} 更新成功"
                )
            else:
                record["update_status"] = "失败"
                fail_count += 1
                logger.warning(
                    f"[{idx}/{len(both)}] product_id={product_id}, number={number} 更新失败: {msg}"
                )

        except Exception as e:
            logger.exception(f"[{idx}/{len(both)}] product_id={product_id}, number={number} 处理异常")
            record["update_status"] = "失败"
            record["msg"] = f"异常: {e}"
            fail_count += 1

        both_records.append(record)
        time.sleep(REQUEST_DELAY)

    # 5. 生成 Excel 报告
    report_path = _build_report_path()

    fs_df = pd.DataFrame(fs_items)
    zh_df = pd.DataFrame(zh_items)
    both_df = pd.DataFrame(both_records)

    with pd.ExcelWriter(report_path, engine="openpyxl") as writer:
        fs_df.to_excel(writer, sheet_name="佛山有的", index=False)
        zh_df.to_excel(writer, sheet_name="珠海有的", index=False)
        both_df.to_excel(writer, sheet_name="都有的", index=False)

    logger.info(f"[CRM价格同步] 报告已保存: {report_path}")
    logger.info("=" * 80)
    logger.info(
        f"[CRM价格同步] 任务完成，成功 {success_count}，失败 {fail_count}，"
        f"价格为0跳过 {len(low_price_items)}"
    )
    logger.info("=" * 80)

    return {
        "total": len(both),
        "valid": len(valid_items),
        "success": success_count,
        "fail": fail_count,
        "low_price_count": len(low_price_items),
        "only_zhuhai_count": len(only_zhuhai),
        "only_foshan_count": len(only_foshan),
        "report_path": report_path,
    }
