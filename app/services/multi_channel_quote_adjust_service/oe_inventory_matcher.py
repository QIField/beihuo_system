"""
OE 匹配与库存查询

职责：
- 读取近 36 小时 multi_channel_quote_import 表的 oe
- 用 original_oe 匹配 replace_number_index 预处理表
- 用匹配到的 key 精确查询 virtual_inventory
- 将库存匹配结果写入 qq_chat_message_result
"""

import re
import time
from typing import List, Dict, Any, Set

from app.utils.logger_config import get_task_logger
from app.services.multi_channel_quote_adjust_service.repository import (
    fetch_unmatched_import_oes,
    fetch_replace_numbers,
    fetch_virtual_inventory_by_oes,
    save_qq_chat_message_results,
    mark_import_oes_matched,
    init_replace_number_index_table,
    clear_replace_number_index,
    batch_insert_replace_number_index,
    fetch_replace_index_by_keys,
    check_replace_number_index_empty,
)

logger = get_task_logger('multi_channel_quote_adjust')


def _normalize_replace_number_part(value: str) -> str:
    """
    替换号拆分项归一化。

    规则：
    - 去除首尾空格
    - 若以字母 A 或 a 开头，则去掉该首字母
    - 保留中间空格及所有非数字字符，不做额外删除
    """
    value = value.strip()
    if value and value[0].lower() == "a":
        value = value[1:]
    return value


def _remove_spaces(value: str) -> str:
    """
    仅去除空格（含制表符），保留连字符等其他所有字符。

    用于 OE 比对：空格可忽略，其余字符严格比对。
    """
    return "".join(ch for ch in value if ch not in (" ", "\t")).lower()


def _split_replace_number(replace_number: str) -> List[str]:
    """按逗号拆分替换号，过滤空项"""
    if not replace_number:
        return []
    return [part for part in re.split(r"[,，]", replace_number) if part.strip()]


def rebuild_replace_number_index() -> Dict[str, Any]:
    """
    重建 replace_number_index 预处理表。

    从 crmapp_compare_summary 全量读取并生成归一化索引。

    Returns:
        {"processed": int, "saved": int, "elapsed": float}
    """
    total_start = time.time()

    step_start = time.time()
    replace_rows = fetch_replace_numbers()
    logger.info("[重建索引] 加载替换号数据: 耗时 %.3fs, 条数 %d", time.time() - step_start, len(replace_rows))

    if not replace_rows:
        return {"processed": 0, "saved": 0, "elapsed": time.time() - total_start}

    step_start = time.time()
    index_rows: List[tuple] = []
    seen: Set[tuple] = set()
    for row in replace_rows:
        oe = row.get("oe", "")
        if not oe:
            continue
        replace_number = row.get("replace_number") or ""
        for part in _split_replace_number(replace_number):
            key = _remove_spaces(_normalize_replace_number_part(part))
            if not key:
                continue
            company = row.get("company", "")
            pair = (key, oe, company)
            if pair not in seen:
                seen.add(pair)
                index_rows.append(pair)
    logger.info("[重建索引] 生成索引行: 耗时 %.3fs, 行数 %d", time.time() - step_start, len(index_rows))

    step_start = time.time()
    init_replace_number_index_table()
    clear_replace_number_index()
    # 分批插入，每批 5000 条
    batch_size = 5000
    for i in range(0, len(index_rows), batch_size):
        batch = index_rows[i:i + batch_size]
        batch_insert_replace_number_index(batch)
    logger.info("[重建索引] 写入数据库: 耗时 %.3fs", time.time() - step_start)

    elapsed = time.time() - total_start
    logger.info("[重建索引] 总耗时 %.3fs, 源数据 %d 条, 索引行 %d 条", elapsed, len(replace_rows), len(index_rows))

    return {
        "processed": len(replace_rows),
        "saved": len(index_rows),
        "elapsed": elapsed,
    }


def _collect_matched_oes_from_db(original_oes: List[str], company: str = "") -> Dict[str, List[str]]:
    """
    通过 replace_number_index 表批量查询匹配的 OE。

    Args:
        original_oes: 原始 OE 列表
        company: 门店/公司代码

    Returns:
        {normalized_key: [oe_list, ...]}
    """
    keys = [_remove_spaces(oe) for oe in original_oes if _remove_spaces(oe)]
    if not keys:
        return {}

    rows = fetch_replace_index_by_keys(keys, company)
    result: Dict[str, List[str]] = {}
    for row in rows:
        key = row.get("normalized_key", "")
        oe = row.get("oe", "")
        if key and oe:
            result.setdefault(key, []).append(oe)
    return result


def _build_search_tasks(original_oe: str, matched_oe_list: List[str]) -> List[Dict[str, str]]:
    """
    将 original_oe 加入 matched_oe_list 后整体去重，生成搜索任务列表。

    每个任务元素：{"search_oe": original_oe, "match_key": key}
    search_oe 恒为 original_oe，match_key 用于实际查询 virtual_inventory。
    """
    search_keys: List[str] = []
    seen: Set[str] = set()

    for key in [original_oe] + matched_oe_list:
        if key and key not in seen:
            seen.add(key)
            search_keys.append(key)

    return [{"search_oe": original_oe, "match_key": key} for key in search_keys]


def match_oe_inventory(company: str = "", hours: int = 36) -> Dict[str, Any]:
    """
    执行 OE 匹配与库存查询流程。

    Args:
        company: 门店/公司代码
        hours: 查询最近 N 小时内的导入 OE

    Returns:
        {
            "processed": int,  # 处理的 original_oe 数量
            "saved": int,      # 写入 qq_chat_message_result 的条数
        }
    """
    total_start = time.time()

    step_start = time.time()
    original_oes = fetch_unmatched_import_oes(hours)
    logger.info("[匹配接口价格] 步骤1-获取未匹配OE: 耗时 %.3fs, 条数 %d", time.time() - step_start, len(original_oes))

    if not original_oes:
        logger.info("[匹配接口价格] 无未匹配OE，流程结束")
        return {"processed": 0, "saved": 0}

    # 检查预处理表是否为空，为空则自动重建
    if check_replace_number_index_empty():
        logger.info("[匹配接口价格] replace_number_index 表为空，自动重建索引...")
        rebuild_result = rebuild_replace_number_index()
        if rebuild_result["saved"] == 0:
            logger.info("[匹配接口价格] 索引重建后仍为空，流程结束")
            return {"processed": len(original_oes), "saved": 0}

    step_start = time.time()
    replace_index = _collect_matched_oes_from_db(original_oes, company)
    logger.info("[匹配接口价格] 步骤2-查询替换号索引(company=%s): 耗时 %.3fs, 命中 key %d 个", company or "全部", time.time() - step_start, len(replace_index))

    step_start = time.time()
    tasks: List[Dict[str, str]] = []
    for original_oe in original_oes:
        key = _remove_spaces(original_oe)
        matched = replace_index.get(key, [])
        tasks.extend(_build_search_tasks(original_oe, matched))
    logger.info("[匹配接口价格] 步骤3-OE匹配生成任务: 耗时 %.3fs, 任务数 %d", time.time() - step_start, len(tasks))

    if not tasks:
        mark_import_oes_matched(original_oes)
        logger.info("[匹配接口价格] 无匹配任务，已标记处理完成")
        return {"processed": len(original_oes), "saved": 0}

    step_start = time.time()
    match_keys = [task["match_key"] for task in tasks]
    inventory_rows = fetch_virtual_inventory_by_oes(match_keys)
    logger.info("[匹配接口价格] 步骤4-查询虚拟库存: 耗时 %.3fs, 返回条数 %d", time.time() - step_start, len(inventory_rows))

    step_start = time.time()
    inventory_by_key: Dict[str, List[Dict[str, Any]]] = {}
    for row in inventory_rows:
        key = row.get("oe_code", "")
        if key not in inventory_by_key:
            inventory_by_key[key] = []
        inventory_by_key[key].append(row)

    result_rows: List[Dict[str, Any]] = []
    for task in tasks:
        match_key = task["match_key"]
        for inv in inventory_by_key.get(match_key, []):
            result_rows.append({
                "chat_message_id": None,
                "supplier": "接口数据",
                "supplier_name": inv.get("supplier_name", ""),
                "search_oe": task["search_oe"],
                "result_oe": inv.get("oe_code", match_key),
                "price": inv.get("original_price", 0),
                "brand": inv.get("brand", ""),
            })
    logger.info("[匹配接口价格] 步骤5-组装结果: 耗时 %.3fs, 结果条数 %d", time.time() - step_start, len(result_rows))

    step_start = time.time()
    if result_rows:
        save_qq_chat_message_results(result_rows)
    logger.info("[匹配接口价格] 步骤6-写入结果表: 耗时 %.3fs", time.time() - step_start)

    step_start = time.time()
    mark_import_oes_matched(original_oes)
    logger.info("[匹配接口价格] 步骤7-标记已处理: 耗时 %.3fs", time.time() - step_start)

    logger.info("[匹配接口价格] 总耗时 %.3fs, 处理OE %d 条, 匹配结果 %d 条", time.time() - total_start, len(original_oes), len(result_rows))

    return {
        "processed": len(original_oes),
        "saved": len(result_rows),
    }
