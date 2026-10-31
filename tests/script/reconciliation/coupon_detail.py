# coding:utf-8
"""
coupon_detail.py —— 开思券明细处理模块

功能：
  1. 读取供应商账单/开思券明细文件（FZD*.xlsx）；
  2. 根据「模拟点击数据源」中有开思券（开思劵金额 ≠ 0）的订单，
     按规范化后的开思订单号关联，提取券明细；
  3. 输出「开思卷明细」sheet 数据，供 下推收款单.py 后续读取并写入金蝶。

输入文件：
  - 供应商账单 Excel（如 FZD260901014968(供应商账单)_1790644768921.xlsx）：
    第 6 行为字段行（header=5），包含「订单/退货编号」「开思劵金额(¥)」等列。

关联逻辑：
  - 模拟点击数据源中的「订单/退货编号-开思」与明细表中的「订单/退货编号」
    使用 ks_process._normalize_order_no 统一规范化后再关联；
  - 销售订单号两边一致；
  - 退货单：对账结果中为 "2608140099(订单:S2608140009562)" 格式，
    只取括号前的退货单号；明细表中为纯数字退货单号。

输出列：
  - 对账上下文列（单据编号-金蝶、客户代码-开思、订单/退货编号-开思、
    开思劵(¥)-开思 等）；
  - 原始券明细列（交易时间、零件号、商品名称、开思劵金额(¥)、小计(¥) 等）。
"""
import os

import pandas as pd

from ks_process import _normalize_order_no


# ======================================================================
# 参数与常量
# ======================================================================

DATA_DIR = os.path.dirname(os.path.abspath(__file__))

# 开思券明细输入文件：目前以 FZD 开头的供应商账单
COUPON_FILE_PREFIX = "FZD"
COUPON_FILE_FALLBACK = "FZD供应商账单.xlsx"

# 供应商账单第 6 行为字段行（pandas 0 基下标 = 5）
COUPON_HEADER_ROW = 5

# 明细表中的订单号列名
COUPON_ORDER_COL = "订单/退货编号"

# 需要从模拟点击数据源带到明细 sheet 的上下文列
COUPON_CONTEXT_COLS = [
    "单据编号-金蝶",
    "客户代码-开思",
    "客户编码-金蝶",
    "订单/退货编号-开思",
    "对账金额(¥)-开思",
    "平台已结算金额（¥）-开思",
    "平台未结算金额（¥）-开思",
    "开思劵(¥)-开思",
    "价税合计-金蝶",
    "已收款金额-金蝶",
    "结算时间-开思",
    "收款信息-开思",
    "销售组织-金蝶",
    "币别-金蝶",
    "业务类型-金蝶",
    "核销状态-金蝶",
    "发票类型-开思",
    "类型",
]

# 明细表中需要数值化的金额/数量列
COUPON_NUMERIC_COLS = [
    "数量",
    "单价(¥)",
    "开思劵金额(¥)",
    "商家优惠金额(¥)",
    "现付优惠金额(¥)",
    "小计(¥)",
]


# ======================================================================
# 工具函数
# ======================================================================

def _find_input_file(directory, prefix, fallback):
    """
    在目录中查找输入文件：优先标准文件名；否则按前缀匹配（兼容带时间戳/下载后缀的文件名）。
    """
    std = os.path.join(directory, fallback)
    if os.path.exists(std):
        return std
    try:
        for f in os.listdir(directory):
            if f.startswith(prefix) and f.endswith(".xlsx"):
                return os.path.join(directory, f)
    except OSError:
        pass
    return std


def _to_num(series):
    """把金额列安全转成数值（去掉 ¥/￥、千分位逗号、空白）"""
    s = series.astype(str).str.replace(r"[¥￥,，]", "", regex=True)
    s = s.str.replace(r"[\s\u00a0]", "", regex=True)
    return pd.to_numeric(s, errors="coerce").fillna(0.0)


# ======================================================================
# 读取券明细文件
# ======================================================================

def read_coupon_detail(filepath=None):
    """
    读取供应商账单/开思券明细 Excel。

    :param filepath: 可选，明细文件路径；默认从 DATA_DIR 按 FZD 前缀自动匹配
    :return: DataFrame（已数值化金额列，并附加规范化合并键 _merge_key）
    """
    if filepath is None:
        filepath = _find_input_file(DATA_DIR, COUPON_FILE_PREFIX, COUPON_FILE_FALLBACK)

    if not os.path.exists(filepath):
        raise FileNotFoundError(
            f"找不到开思券明细文件：{filepath}\n"
            f"请在 {DATA_DIR} 下放置以 '{COUPON_FILE_PREFIX}' 开头的供应商账单 xlsx 文件。"
        )

    df = pd.read_excel(filepath, sheet_name=0, header=COUPON_HEADER_ROW)
    df = df.dropna(how="all").copy()

    if COUPON_ORDER_COL not in df.columns:
        raise KeyError(
            f"开思券明细文件缺少字段「{COUPON_ORDER_COL}」，实际列：{list(df.columns)}"
        )

    # 数值化金额/数量列
    for col in COUPON_NUMERIC_COLS:
        if col in df.columns:
            df[col] = _to_num(df[col])

    # 规范化订单号作为关联键
    df["_merge_key"] = df[COUPON_ORDER_COL].map(_normalize_order_no)

    return df


# ======================================================================
# 生成「开思卷明细」sheet 数据
# ======================================================================

def build_coupon_detail_sheet(source_df, coupon_detail=None, coupon_path=None):
    """
    根据对账结果/模拟点击数据源，生成「开思卷明细」sheet 数据。

    只保留 source_df 中「开思劵(¥)-开思」不等于 0 的行，
    并按规范化后的开思订单号与券明细文件关联，返回所有匹配到的明细行。

    :param source_df: 对账结果 或 模拟点击数据源 DataFrame（已带 -开思/-金蝶 后缀列）
    :param coupon_detail: 可选，已读取的券明细 DataFrame；默认自动读取
    :param coupon_path: 可选，指定券明细文件路径
    :return: 供写入「开思卷明细」sheet 的 DataFrame；无数据时返回空 DataFrame
    """
    if source_df is None or source_df.empty:
        return pd.DataFrame()

    df = source_df.copy()

    coupon_col = "开思劵(¥)-开思"
    if coupon_col not in df.columns:
        # 兼容内部原列名
        coupon_col = "开思劵(¥)"
        if coupon_col not in df.columns:
            raise KeyError(
                f"source_df 缺少开思券列：尝试 '开思劵(¥)-开思' / '开思劵(¥)' 均失败；"
                f"实际列：{list(df.columns)}"
            )

    df[coupon_col] = pd.to_numeric(df[coupon_col], errors="coerce").fillna(0)
    df = df[df[coupon_col] != 0].copy()
    if df.empty:
        return pd.DataFrame()

    # 规范化订单号
    order_col = "订单/退货编号-开思"
    if order_col not in df.columns:
        order_col = "订单/退货编号"
        if order_col not in df.columns:
            raise KeyError(
                f"source_df 缺少订单号列：尝试 '订单/退货编号-开思' / '订单/退货编号' 均失败；"
                f"实际列：{list(df.columns)}"
            )
    df["_merge_key"] = df[order_col].map(_normalize_order_no)

    # 读取券明细
    if coupon_detail is None:
        coupon_detail = read_coupon_detail(coupon_path)

    # 取上下文列
    context_cols = [c for c in COUPON_CONTEXT_COLS if c in df.columns]

    merged = df[context_cols + ["_merge_key"]].merge(
        coupon_detail,
        on="_merge_key",
        how="inner",
        suffixes=("", "_明细"),
    )

    # 删除临时关联键
    merged = merged.drop(columns=[c for c in ["_merge_key"] if c in merged.columns])

    # 列顺序：上下文列在前，原始明细列在后
    detail_cols = [c for c in coupon_detail.columns if c != "_merge_key"]
    out_cols = context_cols + [c for c in detail_cols if c not in context_cols]
    return merged[[c for c in out_cols if c in merged.columns]]
