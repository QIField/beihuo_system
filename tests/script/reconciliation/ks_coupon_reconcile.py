# coding:utf-8
"""
ks_coupon_reconcile.py —— 开思券对账（独立脚本）

输入：
  1. 开思券账单（Excel，首行即列名）
  2. 开思电子对账单（Excel，第 5 行为列名，第 6 行起数据）

输出：
  开思券对账_YYYYMMDD_HHMM.xlsx
  仅含一个 sheet：
    - 开思券对账：以开思电子对账单为主表，仅保留「开思劵(¥) > 0」的行，找出
        1) 在券账单文件中不存在的订单；
        2) 与券账单券金额不一致的订单；
        3) 公式成立的对上订单。
      并写明状态。

状态：
    - 正常：有券且公式成立
    - 券账单无此订单：电子对账单有券，券账单无该订单
    - 券金额不一致：两边都有券，但开思劵(¥) 对不上
"""
import os
import datetime

import pandas as pd


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = BASE_DIR                            # 输入文件目录
OUTPUT_DIR = os.path.join(BASE_DIR, "data")    # 输出文件目录

COUPON_FILE_KEYWORD = "开思券账单"
COUPON_FILE_FALLBACK = "开思券账单.xlsx"
COUPON_KEY = "订单/退货单号"

STMT_FILE_KEYWORD = "开思电子对账单"
STMT_FILE_FALLBACK = "开思电子对账单.xlsx"
STMT_KEY = "订单/退货编号"
STMT_HEADER_ROW = 4

OUTPUT_PREFIX = "开思券对账"

TOLERANCE = 0.01


# ======================================================================
# 工具函数
# ======================================================================

def _find_input_file(directory, keyword, fallback):
    """优先标准文件名，否则按关键字包含匹配首个 .xlsx"""
    std = os.path.join(directory, fallback)
    if os.path.exists(std):
        return std
    try:
        for f in os.listdir(directory):
            if keyword in f and f.endswith(".xlsx"):
                return os.path.join(directory, f)
    except OSError:
        pass
    return std


def _build_path(filename):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    return os.path.join(OUTPUT_DIR, filename)


def _normalize_order_no(val):
    """规范化订单号：退货单取 '(' 之前的部分；空值返回空串"""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    s = str(val).strip()
    if "(" in s:
        s = s.split("(")[0].strip()
    return s


def _to_num(series):
    """金额列转数值：去掉 ¥/￥、逗号、空白，解析失败按 0"""
    s = series.astype(str).str.replace(r"[¥￥,，]", "", regex=True)
    s = s.str.replace(r"[\s\u00a0]", "", regex=True)
    return pd.to_numeric(s, errors="coerce").fillna(0.0)  # pyright: ignore[reportAttributeAccessIssue]


def _parse_rate(val):
    """解析税率字符串，如 '4.0%' -> 0.04；空/非法返回 0"""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return 0.0
    s = str(val).strip().replace("%", "")
    if s == "":
        return 0.0
    try:
        return float(s) / 100
    except ValueError:
        return None


def _now_str():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M")


# ======================================================================
# 读取两张表
# ======================================================================

def read_coupon_bill(filepath):
    """读取开思券账单（首行即列名）"""
    df = pd.read_excel(filepath, sheet_name=0, header=0)
    df = df.dropna(how="all").copy()
    if COUPON_KEY not in df.columns:
        raise KeyError(f"券账单缺少字段 '{COUPON_KEY}'，实际列：{list(df.columns)}")
    df["_order_no"] = df[COUPON_KEY].map(_normalize_order_no)
    return df


def read_ks_statement(filepath):
    """读取开思电子对账单（第 5 行为列名）"""
    df = pd.read_excel(filepath, sheet_name=0, header=STMT_HEADER_ROW)
    df = df.dropna(how="all").copy()
    if STMT_KEY not in df.columns:
        raise KeyError(f"电子对账单缺少字段 '{STMT_KEY}'，实际列：{list(df.columns)}")
    df["_order_no"] = df[STMT_KEY].map(_normalize_order_no)
    # 数值化金额列（避免字符串比较）；列不存在则跳过
    for col in ["对账金额(¥)", "开思劵(¥)", "平台已结算金额（¥）", "价税合计"]:
        if col in df.columns:
            df[col] = _to_num(df[col]).round(2)  # pyright: ignore[reportAttributeAccessIssue]
    return df


# ======================================================================
# 计算与核对
# ======================================================================

def build_coupon_reconcile(coupon_path=None, stmt_path=None):
    """
    核心流程：
      1. 以开思电子对账单为主表，按订单号聚合（金额列求和，其他列取首个）；
      2. 按订单号汇总券账单（券金额求和、税率取首个）；
      3. 仅保留「开思劵(¥) > 0」的行，并显示状态：
         - 正常：有券且公式成立；
         - 券账单无此订单：电子对账单有券，券账单无；
         - 券金额不一致：两边都有券，但开思劵(¥) 不一致。
      4. 返回有券的所有行。
    """
    if coupon_path is None:
        coupon_path = _find_input_file(DATA_DIR, COUPON_FILE_KEYWORD, COUPON_FILE_FALLBACK)
    if stmt_path is None:
        stmt_path = _find_input_file(DATA_DIR, STMT_FILE_KEYWORD, STMT_FILE_FALLBACK)

    for p in (coupon_path, stmt_path):
        if not os.path.exists(p):
            raise FileNotFoundError(f"找不到输入文件：{p}")

    coupon = read_coupon_bill(coupon_path)
    stmt = read_ks_statement(stmt_path)

    # ---- 电子对账单按订单号聚合 ----
    stmt_agg_dict = {}
    for col in stmt.columns:
        if col == "_order_no":
            continue
        if pd.api.types.is_numeric_dtype(stmt[col]):
            stmt_agg_dict[col] = "sum"
        else:
            stmt_agg_dict[col] = "first"
    stmt = stmt.groupby("_order_no", as_index=False).agg(stmt_agg_dict)

    # ---- 券账单计算列 ----
    coupon["_rate_raw"] = coupon["开思券税率"].map(_parse_rate)
    coupon["应收金额(￥)"] = _to_num(coupon["应收金额(￥)"]).round(2)  # pyright: ignore[reportAttributeAccessIssue]

    # ---- 按订单号汇总券账单 ----
    coupon_agg = (  # pyright: ignore[reportCallIssue]
        coupon.groupby("_order_no", as_index=False)
        .agg({"_rate_raw": "first", "应收金额(￥)": "sum"})
        .rename(columns={
            "_rate_raw": "开思券税率_券账单",
            "应收金额(￥)": "应收金额_券账单",
        })
    )

    # ---- 电子对账单为主，左连接券账单汇总 ----
    merged = stmt.merge(coupon_agg, how="left", on="_order_no")

    # ---- 生成状态列 ----
    # 所有行都显示状态；有券行按公式核对，无券行标记为正常
    # 核对公式：开思劵(¥) * (1 + 开思券税率) == 应收金额(￥)
    def _make_status(row):
        stmt_coupon = row.get("开思劵(¥)", 0)
        if pd.isna(stmt_coupon):
            stmt_coupon = 0.0
        stmt_coupon = float(stmt_coupon)

        if stmt_coupon <= 0.001:
            return "正常"

        bill_receivable = row.get("应收金额_券账单")
        if pd.isna(bill_receivable):
            return "券账单无此订单"

        rate = row.get("开思券税率_券账单")
        if pd.isna(rate):
            return "券金额不一致"

        multiplier = round(1 + float(rate), 2)
        expected_receivable = round(stmt_coupon * multiplier, 2)
        if abs(expected_receivable - float(bill_receivable)) > TOLERANCE:
            return "券金额不一致"

        return "正常"

    merged["状态"] = merged.apply(_make_status, axis=1)

    # 只保留「开思劵(¥) > 0」的行；无券行不显示
    merged = merged[merged["开思劵(¥)"] > 0.001].copy()

    # 删除临时辅助列
    merged = merged.drop(columns=[c for c in ["_order_no"] if c in merged.columns], errors="ignore")

    return merged


# ======================================================================
# Excel 输出
# ======================================================================

def save_coupon_reconcile(merged, output_path=None):
    """保存对账结果到 Excel（仅生成一个 sheet）"""
    if output_path is None:
        output_path = _build_path(f"{OUTPUT_PREFIX}_{_now_str()}.xlsx")

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:  # pyright: ignore[reportAbstractUsage]
        merged.to_excel(writer, sheet_name="开思券对账", index=False)

    return output_path


# ======================================================================
# 入口
# ======================================================================

def main():
    merged = build_coupon_reconcile()
    out_path = save_coupon_reconcile(merged)
    abnormal_count = len(merged[merged["状态"] != "正常"])
    print(f"开思券对账完成：{out_path}")
    print(f"  总记录数：{len(merged)}")
    print(f"  异常记录数：{abnormal_count}")


if __name__ == "__main__":
    main()
