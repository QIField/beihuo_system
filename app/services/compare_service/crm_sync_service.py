"""
CRM 产品数据同步服务（替换号对比专用）

用于在新建 CRM 产品档案后，把指定 OE 列表的最新数据从 CRM
同步到本地 crmapp_compare_summary 表，确保替换号对比基于最新数据。
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Tuple

from config import create_crm_session
from app.services.procurement_service.crawl_service import CRMDataCrawlService
from app.services.compare_service.compare_data_service import CompareDataService


CRM_PRODUCT_LIST_URL = 'https://crm.gzbbr.com/api/Product.Product/list'
MAX_WORKERS = 5
MAX_RETRY_ATTEMPTS = 3

_thread_local = threading.local()


def _sync_single_oe(oe: str, company: str, sessions: set, sessions_lock: threading.Lock) -> Tuple[str, int]:
    """
    同步单个 OE。

    Returns:
        (status, count)
        status: 'saved' | 'not_found' | 'failed'
        count: 成功保存的产品记录数
    """

    def _get_session():
        session = getattr(_thread_local, 'session', None)
        if session is None:
            session = create_crm_session(company)
            _thread_local.session = session
            with sessions_lock:
                sessions.add(session)
        return session

    crawler = CRMDataCrawlService(company)

    for attempt in range(MAX_RETRY_ATTEMPTS):
        try:
            session = _get_session()
            response = session.post(
                CRM_PRODUCT_LIST_URL,
                json={
                    'numberlist': oe,
                    'page': 1,
                    'limit': 200
                },
                timeout=60
            )
            response.raise_for_status()
            result = response.json()

            if result.get('status') != 200 and result.get('msg') != '操作成功':
                if attempt < MAX_RETRY_ATTEMPTS - 1:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                return 'failed', 0

            data_groups = result.get('data', {}).get('data', [])
            if not data_groups:
                return 'not_found', 0

            saved_count = 0
            for group in data_groups:
                for product in group.get('child', []):
                    try:
                        parsed = crawler.parse_product(product)
                        parsed['company'] = company
                        CompareDataService.upsert_by_oe_brand_company(parsed)
                        saved_count += 1
                    except Exception:
                        continue

            return ('saved', saved_count) if saved_count > 0 else ('not_found', 0)

        except Exception:
            _thread_local.session = None
            if attempt < MAX_RETRY_ATTEMPTS - 1:
                time.sleep(0.5 * (attempt + 1))
                continue
            return 'failed', 0


def sync_oe_list_from_crm(oe_list: List[str], company: str = 'fsbbr') -> Dict[str, Any]:
    """
    根据 OE 列表从 CRM 拉取最新产品数据，并同步到 crmapp_compare_summary 表。

    说明：
        - 每个 OE 单独调用 CRM 接口（numberlist 字段只传单个 OE）；
        - 5 个 OE 并发同步，提高性能；
        - 每个 OE 失败自动重试 2 次；
        - 保存该 OE 下所有品牌的产品数据；
        - 按 oe + brand + company 更新或插入。

    Args:
        oe_list: OE 号列表
        company: 门店/组织代码，默认 fsbbr

    Returns:
        {
            'total': 传入的唯一 OE 总数,
            'saved': 成功保存的产品记录数,
            'failed': 失败的 OE 数,
            'not_found': CRM 中无产品的 OE 数,
            'company': 组织代码
        }
    """
    if not oe_list:
        return {'total': 0, 'saved': 0, 'failed': 0, 'not_found': 0, 'company': company}

    unique_oes = []
    for oe in oe_list:
        oe = str(oe).strip()
        if oe and oe not in unique_oes:
            unique_oes.append(oe)

    total_oe = len(unique_oes)
    total_saved = 0
    total_failed = 0
    total_not_found = 0

    sessions = set()
    sessions_lock = threading.Lock()

    try:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_oe = {
                executor.submit(_sync_single_oe, oe, company, sessions, sessions_lock): oe
                for oe in unique_oes
            }

            for future in as_completed(future_to_oe):
                status, count = future.result()
                if status == 'saved':
                    total_saved += count
                elif status == 'not_found':
                    total_not_found += 1
                else:
                    total_failed += 1

    finally:
        for session in sessions:
            try:
                session.close()
            except Exception:
                pass

    return {
        'total': total_oe,
        'saved': total_saved,
        'failed': total_failed,
        'not_found': total_not_found,
        'company': company
    }
