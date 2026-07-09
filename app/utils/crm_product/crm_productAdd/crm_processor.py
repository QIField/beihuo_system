"""
CRM 产品处理核心逻辑

职责：
- 处理单个 OE（process_single_oe）
- 批量处理 items（process_items）
- 与 CRM 接口交互获取品牌、OE 信息、添加产品等
"""

import time
from typing import Callable, Dict, List, Optional

from .crm_brand_id import get_brand_list
from .crm_get_oe_link import get_oe_link
from .crm_Product_Add import add_product
from .crm_updateView import update_product_name_by_oe, update_brand_code_by_oe
from .excel_data_loader import find_brand_by_alias, find_product_name_by_oe, find_best_match_product
from .models import ProcessResult, ProcessStatus


CRM_BRAND_INDEX_URL = 'https://crm.gzbbr.com/api/Product.Brand/index'


def _retry_request(func: Callable, name: str, max_retries: int = 1):
    """
    带重试的请求包装器
    """
    for i in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            if i < max_retries:
                print(f"  {name} 请求失败，重试第 {i + 1} 次...")
                time.sleep(1)
            else:
                print(f"  {name} 请求失败: {e}")
                return None
    return None


def _save_result(db_manager, oe_number: str, brand: str, result: ProcessResult):
    """
    保存处理结果到数据库（数据库模式用）
    """
    if db_manager is None:
        return

    try:
        from .db_manager import update_msg_with_processed_result
        update_msg_with_processed_result(db_manager, oe_number, brand, _format_result_message(result))
    except Exception as e:
        print(f"更新数据库中 OE号 {oe_number} 和品牌 {brand} 的处理结果时出错: {e}")


def _format_result_message(result: ProcessResult) -> str:
    """
    将 ProcessResult 格式化为旧的字符串消息，兼容数据库模式
    """
    if result.status == ProcessStatus.SUCCESS:
        msg = f"成功 - product_id: {result.product_id}" if result.product_id else f"成功 - {result.message}"
    elif result.status == ProcessStatus.EXISTED:
        msg = f"已存在 - {result.message}"
    else:
        msg = f"失败 - {result.message}"

    if result.brand_code_updated:
        msg += " | brand_code更新成功"

    return msg


def _search_brand_id_by_name(session, headers: dict, brand_name: str) -> Optional[str]:
    """
    根据品牌名称从 CRM 查询品牌 ID
    """
    id_response = session.get(
        CRM_BRAND_INDEX_URL,
        params={'l_name_zh': brand_name},
        headers=headers,
        timeout=30
    )
    if id_response.status_code != 200:
        return None

    brand_list = id_response.json().get('data', {}).get('list', [])
    for brand_item in brand_list:
        if brand_item.get('l_name_zh') == brand_name:
            return brand_item.get('brand_id')
    return None


def _get_brand_id(session, brand: str) -> Optional[str]:
    """
    根据品牌名称获取品牌 ID，支持别名匹配
    """
    from config import get_auth_headers

    headers = get_auth_headers(session)

    # 直接匹配
    brand_id = _search_brand_id_by_name(session, headers, brand)
    if brand_id:
        return brand_id

    # 别名匹配
    corrected_brand = find_brand_by_alias(brand)
    if corrected_brand and corrected_brand != brand:
        return _search_brand_id_by_name(session, headers, corrected_brand)

    return None


def _get_oe_info(session, oe_number: str) -> Optional[dict]:
    """
    获取 OE 信息
    """
    return _retry_request(lambda: get_oe_link(oe_number, session), 'get_oe_link')


def _resolve_product_name(oe_number: str, oe_info: dict, product_df) -> Optional[str]:
    """
    解析产品名称：优先使用 CRM 返回，空则从 Excel 匹配
    """
    product_name = oe_info.get('product_name', '')
    if product_name:
        return product_name

    if product_df is not None:
        matched_name = find_product_name_by_oe(oe_number)
        if matched_name:
            return matched_name

    return None


def _add_product(session, oe_number: str, brand_id: str, product_name: str, oe_info: dict) -> dict:
    """
    调用 CRM 添加产品

    Returns:
        CRM 接口原始响应
    """
    vehicle_name = oe_info.get('vehicle_name', '')
    brand_name = oe_info.get('brand_name', '') or '其他'

    product_data = {
        'number': oe_number,
        'brand_id': brand_id,
        'l_name_zh': product_name,
        'l_name_zh_store': product_name,
        'cass_oebrand_name': brand_name,
        'l_model_zh': vehicle_name if vehicle_name else '暂无'
    }

    return _retry_request(lambda: add_product(product_data, session), 'crmProductAdd')


def _update_best_match_name(session, oe_number: str, brand: str, product_name: str):
    """
    使用最佳匹配名称更新产品
    """
    try:
        search_result = get_brand_list({'product_name': product_name}, session)
        if not search_result or search_result.get('status') != 200:
            return

        name_list = search_result.get('data', {}).get('name_list', [])
        if not name_list:
            return

        best_match = find_best_match_product(product_name, name_list)
        if not best_match:
            return

        matched_name = best_match.get('product_name', '')
        update_product_name_by_oe(session, oe_number, brand, matched_name)
    except Exception:
        pass


def process_single_oe(item: dict, product_df, alias_df, db_manager=None, session=None) -> ProcessResult:
    """
    处理单个 OE 号码（核心逻辑）

    Args:
        item: {oe_number, brand, brand_code?, mode}
        product_df: 产品数据 DataFrame
        alias_df: 别名数据 DataFrame（保留兼容，当前未使用）
        db_manager: 数据库管理器（数据库模式用）
        session: 已认证的 CRM session

    Returns:
        ProcessResult
    """
    oe_number = item['oe_number']
    brand = item['brand']
    brand_code = item.get('brand_code', '')
    is_three_column = item.get('mode') == 'three_column'

    # 步骤 1: 获取品牌 ID
    brand_id = _get_brand_id(session, brand)
    if not brand_id:
        result = ProcessResult(oe_number, ProcessStatus.FAILED, message=f"没有匹配到品牌ID: {brand}")
        _save_result(db_manager, oe_number, brand, result)
        return result

    # 步骤 2: 获取 OE 信息
    oe_info = _get_oe_info(session, oe_number)
    if not oe_info:
        result = ProcessResult(oe_number, ProcessStatus.FAILED, message='获取 OE 信息失败')
        _save_result(db_manager, oe_number, brand, result)
        return result

    # 步骤 3: 解析产品名称
    product_name = _resolve_product_name(oe_number, oe_info, product_df)
    if not product_name:
        result = ProcessResult(oe_number, ProcessStatus.FAILED, message='未找到产品名称')
        _save_result(db_manager, oe_number, brand, result)
        return result

    used_excel_name = not oe_info.get('product_name')

    # 步骤 4: 添加产品
    add_response = _add_product(session, oe_number, brand_id, product_name, oe_info)
    if not add_response:
        result = ProcessResult(oe_number, ProcessStatus.FAILED, message='添加产品请求失败')
        _save_result(db_manager, oe_number, brand, result)
        return result

    status = add_response.get('status')
    msg = add_response.get('msg', '')
    product_id = add_response.get('data')

    # 检查车型为空
    vehicle_name = oe_info.get('vehicle_name', '')
    if not vehicle_name or '车型不能为空' in msg or ('车型' in msg and '不能为空' in msg):
        result = ProcessResult(oe_number, ProcessStatus.FAILED, message=f"车型不能为空 | {msg}")
        _save_result(db_manager, oe_number, brand, result)
        return result

    # 步骤 5: 处理响应结果
    if status == 200:
        result = ProcessResult(oe_number, ProcessStatus.SUCCESS, product_id=str(product_id), message=msg)
    elif status == 201:
        if '该物料已关联当前组织' in msg:
            result = ProcessResult(oe_number, ProcessStatus.EXISTED, product_id=str(product_id) if product_id else None, message=msg)
        else:
            result = ProcessResult(oe_number, ProcessStatus.SUCCESS, product_id=str(product_id) if product_id else None, message=msg)
    else:
        result = ProcessResult(oe_number, ProcessStatus.FAILED, message=msg)
        _save_result(db_manager, oe_number, brand, result)
        return result

    # 步骤 6: 更新最佳匹配名称
    if used_excel_name:
        _update_best_match_name(session, oe_number, brand, product_name)

    # 步骤 7: 三列模式更新 brand_code
    if is_three_column and brand_code:
        update_result = update_brand_code_by_oe(session, oe_number, brand, brand_code)
        result.brand_code_updated = bool(update_result)

    _save_result(db_manager, oe_number, brand, result)
    return result


def process_items(items: List[dict], product_df, alias_df, session, progress_callback=None, progress_offset: int = 0, total_items: int = None) -> Dict[str, ProcessResult]:
    """
    统一批量处理 items

    Args:
        items: 待处理 item 列表
        product_df: 产品数据 DataFrame
        alias_df: 别名数据 DataFrame
        session: CRM session
        progress_callback: 进度回调函数(current, total, message)
        progress_offset: 进度偏移量（多工作表场景）
        total_items: 总项目数

    Returns:
        {oe_number: ProcessResult}
    """
    results = {}
    completed = 0
    total = len(items)
    overall_total = total_items if total_items is not None else total

    for item in items:
        oe_number = item['oe_number']

        try:
            result = process_single_oe(item, product_df, alias_df, session=session)
            results[oe_number] = result
        except Exception as e:
            result = ProcessResult(oe_number, ProcessStatus.FAILED, message=f"处理异常: {e}")
            results[oe_number] = result
            print(f"[失败] {oe_number}: {result.message}")

        completed += 1
        if completed % 10 == 0 or completed == total:
            print(f"进度: {completed}/{total}")

        if progress_callback:
            overall_progress = progress_offset + completed
            progress_callback(overall_progress, overall_total, f"已处理 {completed}/{total}")

    print(f"\n处理完成: {total} 条")
    return results
