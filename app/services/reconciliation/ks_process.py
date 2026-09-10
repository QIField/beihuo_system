# coding:utf-8
"""
ks_process.py —— 开思电子对账单 数据合并模块

依据：
- 08_最终完整方案.md
- e:/Barbori/complete_project/AuditSoftware/d（表结构与合并规则）

当前只实现「开思数据合并」：
  主表「开思电子对账单」（Excel1）  ←左连接←  明细表「订单结算明细」（Excel2）
两个输入 Excel 和合并结果 Excel 都放在同一个相对目录 KS_DATA_DIR 下。
其余（对账判断、收款单生成等）后续再补。
"""
import os
import datetime

import pandas as pd


# ======================================================================
# 一、表结构与合并规则常量（依据 d 文件）
# ======================================================================

# ---- 输入/输出文件目录：两个开思 Excel 都放这里，结果也输出到这里 ----
# 以「本脚本文件位置」为基准定位 data 目录（脚本在 new_code/，data 在其上一级），
# 避免相对路径受「当前运行目录」影响而找不到文件。
KS_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "data")

# ---- 输入 1：主表 开思电子对账单（独立 Excel 文件） ----
# d 文件：第 5 行为列名，第 6 行起为数据行（第 1~4 行是账单抬头信息，跳过）
KS_STMT_FILE = "开思电子对账单.xlsx"
KS_STMT_HEADER_ROW = 4          # pandas 0 基下标 = Excel 第 5 行
KS_STMT_KEY = "订单/退货编号"    # 主表合并键（销售订单 / 退货单）

# ---- 输入 2：明细表 订单结算明细（独立 Excel 文件） ----
# d 文件：第 1 行为列名，第 2 行起为数据行
KS_DETAIL_FILE = "订单结算明细.xlsx"
KS_DETAIL_KEY = "订单/退单编号"  # 明细表合并键

# ---- 输出：合并结果文件（同样放到 KS_DATA_DIR，带时间戳避免覆盖） ----
KS_MERGED_FILE_PREFIX = "开思对账_合并结果"

# ---- 数据处理后保留的字段（依据 d6 文件） ----
# 前 11 个来自主表（开思电子对账单），后 5 个来自明细表（订单结算明细）
KS_KEEP_COLS = [
    "订单/退货编号",        # 主表合并键（明细表的订单/退单编号不保留）
    "单据类型",
    "发票类型",
    "支付方式",
    "客户名称",
    "客户代码",
    "下单人",
    "审核人",
    "交易时间",
    "对账金额(¥)",
    "开思劵(¥)",
    "平台已结算金额不含开思劵",   # 计算列 = 平台已结算金额（¥） - 开思劵(¥)
   #  以下来自明细表
    "结算时间",
    "出账时间",
    "平台已结算金额（¥）",
    "平台未结算金额（¥）",
    "结算状态（含冻结）",
]


# ======================================================================
# 二、工具函数
# ======================================================================

def _find_key_col(df, candidates, table_name):
    """
    在 df 中按候选列名定位合并键列。

    :param df: DataFrame
    :param candidates: 候选列名列表
    :param table_name: 表名（用于报错信息）
    :return: 实际命中的列名
    """
    for col in candidates:
        if col in df.columns:
            return col
    raise KeyError(
        f"[{table_name}] 未找到合并键列，候选：{candidates}；"
        f"实际列：{list(df.columns)}"
    )


def _normalize_order_no(val):
    """
    规范化「订单/退货编号」合并键（规则见 d 文件）：
      - 销售订单：两边同格式（如 "S2607300018613"），原样返回；
      - 退货单：主表为 "2607300191(订单:S2607300018801)" 复合格式，
        只取 "(" 之前的退货单号参与匹配；明细表为纯数字，原样返回；
      - 空值：返回空串（不参与匹配）。

    :param val: 原始编号（可能是 str / int / NaN）
    :return: 规范化后的合并键字符串
    """
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    s = str(val).strip()
    if "(" in s:
        s = s.split("(")[0].strip()   # 退货单：取括号前的退货单号
    return s


def _build_path(filename):
    """
    拼接 KS_DATA_DIR 下的完整路径，并确保目录存在。

    :param filename: 文件名
    :return: 完整路径
    """
    os.makedirs(KS_DATA_DIR, exist_ok=True)
    return os.path.join(KS_DATA_DIR, filename)


def _to_num(series):
    """
    把金额列安全转成数值。

    去掉 ¥/￥、千分位逗号、各种空白（含 Excel 常见的 U+00A0 不间断空格），
    解析失败（#N/A、纯文本等）按 0 处理，避免整列塌成 0 或报错。

    :param series: 金额 Series
    :return: float64 的 Series
    """
    s = series.astype(str).str.replace(r"[¥￥,，]", "", regex=True)
    s = s.str.replace(r"[\s\u00a0]", "", regex=True)
    return pd.to_numeric(s, errors="coerce").fillna(0.0)  # pyright: ignore[reportAttributeAccessIssue]


# ======================================================================
# 三、读取两张开思表
# ======================================================================

def read_ks_statement(filepath):
    """
    读取主表「开思电子对账单」（独立 Excel 文件，取第一个 sheet）。

    规则（d 文件）：第 5 行为列名，第 6 行起为数据行；
    第 1~4 行的账单抬头信息（账单编号/开思券总额等）不读入数据区。

    :param filepath: Excel 文件路径
    :return: DataFrame（多一列规范化合并键 _merge_key）
    """
    df = pd.read_excel(filepath, sheet_name=0, header=KS_STMT_HEADER_ROW)
    df = df.dropna(how="all").copy()          # 去掉全空行（分隔线等）
    key_col = _find_key_col(df, [KS_STMT_KEY], KS_STMT_FILE)
    df["_merge_key"] = df[key_col].map(_normalize_order_no)
    return df


def read_ks_settle_detail(filepath):
    """
    读取明细表「订单结算明细」（独立 Excel 文件，取第一个 sheet）。

    规则（d 文件）：第 1 行为列名，第 2 行起为数据行。

    :param filepath: Excel 文件路径
    :return: DataFrame（多一列规范化合并键 _merge_key）
    """
    df = pd.read_excel(filepath, sheet_name=0, header=0)
    df = df.dropna(how="all").copy()          # 去掉全空行
    key_col = _find_key_col(df, [KS_DETAIL_KEY], KS_DETAIL_FILE)
    df["_merge_key"] = df[key_col].map(_normalize_order_no)
    return df


def data_process(df):
    """
    数据处理：只保留 d6 文件指定的字段，其余列（含明细表订单/退单编号等）丢弃；
    并只保留「结算状态（含冻结）」为"已结算"的行。

    :param df: 合并后的 DataFrame
    :return: 只含 KS_KEEP_COLS 字段且已结算的 DataFrame
    """

     # 先计算新增列：平台已结算金额不含开思劵 = 平台已结算金额（¥） - 开思劵(¥)
    # 必须在字段校验之前算，因为 KS_KEEP_COLS 里包含这一列
    amount = _to_num(df["平台已结算金额（¥）"])
    coupon = _to_num(df["开思劵(¥)"])
    df["平台已结算金额不含开思劵"] = (amount - coupon).round(2)  # pyright: ignore[reportOperatorIssue]

    # 校验必保留字段在合并结果中都存在，避免静默丢列
    missing = [c for c in KS_KEEP_COLS if c not in df.columns]
    if missing:
        raise KeyError(f"合并结果缺少字段：{missing}")



    # 只保留结算状态 = 已结算 的行（空值/其他状态一律过滤掉）
    df = df[df["结算状态（含冻结）"] == "已结算"]

    return df[KS_KEEP_COLS]






# ======================================================================
# 四、合并主流程
# ======================================================================

def merge_ks_data(stmt_path=None, detail_path=None):
    """
    合并开思电子对账单（主表）与订单结算明细（明细表）。

    合并规则（依据 d 文件）：
      1. 开思电子对账单为主表 → 左连接，保留主表全部行；
      2. 合并键：主表「订单/退货编号」= 明细表「订单/退单编号」；
      3. 销售订单两边格式一致，直接相等；
      4. 退货单主表 "2607300191(订单:...)"，只取括号前退货单号匹配。

    重名且含义不同的列（如订单金额(¥) 与 订单金额（¥））用后缀 "_明细" 区分；
    规范化合并键 _merge_key 用后即删，不留在结果里。
    本函数只返回 DataFrame，不生成 Excel；Excel 输出在 __main__（调试用）。

    :param stmt_path: 可选，主表文件路径（默认从 KS_DATA_DIR 读取）
    :param detail_path: 可选，明细表文件路径（默认从 KS_DATA_DIR 读取）
    :return: 合并并处理后的 DataFrame（只含 KS_KEEP_COLS 且已结算的行）
    """
    # 输入文件路径（都在 KS_DATA_DIR 下）
    if stmt_path is None:
        stmt_path = _build_path(KS_STMT_FILE)
    if detail_path is None:
        detail_path = _build_path(KS_DETAIL_FILE)

    # 校验输入文件存在，便于定位问题
    for p in (stmt_path, detail_path):
        if not os.path.exists(p):
            raise FileNotFoundError(f"找不到输入文件：{p}")

    stmt = read_ks_statement(stmt_path)
    detail = read_ks_settle_detail(detail_path)

    merged = stmt.merge(
        detail,
        how="left",              # 主表为准，左连接
        on="_merge_key",         # 规范化后的合并键
        suffixes=("", "_明细"),  # 避免两边重名列冲突
    ).drop(columns=["_merge_key"])

    # 数据处理：只保留 d6 指定字段
    merged = data_process(merged)

    return merged


# if __name__ == "__main__":
#     # 调试用：单独运行本脚本时，才把合并结果输出为 Excel
#     result = merge_ks_data()
#     ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
#     out_path = _build_path(f"{KS_MERGED_FILE_PREFIX}_{ts}.xlsx")
#     result.to_excel(out_path, index=False)  # pyright: ignore[reportAttributeAccessIssue]
#     print(f"合并结果已输出：{out_path}")
#     print("合并完成，共", len(result), "行")
#     print("列：", list(result.columns))  # pyright: ignore[reportAttributeAccessIssue]
#     print(result.head(10).to_string())  # pyright: ignore[reportAttributeAccessIssue]
