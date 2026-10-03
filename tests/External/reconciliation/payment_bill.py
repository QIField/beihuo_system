# coding:utf-8
"""
payment_bill.py —— 开思对账 重构第2步：开思 vs 金蝶应收单 按行合并（不聚合）

依据：
- 08_最终完整方案.md
- d / d6（开思表结构与合并规则）
- dd2（应收单「按列表引出」：第1行中文列名，最后一行"合计"需剔除）
- dd3（金蝶客户编码带前缀，开思代码取最后一个 '-' 之后的部分）

合并方式：客户代码 + 价格 完全匹配（内连接，不做聚合）。三值等值校验：
  - 开思侧价格 = 对账金额(¥)
  - 开思侧还需满足：对账金额(¥) == 平台已结算金额（¥）
  - 金蝶侧价格 = 价税合计
  - 只有「对账金额(¥) == 平台已结算金额（¥）== 价税合计」三者相等才算符合

输出 3 个 sheet：
  1) 合并数据   ：两侧按 (客户代码, 价格) 内连接命中，且三值相等的行
  2) 开思剩下   ：开思侧没进合并的行（含规则排除）
  3) 金蝶剩下   ：金蝶侧没进合并的行（含规则排除）

合并前先执行规则（两侧各自独立判断）：
  规则1：同一客户代码下相同价格，开思与金蝶行数一致（两两/三三…）即可直接对账，
         仅两侧行数不一致（无法配对）时该部分排除，进「剩下」
  规则2：金蝶核销状态非空 → 不参与合并，直接进「金蝶剩下」（核销状态为空的单元格填"空"）
  规则3：开思 对账金额(¥) != 平台已结算金额（¥） → 进「开思剩下」
"""
import datetime
import os

import pandas as pd

from ks_process import merge_ks_data, KS_KEEP_COLS


# ======================================================================
# 一、参数与常量
# ======================================================================

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")

AR_FILE = "应收单.xlsx"   # 应收单「按列表引出」文件（dd2 结构）

# ---- 开思合并结果列（与 ks_process 输出对齐） ----
KS_COL_CUSTOMER = "客户代码"
KS_COL_PRICE = "对账金额(¥)"        # 开思侧参与合并的价格
KS_COL_SETTLED = "平台已结算金额（¥）"  # 开思侧需与对账金额相等才合并

# ---- 应收单列：输出中文列名 -> 文件里实际的列名（dd2） ----
AR_COL_MAP = {
    "单据编号": "单据编号",
    "客户编码": "客户编码",
    "币别": "币别",
    "价税合计": "价税合计",
    "已收款金额": "已收款金额",
    "收款组织": "收款组织",
    "结算组织": "结算组织",
    "销售组织": "销售组织",
    "业务类型": "业务类型",
    "核销状态": "表头基本 - 收款核销状态",   # 规则2：只处理核销状态为空的行
}

# ---- 输出统一保留的列 ----
MERGED_OUT_COLS = [
    "客户代码", "客户编码", "开思客户代码", "单据编号",
    "对账金额(¥)", "平台已结算金额（¥）", "开思劵(¥)", "价税合计", "已收款金额",
    "收款组织", "结算组织", "销售组织", "币别", "业务类型", "核销状态",
]
KS_OUT_COLS = KS_KEEP_COLS + ["剩余原因"]   # 开思剩下
AR_OUT_COLS = [                              # 金蝶剩下
    "单据编号", "客户编码", "开思客户代码", "币别", "价税合计", "已收款金额",
    "收款组织", "结算组织", "销售组织", "业务类型", "核销状态", "剩余原因",
]

OUT_MERGED_PREFIX = "开思对账_行合并"


def _data_path(filename):
    """拼接 DATA_DIR 下的完整路径"""
    os.makedirs(DATA_DIR, exist_ok=True)
    return os.path.join(DATA_DIR, filename)


# ======================================================================
# 二、工具函数
# ======================================================================

def _to_ks_cust_code(series):
    """
    金蝶客户编码 → 开思客户代码。
    金蝶编码带前缀（如 FOSBBR-FOS-C0388775 / FOSBBR- C0420381），
    开思代码 = 取最后一个 '-' 之后的部分并去空白（C0388775）。
    """
    s = series.astype(str).str.strip()
    return s.str.rsplit("-", n=1).str[-1].str.strip()


def _balanced_keys(ks_df, ar_df, ks_key_cols, ar_key_cols):
    """
    判断哪些 (客户, 价格) 分组在开思与金蝶两侧数量一致（可两两对账）。

    规则1（放宽版）：同一客户下相同价格出现多次时，只要开思与金蝶该分组的
    行数相同（两两、三三……均可互相配对），就视为符合可直接对账；
    只有当两侧行数不一致（如开思 2 条对金蝶 3 条）时才因无法配对而被排除。

    :param ks_df: 开思侧 DataFrame
    :param ar_df: 金蝶侧 DataFrame
    :param ks_key_cols: 开思分组的 [客户代码, 价格] 列
    :param ar_key_cols: 金蝶分组的 [客户代码, 价格] 列
    :return: set —— 两侧数量一致（允许对账）的分组键集合
    """
    ks_cnt = ks_df.groupby(ks_key_cols).size()
    ar_cnt = ar_df.groupby(ar_key_cols).size()
    fmt = lambda idx: ["|".join(map(str, t)) for t in idx]  # 键格式化成字符串
    kd = dict(zip(fmt(ks_cnt.index), ks_cnt.values))
    ad = dict(zip(fmt(ar_cnt.index), ar_cnt.values))
    all_keys = set(kd) | set(ad)
    # 只有开思与金蝶行数相等的分组才保留（允许 1:1、两两、三三…）
    return {k for k in all_keys if kd.get(k, 0) == ad.get(k, 0)}


def _keep_cols(df, cols):
    """只保留指定列（缺失的列忽略，避免报错）"""
    return df[[c for c in cols if c in df.columns]]


# ======================================================================
# 三、读应收单列表（dd2：单行中文表头，最后一行为合计需剔除）
# ======================================================================

def read_ar_data(filepath):
    """
    读取应收单「按列表引出」文件。
    - 第 1 行为中文列名，第 2 行起为数据；
    - 最后一行「合计」单据编号为空 → 剔除；
    - 只保留 AR_COL_MAP 用到的列（键即输出中文列名）。
    """
    df = pd.read_excel(filepath)
    # 校验所需列都存在
    miss = [c for c in AR_COL_MAP.values() if c not in df.columns]
    if miss:
        raise KeyError(f"应收单列表缺少字段：{miss}")
    # 只取所需列，列名 = AR_COL_MAP 的键（中文）
    ar = pd.DataFrame({k: df[v] for k, v in AR_COL_MAP.items()})
    # 剔除「合计」行（单据编号为空）
    ar = ar.dropna(subset=["单据编号"]).copy()
    # 金额转数值（标准数据，仅最简转换）
    for k in ("价税合计", "已收款金额"):
        ar[k] = pd.to_numeric(ar[k], errors="coerce")
    # 生成开思客户代码（金蝶编码取最后一个 '-' 之后的部分）
    ar["开思客户代码"] = _to_ks_cust_code(ar["客户编码"])
    return ar


# ======================================================================
# 四、规则过滤 + 行级内连接合并
# ======================================================================

def build_merge_result(ks=None):
    """
    开思 vs 金蝶应收单 按 (客户代码, 价格) 行级内连接合并（不聚合）。
    三值相等才算符合：开思对账金额(¥) == 开思平台已结算金额（¥）== 金蝶价税合计。
    合并前执行：
      规则1 同客户同价格，两侧行数一致才配对，不一致 → 排除进「剩下」
      规则2 金蝶核销状态非空 → 直接进「金蝶剩下」
      规则3 开思对账金额 != 平台已结算金额 → 直接进「开思剩下」
    :param ks: 可选，预加载的开思合并数据（默认调用 ks_process.merge_ks_data()）
    :return: (merged, ks_rest, ar_rest) 三个 DataFrame
    """
    # 1) 开思数据
    if ks is None:
        ks = merge_ks_data()
    ks[KS_COL_PRICE] = pd.to_numeric(ks[KS_COL_PRICE], errors="coerce").round(2)      # pyright: ignore[reportAttributeAccessIssue, reportArgumentType]
    ks[KS_COL_SETTLED] = pd.to_numeric(ks[KS_COL_SETTLED], errors="coerce").round(2)  # pyright: ignore[reportAttributeAccessIssue, reportArgumentType]

    # 2) 金蝶应收单
    ar = read_ar_data(_data_path(AR_FILE))
    ar["价税合计"] = ar["价税合计"].round(2)

    # ---- 规则2：核销状态非空 → 不参与合并，直接进「金蝶剩下」 ----
    wx_blank = ar["核销状态"].isna() | (ar["核销状态"].astype(str).str.strip() == "空")
    ar_rest_rule2 = ar[~wx_blank].copy()
    ar_rest_rule2["剩余原因"] = "核销状态非空，不参与合并"
    ar_keep = ar[wx_blank].copy()

    # ---- 规则3：开思 对账金额 != 平台已结算金额 → 进「开思剩下」 ----
    # 三值相等的前提是开思侧两个金额也相等，否则无法匹配金蝶价税合计
    price_eq = ks[KS_COL_PRICE] == ks[KS_COL_SETTLED]
    ks_rest_rule3 = ks[~price_eq].copy()
    ks_rest_rule3["剩余原因"] = "开思对账金额 != 平台已结算金额，排除"
    ks = ks[price_eq].copy()

    # ---- 规则1：同客户同价格重复 —— 仅当两侧数量一致才可两两对账，否则排除 ----
    # 开思与金蝶同一个 (客户, 价格) 分组行数相同（1:1/两两/三三…）即可配对；
    # 行数不一致（如开思 2 条对金蝶 3 条）无法确定配对关系 → 整组排除。
    bal_key = _balanced_keys(
        ks, ar_keep,
        [KS_COL_CUSTOMER, KS_COL_PRICE],
        ["开思客户代码", "价税合计"],
    )
    ks_gkey = ks[KS_COL_CUSTOMER] + "|" + ks[KS_COL_PRICE].astype(str)
    ar_gkey = ar_keep["开思客户代码"] + "|" + ar_keep["价税合计"].astype(str)
    ks_keep_mask = ks_gkey.isin(bal_key)  # pyright: ignore[reportAttributeAccessIssue]  # pyright: ignore[reportAttributeAccessIssue]
    ar_keep_mask = ar_gkey.isin(bal_key)  # pyright: ignore[reportAttributeAccessIssue]
    ks_rest_rule1 = ks[~ks_keep_mask].copy()
    ks_rest_rule1["剩余原因"] = "同客户同价格两侧数量不一致，无法配对，排除"
    ar_rest_rule1 = ar_keep[~ar_keep_mask].copy()
    ar_rest_rule1["剩余原因"] = "同客户同价格两侧数量不一致，无法配对，排除"
    ks_keep = ks[ks_keep_mask].copy()
    ar_keep = ar_keep[ar_keep_mask].copy()

    # ---- 合并键：客户代码|价格（保留2位小数，避免浮点误差） ----
    ks_keep["_key"] = ks_keep[KS_COL_CUSTOMER] + "|" + ks_keep[KS_COL_PRICE].astype(str)
    ar_keep["_key"] = ar_keep["开思客户代码"] + "|" + ar_keep["价税合计"].astype(str)

    # ---- 内连接合并 ----
    merged = ks_keep.merge(ar_keep, on="_key", how="inner")  # pyright: ignore[reportArgumentType, reportAttributeAccessIssue]

    # ---- 剩下的数据 = 规则排除 + 合并未匹配 ----
    ks_rest_merge = ks_keep[~ks_keep["_key"].isin(merged["_key"])].copy()  # pyright: ignore[reportAttributeAccessIssue]
    ks_rest_merge["剩余原因"] = "合并后未匹配上（金蝶无对应）"
    ar_rest_merge = ar_keep[~ar_keep["_key"].isin(merged["_key"])].copy()  # pyright: ignore[reportAttributeAccessIssue]
    ar_rest_merge["剩余原因"] = "合并后未匹配上（开思无对应）"

    ks_rest = pd.concat([ks_rest_rule3, ks_rest_rule1, ks_rest_merge], ignore_index=True)  # pyright: ignore[reportCallIssue, reportArgumentType]
    ar_rest = pd.concat([ar_rest_rule2, ar_rest_rule1, ar_rest_merge], ignore_index=True)  # pyright: ignore[reportCallIssue, reportArgumentType]
    return merged, ks_rest, ar_rest


# ---- 核销状态为"部分"的金蝶行：单独对账（本函数暂时不调用，是否启用待定） ----
# 业务口径：
#   金蝶侧部分核销的单（核销状态="部分"），其未收款部分 = 价税合计 - 已收款金额；
#   拿它和开思的 平台已结算金额（¥） 对账。
# 前提：先取「开思剩下 + 金蝶剩下」里 开思对账金额 == 金蝶价税合计 的行作候选，
#       再判断 金蝶(价税合计 - 已收款金额) == 开思平台已结算金额（¥） 才算符合。
def build_partial_reconcile(ks_rest, ar_rest):
    """
    对核销状态为"部分"的金蝶行做二次对账（可选用，暂未在主流程调用）。

    参数沿用 build_merge_result 产出的「开思剩下 / 金蝶剩下」两个 DataFrame，
    只用其中有「核销状态 == 部分」的金蝶行与开思剩下的行比对。

    :param ks_rest: build_merge_result 返回的「开思剩下」
    :param ar_rest: build_merge_result 返回的「金蝶剩下」
    :return: (matched, ks_unmatched, ar_unmatched) 三值对账结果（本函数不做 Excel 输出）
    """
    # 只取核销状态为"部分"的金蝶行，其余保持不动
    ar_part = ar_rest[ar_rest["核销状态"].astype(str).str.strip() == "部分"].copy()

    if ar_part.empty:
        # 没有"部分"行，直接返回空结果
        return (
            pd.DataFrame(),
            ks_rest.copy(),
            ar_rest.copy(),
        )

    # 金额统一 > 数值并补齐 2 位小数
    for col in ("对账金额(¥)", "平台已结算金额（¥）"):
        ks_rest[col] = pd.to_numeric(ks_rest[col], errors="coerce").round(2)  # pyright: ignore[reportIndexIssue, reportCallIssue, reportAttributeAccessIssue, reportArgumentType]
    for col in ("价税合计", "已收款金额"):
        ar_part[col] = pd.to_numeric(ar_part[col], errors="coerce").round(2)  # pyright: ignore[reportIndexIssue, reportCallIssue, reportAttributeAccessIssue, reportArgumentType]

    # 金蝶侧未收款部分 = 价税合计 - 已收款金额
    ar_part["未收款金额"] = (ar_part["价税合计"] - ar_part["已收款金额"]).round(2)  # pyright: ignore[reportOperatorIssue, reportIndexIssue]

    # 前提：开思对账金额 == 金蝶价税合计（对账金额对得上，才谈得上"未收款是否等于平台已结算"）
    prer = ks_rest.merge(
        ar_part,
        left_on=[KS_COL_CUSTOMER, KS_COL_PRICE],
        right_on=["开思客户代码", "价税合计"],
        how="inner",
        suffixes=("_开思", "_金蝶"),
    )
    matched_prer = prer[prer["对账金额(¥)_开思"] == prer["价税合计"]]  # 前提校验

    # 三值/两值相等：金蝶(价税合计 - 已收款金额) == 开思平台已结算金额（¥）
    predicted = matched_prer[
        matched_prer["未收款金额"] == matched_prer["平台已结算金额（¥）_开思"]
    ].copy()  # pyright: ignore[reportCallIssue]

    return predicted, ks_rest.copy(), ar_part.copy()


# ======================================================================
# 五、主流程（输出3个 sheet，只保留统一列）
# ======================================================================

# if __name__ == "__main__":
#     merged, ks_rest, ar_rest = build_merge_result()
#     m_out = _keep_cols(merged, MERGED_OUT_COLS)
#     ks_out = _keep_cols(ks_rest, KS_OUT_COLS)
#     ar_out = _keep_cols(ar_rest, AR_OUT_COLS)

#     ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
#     out_path = _data_path(f"{OUT_MERGED_PREFIX}_{ts}.xlsx")
#     with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
#         m_out.to_excel(writer, sheet_name="合并数据", index=False)
#         ks_out.to_excel(writer, sheet_name="开思剩下", index=False)
#         ar_out.to_excel(writer, sheet_name="金蝶剩下", index=False)

#     print(f"合并结果已输出：{out_path}")
#     print(f"合并数据 {len(m_out)} 行；开思剩下 {len(ks_out)} 行；金蝶剩下 {len(ar_out)} 行")
#     if len(ks_out):
#         print("开思剩下-原因：", ks_out["剩余原因"].value_counts().to_dict())
#     if len(ar_out):
#         print("金蝶剩下-原因：", ar_out["剩余原因"].value_counts().to_dict())



