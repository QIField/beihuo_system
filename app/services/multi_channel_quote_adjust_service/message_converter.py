"""
QQ 聊天消息转换器

职责：
- 读取 qq_chat_message 表中未转换的记录
- 根据发送对象匹配对应供应商解析策略
- 将发送内容作为搜索号码、回复内容作为搜索结果进行解析
- 价格大于 0 的结果写入 qq_chat_message_result 表
- 更新原消息转换状态
"""

import re
from typing import List, Dict, Any, Callable

from app.services.multi_channel_quote_adjust_service.message_parser import (
    parse_tenglong,
    parse_changsheng,
    parse_hengye,
    parse_deshang,
    parse_shengmin,
    parse_fengchi,
    parse_yuhe,
)
from app.services.multi_channel_quote_adjust_service.repository import (
    fetch_unconverted_qq_chat_messages,
    update_qq_chat_message_status,
    save_qq_chat_message_results,
)


# 发送对象 -> 解析函数 映射（策略模式）
SUPPLIER_STRATEGY: Dict[str, Callable[[List[str], str], List[Dict[str, str]]]] = {
    "广州腾隆-啊钿 报价秒回": parse_tenglong,
    "A广州昌盛-小杨": parse_changsheng,
    "aa.广州恒业-陈浩生": parse_hengye,
    "广州德上行-小吴": parse_deshang,
    "广州盛旻-庄晓婷": parse_shengmin,
    "广州丰驰-李小飞": parse_fengchi,
    "广州六友(玉和)-彬": parse_yuhe,
}

# 发送对象 -> 供应商简称 映射
SUPPLIER_NAME_MAP: Dict[str, str] = {
    "广州腾隆-啊钿 报价秒回": "腾隆",
    "A广州昌盛-小杨": "昌盛",
    "aa.广州恒业-陈浩生": "恒业",
    "广州德上行-小吴": "德上行",
    "广州盛旻-庄晓婷": "盛旻",
    "广州丰驰-李小飞": "丰驰",
    "广州六友(玉和)-彬": "玉和",
}


STATUS_CONVERTED = "已转换"
STATUS_NO_MATCH = "转换对象不符合"


def _extract_search_numbers(content: str) -> List[str]:
    """
    从发送内容中提取搜索号码列表。
    支持按行或逗号分隔，只保留含数字的非空字符串。
    """
    if not content:
        return []

    numbers = []
    for part in re.split(r"[\r\n,，]+", content):
        part = part.strip()
        if not part:
            continue
        if not re.search(r"\d", part):
            continue
        numbers.append(part)
    return numbers


def _is_valid_price(price: Any) -> bool:
    """校验价格是否有效且大于 0"""
    if price is None or price == "":
        return False
    try:
        return float(price) > 0
    except (ValueError, TypeError):
        return False


def convert_qq_chat_messages(limit: int = 100) -> Dict[str, Any]:
    """
    执行 QQ 聊天消息转换流程。

    Args:
        limit: 单次处理条数上限

    Returns:
        {
            "processed": int,      # 处理消息数
            "saved": int,          # 保存结果条数
            "no_match": int,       # 对象不匹配数
            "failed": int,         # 解析异常数
        }
    """
    messages = fetch_unconverted_qq_chat_messages(limit)

    processed = 0
    saved = 0
    no_match = 0
    failed = 0

    for msg in messages:
        message_id = msg.get("序号")
        supplier = msg.get("发送对象", "")
        search_content = msg.get("发送内容", "")
        reply_content = msg.get("回复内容", "")

        parser = SUPPLIER_STRATEGY.get(supplier)
        if not parser:
            update_qq_chat_message_status(message_id, STATUS_NO_MATCH)
            no_match += 1
            processed += 1
            continue

        search_numbers = _extract_search_numbers(search_content)
        if not search_numbers:
            update_qq_chat_message_status(message_id, STATUS_CONVERTED)
            processed += 1
            continue

        try:
            parsed_results = parser(search_numbers, reply_content or "")
        except Exception:
            failed += 1
            processed += 1
            continue

        supplier_name = SUPPLIER_NAME_MAP.get(supplier, supplier)

        result_rows = []
        for item in parsed_results:
            if not _is_valid_price(item.get("price")):
                continue
            result_rows.append({
                "chat_message_id": message_id,
                "supplier": supplier,
                "supplier_name": supplier_name,
                "search_oe": item.get("search_oe", ""),
                "result_oe": item.get("result_oe", ""),
                "price": item.get("price", 0),
                "brand": item.get("brand", ""),
            })

        if result_rows:
            save_qq_chat_message_results(result_rows)
            saved += len(result_rows)

        update_qq_chat_message_status(message_id, STATUS_CONVERTED)
        processed += 1

    return {
        "processed": processed,
        "saved": saved,
        "no_match": no_match,
        "failed": failed,
    }
