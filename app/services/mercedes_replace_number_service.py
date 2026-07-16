# -*- coding: utf-8 -*-
"""
奔驰报价 OE 替换号自动同步主服务
"""

from datetime import date, timedelta
from typing import List

from app.services.report_wx_quote_data_services.weixin_decoding_result_clear import (
    fetch_data_and_save_to_database,
)
from app.utils.logger_config import get_task_logger
from app.utils.mercedes_replace_number.config import (
    DATE_OFFSET_DAYS,
    DEFAULT_COMPANY,
    TASK_NAME,
)
from app.utils.mercedes_replace_number.crm_client import update_oe_replace_numbers
from app.utils.mercedes_replace_number.data_source import collect_oe_codes
from app.utils.mercedes_replace_number.excel_exporter import export_update_records
from app.utils.mercedes_replace_number.mercedes_client import fetch_part_info
from app.utils.mercedes_replace_number.models import UpdateRecord
from app.utils.mercedes_replace_number.oe_processor import (
    build_oe_pairs,
    filter_valid_oe_codes,
)


logger = get_task_logger(TASK_NAME)


def run_mercedes_replace_number_sync(
    target_date: date = None,
    company: str = DEFAULT_COMPANY
) -> dict:
    """
    执行奔驰报价 OE 替换号自动同步任务。

    Args:
        target_date: 目标日期，默认前一天
        company: 公司代码，默认 fsbbr

    Returns:
        统计结果字典
    """
    if target_date is None:
        target_date = date.today() - timedelta(days=DATE_OFFSET_DAYS)

    date_str = target_date.strftime('%Y-%m-%d')
    logger.info(f"[{company}] 任务开始，目标日期: {date_str}")

    # 1. 更新源数据
    logger.info(f"[{company}] 开始更新 wechat_daily_quote_detail 数据")
    fetch_data_and_save_to_database(date_str, date_str)

    # 2. 收集 OE
    logger.info(f"[{company}] 开始收集 OE")
    raw_oe_codes = collect_oe_codes(target_date, company)

    # 3. 筛选有效 OE
    valid_oe_codes = filter_valid_oe_codes(raw_oe_codes)
    logger.info(f"[{company}] 有效 OE 数量: {len(valid_oe_codes)}")

    # 4. 分组
    oe_pairs = build_oe_pairs(valid_oe_codes)
    logger.info(f"[{company}] OE 对数量: {len(oe_pairs)}")

    # 5. 查询奔驰替换号并更新 CRM
    all_records: List[UpdateRecord] = []
    for idx, oe_pair in enumerate(oe_pairs, start=1):
        logger.info(
            f"[{company}] 处理 [{idx}/{len(oe_pairs)}] "
            f"{oe_pair.with_a} / {oe_pair.without_a}"
        )

        part_info = fetch_part_info(
            oe_pair.with_a,
            excluded_number=oe_pair.without_a
        )
        replace_numbers = part_info.get('replace_numbers', [])
        if not replace_numbers:
            logger.warning(f"[{company}] 未获取到替换号: {oe_pair.with_a}")
            continue

        records = update_oe_replace_numbers(company, oe_pair, replace_numbers)
        all_records.extend(records)

    # 6. 导出 Excel
    excel_path = export_update_records(all_records, target_date)

    success_count = sum(1 for r in all_records if r.status == '成功')
    failed_count = len(all_records) - success_count

    result = {
        'target_date': date_str,
        'company': company,
        'oe_total': len(oe_pairs),
        'record_total': len(all_records),
        'success_count': success_count,
        'failed_count': failed_count,
        'excel_path': excel_path,
    }

    logger.info(f"[{company}] 任务完成: {result}")
    return result
