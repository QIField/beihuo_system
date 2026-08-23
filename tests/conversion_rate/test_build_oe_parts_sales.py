# -*- coding:utf-8 -*-
# @Time    : 2026/08/06
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : test_build_oe_parts_sales.py
# @Software: trae-cn

"""
OE零件销量表（oe_parts_sales）构建 - 服务层单元测试

测试范围（纯函数逻辑，无需数据库）：
1. _last_12_months：近12个月键列表生成（含跨年、格式、顺序）
2. _last_52_weeks：近52周范围生成（含周数、标签格式、范围计算）
3. _derive_fields：pandas 向量化派生统计字段（日均/月均/周标准差/月度JSON/周度JSON补0/多组合/零销量）
4. run_sync：主流程测试（mock DAO 层，不触库），涵盖正常/空数据/异常场景

运行方式：
    python -m tests.conversion_rate.test_build_oe_parts_sales
"""

import sys
import os
import json
import logging
from datetime import date, datetime

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(filename)s:%(lineno)d | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)


def create_logger():
    logger = logging.getLogger("stock_safe_test")
    logger.setLevel(logging.DEBUG)
    if logger.handlers:
        return logger
    log_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(filename)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)
    return logger


test_logger = create_logger()


try:
    from app.services.stock_safe_service.build_oe_parts_sales_service import (
        _last_12_months,
        _last_52_weeks,
        _derive_fields,
        run_sync,
        WEEK_COLUMNS,
    )
    test_logger.info("[成功] 导入测试模块")
except ImportError as e:
    test_logger.error(f"[失败] 导入模块失败: {e}")
    sys.exit(1)


# ==================== 测试辅助函数 ====================

def _build_row(number, brand_name, annual, this_year, last_year, month_values, week_values=None):
    """
    构造一条 DAO 聚合查询返回的记录

    Args:
        number: OE号
        brand_name: 品牌名
        annual: 近一年总净销量
        this_year: 当前自然年销量
        last_year: 上一自然年销量
        month_values: 长度 12 的列表，对应 month_1~month_12 各月净销量（从旧到新）
        week_values: 长度 52 的列表，对应 week_1~week_52 各周净销量（从旧到新），可选

    Returns:
        聚合记录字典
    """
    row = {
        "number": number, "brand_name": brand_name,
        "pdname": f"产品{number}", "frey_no": f"F{number}",
        "annual_sales_1y": annual,
        "sales_this_year": this_year,
        "sales_last_year": last_year,
    }
    for i, v in enumerate(month_values, 1):
        row[f"month_{i}"] = v
    if week_values is not None:
        for i, v in enumerate(week_values, 1):
            row[f"week_{i}"] = v
    return row


# ==================== _last_12_months 测试 ====================

def test_last_12_months_normal():
    """常规场景：含当月共12个月，从旧到新，格式 YYYY-MM"""
    months = _last_12_months(date(2026, 8, 6))
    assert len(months) == 12, f"应为12个月，实际{len(months)}"
    assert months[0] == "2025-09", f"首月应为2025-09，实际{months[0]}"
    assert months[-1] == "2026-08", f"末月应为2026-08，实际{months[-1]}"
    assert months == sorted(months), f"月份应递增，实际{months}"
    assert len(set(months)) == 12, "月份不应重复"
    print("[PASS] test_last_12_months_normal")


def test_last_12_months_january():
    """跨年场景：stat_date 为 1 月时，需回退到上一年"""
    months = _last_12_months(date(2026, 1, 15))
    assert len(months) == 12
    assert months[0] == "2025-02", f"首月应为2025-02，实际{months[0]}"
    assert months[-1] == "2026-01", f"末月应为2026-01，实际{months[-1]}"
    print("[PASS] test_last_12_months_january")


# ==================== _last_52_weeks 测试 ====================

def test_last_52_weeks_count():
    """应返回52个周范围，长度正确"""
    stat_date_ts = int(datetime(2026, 7, 31, 23, 59, 59).timestamp())
    ranges = _last_52_weeks(stat_date_ts)
    assert len(ranges) == 52, f"应为52周，实际{len(ranges)}"
    print("[PASS] test_last_52_weeks_count")


def test_last_52_weeks_order():
    """周范围从旧到新排列，时间戳递增"""
    stat_date_ts = int(datetime(2026, 7, 31, 23, 59, 59).timestamp())
    ranges = _last_52_weeks(stat_date_ts)
    # 验证从旧到新：start_ts 递增
    start_tss = [ws for ws, _, _ in ranges]
    assert start_tss == sorted(start_tss), "周范围应从旧到新排列"
    print("[PASS] test_last_52_weeks_order")


def test_last_52_weeks_boundary():
    """最新周（week_52）结束于 stat_date_ts，起始于 stat_date_ts - 6天"""
    stat_date_ts = int(datetime(2026, 7, 31, 23, 59, 59).timestamp())
    DAY_SECONDS = 86400
    ranges = _last_52_weeks(stat_date_ts)
    # 最新周（最后一个元素，week_52）
    last_ws, last_we, _ = ranges[-1]
    assert last_we == stat_date_ts, f"最新周结束应等于 stat_date_ts，实际{last_we}"
    assert last_ws == stat_date_ts - 6 * DAY_SECONDS, f"最新周起始应为 stat_date_ts-6天，实际{last_ws}"
    print("[PASS] test_last_52_weeks_boundary")


def test_last_52_weeks_oldest():
    """最旧周（week_1）起始于 stat_date_ts - 363天，结束于 stat_date_ts - 357天"""
    stat_date_ts = int(datetime(2026, 7, 31, 23, 59, 59).timestamp())
    DAY_SECONDS = 86400
    ranges = _last_52_weeks(stat_date_ts)
    # 最旧周（第一个元素，week_1）
    first_ws, first_we, _ = ranges[0]
    assert first_ws == stat_date_ts - 363 * DAY_SECONDS, f"最旧周起始应为 stat_date_ts-363天，实际{first_ws}"
    assert first_we == stat_date_ts - 357 * DAY_SECONDS, f"最旧周结束应为 stat_date_ts-357天，实际{first_we}"
    print("[PASS] test_last_52_weeks_oldest")


def test_last_52_weeks_label_unique():
    """52个周标签唯一，格式为 YYYY-MM-DD"""
    stat_date_ts = int(datetime(2026, 7, 31, 23, 59, 59).timestamp())
    ranges = _last_52_weeks(stat_date_ts)
    labels = [lbl for _, _, lbl in ranges]
    assert len(set(labels)) == 52, "周标签应唯一不重复"
    # 验证格式：YYYY-MM-DD，共10字符
    for lbl in labels:
        assert len(lbl) == 10, f"标签格式应为 YYYY-MM-DD，实际{lbl}"
    print("[PASS] test_last_52_weeks_label_unique")


# ==================== _derive_fields 测试 ====================

def test_derive_fields_normal():
    """派生字段计算：日均/月均/年销量/周标准差/月度JSON/周度JSON补0"""
    stat_date = date(2026, 8, 6)
    months = _last_12_months(stat_date)
    # 生成周标签
    stat_date_ts = int(datetime.combine(stat_date, datetime.max.time()).timestamp())
    weekly_tuples = _last_52_weeks(stat_date_ts)
    weekly_labels = [lbl for _, _, lbl in weekly_tuples]

    # 构造月度数据：三笔销量：2025-09(3), 2026-07(5), 2026-08(10)
    month_values = [0] * 12
    month_values[0] = 3    # 2025-09
    month_values[10] = 5   # 2026-07
    month_values[11] = 10  # 2026-08

    # 构造周度数据：最后1周（week_52）销量10，最后2周销量5，第一周销量3
    # 这样周数据总量与月数据一致：3+5+10=18
    week_values = [0] * 52
    week_values[0] = 3    # week_1（最旧周）
    week_values[50] = 5   # week_51
    week_values[51] = 10  # week_52（最新周）

    rows = [_build_row("E", "B", annual=18, this_year=15, last_year=3,
                       month_values=month_values, week_values=week_values)]

    records = _derive_fields(rows, stat_date, months, actual_days=365,
                             weekly_labels=weekly_labels)
    assert len(records) == 1, "应派生1条记录"
    rec = records[0]
    assert rec["number"] == "E" and rec["brand_name"] == "B"
    assert rec["annual_sales_1y"] == 18, "近一年总净销量应为 3+5+10"
    assert rec["avg_daily_sales_1y"] == round(18 / 365, 3)
    assert rec["avg_monthly_sales_1y"] == round(18 / 12, 3)
    assert rec["sales_this_year"] == 15, "今年销量应为 5+10"
    assert rec["sales_last_year"] == 3, "去年销量应为 3"

    # 月度JSON：近12个月键齐全，缺失月份补0，且与输入月度值一致
    monthly = json.loads(rec["monthly_sales_json"])
    assert len(monthly) == 12, "月度JSON应包含12个键"
    assert monthly["2026-08"] == 10
    assert monthly["2026-07"] == 5
    assert monthly["2025-09"] == 3
    assert monthly["2026-06"] == 0, "无销量月份应补0"

    # 周标准差：基于52周周销量计算（方案一：真实周标准差）
    import statistics
    expected_std = round(statistics.pstdev(week_values), 3)
    assert rec["sales_std_dev_1y"] == expected_std, \
        f"周标准差应为{expected_std}，实际{rec['sales_std_dev_1y']}"

    # 周度JSON：52周键齐全，缺失周补0，且与输入周度值一致
    weekly = json.loads(rec["weekly_sales_json"])
    assert len(weekly) == 52, "周度JSON应包含52个键"
    # 验证最近3周的值
    last_3_labels = weekly_labels[-3:]  # 最后3个标签
    weekly_vals = list(weekly.values())
    assert weekly_vals[-1] == 10, f"最新周应为10，实际{weekly_vals[-1]}"
    assert weekly_vals[-2] == 5, f"倒数第二周应为5，实际{weekly_vals[-2]}"
    assert weekly_vals[0] == 3, f"最旧周应为3，实际{weekly_vals[0]}"

    assert rec["stat_date"] == "2026-08-06"
    print("[PASS] test_derive_fields_normal")


def test_derive_fields_zero_sales():
    """零销量场景：所有月度和周度为0，各统计字段为0"""
    stat_date = date(2026, 8, 6)
    months = _last_12_months(stat_date)
    stat_date_ts = int(datetime.combine(stat_date, datetime.max.time()).timestamp())
    weekly_tuples = _last_52_weeks(stat_date_ts)
    weekly_labels = [lbl for _, _, lbl in weekly_tuples]

    rows = [_build_row("F", "B", annual=0, this_year=0, last_year=0,
                       month_values=[0] * 12, week_values=[0] * 52)]

    records = _derive_fields(rows, stat_date, months, actual_days=365,
                             weekly_labels=weekly_labels)
    rec = records[0]
    assert rec["annual_sales_1y"] == 0
    assert rec["avg_daily_sales_1y"] == 0.0
    assert rec["avg_monthly_sales_1y"] == 0.0
    assert rec["sales_std_dev_1y"] == 0.0
    monthly = json.loads(rec["monthly_sales_json"])
    assert all(v == 0 for v in monthly.values()), "零销量月份全部为0"
    weekly = json.loads(rec["weekly_sales_json"])
    assert all(v == 0 for v in weekly.values()), "零销量周度全部为0"
    assert len(weekly) == 52, "周度JSON应包含52个键"
    print("[PASS] test_derive_fields_zero_sales")


def test_derive_fields_multiple_keys():
    """多个 (number, brand_name) 组合派生多条记录"""
    stat_date = date(2026, 8, 6)
    months = _last_12_months(stat_date)
    stat_date_ts = int(datetime.combine(stat_date, datetime.max.time()).timestamp())
    weekly_tuples = _last_52_weeks(stat_date_ts)
    weekly_labels = [lbl for _, _, lbl in weekly_tuples]

    month_values = [0] * 12
    month_values[11] = 2  # 2026-08
    week_values = [0] * 52
    week_values[51] = 2  # 最新周
    rows = [
        _build_row("G1", "A", annual=2, this_year=2, last_year=0,
                   month_values=month_values, week_values=week_values),
        _build_row("G2", "A", annual=4, this_year=4, last_year=0,
                   month_values=month_values, week_values=week_values),
        _build_row("G1", "B", annual=6, this_year=6, last_year=0,
                   month_values=month_values, week_values=week_values),
    ]

    records = _derive_fields(rows, stat_date, months, actual_days=365,
                             weekly_labels=weekly_labels)
    assert len(records) == 3, "应为3个组合"
    keys = {(r["number"], r["brand_name"]) for r in records}
    assert ("G1", "A") in keys and ("G2", "A") in keys and ("G1", "B") in keys
    # 验证周度JSON存在
    for rec in records:
        weekly = json.loads(rec["weekly_sales_json"])
        assert len(weekly) == 52, "周度JSON应包含52个键"
    print("[PASS] test_derive_fields_multiple_keys")


def test_derive_fields_empty():
    """空输入应返回空列表"""
    stat_date = date(2026, 8, 6)
    months = _last_12_months(stat_date)
    stat_date_ts = int(datetime.combine(stat_date, datetime.max.time()).timestamp())
    weekly_labels = [lbl for _, _, lbl in _last_52_weeks(stat_date_ts)]
    records = _derive_fields([], stat_date, months, actual_days=365,
                             weekly_labels=weekly_labels)
    assert records == [], "空输入应返回空列表"
    print("[PASS] test_derive_fields_empty")


def test_derive_fields_monthly_json_alignment():
    """月度JSON键与 month_1~month_12 顺序严格对齐"""
    stat_date = date(2026, 8, 6)
    months = _last_12_months(stat_date)
    stat_date_ts = int(datetime.combine(stat_date, datetime.max.time()).timestamp())
    weekly_tuples = _last_52_weeks(stat_date_ts)
    weekly_labels = [lbl for _, _, lbl in weekly_tuples]

    # 构造每月不同值，验证 JSON 键值与 month 列一一对应
    month_values = list(range(1, 13))  # month_1=1, month_2=2, ..., month_12=12
    week_values = list(range(1, 53))  # week_1=1, week_2=2, ..., week_52=52
    rows = [_build_row("H", "B", annual=sum(month_values),
                       this_year=month_values[11], last_year=0,
                       month_values=month_values, week_values=week_values)]

    rec = _derive_fields(rows, stat_date, months, actual_days=365,
                         weekly_labels=weekly_labels)[0]
    monthly = json.loads(rec["monthly_sales_json"])
    for i, m in enumerate(months):
        assert monthly[m] == month_values[i], \
            f"月份{m}应为{month_values[i]}，实际{monthly[m]}"

    # 周度JSON键与 week_1~week_52 顺序严格对齐
    weekly = json.loads(rec["weekly_sales_json"])
    for i, lbl in enumerate(weekly_labels):
        assert weekly[lbl] == week_values[i], \
            f"周{lbl}应为{week_values[i]}，实际{weekly[lbl]}"
    print("[PASS] test_derive_fields_monthly_json_alignment")


def test_derive_fields_weekly_std_dev():
    """
    周标准差计算验证：构造已知周数据，验证 sales_std_dev_1y 计算结果

    验证场景：
    - 52周数据标准正态分布验证
    - 确认 sales_std_dev_1y = 周销量总体标准差（ddof=0）
    """
    import statistics
    stat_date = date(2026, 8, 6)
    months = _last_12_months(stat_date)
    stat_date_ts = int(datetime.combine(stat_date, datetime.max.time()).timestamp())
    weekly_tuples = _last_52_weeks(stat_date_ts)
    weekly_labels = [lbl for _, _, lbl in weekly_tuples]

    # 构造递增周数据：1, 2, 3, ..., 52
    week_values = list(range(1, 53))
    expected_std = round(statistics.pstdev(week_values), 3)

    rows = [_build_row("W", "B", annual=sum(week_values), this_year=sum(week_values),
                       last_year=0, month_values=[0] * 12,
                       week_values=week_values)]

    records = _derive_fields(rows, stat_date, months, actual_days=365,
                             weekly_labels=weekly_labels)
    rec = records[0]
    assert rec["sales_std_dev_1y"] == expected_std, \
        f"周标准差应为{expected_std}，实际{rec['sales_std_dev_1y']}"
    print("[PASS] test_derive_fields_weekly_std_dev")


# ==================== run_sync 测试 ====================

import app.services.stock_safe_service.build_oe_parts_sales_service as service


def test_run_sync_success():
    """
    正常流程：DB 聚合 → 派生 → TRUNCATE → 批量写入，返回完成状态

    验证点：
    - 各阶段依次执行，无异常抛出
    - aggregate_count 等于 DAO 返回行数
    - inserted_count 等于 batch_insert 返回行数
    - total_elapsed_time > 0（有实际耗时）
    - timestamp 为 int 类型
    """
    # 保存原始函数引用，用于 finally 恢复
    original_fetch = service.fetch_aggregated_sales
    original_truncate = service.truncate_table
    original_batch = service.batch_insert
    try:
        # 构造周数据：与月数据对齐
        week_values_1 = [0] * 52
        week_values_1[0] = 3    # week_1
        week_values_1[50] = 5   # week_51
        week_values_1[51] = 10  # week_52
        week_values_2 = [0] * 52
        week_values_2[51] = 5  # week_52
        # Mock DAO 聚合返回 2 条记录（含周数据）
        service.fetch_aggregated_sales = lambda *a, **k: [
            _build_row("E01", "B1", annual=18, this_year=15, last_year=3,
                       month_values=[3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 5, 10],
                       week_values=week_values_1),
            _build_row("E02", "B2", annual=5, this_year=5, last_year=0,
                       month_values=[0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 5],
                       week_values=week_values_2),
        ]
        # Mock TRUNCATE 为空操作
        service.truncate_table = lambda: None
        # Mock 批量写入返回写入行数（模拟成功插入）
        service.batch_insert = lambda rows, **k: len(rows)

        result = run_sync()
        assert result["status"] == "completed", f"应为 completed，实际 {result['status']}"
        assert result["aggregate_count"] == 2, f"应返回 2 个组合，实际 {result['aggregate_count']}"
        assert result["inserted_count"] == 2, f"应写入 2 行，实际 {result['inserted_count']}"
        assert result["total_elapsed_time"] > 0, "耗时应大于 0"
        assert isinstance(result["timestamp"], int), "时间戳应为 int"
    finally:
        # 恢复原始函数，不影响其他测试
        service.fetch_aggregated_sales = original_fetch
        service.truncate_table = original_truncate
        service.batch_insert = original_batch
    print("[PASS] test_run_sync_success")


def test_run_sync_empty_data():
    """
    空数据场景：DAO 返回空列表，应正常完成

    验证点：
    - 不抛出异常
    - aggregate_count = 0
    - inserted_count = 0
    """
    original_fetch = service.fetch_aggregated_sales
    original_truncate = service.truncate_table
    original_batch = service.batch_insert
    try:
        # Mock DAO 聚合返回空列表
        service.fetch_aggregated_sales = lambda *a, **k: []
        service.truncate_table = lambda: None
        service.batch_insert = lambda rows, **k: len(rows)

        result = run_sync()
        assert result["status"] == "completed", f"应为 completed，实际 {result['status']}"
        assert result["aggregate_count"] == 0, f"aggregate_count 应为 0，实际 {result['aggregate_count']}"
        assert result["inserted_count"] == 0, f"inserted_count 应为 0，实际 {result['inserted_count']}"
        assert result["total_elapsed_time"] > 0, "耗时应大于 0"
    finally:
        service.fetch_aggregated_sales = original_fetch
        service.truncate_table = original_truncate
        service.batch_insert = original_batch
    print("[PASS] test_run_sync_empty_data")


def test_run_sync_dao_failure():
    """
    DAO 异常场景：聚合查询抛出异常 → 应向上抛出

    验证点：
    - 异常被 run_sync 的 except 块捕获后重新抛出
    - 调用方感知到失败
    """
    original_fetch = service.fetch_aggregated_sales
    original_truncate = service.truncate_table
    original_batch = service.batch_insert
    try:
        # Mock DAO 聚合抛出异常
        service.fetch_aggregated_sales = lambda *a, **k: (_ for _ in ()).throw(
            RuntimeError("DB_CONNECTION_FAILED"))
        service.truncate_table = lambda: None
        service.batch_insert = lambda rows, **k: len(rows)

        try:
            run_sync()
            assert False, "应因 DAO 异常而抛出 RuntimeError"
        except RuntimeError as e:
            assert "DB_CONNECTION_FAILED" in str(e), "异常消息应透传"
    finally:
        service.fetch_aggregated_sales = original_fetch
        service.truncate_table = original_truncate
        service.batch_insert = original_batch
    print("[PASS] test_run_sync_dao_failure")





# ==================== 主测试函数 ====================

def _run_test(test_name: str, test_func) -> bool:
    """执行单个测试并捕获异常"""
    try:
        test_func()
        return True
    except AssertionError as e:
        test_logger.error(f"[失败] {test_name}: {e}")
        return False
    except Exception as e:
        test_logger.error(f"[异常] {test_name}: {e}")
        return False


def run_all_tests():
    test_logger.info("\n" + "=" * 80)
    test_logger.info("[开始] 运行 OE零件销量表 服务层单元测试套件")
    test_logger.info("=" * 80)

    test_cases = [
        ("_last_12_months 常规", test_last_12_months_normal),
        ("_last_12_months 跨年", test_last_12_months_january),
        ("_last_52_weeks 数量", test_last_52_weeks_count),
        ("_last_52_weeks 顺序", test_last_52_weeks_order),
        ("_last_52_weeks 最新周边界", test_last_52_weeks_boundary),
        ("_last_52_weeks 最旧周边界", test_last_52_weeks_oldest),
        ("_last_52_weeks 标签唯一性", test_last_52_weeks_label_unique),
        ("_derive_fields 派生计算", test_derive_fields_normal),
        ("_derive_fields 零销量", test_derive_fields_zero_sales),
        ("_derive_fields 多组合", test_derive_fields_multiple_keys),
        ("_derive_fields 空输入", test_derive_fields_empty),
        ("_derive_fields 月度JSON对齐", test_derive_fields_monthly_json_alignment),
        ("_derive_fields 周标准差验证", test_derive_fields_weekly_std_dev),
        ("run_sync 正常流程", test_run_sync_success),
        ("run_sync 空数据", test_run_sync_empty_data),
        ("run_sync DAO异常", test_run_sync_dao_failure),
    ]

    test_results = [(name, _run_test(name, func)) for name, func in test_cases]

    test_logger.info("\n" + "=" * 80)
    test_logger.info("[结束] 测试结果汇总")
    test_logger.info("=" * 80)

    passed = sum(1 for _, result in test_results if result)
    failed = len(test_results) - passed

    test_logger.info(f"\n测试总数: {len(test_results)}")
    test_logger.info(f"通过: {passed}")
    test_logger.info(f"失败: {failed}")

    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        test_logger.info(f"  {status} - {test_name}")

    if failed == 0:
        test_logger.info("\n🎉 所有测试通过！")
    else:
        test_logger.info("\n⚠️ 部分测试失败，请检查日志")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
