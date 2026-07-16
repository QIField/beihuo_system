"""
直接添加替换号处理逻辑
"""

from concurrent.futures import ThreadPoolExecutor
from typing import List

from app.utils.replace_number.crm_api_client import (
    search_products_by_numberlist,
    update_product_numbers,
)
from app.utils.replace_number.excel_utils import (
    dedup_numbers,
    read_replace_number_excel,
    save_direct_result,
)
from app.utils.logger_config import get_task_logger
from .matcher import match_products, extract_brand_codes
from .models import ReplaceNumberRow


logger = get_task_logger('replace_number')


def _to_row_objects(raw_rows: List[dict]) -> List[ReplaceNumberRow]:
    """将原始字典转为 ReplaceNumberRow 对象"""
    return [
        ReplaceNumberRow(
            row_index=r["row_index"],
            oe=r["oe"],
            brand=r["brand"],
            new_numbers=r["new_numbers"],
        )
        for r in raw_rows
    ]


def _search_batch(company: str, rows: List[ReplaceNumberRow]):
    """批量搜索，线程内串行"""
    for row in rows:
        if not row.oe or not row.brand:
            row.status = "缺少字段"
            continue

        api_data = search_products_by_numberlist(company, row.oe)
        if api_data:
            row.brand_codes = extract_brand_codes(api_data)
            row.matched_products = match_products(api_data, row.oe, row.brand)
        if not row.matched_products:
            row.status = "未匹配到产品"


def _update_batch(company: str, rows: List[ReplaceNumberRow]):
    """批量更新，线程内串行"""
    for row in rows:
        if row.status:
            continue
        if not row.matched_products:
            row.status = "未匹配到产品"
            continue
        if not row.new_numbers:
            row.status = "缺少替换号"
            continue

        all_ok = True
        updated = []
        brand_codes = row.brand_codes or []

        for product in row.matched_products:
            merged = dedup_numbers(product.display_numbers + row.new_numbers)
            if brand_codes:
                merged = [n for n in merged if n not in brand_codes]
            if not merged:
                row.status = "替换号均被品牌编码过滤"
                all_ok = False
                continue

            response = update_product_numbers(company, product.product_id, merged)

            if response.get("status") == 200 or response.get("msg") == "操作成功":
                updated = merged
            else:
                all_ok = False
                row.status = f"更新失败: {response.get('msg', '未知错误')}"

        row.updated_numbers = updated
        if all_ok and not row.status:
            row.status = "更新成功"


def process_direct_replace_number(file_path: str, company: str, progress_callback=None) -> str:
    """
    直接添加替换号主入口

    Args:
        file_path: Excel 临时文件路径
        company: 公司代码
        progress_callback: 进度回调函数

    Returns:
        结果文件路径
    """
    logger.info(f"直接添加替换号开始: file={file_path}, company={company}")

    df, raw_rows = read_replace_number_excel(file_path)
    rows = _to_row_objects(raw_rows)

    mid = len(rows) // 2
    batches = [rows[:mid], rows[mid:]]

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(_search_batch, company, batch) for batch in batches]
        for future in futures:
            future.result()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(_update_batch, company, batch) for batch in batches]
        for future in futures:
            future.result()

    for r, raw in zip(rows, raw_rows):
        raw["matched_products"] = r.matched_products
        raw["updated_numbers"] = r.updated_numbers
        raw["status"] = r.status

    result_path = save_direct_result(file_path, df, raw_rows)
    logger.info(f"直接添加替换号完成: result={result_path}")
    return result_path
