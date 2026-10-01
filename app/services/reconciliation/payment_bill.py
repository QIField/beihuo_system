# coding:utf-8
"""
payment_bill.py —— 开思对账：开思 vs 金蝶应收单 按行合并（不聚合）

依据：
- 08_最终完整方案.md
- d / d6（开思表结构与合并规则）
- dd2（应收单「按列表引出」：第1行中文列名，最后一行"合计"需剔除）
- dd3（金蝶客户编码带前缀，开思代码取最后一个 '-' 之后的部分）

对账规则（核心前提）：
  对账金额(¥) + 开思劵(¥) = 价税合计

合并方式：客户代码 + 价税合计（=对账金额+开思劵） 完全匹配（内连接，不做聚合）。

金蝶应收单新结构（主表+明细，见 demo/t1）：
  一张应收单含多条明细行，同一单据的明细行重复携带主表字段；
  重复列名（价税合计/已结算金额）pandas 读取时自动加 .1 后缀（主表取原名，明细取 .1）。
  处理方式：先按「单据编号」合并（同单明细行去重为每单 1 条，恢复原 1:1 结构），
  再执行原有规则与开思合并；原始明细 df 保留，对账命中后按「单据编号」关联出「明细」sheet。

输出 4 个 sheet（build_merge_result_dual）：
  1) 对账  ：无开思券 + 有开思券 合并，用「类型」列区分；正常对账命中数据
  2) 明细  ：对账命中单据，按金蝶「单据编号」关联原始应收单明细，展开每单的物料明细
  3) 开思  ：开思数据需人工处理（含规则排除）
  4) 金蝶  ：金蝶数据需人工处理（含规则排除）

合并前执行的规则（一侧一个函数，见下方 rule* 区）：
  规则0：开思 对账金额(¥) ≠ 平台已结算金额（¥）→ 进开思剩下
  规则1：同客户同价税合计，两侧行数一致才可配对，不一致 → 进剩下
  规则2：金蝶 核销状态非空 → 进金蝶剩下（核销状态为空填"空"）
  规则3：有开思券时按已收款金额校验，异常 → 进两侧人工核对
  （开思 结算状态 ≠ 已结算 由 ks_process 已预先过滤）
"""
import os

import pandas as pd

from .ks_process import merge_ks_data, KS_KEEP_COLS


# ======================================================================
# 一、参数与常量
# ======================================================================

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "data")

AR_FILE = "应收单.xlsx"   # 应收单「按列表引出」文件（dd2 结构）

# ---- 开思合并结果列（与 ks_process 输出对齐） ----
KS_COL_CUSTOMER = "客户代码"
KS_COL_PRICE = "对账金额(¥)"            # 开思侧对账金额（不含券的实收金额）
KS_COL_COUPON = "开思劵(¥)"              # 开思券金额
KS_COL_SETTLED = "平台已结算金额（¥）"   # 平台已结算金额
KS_COL_TOTAL = "_开思价税合计"            # 内部计算列 = 对账金额 + 开思劵

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

# ---- 应收单明细列（新结构：主表+明细，重复列名 pandas 读取时自动加 .1 后缀） ----
# 明细列为可选：旧结构文件缺失时自动跳过（赋空），不影响主表读取
# 键 = 最终输出列名：明细 sheet 中统一带「明细-」前缀，与「总-」前缀的对账数据列区分
AR_DETAIL_MAP = {
    "明细-价税合计": "价税合计.1",
    "明细-已结算金额": "已结算金额.1",
    "明细-物料编码": "物料编码",
    "明细-物料名称": "物料名称",
    "明细-品牌": "品牌",
    "明细-计价数量": "计价数量",
    "明细-含税单价": "含税单价",
    "明细-总金额": "总金额",
}

# ---- 输出统一保留的列 ----
MERGED_OUT_COLS = [                            # 对账命中（主表信息，不含明细；开思客户代码为中间匹配字段，不输出）
    "客户代码", "客户编码", "单据编号", "订单/退货编号",
    "对账金额(¥)", "平台已结算金额（¥）", "平台未结算金额（¥）", "开思劵(¥)",
    "价税合计", "已收款金额", "结算时间", "收款信息",
    "收款组织", "结算组织", "销售组织", "币别", "业务类型", "核销状态",
]
RECONCILE_OUT_COLS = MERGED_OUT_COLS + ["类型"]   # 对账命中内部列（无来源后缀，明细 sheet 复用）
DETAIL_OUT_COLS = ["总-" + c for c in RECONCILE_OUT_COLS if c not in ("收款组织", "结算组织")] + list(AR_DETAIL_MAP)   # sheet「对账成功数据-明细」= 总-对账列(不含收款/结算组织) + 明细-明细列

# ---- 对账成功数据 sheet 输出列：来源后缀（开思列→-开思，金蝶列→-金蝶） ----
# 收款组织/结算组织：代码内部保留（生成收款单要用），仅 Excel 输出删除
KS_EXCEL_RENAME = {                  # 开思来源列 → Excel 列名
    "订单/退货编号": "订单/退货编号-开思",
    "客户代码": "客户代码-开思",
    "对账金额(¥)": "对账金额(¥)-开思",
    "平台已结算金额（¥）": "平台已结算金额（¥）-开思",
    "平台未结算金额（¥）": "平台未结算金额（¥）-开思",
    "开思劵(¥)": "开思劵(¥)-开思",
    "结算时间": "结算时间-开思",
    "收款信息": "收款信息-开思",
}
AR_EXCEL_RENAME = {                  # 金蝶来源列 → Excel 列名
    "客户编码": "客户编码-金蝶",
    "单据编号": "单据编号-金蝶",
    "价税合计": "价税合计-金蝶",
    "已收款金额": "已收款金额-金蝶",
    "销售组织": "销售组织-金蝶",
    "币别": "币别-金蝶",
    "业务类型": "业务类型-金蝶",
    "核销状态": "核销状态-金蝶",
}
RECONCILE_RENAME = {**KS_EXCEL_RENAME, **AR_EXCEL_RENAME}
# 对账成功数据 Excel 输出列顺序（排除收款组织/结算组织；类型列保持原名）
RECONCILE_EXCEL_OUT_COLS = (
    [RECONCILE_RENAME[c] for c in MERGED_OUT_COLS if c in RECONCILE_RENAME] + ["类型"]
)
KS_OUT_COLS = KS_KEEP_COLS + ["剩余原因"]   # 开思数据需人工处理
AR_OUT_COLS = [                              # 金蝶数据需人工处理（开思客户代码为中间匹配字段，不输出）
    "单据编号", "客户编码", "币别", "价税合计", "已收款金额",
    "收款组织", "结算组织", "销售组织", "业务类型", "核销状态", "剩余原因",
]

# ---- 对账「类型」列取值 ----
R_COUPON_YES = "有开思券"
R_COUPON_NO = "无开思券"

OUT_MERGED_PREFIX = "开思对账_行合并"

# ---- 规则排除原因（去重，供 rule* 函数复用） ----
R_SETTLED = "对账金额(¥) ≠ 平台已结算金额（¥），进人工核对"
R_WX = "核销状态非空，不参与合并"
R_BAL = "同客户同价税合计两侧数量不一致，无法配对，排除"
R_COUPON = "有开思券且已收款金额>0，但对账金额≠价税合计-已收款金额"


def _data_path(filename):
    """拼接 DATA_DIR 下的完整路径"""
    os.makedirs(DATA_DIR, exist_ok=True)
    return os.path.join(DATA_DIR, filename)


def _drop(df, cols):
    """删除临时列（列不存在时忽略）"""
    return df.drop(columns=[c for c in cols if c in df.columns])


def _fmt_key(df, col):
    """金额统一保留2位小数，避免 int/float 格式差异"""
    return df[col].map(lambda x: f"{float(x):.2f}")


# ======================================================================
# 二、对账规则（一个规则一个函数）
# ======================================================================

def rule0_settled(ks):
    """规则0：开思 对账金额(¥) ≠ 平台已结算金额（¥）→ 不参与合并，直接进「开思剩下」"""
    ok = (ks[KS_COL_PRICE] - ks[KS_COL_SETTLED]).abs() <= 0.01
    rest = ks[~ok].copy()
    rest["剩余原因"] = R_SETTLED
    return ks[ok].copy(), rest


def rule2_wx_blank(ar):
    """规则2：金蝶 核销状态非空 → 不参与合并，直接进「金蝶剩下」"""
    blank = ar["核销状态"].isna() | (ar["核销状态"].astype(str).str.strip() == "空")
    rest = ar[~blank].copy()
    rest["剩余原因"] = R_WX
    return ar[blank].copy(), rest


def rule1_balance(ks, ar):
    """规则1：同一客户下相同价税合计，仅两侧行数一致才可两两/三三配对；不一致进剩下"""
    bal = _balanced_keys(ks, ar, [KS_COL_CUSTOMER, KS_COL_TOTAL], ["开思客户代码", "价税合计"])
    kk = ks[KS_COL_CUSTOMER] + "|" + _fmt_key(ks, KS_COL_TOTAL)
    ak = ar["开思客户代码"] + "|" + _fmt_key(ar, "价税合计")
    ks_m, ar_m = kk.isin(bal), ak.isin(bal)
    ks_rest = ks[~ks_m].copy(); ks_rest["剩余原因"] = R_BAL
    ar_rest = ar[~ar_m].copy(); ar_rest["剩余原因"] = R_BAL
    return ks[ks_m].copy(), ks_rest, ar[ar_m].copy(), ar_rest


def rule3_coupon(merged):
    """
    规则3：有开思券(开思劵>0)时按已收款金额校验。
      已收款=0 或 对账金额=价税合计-已收款金额 → 正常进「有开思卷对账数据」
      对账金额≠价税合计-已收款金额       → 异常，拆到两侧人工核对
    """
    has = merged[KS_COL_COUPON] > 0.001
    no_coupon = merged[~has].copy()
    wc = merged[has].copy()
    recv0 = wc["已收款金额"].abs() <= 0.001
    pc = wc[wc["已收款金额"] > 0.001].copy()
    match = (pc[KS_COL_PRICE] - (pc["价税合计"] - pc["已收款金额"]).round(2)).abs() <= 0.01
    abn = pc[~match].copy()
    abn["剩余原因"] = R_COUPON
    ar_abn = abn[[c for c in AR_OUT_COLS if c != "剩余原因" and c in abn.columns]].copy()
    ar_abn["剩余原因"] = R_COUPON
    with_coupon = pd.concat([wc[recv0].copy(), pc[match].copy()], ignore_index=True)
    return no_coupon, with_coupon, abn, ar_abn


# ======================================================================
# 三、工具函数 + 读应收单
# ======================================================================

def _to_ks_cust_code(series):
    """金蝶客户编码 → 开思客户代码（取最后一个 '-' 之后的部分并去空白）"""
    s = series.astype(str).str.strip()
    return s.str.rsplit("-", n=1).str[-1].str.strip()


def _balanced_keys(ks_df, ar_df, ks_key_cols, ar_key_cols):
    """
    判断哪些 (客户, 价格) 分组在开思与金蝶两侧数量一致（可两两/三三对账）。
    仅两侧行数相等（1:1、两两、三三…）的分组保留；不一致则因无法配对而被排除。
    :return: set —— 两侧数量一致的规范化分组键集合
    """
    def _fmt(idx):
        keys = []
        for t in idx:
            keys.append("|".join(f"{float(v):.2f}" if isinstance(v, (int, float)) else str(v) for v in t))
        return keys
    kd = dict(zip(_fmt(ks_df.groupby(ks_key_cols).size().index), ks_df.groupby(ks_key_cols).size().values))
    ad = dict(zip(_fmt(ar_df.groupby(ar_key_cols).size().index), ar_df.groupby(ar_key_cols).size().values))
    return {k for k in set(kd) | set(ad) if kd.get(k, 0) == ad.get(k, 0)}


def _keep_cols(df, cols):
    """只保留指定列（缺失的列忽略，避免报错）"""
    return df[[c for c in cols if c in df.columns]]


def build_reconcile_output(reconcile_df):
    """
    对账成功数据 sheet 输出：
      - 列加来源后缀（开思列→-开思，金蝶列→-金蝶），类型列保持原名
      - 删除收款组织/结算组织（内部数据仍保留，供收款单生成使用）
    :param reconcile_df: build_merge_result_dual 返回的「对账」DataFrame（内部原列名）
    :return: 输出用 DataFrame（带来源后缀列名）
    """
    out = _keep_cols(reconcile_df, list(RECONCILE_RENAME) + ["类型"])
    out = out.rename(columns=RECONCILE_RENAME)
    return _keep_cols(out, RECONCILE_EXCEL_OUT_COLS)


def read_ar_data(filepath):
    """
    读取应收单「按列表引出」文件（dd2：单行中文表头，最后一行为合计需剔除）。
    新结构含主表+明细：重复列名（价税合计/已结算金额）pandas 自动加 .1 后缀，
    主表取原名列，明细取 .1 列（缺失时赋空，兼容旧结构）。
    只保留 AR_COL_MAP + AR_DETAIL_MAP 用到的列，并生成开思客户代码。
    """
    df = pd.read_excel(filepath)
    miss = [c for c in AR_COL_MAP.values() if c not in df.columns]
    if miss:
        raise KeyError(f"应收单列表缺少字段：{miss}")
    ar = pd.DataFrame({k: df[v] for k, v in AR_COL_MAP.items()})
    # 明细列（可选）：新结构读取，旧结构缺失则置空，保证一对多输出兼容
    for k, v in AR_DETAIL_MAP.items():
        ar[k] = df[v] if v in df.columns else None
    ar = ar.dropna(subset=["单据编号"]).copy()   # 剔除「合计」行
    for k in ("价税合计", "已收款金额"):          # 金额转数值
        ar[k] = pd.to_numeric(ar[k], errors="coerce")
    ar["开思客户代码"] = _to_ks_cust_code(ar["客户编码"])   # 取最后一个 '-' 之后的部分
    return ar


# ======================================================================
# 四、主流程：行级内连接合并 + 完整对账入口
# ======================================================================

def build_merge_result(ks=None, ar_path=None, ar_full=None):
    """
    开思 vs 金蝶应收单 按 (客户代码, 价税合计) 行级内连接合并（不聚合）。
    金蝶先按「单据编号」合并（同单明细行去重为每单 1 条，恢复原 1:1 结构），
    再执行原有规则0/规则2/规则1（见 rule*），剩下的再按边界分类。
    :param ks: 可选，预加载的开思合并数据（默认调用 ks_process.merge_ks_data()）
    :param ar_path: 可选，应收单文件路径（默认从 DATA_DIR 读取）
    :param ar_full: 可选，预读取的应收单原始明细 DataFrame（含明细行）
    :return: (merged, ks_rest, ar_rest) 三个 DataFrame
    """
    # 1) 开思数据：数值化 + 计算价税合计，并应用规则0
    if ks is None:
        ks = merge_ks_data()
    ks = ks.copy()
    for c in (KS_COL_PRICE, KS_COL_COUPON, KS_COL_SETTLED):
        ks[c] = pd.to_numeric(ks[c], errors="coerce").round(2)  # pyright: ignore[reportAttributeAccessIssue]
    ks[KS_COL_TOTAL] = (ks[KS_COL_PRICE] + ks[KS_COL_COUPON]).round(2)
    ks, ks_rest0 = rule0_settled(ks)

    # 2) 金蝶应收单：按「单据编号」合并（同单多条明细行 → 每单 1 条主表记录）
    if ar_path is None:
        ar_path = _data_path(AR_FILE)
    if ar_full is None:
        ar_full = read_ar_data(ar_path)
    ar = ar_full.drop_duplicates(subset=["单据编号"]).copy()
    ar["价税合计"] = ar["价税合计"].round(2)
    ar, ar_rest2 = rule2_wx_blank(ar)

    # 3) 规则1：两侧数量一致才可配对
    ks, ks_rest1, ar, ar_rest1 = rule1_balance(ks, ar)

    # 4) 内连接合并（合并键 = 客户代码|价税合计）
    ks["_key"] = ks[KS_COL_CUSTOMER] + "|" + _fmt_key(ks, KS_COL_TOTAL)
    ar["_key"] = ar["开思客户代码"] + "|" + _fmt_key(ar, "价税合计")
    merged = ks.merge(ar, on="_key", how="inner")  # pyright: ignore[reportArgumentType, reportAttributeAccessIssue]

    # 5) 剩下 = 规则排除 + 合并后未匹配
    ks_rest3 = ks[~ks["_key"].isin(merged["_key"])].copy()  # pyright: ignore[reportAttributeAccessIssue]
    ks_rest3["剩余原因"] = "合并后未匹配上（金蝶无对应）"
    ar_rest3 = ar[~ar["_key"].isin(merged["_key"])].copy()  # pyright: ignore[reportAttributeAccessIssue]
    ar_rest3["剩余原因"] = "合并后未匹配上（开思无对应）"
    ks_rest = pd.concat([ks_rest0, ks_rest1, ks_rest3], ignore_index=True)  # pyright: ignore[reportCallIssue, reportArgumentType, reportArgumentType]
    ar_rest = pd.concat([ar_rest2, ar_rest1, ar_rest3], ignore_index=True)  # pyright: ignore[reportCallIssue, reportArgumentType]

    # 清理临时列（_key、_开思价税合计）
    merged = _drop(merged, ["_key", KS_COL_TOTAL])
    ks_rest = _drop(ks_rest, ["_key", KS_COL_TOTAL])
    ar_rest = _drop(ar_rest, ["_key", KS_COL_TOTAL])
    return merged, ks_rest, ar_rest


def build_merge_result_dual(ks=None, ar_path=None, ar_full=None):
    """
    完整对账入口，输出 4 个 sheet 对应数据：
      1) 对账（reconcile）：无开思券+有开思券 合并，用「类型」列（R_COUPON_NO/YES）区分
      2) 明细（detail）：对账命中单据，按金蝶「单据编号」关联原始应收单明细，展开物料明细
      3) 开思（ks_rest_final）：开思数据需人工处理（基础合并剩下 + 规则3异常）
      4) 金蝶（ar_rest_final）：金蝶数据需人工处理（基础合并剩下 + 规则3异常）
    :param ks: 开思合并数据（默认调用 ks_process.merge_ks_data()）
    :param ar_path: 应收单文件路径
    :param ar_full: 可选，预读取的应收单原始明细 DataFrame
    :return: (reconcile, detail, ks_rest_final, ar_rest_final) 四个 DataFrame
    """
    if ar_full is None:
        ar_full = read_ar_data(ar_path if ar_path else _data_path(AR_FILE))
    merged, ks_rest, ar_rest = build_merge_result(ks=ks, ar_path=ar_path, ar_full=ar_full)
    if merged.empty:
        return pd.DataFrame(), pd.DataFrame(), ks_rest, ar_rest

    for c in (KS_COL_PRICE, KS_COL_COUPON):
        merged[c] = pd.to_numeric(merged[c], errors="coerce").round(2)  # pyright: ignore[reportAttributeAccessIssue]
    merged["价税合计"] = pd.to_numeric(merged["价税合计"], errors="coerce").round(2)  # pyright: ignore[reportAttributeAccessIssue]
    merged["已收款金额"] = pd.to_numeric(merged["已收款金额"], errors="coerce").fillna(0).round(2)  # pyright: ignore[reportAttributeAccessIssue]

    # 规则3：拆分无开思券 / 有开思券，异常进两侧人工核对
    no_coupon, with_coupon, ks_abn, ar_abn = rule3_coupon(merged)
    if not ks_abn.empty:  # pyright: ignore[reportAttributeAccessIssue]
        ks_rest = pd.concat(  # pyright: ignore[reportCallIssue]
            [ks_rest, ks_abn[[c for c in KS_KEEP_COLS + ["剩余原因"] if c in ks_abn.columns]]],  # pyright: ignore[reportArgumentType, reportAttributeAccessIssue]
            ignore_index=True,
        )
    if not ar_abn.empty:  # pyright: ignore[reportAttributeAccessIssue]
        ar_rest = pd.concat([ar_rest, ar_abn], ignore_index=True)  # pyright: ignore[reportCallIssue, reportArgumentType]

    # ---- sheet「对账」：无券 + 有券 合并，加「类型」列 ----
    reconcile = no_coupon.copy()
    if not with_coupon.empty:
        reconcile = pd.concat([reconcile, with_coupon], ignore_index=True)
    reconcile["类型"] = reconcile[KS_COL_COUPON].apply(
        lambda x: R_COUPON_YES if x > 0.001 else R_COUPON_NO
    )

    # ---- sheet「对账成功数据-明细」：对账命中单据 按金蝶「单据编号」关联原始应收单明细 ----
    # 对账成功数据列统一加「总-」前缀；原生明细列（AR_DETAIL_MAP 键）自带「明细-」前缀，
    # 两者合并互不冲突，输出 = 总-对账列 + 明细-明细列
    recon4detail = reconcile.drop(columns=[c for c in AR_DETAIL_MAP if c in reconcile.columns])
    recon4detail = recon4detail.rename(columns=lambda c: f"总-{c}")
    detail_src = ar_full[["单据编号"] + list(AR_DETAIL_MAP)].copy()
    detail = recon4detail.merge(
        detail_src, left_on="总-单据编号", right_on="单据编号", how="left"
    ).drop(columns=["单据编号"])
    return reconcile, detail, ks_rest, ar_rest


# ---- 核销状态为"部分"的金蝶行：单独对账（可选用，暂未在主流程调用） ----
def build_partial_reconcile(ks_rest, ar_rest):
    """
    对核销状态为"部分"的金蝶行做二次对账（可选用，暂未在主流程调用）。
    前提：开思对账金额 == 金蝶价税合计；再判断 金蝶(价税合计-已收款金额) == 开思平台已结算金额（¥）。
    :param ks_rest: build_merge_result 返回的「开思剩下」
    :param ar_rest: build_merge_result 返回的「金蝶剩下」
    :return: (matched, ks_unmatched, ar_unmatched) 三值对账结果（不做 Excel 输出）
    """
    ar_part = ar_rest[ar_rest["核销状态"].astype(str).str.strip() == "部分"].copy()
    if ar_part.empty:
        return pd.DataFrame(), ks_rest.copy(), ar_rest.copy()
    for col in ("对账金额(¥)", "平台已结算金额（¥）"):
        ks_rest[col] = pd.to_numeric(ks_rest[col], errors="coerce").round(2)  # pyright: ignore[reportAttributeAccessIssue]
    for col in ("价税合计", "已收款金额"):
        ar_part[col] = pd.to_numeric(ar_part[col], errors="coerce").round(2)  # pyright: ignore[reportAttributeAccessIssue]
    ar_part["未收款金额"] = (ar_part["价税合计"] - ar_part["已收款金额"]).round(2)
    prer = ks_rest.merge(
        ar_part,
        left_on=[KS_COL_CUSTOMER, KS_COL_PRICE],
        right_on=["开思客户代码", "价税合计"],
        how="inner",
        suffixes=("_开思", "_金蝶"),
    )
    matched_prer = prer[prer["对账金额(¥)_开思"] == prer["价税合计"]]  # 前提校验
    predicted = matched_prer[matched_prer["未收款金额"] == matched_prer["平台已结算金额（¥）_开思"]].copy()
    return predicted, ks_rest.copy(), ar_part.copy()