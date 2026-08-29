# -*- coding: utf-8 -*-
"""
微信群聊图片解析业务服务
负责：提取待解析图片 -> 调用视觉模型 -> 清洗结果 -> 入库 -> 更新状态
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple

from app.dao.external_system_dao.wx_chat_image import get_pending_images, update_image_status
from app.models.orm_models.crmapp_price_inquiry_direct import CrmappPriceInquiryDirect
from app.services.ai_image_recognition.image_processor import image_processor
from app.utils.logger_config import get_task_logger
from app.utils.orm.session import orm_session


logger = get_task_logger('wx_chat_image_parse')

# 去重键：oe + 品牌 + 群 + 价格
DedupKey = Tuple[str, str, str, Decimal]


def _normalize_price(price: Any) -> Optional[Decimal]:
    """
    把价格规范化为 Decimal，便于去重键比较
    """
    if price in (None, "", 0, 0.0):
        return None
    try:
        return Decimal(str(price))
    except Exception:
        return None


def _build_dedup_key(oe: str, brand: str, supplier: str, price: Any) -> Optional[DedupKey]:
    """
    构建跨图片当天去重键
    """
    normalized_price = _normalize_price(price)
    if normalized_price is None:
        return None
    return (
        str(oe).strip().upper(),
        str(brand).strip().upper(),
        str(supplier).strip(),
        normalized_price,
    )


def _clean_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    清洗报价信息：
    - 移除价格为 0、为空或字段缺失的条目
    - 对同一张图片内的重复报价去重
    """
    valid_items = []
    seen: set = set()

    for record in records or []:
        for item in record.get("报价信息", []):
            price = item.get("价格")
            oe = str(item.get("报价OE", "")).strip().upper().lstrip("=")
            brand = str(item.get("品质", "")).strip().upper()

            if price in (None, "", 0, 0.0) or not oe or not brand:
                continue

            # 单图片内去重（不含 supplier，因为同一张图片来自同一个群）
            inner_key = (oe, brand, _normalize_price(price))
            if inner_key in seen:
                continue
            seen.add(inner_key)

            valid_items.append({
                "oe": oe,
                "brand": brand,
                "original_price": price,
            })

    return valid_items


def _load_existing_keys(session, task_date) -> set:
    """
    加载当天已入库的报价去重键集合
    """
    start = datetime.combine(task_date, datetime.min.time())
    end = start + timedelta(days=1)

    rows = session.query(
        CrmappPriceInquiryDirect.oe,
        CrmappPriceInquiryDirect.brand,
        CrmappPriceInquiryDirect.supplier,
        CrmappPriceInquiryDirect.original_price,
    ).filter(
        CrmappPriceInquiryDirect.import_time >= start,
        CrmappPriceInquiryDirect.import_time < end,
    ).distinct().all()

    keys = set()
    for oe, brand, supplier, price in rows:
        key = _build_dedup_key(oe, brand, supplier, price)
        if key:
            keys.add(key)

    return keys


def _save_direct_inquiries(
    session,
    items: List[Dict[str, Any]],
    supplier: str,
    existing_keys: set,
) -> int:
    """
    将清洗后的报价数据写入 crmapp_price_inquiry_direct，并做当天跨图片去重
    """
    now = datetime.now()
    inserted_count = 0

    for item in items:
        key = _build_dedup_key(item["oe"], item["brand"], supplier, item["original_price"])
        if key is None or key in existing_keys:
            continue

        existing_keys.add(key)

        record = CrmappPriceInquiryDirect(
            oe=item["oe"],
            brand=item["brand"],
            supplier=supplier,
            original_price=item["original_price"],
            company="fsbbr",
            source_file="询价群识别",
            import_time=now,
        )
        session.add(record)
        inserted_count += 1

    return inserted_count


def parse_wx_chat_images(days: Optional[int] = 3) -> None:
    """
    微信群聊图片解析任务主入口

    流程：
    1. 查询状态为空的图片记录（默认近 3 天）
    2. 加载当天已入库的去重键集合
    3. 逐条调用 image_processor 进行视觉识别
    4. 清洗识别结果并去重
    5. 将有效数据写入 crmapp_price_inquiry_direct
    6. 更新 wx_chat_image 状态（成功/失败）
    """
    logger.info("[wx_chat_image_parse] 任务开始")
    task_date = datetime.now().date()

    with orm_session() as session:
        pending_images = get_pending_images(session, days=days)
        existing_keys = _load_existing_keys(session, task_date)

    total = len(pending_images)
    logger.info(f"[wx_chat_image_parse] 待处理图片数量: {total}")

    for image in pending_images:
        image_id = image["序号"]
        image_name = image["图片名称"]
        supplier = str(image.get("群名称") or "").strip()

        try:
            records = image_processor({"图片名称": image_name})
        except Exception as e:
            logger.error(f"[wx_chat_image_parse] 图片识别异常 id={image_id}, name={image_name}: {e}")
            with orm_session() as session:
                update_image_status(session, image_id, "解析出错")
            continue

        try:
            valid_items = _clean_records(records)

            # 同一事务内完成写入 + 状态更新
            with orm_session() as session:
                inserted = _save_direct_inquiries(session, valid_items, supplier, existing_keys)
                update_image_status(session, image_id, "已解析")

            logger.info(f"[wx_chat_image_parse] id={image_id} 处理完成，导入 {inserted} 条")
        except Exception as e:
            logger.error(f"[wx_chat_image_parse] 数据保存异常 id={image_id}: {e}")
            with orm_session() as session:
                update_image_status(session, image_id, "解析出错")

    logger.info("[wx_chat_image_parse] 任务结束")
