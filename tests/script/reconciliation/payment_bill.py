# coding:utf-8
"""
payment_bill.py —— 开思对账：开思 vs 金蝶应收单 按行合并（不聚合）

依据：
- 08_最终完整方案.md
- d / d6（开思表结构与合并规则）
- demo/t1（应收单「按列表引出」：第1行中文列名，无明细行，最后一行"合计"需剔除）
- dd3（金蝶客户编码带前缀，开思代码取最后一个 '-' 之后的部分）

对账规则（核心前提）：
  对账金额(¥) + 开思劵(¥) = 价税合计

合并方式：客户代码 + 价税合计（=对账金额+开思劵） 完全匹配，组内 1:1 顺序配对（不做聚合）。

1:1 配对约束（仅针对 22/33 等多行组，与开思券无关）：
  同一 (客户代码, 价税合计) 组内，开思按「订单/退货编号」、金蝶按「单据编号」排序后一一对应；
  一张金蝶单据号只能配对 1 个开思订单号，组内所有行都被配对，不重复、不丢失（无笛卡尔积）。

金蝶应收单结构（demo/t1）：
  仅含主表行，一行一个应收单据；不存在物料明细行。
  直接按「单据编号」去重后参与对账。

输出 4 个 sheet（build_merge_result_dual）：
  1) 对账结果      ：以开思电子对账单为主表，每行标注「状态」
  2) 模拟点击数据源：从「对账结果」中提取 状态 == 正常 的行（供 V5 自动化下推收款单）
  3) 开思人工核对  ：「对账结果」中 状态 != 正常 的开思行
  4) 金蝶人工核对  ：金蝶数据需人工处理（含规则排除）

合并前执行的规则（一侧一个函数，见下方 rule* 区）：
  规则0：开思 对账金额(¥) ≠ 平台已结算金额（¥）→ 进开思人工核对
  规则1：同客户同价税合计，两侧行数一致才可配对，不一致 → 开思状态 = 人工核对
  规则2：配对命中后
           - 有开思券且金蝶已收款金额 = 平台已结算金额（¥）→ 状态 = 除开思卷完全核销
           - 金蝶已收款金额 = 价税合计                         → 状态 = 完全核销
           - 否则                                           → 状态 = 正常
  （开思 结算状态 ≠ 已结算 由 ks_process 已预先过滤）
"""
import os

import pandas as pd

from ks_process import merge_ks_data, KS_KEEP_COLS


# ======================================================================
# 一、参数与常量
# ======================================================================

DATA_DIR = os.path.dirname(os.path.abspath(__file__))

AR_FILE = "应收单.xlsx"   # 应收单「按列表引出」文件（dd2 结构）


def _find_input_file(directory, prefix, fallback):
    """
    在目录中查找输入文件：优先标准文件名；否则按前缀匹配（兼容带时间戳/下载后缀的文件名）。
    :param directory: 目录
    :param prefix: 文件名前缀（如 "应收单"）
    :param fallback: 标准文件名（找不到前缀匹配时返回此路径，供报错提示）
    :return: 匹配到的完整路径
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
    "核销状态": "表头基本 - 收款核销状态",   # 保留输出，不再作为排除条件
}

# ---- 输出统一保留的列 ----
MERGED_OUT_COLS = [                            # 对账命中（主表信息；开思客户代码为中间匹配字段，不输出）
    "客户代码", "客户名称", "客户编码", "单据编号", "订单/退货编号",
    "对账金额(¥)", "平台已结算金额（¥）", "平台未结算金额（¥）", "开思劵(¥)",
    "价税合计", "已收款金额", "结算时间", "收款信息",
    "收款组织", "结算组织", "销售组织", "币别", "业务类型", "核销状态",
]
RECONCILE_OUT_COLS = MERGED_OUT_COLS + ["类型"]   # 对账命中内部列（无来源后缀）

# ---- 对账成功数据 sheet 输出列：来源后缀（开思列→-开思，金蝶列→-金蝶） ----
# 收款组织/结算组织：代码内部保留（生成收款单要用），仅 Excel 输出删除
KS_EXCEL_RENAME = {                  # 开思来源列 → Excel 列名
    "订单/退货编号": "订单/退货编号-开思",
    "客户代码": "客户代码-开思",
    "客户名称": "开思客户名称",
    "发票类型": "发票类型-开思",
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
# 发票类型不在 MERGED_OUT_COLS 中，单独追加（V5 自动化选银行账号需要）
RECONCILE_EXCEL_OUT_COLS = (
    [RECONCILE_RENAME[c] for c in MERGED_OUT_COLS if c in RECONCILE_RENAME]
    + (["发票类型-开思"] if "发票类型" in RECONCILE_RENAME else [])
    + ["类型"]
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

# ---- 对账结果「状态」列取值 ----
STATUS_NORMAL = "正常"
STATUS_FULL_WX = "完全核销"
STATUS_FULL_WX_EXCEPT_COUPON = "除开思卷完全核销"
STATUS_MANUAL = "人工核对"

# ---- 规则排除原因（去重，供 rule* 函数复用） ----
R_SETTLED = "对账金额(¥) ≠ 平台已结算金额（¥），进人工核对"
R_BAL = "人工核对"


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


def rule1_balance(ks, ar):
    """规则1：同一客户下相同价税合计，仅两侧行数一致才可两两/三三配对；不一致进剩下"""
    bal = _balanced_keys(ks, ar, [KS_COL_CUSTOMER, KS_COL_TOTAL], ["开思客户代码", "价税合计"])
    kk = ks[KS_COL_CUSTOMER] + "|" + _fmt_key(ks, KS_COL_TOTAL)
    ak = ar["开思客户代码"] + "|" + _fmt_key(ar, "价税合计")
    ks_m, ar_m = kk.isin(bal), ak.isin(bal)
    ks_rest = ks[~ks_m].copy(); ks_rest["剩余原因"] = R_BAL
    ar_rest = ar[~ar_m].copy(); ar_rest["剩余原因"] = R_BAL
    return ks[ks_m].copy(), ks_rest, ar[ar_m].copy(), ar_rest


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
    读取应收单「按列表引出」文件（demo/t1：单行中文表头，无明细行，最后一行为合计需剔除）。
    只保留 AR_COL_MAP 用到的列，并生成开思客户代码。
    """
    df = pd.read_excel(filepath)
    miss = [c for c in AR_COL_MAP.values() if c not in df.columns]
    if miss:
        raise KeyError(f"应收单列表缺少字段：{miss}")
    ar = pd.DataFrame({k: df[v] for k, v in AR_COL_MAP.items()})
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
    开思 vs 金蝶应收单 按 (客户代码, 价税合计) 行级合并（不聚合）。
    金蝶先按「单据编号」去重（确保每单 1 条），
    再执行规则0/规则1（见 rule*）；22/33 等多行组内按单号排序后 1:1 顺序配对
    （一张金蝶单据号只对 1 个开思订单号，不重复、不丢失），剩下的再按边界分类。
    :param ks: 可选，预加载的开思合并数据（默认调用 ks_process.merge_ks_data()）
    :param ar_path: 可选，应收单文件路径（默认从 DATA_DIR 读取）
    :param ar_full: 可选，预读取的应收单 DataFrame
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

    # 2) 金蝶应收单：按「单据编号」去重（确保每单 1 条）
    if ar_path is None:
        ar_path = _find_input_file(DATA_DIR, "应收单", AR_FILE)
    if ar_full is None:
        ar_full = read_ar_data(ar_path)
    ar = ar_full.drop_duplicates(subset=["单据编号"]).copy()  # pyright: ignore[reportOptionalMemberAccess]
    ar["价税合计"] = ar["价税合计"].round(2)

    # 3) 规则1：两侧数量一致才可配对
    ks, ks_rest1, ar, ar_rest1 = rule1_balance(ks, ar)

    # 4) 按 (客户代码, 价税合计) 分组，组内 1:1 顺序配对合并（22/33 组消除笛卡尔积）
    #    约束（仅针对 22/33 等多行组，与开思券无关）：组内 开思 按「订单/退货编号」、
    #    金蝶 按「单据编号」排序后一一对应；一张金蝶单据号只能配对 1 个开思订单号，
    #    组内所有行都被配对，不重复、不丢失。
    ks["_key"] = ks[KS_COL_CUSTOMER] + "|" + _fmt_key(ks, KS_COL_TOTAL)
    ar["_key"] = ar["开思客户代码"] + "|" + _fmt_key(ar, "价税合计")
    ks = ks.sort_values(["_key", "订单/退货编号"], kind="stable")   # 组内按开思单号排序  # pyright: ignore[reportCallIssue, reportAttributeAccessIssue]
    ar = ar.sort_values(["_key", "单据编号"], kind="stable")        # 组内按金蝶单号排序  # pyright: ignore[reportCallIssue, reportAttributeAccessIssue]
    ks["_pair"] = ks.groupby("_key", sort=False).cumcount()         # 组内配对序号 0..n-1
    ar["_pair"] = ar.groupby("_key", sort=False).cumcount()
    merged = ks.merge(ar, on=["_key", "_pair"], how="inner")  # pyright: ignore[reportArgumentType, reportAttributeAccessIssue]

    # 5) 剩下 = 规则排除 + 合并后未匹配（按 键+配对序号 行级判断，任何一行都不丢失）
    ks_mkey = ks["_key"] + "#" + ks["_pair"].astype(str)
    ar_mkey = ar["_key"] + "#" + ar["_pair"].astype(str)
    m_mkey = merged["_key"] + "#" + merged["_pair"].astype(str)
    ks_rest3 = ks[~ks_mkey.isin(m_mkey)].copy()  # pyright: ignore[reportAttributeAccessIssue]
    ks_rest3["剩余原因"] = "合并后未匹配上（金蝶无对应）"
    ar_rest3 = ar[~ar_mkey.isin(m_mkey)].copy()  # pyright: ignore[reportAttributeAccessIssue]
    ar_rest3["剩余原因"] = "合并后未匹配上（开思无对应）"
    ks_rest = pd.concat([ks_rest0, ks_rest1, ks_rest3], ignore_index=True)  # pyright: ignore[reportCallIssue, reportArgumentType, reportArgumentType]
    ar_rest = pd.concat([ar_rest1, ar_rest3], ignore_index=True)  # pyright: ignore[reportCallIssue, reportArgumentType]

    # 清理临时列（_key、_pair、_开思价税合计）
    merged = _drop(merged, ["_key", "_pair", KS_COL_TOTAL])
    ks_rest = _drop(ks_rest, ["_key", "_pair", KS_COL_TOTAL])
    ar_rest = _drop(ar_rest, ["_key", "_pair", KS_COL_TOTAL])
    return merged, ks_rest, ar_rest


def build_merge_result_dual(ks=None, ar_path=None, ar_full=None):
    """
    完整对账入口，输出 4 个 sheet 对应数据：
      1) 对账结果（duizhang_result）：以开思电子对账单为主表，含「状态」列
      2) 模拟点击数据源（moshi_datasource）：对账结果中 状态 == 正常 的行
      3) 开思人工核对（ks_manual）：对账结果中 状态 != 正常 的行
      4) 金蝶人工核对（ar_manual）：金蝶数据需人工处理
    :param ks: 开思合并数据（默认调用 ks_process.merge_ks_data()）
    :param ar_path: 应收单文件路径
    :param ar_full: 可选，预读取的应收单 DataFrame
    :return: (duizhang_result, moshi_datasource, ks_manual, ar_manual) 四个 DataFrame
    """
    if ar_full is None:
        ar_full = read_ar_data(ar_path if ar_path else _find_input_file(DATA_DIR, "应收单", AR_FILE))
    merged, ks_rest, ar_rest = build_merge_result(ks=ks, ar_path=ar_path, ar_full=ar_full)

    # 命中数据统一数值化
    if not merged.empty:
        for c in (KS_COL_PRICE, KS_COL_COUPON):
            merged[c] = pd.to_numeric(merged[c], errors="coerce").round(2)  # pyright: ignore[reportAttributeAccessIssue]
        merged["价税合计"] = pd.to_numeric(merged["价税合计"], errors="coerce").round(2)  # pyright: ignore[reportAttributeAccessIssue]
        merged["已收款金额"] = pd.to_numeric(merged["已收款金额"], errors="coerce").fillna(0).round(2)  # pyright: ignore[reportAttributeAccessIssue]

    # ---- 生成「对账结果」：以开思电子对账单为主表，标注状态 ----
    duizhang = _build_duizhang_result(merged, ks_rest)
    if duizhang.empty:
        empty_out = pd.DataFrame(columns=RECONCILE_EXCEL_OUT_COLS)
        return empty_out.copy(), empty_out.copy(), empty_out.copy(), _keep_cols(ar_rest, AR_OUT_COLS)

    duizhang_result = build_duizhang_result_output(duizhang)

    # ---- 模拟点击数据源：状态 == 正常 ----
    moshi_datasource = duizhang_result[duizhang_result["状态"] == STATUS_NORMAL].drop(columns=["状态"]).copy()

    # ---- 开思人工核对：状态 != 正常 ----
    ks_manual = duizhang_result[duizhang_result["状态"] != STATUS_NORMAL].copy()

    # ---- 金蝶人工核对 ----
    ar_manual = _keep_cols(ar_rest, AR_OUT_COLS)

    return duizhang_result, moshi_datasource, ks_manual, ar_manual


def _build_duizhang_result(matched, ks_rest):
    """
    以对账结果为主表，汇总全部开思行并标注状态。
    状态规则：
      - 正常：            配对命中，且不属于以下两种核销
      - 完全核销：        配对命中且金蝶已收款金额 == 价税合计
      - 除开思卷完全核销：配对命中、有开思券且金蝶已收款金额 == 平台已结算金额（¥）
      - 人工核对：        规则1（同客户同价税合计数量不一致）
      - 其他：            保留原剩余原因（规则0、合并后未匹配等）
    """
    parts = []

    # 命中行：正常 / 完全核销 / 除开思卷完全核销
    if not matched.empty:
        recv = pd.to_numeric(matched["已收款金额"], errors="coerce").fillna(0).round(2)
        total = pd.to_numeric(matched["价税合计"], errors="coerce").fillna(0).round(2)
        settled = pd.to_numeric(matched["平台已结算金额（¥）"], errors="coerce").fillna(0).round(2)
        coupon = matched[KS_COL_COUPON].fillna(0).round(2)
        matched = matched.copy()

        # 有开思券且 金蝶已收款金额 = 开思平台已结算金额 → 除券外已收齐
        matched["状态"] = STATUS_NORMAL
        matched.loc[(coupon != 0) & (recv == settled), "状态"] = STATUS_FULL_WX_EXCEPT_COUPON
        matched.loc[recv == total, "状态"] = STATUS_FULL_WX
        parts.append(matched)

    # 开思剩下：规则0 / 规则1 / 合并后未匹配
    if not ks_rest.empty:
        ks_rest = ks_rest.copy()

        def _map_status(reason):
            if reason == R_BAL:
                return STATUS_MANUAL
            return reason

        ks_rest["状态"] = ks_rest["剩余原因"].map(_map_status)
        parts.append(ks_rest)

    if not parts:
        return pd.DataFrame()

    duizhang = pd.concat(parts, ignore_index=True)

    # 类型列（无开思券 / 有开思券）：开思劵(¥) ≠ 0 视为有券
    duizhang["类型"] = duizhang[KS_COL_COUPON].apply(
        lambda x: R_COUPON_YES if pd.notna(x) and x != 0 else R_COUPON_NO
    )
    return duizhang


def build_duizhang_result_output(duizhang_df):
    """
    对账结果 sheet 输出：
      - 列加来源后缀（开思列→-开思，金蝶列→-金蝶），类型/状态列保持原名
      - 删除收款组织/结算组织（内部数据仍保留，供收款单生成使用）
    :param duizhang_df: 内部原列名的「对账结果」DataFrame（含「状态」列）
    :return: 输出用 DataFrame（带来源后缀列名 + 状态列）
    """
    out = _keep_cols(duizhang_df, list(RECONCILE_RENAME) + ["类型", "状态"])
    out = out.rename(columns=RECONCILE_RENAME)
    return _keep_cols(out, RECONCILE_EXCEL_OUT_COLS + ["状态"])


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