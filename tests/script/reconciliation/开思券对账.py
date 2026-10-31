# coding:utf-8
"""
开思券对账.py —— 开思券对账（独立脚本）

输入：
  1. 开思券账单（Excel，首行即列名）
  2. 开思电子对账单（Excel，第 5 行为列名，第 6 行起数据）
  3. 订单结算明细（Excel，首行即列名）
  4. 金蝶应收单（Excel，首行即列名）

输出：
  开思券对账_YYYYMMDD_HHMM.xlsx
  sheet：开思券对账（主表）；有「只缺开思卷」行时附加「金蝶写入数据源」

以「开思券账单」为主表，按订单号聚合后：
  - 左连接「开思电子对账单」（列加「对账单-」前缀）
  - 左连接「订单结算明细」（列加「结算明细-」前缀）
  - 按 (客户代码, 价税合计) 与「应收单」严格 1:1 配对（列加「应收单-」前缀）
并按收款进度标识「对账状态」。

对账状态（仅「只缺开思卷」会进入「金蝶写入数据源」参与下推）：
  - 完全核销：金蝶已收款 = 价税合计
  - 只缺开思卷：金蝶已收款 = 价税合计 - 券
  - 未收款：金蝶已收款 ≈ 0
  - 人工核对：部分收款或未匹配到应收单

开思税金：
  开思税金 = 应收金额(￥) - 开思电子对账单的开思劵(¥)；
  电子对账单无此订单时该列为空。
"""
import os
import datetime

import pandas as pd


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = BASE_DIR
OUTPUT_DIR = os.path.join(BASE_DIR, "data")

# ---- 输入 1：开思券账单（主表） ----
COUPON_FILE_KEYWORD = "开思券账单"
COUPON_FILE_FALLBACK = "开思券账单.xlsx"
COUPON_KEY = "订单/退货单号"
COUPON_HEADER_ROW = 0

# ---- 输入 2：开思电子对账单 ----
STMT_FILE_KEYWORD = "开思电子对账单"
STMT_FILE_FALLBACK = "开思电子对账单.xlsx"
STMT_KEY = "订单/退货编号"
STMT_HEADER_ROW = 4

# ---- 输入 3：订单结算明细 ----
DETAIL_FILE_KEYWORD = "订单结算明细"
DETAIL_FILE_FALLBACK = "订单结算明细.xlsx"
DETAIL_KEY = "订单/退单编号"

# ---- 输入 4：金蝶应收单 ----
AR_FILE_KEYWORD = "应收单"
AR_FILE_FALLBACK = "应收单.xlsx"

OUTPUT_PREFIX = "开思券对账"

TOLERANCE = 0.01

# ---- 金蝶自动化 sheet 配置 ----
KINGDEE_SHEET = "金蝶写入数据源"
KINGDEE_STATUS_COLUMN = "是否写入金蝶"
KINGDEE_STATUS_DONE = "已写入金蝶"


# ==============================================================================
# 工具函数
# ==============================================================================

def _find_input_file(directory, keyword, fallback):
    """优先标准文件名，否则按关键字包含匹配首个 .xlsx（兼容带时间戳文件名）"""
    std = os.path.join(directory, fallback)
    if os.path.exists(std):
        return std
    try:
        for f in os.listdir(directory):
            if f.startswith("~$") or f.startswith("."):
                continue
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
    return pd.to_numeric(s, errors="coerce").fillna(0.0)


def _now_str():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M")


# ==============================================================================
# 读取三张表
# ==============================================================================

def read_coupon_bill(filepath):
    """读取开思券账单（首行即列名）"""
    df = pd.read_excel(filepath, sheet_name=0, header=COUPON_HEADER_ROW)
    df = df.dropna(how="all").copy()

    # 新版券账单把「开票类型」列改名为「需要发票」，值域不变（无需发票/不开票/已开票等），改回统一列名
    # （与 ks_process.py 对电子对账单「发票类型」→「需要发票」的处理一致）
    if "开票类型" not in df.columns and "需要发票" in df.columns:
        df = df.rename(columns={"需要发票": "开票类型"})

    required = [COUPON_KEY, "开票类型", "交易金额(￥)", "应收金额(￥)"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(f"券账单缺少字段 {missing}，实际列：{list(df.columns)}")

    df["_order_no"] = df[COUPON_KEY].map(_normalize_order_no)
    df["交易金额(￥)"] = _to_num(df["交易金额(￥)"]).round(2)
    df["应收金额(￥)"] = _to_num(df["应收金额(￥)"]).round(2)
    return df


def read_ks_statement(filepath):
    """读取开思电子对账单（第 5 行为列名）"""
    df = pd.read_excel(filepath, sheet_name=0, header=STMT_HEADER_ROW)
    df = df.dropna(how="all").copy()

    if STMT_KEY not in df.columns:
        raise KeyError(f"电子对账单缺少字段 '{STMT_KEY}'，实际列：{list(df.columns)}")

    df["_order_no"] = df[STMT_KEY].map(_normalize_order_no)

    for col in ["对账金额(¥)", "开思劵(¥)"]:
        if col in df.columns:
            df[col] = _to_num(df[col]).round(2)
    return df


def read_settle_detail(filepath):
    """读取订单结算明细（首行即列名）"""
    df = pd.read_excel(filepath, sheet_name=0, header=0)
    df = df.dropna(how="all").copy()

    if DETAIL_KEY not in df.columns:
        raise KeyError(f"订单结算明细缺少字段 '{DETAIL_KEY}'，实际列：{list(df.columns)}")

    df["_order_no"] = df[DETAIL_KEY].map(_normalize_order_no)

    if "平台已结算金额（¥）" in df.columns:
        df["平台已结算金额（¥）"] = _to_num(df["平台已结算金额（¥）"]).round(2)
    return df


def read_ar_data(filepath):
    """读取金蝶应收单列表（首行即列名，剔除合计行），计算开思客户代码。"""
    df = pd.read_excel(filepath, sheet_name=0, header=0)
    df = df.dropna(how="all").copy()

    required = ["单据编号", "客户编码", "价税合计", "已收款金额"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(f"应收单缺少字段 {missing}，实际列：{list(df.columns)}")

    ar = df[required].copy()
    ar = ar.dropna(subset=["单据编号"]).copy()

    for col in ("价税合计", "已收款金额"):
        ar[col] = pd.to_numeric(ar[col], errors="coerce")

    # 金蝶客户编码 -> 开思客户代码：取最后一个 '-' 之后的部分
    ar["开思客户代码"] = (
        ar["客户编码"].astype(str).str.strip().str.rsplit("-", n=1).str[-1].str.strip()
    )
    return ar


# ==============================================================================
# 计算与核对
# ==============================================================================

def _agg_by_order_no(df, key_cols, prefix):
    """
    按 _order_no 聚合，只保留 key_cols 中的列，并重命名为加 prefix 前缀。
    数值列求和，非数值列取第一个。
    """
    missing = [c for c in key_cols if c not in df.columns]
    if missing:
        raise KeyError(f"{prefix} 表缺少字段 {missing}，实际列：{list(df.columns)}")

    agg_dict = {}
    for col in key_cols:
        if pd.api.types.is_numeric_dtype(df[col]):
            agg_dict[col] = "sum"
        else:
            agg_dict[col] = "first"

    return (
        df.groupby("_order_no", as_index=False)
        .agg(agg_dict)
        .rename(columns={col: f"{prefix}{col}" for col in key_cols})
    )


def build_coupon_reconcile(coupon_path=None, stmt_path=None, detail_path=None, ar_path=None):
    """
    核心流程：
      1. 以开思券账单为主表，按订单号聚合；
      2. 电子对账单、订单结算明细分别按订单号聚合并加前缀；
      3. 按 (客户代码, 价税合计) 与应收单严格 1:1 配对；
      4. 按公式核对状态。
    """
    if coupon_path is None:
        coupon_path = _find_input_file(DATA_DIR, COUPON_FILE_KEYWORD, COUPON_FILE_FALLBACK)
    if stmt_path is None:
        stmt_path = _find_input_file(DATA_DIR, STMT_FILE_KEYWORD, STMT_FILE_FALLBACK)
    if detail_path is None:
        detail_path = _find_input_file(DATA_DIR, DETAIL_FILE_KEYWORD, DETAIL_FILE_FALLBACK)
    if ar_path is None:
        ar_path = _find_input_file(DATA_DIR, AR_FILE_KEYWORD, AR_FILE_FALLBACK)

    for p in (coupon_path, stmt_path, detail_path, ar_path):
        if not os.path.exists(p):
            raise FileNotFoundError(f"找不到输入文件：{p}")

    coupon = read_coupon_bill(coupon_path)
    stmt = read_ks_statement(stmt_path)
    detail = read_settle_detail(detail_path)
    ar_full = read_ar_data(ar_path)

    # ---- 主表：券账单聚合 ----
    coupon_agg = (
        coupon.groupby("_order_no", as_index=False)
        .agg({
            "开票类型": "first",
            "交易金额(￥)": "sum",
            "应收金额(￥)": "sum",
        })
    )

    # ---- 辅表 1：电子对账单 ----
    stmt_agg = _agg_by_order_no(
        stmt,
        ["客户名称", "客户代码", "对账金额(¥)", "开思劵(¥)"],
        "对账单-",
    )

    # ---- 辅表 2：订单结算明细 ----
    detail_agg = _agg_by_order_no(
        detail,
        ["平台已结算金额（¥）", "结算状态（含冻结）", "收款信息"],
        "结算明细-",
    )

    # ---- 主表左连接两张辅表 ----
    merged = coupon_agg.merge(stmt_agg, how="left", on="_order_no")
    merged = merged.merge(detail_agg, how="left", on="_order_no")

    # ---- 开思税金：应收金额(￥) - 对账单-开思劵(¥) ----
    # 电子对账单无此订单时开思劵为 NaN，税金保持 NaN（不按 0 处理，避免误判）
    merged["开思税金"] = (
        merged["应收金额(￥)"] - merged["对账单-开思劵(¥)"]
    ).round(2)

    # ---- 辅表 3：应收单严格 1:1 配对 ----
    # 价税合计 = 对账金额 + 开思劵；按 (客户代码, 价税合计) 分组，
    # 仅两侧数量一致的分组才配对（与 payment_bill.py 的 rule1 一致），
    # 组内开思按订单号、应收单按单据编号排序后一一对应。
    ar = ar_full.drop_duplicates(subset=["单据编号"]).copy()
    ar["价税合计"] = ar["价税合计"].round(2)

    merged["_price_total"] = (merged["对账单-对账金额(¥)"] + merged["对账单-开思劵(¥)"]).round(2)

    def _fmt_price(x):
        return f"{float(x):.2f}"

    merged["_match_key"] = (
        merged["对账单-客户代码"].fillna("").astype(str)
        + "|"
        + merged["_price_total"].map(_fmt_price, na_action="ignore")
    )
    ar["_match_key"] = (
        ar["开思客户代码"].astype(str) + "|" + ar["价税合计"].map(_fmt_price)
    )

    # rule1：仅两侧数量一致的分组参与配对
    ks_counts = merged.groupby("_match_key").size()
    ar_counts = ar.groupby("_match_key").size()
    counts = pd.concat([ks_counts, ar_counts], axis=1).fillna(0)
    counts.columns = ["ks", "ar"]
    balanced_keys = counts[counts["ks"] == counts["ar"]].index

    merged_balanced = merged[merged["_match_key"].isin(balanced_keys)].copy()
    ar_balanced = ar[ar["_match_key"].isin(balanced_keys)].copy()

    # 组内排序并生成配对序号
    merged_balanced = merged_balanced.sort_values(["_match_key", "_order_no"], kind="stable")
    ar_balanced = ar_balanced.sort_values(["_match_key", "单据编号"], kind="stable")
    merged_balanced["_pair"] = merged_balanced.groupby("_match_key", sort=False).cumcount()
    ar_balanced["_pair"] = ar_balanced.groupby("_match_key", sort=False).cumcount()

    # 1:1 配对
    merged_balanced = merged_balanced.merge(
        ar_balanced[["单据编号", "价税合计", "已收款金额", "_match_key", "_pair"]],
        on=["_match_key", "_pair"],
        how="left",
        suffixes=("", "_ar"),
    )
    merged_balanced = merged_balanced.rename(columns={
        "单据编号": "应收单-单据编号",
        "价税合计": "应收单-价税合计",
        "已收款金额": "应收单-已收款金额",
    })

    # 不平衡分组保持空值
    merged_unbalanced = merged[~merged["_match_key"].isin(balanced_keys)].copy()
    merged = pd.concat([merged_balanced, merged_unbalanced], ignore_index=True)

    # ---- 对账状态 ----
    def _make_reconcile_status(row):
        ar_paid = row.get("应收单-已收款金额")
        ar_total = row.get("应收单-价税合计")
        coupon = row.get("对账单-开思劵(¥)")

        # 能拿到应收单金额时才判断三种状态；拿不到（未匹配到应收单）也归到「其他」
        if pd.notna(ar_paid) and pd.notna(ar_total):
            paid = float(ar_paid)
            total = float(ar_total)

            if abs(paid - total) <= TOLERANCE:
                return "完全核销"
            if abs(paid - (total - float(coupon or 0))) <= TOLERANCE:
                return "只缺开思卷"
            if abs(paid) <= TOLERANCE:
                return "未收款"

        return "人工核对"

    merged["对账状态"] = merged.apply(_make_reconcile_status, axis=1)

    # ---- 整理列名与顺序 ----
    merged = merged.rename(columns={"_order_no": "订单/退货单号"})
    merged = merged.drop(
        columns=[c for c in ["_match_key", "_pair", "_price_total", "对账单-对账金额(¥)"] if c in merged.columns],
        errors="ignore",
    )

    final_cols = [
        "订单/退货单号",
        "开票类型",
        "交易金额(￥)",
        "应收金额(￥)",
        "对账单-客户名称",
        "对账单-客户代码",
        "对账单-开思劵(¥)",
        "开思税金",
        "应收单-单据编号",
        "应收单-价税合计",
        "应收单-已收款金额",
        "对账状态",
        "结算明细-平台已结算金额（¥）",
        "结算明细-结算状态（含冻结）",
        "结算明细-收款信息",
    ]
    existing_cols = [c for c in final_cols if c in merged.columns]
    return merged[existing_cols]


# ==============================================================================
# Excel 输出
# ==============================================================================

def save_coupon_reconcile(merged, push_df=None, output_path=None):
    """保存对账结果到 Excel（主 sheet + 可选的金蝶写入数据源 sheet）"""
    if output_path is None:
        output_path = _build_path(f"{OUTPUT_PREFIX}_{_now_str()}.xlsx")

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        merged.to_excel(writer, sheet_name="开思券对账", index=False)
        if push_df is not None and not push_df.empty:
            push_df.to_excel(writer, sheet_name=KINGDEE_SHEET, index=False)

    return output_path


# ==============================================================================
# 入口
# ==============================================================================

def main():
    merged = build_coupon_reconcile()

    # 仅「只缺开思卷」的行需要下推金蝶
    push_cols = [
        "应收单-单据编号",
        "订单/退货单号",
        "对账单-客户代码",
        "对账单-开思劵(¥)",
        "开票类型",
        "应收单-价税合计",
        "应收单-已收款金额",
    ]
    existing_push_cols = [c for c in push_cols if c in merged.columns]
    push_df = merged[merged["对账状态"] == "只缺开思卷"][existing_push_cols].copy()
    if not push_df.empty:
        push_df[KINGDEE_STATUS_COLUMN] = ""

    out_path = save_coupon_reconcile(merged, push_df)
    print(f"开思券对账完成：{out_path}")
    print(f"  总记录数：{len(merged)}")
    if not push_df.empty:
        print(f"  金蝶待写入：{len(push_df)} 行")


if __name__ == "__main__":
    main()
