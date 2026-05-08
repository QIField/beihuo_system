"""
批量渠道价格推送服务
用于在询价导入成功后，批量推送渠道价格到 BatchChannel
"""

from typing import List, Dict, Any
from app.utils.database_connection import get_db_connection
from app.utils.Batchchannel.api_client import batch_channel_request
from config.config_list_manager.config_cache import get_config_value


# 门店到 Cookie 配置的映射
COMPANY_COOKIE_MAP = {
    'fsbbr': 'data_gzbbr_com_fs'
    # 其他门店后续添加
}


def push_to_batch_channel(upload_success_items: List[Dict[str, Any]], company: str):
    """
    批量推送渠道价格

    Args:
        upload_success_items: 上传成功的数据列表，每项包含 oe 和 brand
        company: 门店代码
    """
    if not upload_success_items:
        print("[BatchChannel] 没有上传成功的数据，跳过推送")
        return

    # 1. 提取 OE+Brand 列表
    oe_brand_list = []
    for item in upload_success_items:
        oe = item.get('oe')
        brand = item.get('mapped_brand') or item.get('brand')
        if oe and brand:
            oe_brand_list.append((oe, brand))

    if not oe_brand_list:
        print("[BatchChannel] 没有有效的 OE+Brand 数据")
        return

    # 2. 批量查询 product_id
    product_ids = _query_product_ids(oe_brand_list, company)

    if not product_ids:
        print("[BatchChannel] 未找到任何 product_id")
        return

    # 3. 根据门店获取 Cookie
    if company not in COMPANY_COOKIE_MAP:
        print(f"[BatchChannel] 门店 {company} 暂无 Cookie 配置")
        return

    cookie = get_config_value(COMPANY_COOKIE_MAP[company])

    # 4. 打印请求信息
    print(f"[BatchChannel] 开始推送")
    print(f"[BatchChannel] 门店: {company}")
    print(f"[BatchChannel] 共 {len(product_ids)} 个 product_id: {product_ids}")

    # 5. 一次性批量调用 API
    response = batch_channel_request(product_ids, cookie)

    # 6. 打印完整响应
    print(f"[BatchChannel] 响应: {response}")


def _query_product_ids(oe_brand_list: List[tuple], company: str) -> List[str]:
    """
    批量查询 product_id

    Args:
        oe_brand_list: [(oe, brand), ...]
        company: 门店代码

    Returns:
        product_id 列表
    """
    if not oe_brand_list:
        return []

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 构建 (oe, brand) IN 条件
            placeholders = ', '.join(['(%s, %s)'] * len(oe_brand_list))
            params = []
            for oe, brand in oe_brand_list:
                params.extend([oe, brand])
            params.append(company)

            sql = f"""
                SELECT product_id
                FROM crmapp_compare_summary
                WHERE (oe, brand) IN ({placeholders})
                AND company = %s
                AND product_id IS NOT NULL
                AND product_id != ''
            """

            cursor.execute(sql, params)
            rows = cursor.fetchall()

            # 提取 product_id
            product_ids = []
            for row in rows:
                if isinstance(row, dict):
                    pid = row.get('product_id')
                else:
                    pid = row[0] if row else None

                if pid:
                    product_ids.append(str(pid))

            return product_ids
    finally:
        conn.close()
