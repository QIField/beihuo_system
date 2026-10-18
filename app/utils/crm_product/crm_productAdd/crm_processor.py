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
from .crm_updateView import update_brand_code, update_brand_code_by_oe
from .excel_data_loader import find_brand_by_alias
from .models import ProcessResult, ProcessStatus


CRM_BRAND_INDEX_URL = 'https://crm.gzbbr.com/api/Product.Brand/index'
CRM_PRODUCT_LIST_URL = 'https://crm.gzbbr.com/api/Product.Product/list'

# 需要 OE + 品牌同时精确匹配的品牌
ORIGINAL_BRANDS = {'原厂', '原厂国内4s件'}


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


def _search_brand_info_by_name(session, headers: dict, brand_name: str) -> Optional[tuple]:
    """
    根据品牌名称从 CRM 查询品牌信息

    Returns:
        (brand_id, 系统品牌名)，未匹配返回 None
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
            return (brand_item.get('brand_id'), brand_item.get('l_name_zh') or brand_name)
    return None


def _get_brand_id(session, brand: str, use_alias: bool = True) -> Optional[str]:
    """
    根据品牌名称获取品牌 ID，支持别名匹配
    """
    info = _get_brand_info(session, brand, use_alias)
    return info[0] if info else None


def _get_brand_info(session, brand: str, use_alias: bool = True) -> Optional[tuple]:
    """
    根据品牌名称获取品牌信息，支持别名匹配

    Returns:
        (brand_id, 系统品牌名)，未匹配返回 None
    """
    from config import get_auth_headers

    headers = get_auth_headers(session)

    # 直接匹配
    matched = _search_brand_info_by_name(session, headers, brand)
    if matched:
        return matched

    # 别名匹配
    if use_alias:
        corrected_brand = find_brand_by_alias(brand)
        if corrected_brand and corrected_brand != brand:
            return _search_brand_info_by_name(session, headers, corrected_brand)

    return None


def _query_product_list(session, oe_number: str) -> Optional[list]:
    """
    根据 OE 查询 CRM Product.Product/list，返回所有 (number, brand_name, product_id, brand_code) 组合
    """
    from config import get_auth_headers

    headers = get_auth_headers(session)
    response = session.get(
        CRM_PRODUCT_LIST_URL,
        params={'number': oe_number},
        headers=headers,
        timeout=30
    )
    if response.status_code != 200:
        return None

    response_data = response.json()
    if response_data.get('status') not in (200, 0) and response_data.get('msg') != '操作成功':
        return None

    data = response_data.get('data', {})
    data_list = data.get('data', []) if isinstance(data, dict) else data
    if not isinstance(data_list, list):
        return None

    items = []
    for item in data_list:
        if not isinstance(item, dict) or 'child' not in item:
            continue
        for child_item in item['child']:
            if isinstance(child_item, dict):
                items.append((
                    child_item.get('number', ''),
                    child_item.get('brand_name', ''),
                    child_item.get('product_id'),
                    child_item.get('brand_code', '')
                ))
    return items


def _find_existed_children(oe_number: str, brand: str, product_items: list) -> list:
    """
    查找 OE+品牌已存在于 CRM 中的所有产品条目。

    原厂 / 原厂国内4s件：必须 OE 和品牌同时精确匹配。
    其他品牌：只要品牌名在结果中出现过即视为已存在。

    Returns:
        所有匹配的 (number, brand_name, product_id, brand_code) 元组列表
    """
    if not product_items:
        return []

    if brand in ORIGINAL_BRANDS:
        return [item for item in product_items if item[0] == oe_number and item[1] == brand]

    return [item for item in product_items if item[1] == brand]


def _find_existed_child(oe_number: str, brand: str, product_items: list) -> Optional[tuple]:
    """
    查找 OE+品牌已存在于 CRM 中的第一条产品条目。

    Returns:
        匹配的 (number, brand_name, product_id, brand_code) 元组，不存在返回 None
    """
    children = _find_existed_children(oe_number, brand, product_items)
    return children[0] if children else None


def _is_product_existed_in_crm(oe_number: str, brand: str, product_items: list) -> bool:
    """
    判断 OE+品牌是否已存在于 CRM 中。
    """
    return _find_existed_child(oe_number, brand, product_items) is not None


def _get_oe_info(session, oe_number: str) -> Optional[dict]:
    """
    获取 OE 信息
    """
    return _retry_request(lambda: get_oe_link(oe_number, session), 'get_oe_link')


def _resolve_product_name(oe_number: str, oe_info: dict, product_df) -> Optional[str]:
    """
    解析产品名称：仅使用 CRM 返回
    """
    return oe_info.get('product_name') or None


def _add_product(session, oe_number: str, brand_id: str, product_name: str, oe_info: dict) -> dict:
    """
    调用 CRM 添加产品

    Returns:
        CRM 接口原始响应
    """
    vehicle_name = oe_info.get('vehicle_name', '')
    brand_name = oe_info.get('brand_name', '')

    product_data = {
        'number': oe_number,
        'brand_id': brand_id,
        'l_name_zh': product_name,
        'l_name_zh_store': product_name,
        'cass_oebrand_name': brand_name,
        'l_model_zh': vehicle_name
    }

    return _retry_request(lambda: add_product(product_data, session), 'crmProductAdd')


def process_single_oe(item: dict, product_df, alias_df, db_manager=None, session=None, use_brand_alias: bool = True) -> ProcessResult:
    """
    处理单个 OE 号码（核心逻辑）

    Args:
        item: {oe_number, brand, brand_code?, mode}
        product_df: 产品数据 DataFrame
        alias_df: 别名数据 DataFrame（保留兼容，当前未使用）
        db_manager: 数据库管理器（数据库模式用）
        session: 已认证的 CRM session
        use_brand_alias: 是否使用品牌别名映射

    Returns:
        ProcessResult
    """
    oe_number = item['oe_number']
    brand = item['brand']
    brand_code = item.get('brand_code', '')

    # 步骤 1: 获取品牌 ID
    brand_id = _get_brand_id(session, brand, use_alias=use_brand_alias)
    if not brand_id:
        result = ProcessResult(oe_number, ProcessStatus.FAILED, brand=brand, message=f"没有匹配到品牌ID: {brand}")
        _save_result(db_manager, oe_number, brand, result)
        return result

    # 步骤 1.5: 前置存在性校验
    product_items = _query_product_list(session, oe_number)
    if product_items is not None and _is_product_existed_in_crm(oe_number, brand, product_items):
        result = ProcessResult(oe_number, ProcessStatus.EXISTED, brand=brand, message='OE和品牌已存在于CRM中')
        _save_result(db_manager, oe_number, brand, result)
        return result

    # 步骤 2: 获取 OE 信息
    oe_info = _get_oe_info(session, oe_number)
    if not oe_info:
        result = ProcessResult(oe_number, ProcessStatus.FAILED, brand=brand, message='获取 OE 信息失败')
        _save_result(db_manager, oe_number, brand, result)
        return result

    # 步骤 3: 校验 OE 信息字段（产品名称 > 车型 > 原厂品牌）
    product_name = oe_info.get('product_name', '')
    if not product_name:
        result = ProcessResult(oe_number, ProcessStatus.FAILED, brand=brand, message='未返回产品名称')
        _save_result(db_manager, oe_number, brand, result)
        return result

    vehicle_name = oe_info.get('vehicle_name', '')
    if not vehicle_name:
        result = ProcessResult(oe_number, ProcessStatus.FAILED, brand=brand, message='未返回车型')
        _save_result(db_manager, oe_number, brand, result)
        return result

    brand_name = oe_info.get('brand_name', '')
    if not brand_name:
        result = ProcessResult(oe_number, ProcessStatus.FAILED, brand=brand, message='未返回原厂品牌')
        _save_result(db_manager, oe_number, brand, result)
        return result

    # 步骤 4: 添加产品
    add_response = _add_product(session, oe_number, brand_id, product_name, oe_info)
    if not add_response:
        result = ProcessResult(oe_number, ProcessStatus.FAILED, brand=brand, message='添加产品请求失败')
        _save_result(db_manager, oe_number, brand, result)
        return result

    status = add_response.get('status')
    msg = add_response.get('msg', '')
    product_id = add_response.get('data')

    # 步骤 5: 处理响应结果
    if status == 200:
        result = ProcessResult(oe_number, ProcessStatus.SUCCESS, brand=brand, product_id=str(product_id), message=msg)
    elif status == 201:
        if '该物料已关联当前组织' in msg:
            result = ProcessResult(oe_number, ProcessStatus.EXISTED, brand=brand, product_id=str(product_id) if product_id else None, message=msg)
        else:
            result = ProcessResult(oe_number, ProcessStatus.SUCCESS, brand=brand, product_id=str(product_id) if product_id else None, message=msg)
    else:
        result = ProcessResult(oe_number, ProcessStatus.FAILED, brand=brand, message=msg)
        _save_result(db_manager, oe_number, brand, result)
        return result

    # 步骤 6: 更新 brand_code（三列模式取文件品牌号 / 确认新建取实际更新品牌号）
    if brand_code and result.product_id:
        update_result = update_brand_code(session, result.product_id, brand_code)
        result.brand_code_updated = bool(update_result)

    _save_result(db_manager, oe_number, brand, result)
    return result


def process_items(items: List[dict], product_df, alias_df, session, progress_callback=None, progress_offset: int = 0, total_items: int = None, use_brand_alias: bool = True) -> Dict[str, ProcessResult]:
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
        use_brand_alias: 是否使用品牌别名映射

    Returns:
        {(oe_number, brand): ProcessResult}
    """
    results = {}
    completed = 0
    total = len(items)
    overall_total = total_items if total_items is not None else total

    for item in items:
        oe_number = item['oe_number']
        brand = item['brand']

        try:
            result = process_single_oe(item, product_df, alias_df, session=session, use_brand_alias=use_brand_alias)
            results[(oe_number, brand)] = result
        except Exception as e:
            result = ProcessResult(oe_number, ProcessStatus.FAILED, brand=brand, message=f"处理异常: {e}")
            results[(oe_number, brand)] = result
            print(f"[失败] {oe_number} {brand}: {result.message}")

        completed += 1
        if completed % 10 == 0 or completed == total:
            print(f"进度: {completed}/{total}")

        if progress_callback:
            overall_progress = progress_offset + completed
            progress_callback(overall_progress, overall_total, f"已处理 {completed}/{total}")

    print(f"\n处理完成: {total} 条")
    return results
