# -*- coding: utf-8 -*-
"""
微信群聊图片解析业务服务
负责：提取待解析图片 -> 调用视觉模型 -> 清洗结果 -> 入库 -> 更新状态
"""

from datetime import datetime
from typing import List, Dict, Any, Optional

from app.dao.external_system_dao.wx_chat_image import get_pending_images, update_image_status
from app.models.orm_models.crmapp_price_inquiry_direct import CrmappPriceInquiryDirect
from app.services.ai_image_recognition.image_processor import image_processor
from app.utils.logger_config import get_task_logger
from app.utils.orm.session import orm_session


logger = get_task_logger('wx_chat_image_parse')


def _clean_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    清洗报价信息：移除价格为 0、为空或字段缺失的条目

    :param records: image_processor 返回的 records 列表
    :return: 清洗后的有效报价条目列表
    """
    valid_items = []
    for record in records or []:
        for item in record.get("报价信息", []):
            price = item.get("价格")
            oe = str(item.get("报价OE", "")).strip()
            brand = str(item.get("品质", "")).strip()
            if price in (None, "", 0, 0.0) or not oe or not brand:
                continue
            valid_items.append({
                "oe": oe,
                "brand": brand,
                "original_price": price,
            })
    return valid_items


def _save_direct_inquiries(
    session,
    items: List[Dict[str, Any]],
    supplier: str,
    source_file: str,
) -> None:
    """
    将清洗后的报价数据写入 crmapp_price_inquiry_direct

    :param session: 数据库会话
    :param items: 清洗后的报价条目列表
    :param supplier: 群名称，写入 supplier 字段
    :param source_file: 来源图片名称，写入 source_file 字段
    """
    now = datetime.now()
    for item in items:
        record = CrmappPriceInquiryDirect(
            oe=item["oe"],
            brand=item["brand"],
            supplier=supplier,
            original_price=item["original_price"],
            company="fsbbr",
            source_file=source_file,
            import_time=now,
        )
        session.add(record)


def parse_wx_chat_images(days: Optional[int] = 3) -> None:
    """
    微信群聊图片解析任务主入口

    流程：
    1. 查询状态为空的图片记录（默认近 3 天）
    2. 逐条调用 image_processor 进行视觉识别
    3. 清洗识别结果，移除价格为 0 的条目
    4. 将有效数据写入 crmapp_price_inquiry_direct
    5. 更新 wx_chat_image 状态（成功/失败）

    :param days: 只查询近 N 天的记录，传 None 表示不限制创建时间
    """
    logger.info("[wx_chat_image_parse] 任务开始")

    with orm_session() as session:
        pending_images = get_pending_images(session, days=days)

    total = len(pending_images)
    logger.info(f"[wx_chat_image_parse] 待处理图片数量: {total}")

    for image in pending_images:
        image_id = image["序号"]
        image_name = image["图片名称"]
        image_url = f"http://113.45.176.129:8001/static/wxImage/{image_name}"
        supplier = image.get("群名称", "")

        try:
            records = image_processor({"图片url": image_url})
        except Exception as e:
            logger.error(f"[wx_chat_image_parse] 图片识别异常 id={image_id}, name={image_name}: {e}")
            with orm_session() as session:
                update_image_status(session, image_id, "解析出错")
            continue

        try:
            valid_items = _clean_records(records)
            if valid_items:
                with orm_session() as session:
                    _save_direct_inquiries(session, valid_items, supplier, image_url)

            with orm_session() as session:
                update_image_status(session, image_id, "已解析")

            logger.info(f"[wx_chat_image_parse] id={image_id} 处理完成，导入 {len(valid_items)} 条")
        except Exception as e:
            logger.error(f"[wx_chat_image_parse] 数据保存异常 id={image_id}: {e}")
            with orm_session() as session:
                update_image_status(session, image_id, "解析出错")

    logger.info("[wx_chat_image_parse] 任务结束")
