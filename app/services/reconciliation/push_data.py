# coding:utf-8
"""
push_data.py —— 复制收款单模板，生成最终导入数据（新版模板，源单明细按物料行展开）

依据：
- 08_最终完整方案.md（收款单引入模板结构：头段/明细段/源单明细段，同一序号）
- payment_bill.py 合并结果（合并数据 = 开思订单 ↔ 金蝶应收单 按客户+价格命中）
- 金蝶新版收款单引入模板（源单明细含物料编码/名称/含税单价/数量等字段）

流程：
  S1 调 ks_process.merge_ks_data()                （开思合并数据）
  S2 调 payment_bill.build_merge_result_dual()    （开思+金蝶 行级对账）
  S3 每行对账命中 → 一张收款单：头+明细同行（第1行）+ 源单明细行（第2行起，按物料展开）
  S4 复制「收款单导入模板.xlsx」，从第3行追加 → 收款单_批量导入_时间戳.xlsx

收款单结构（同一张单，同一单据头序号）：
  第1行：单据头 + 收款单明细（FRECEIVEBILLENTRY段）
  第2行起：单据头（重复） + 收款单源单明细（FRECEIVEBILLSRCENTRY段），每行对应一条物料明细
"""
import datetime
import os
import shutil

import openpyxl
import pandas as pd

from .ks_process import merge_ks_data
from .payment_bill import (
    build_merge_result_dual,
    AR_DETAIL_MAP,
)


# ======================================================================
# 一、参数与常量
# ======================================================================

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "data")

PAY_TEMPLATE_FILE = "收款单导入模板.xlsx"     # 收款单引入模板（只复制，不改原件）
OUT_PAY_PREFIX = "收款单_批量导入"


def get_default_skd_date():
    """
    获取默认收款单业务日期 = 今天，格式 YYYY-MM-DD（与金蝶日期格式一致）。

    前端未传 skd_date 时使用，避免固定日期过期。
    """
    now = datetime.datetime.now()
    return f"{now.year}-{now.month:02d}-{now.day:02d}"


def _normalize_date(skd_date):
    """
    统一日期格式为 YYYY-MM-DD（金蝶导入要求）。
    支持输入 YYYY/M/D 或 YYYY-MM-DD 等格式。
    """
    if not skd_date:
        return get_default_skd_date()
    s = str(skd_date).strip()
    # 尝试多种分隔符解析
    for sep in ("/", "-", "."):
        if sep in s:
            parts = s.split(sep)
            if len(parts) == 3:
                y, m, d = parts
                return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    return s

# ---- 枚举编码（方案默认值，如与实际不符改这里） ----
PAY_BILL_TYPE = "SKDLX01_SYS"      # 单据类型（销售收款单）
PAY_SETTLE_TYPE = "JSFS04_SYS"     # 结算方式 = 电汇
PAY_PURPOSE = "SFKYT01_SYS"        # 收款用途 = 销售收款（需挂源单）
PAY_PURPOSE_REFUND = "SFKYT01_SYS" # 退款单用途（同销售收款，金额为负）
CONTACT_UNIT_TYPE = "客户"         # 往来/付款单位类型（客户）
PAY_COMMENT = "开思对账自动生成"     # 摘要

# 我方银行账号（按开思"发票类型"选择，与旧版开思对账V5逻辑一致）
BANK_ACCOUNT_NO_INVOICE = "6214860209811922"   # 无需发票账户
BANK_ACCOUNT_INVOICED = "44428301040011286"    # 已开票账户

# ---- 组织编码（硬编码，单公司场景固定值） ----
PAY_ORG_CODE = "FOSBBR"            # 收款组织编码
SETTLE_ORG_CODE = "FOSBBR"         # 结算组织编码
SALE_ORG_CODE = "FOSBBR"           # 销售组织编码

# ---- 币别编码（硬编码，单币别场景） ----
CURRENCY_CODE = "PRE001"           # 币别编码（人民币）

# ---- 业务类型 ----
BUSINESS_TYPE = "销售业务"          # 业务类型（销售业务）

# ---- 模板 sheet 名 ----
TEMPLATE_SHEET = "收款单#单据头(FBillHead)"

# ---- 单据头字段（新版模板，按模板实际列名）----
HEAD_FIELDS = [
    "FBillTypeID",       # 单据类型
    "FPAYORGID",         # 收款组织编码
    "FSETTLEORGID",      # 结算组织编码
    "FSALEORGID",        # 销售组织编码
    "FDATE",             # 业务日期
    "FCONTACTUNITTYPE",  # 往来单位类型
    "FCONTACTUNIT",      # 往来单位编码
    "FPAYUNITTYPE",      # 付款单位类型
    "FPAYUNIT",          # 付款单位编码
    "FCURRENCYID",       # 币别
    "FEXCHANGERATE",     # 汇率
    "FSETTLECUR",        # 结算币别
    "FSETTLERATE",       # 结算汇率
    "FREMARK",           # 备注
    "F_ora_Text",        # 出库单单号
    "F_CUSTOMERID",      # 客户编码
]

# 单据头名称列字段映射（#Name 列，存在才写入）
HEAD_NAME_FIELDS = {
    "FPAYORGID#Name": "收款组织",           # 收款组织#名称
    "FSETTLEORGID#Name": "结算组织",        # 结算组织#名称
    "FSALEORGID#Name": "销售组织",          # 销售组织#名称
    "FCONTACTUNIT#Name": "客户名称",        # 往来单位#名称
    "FPAYUNIT#Name": "客户名称",            # 付款单位#名称
    "FCURRENCYID#Name": "人民币",           # 币别#名称
    "FSETTLECUR#Name": "人民币",            # 结算币别#名称
    "F_CUSTOMERID#Name": "客户名称",        # 客户#名称
}

# ---- 收款单明细段字段（新版模板）----
ENTRY_FIELDS = [
    "FSETTLETYPEID",       # 结算方式
    "FPURPOSEID",          # 收款用途
    "FRECTOTALAMOUNTFOR",  # 表体-应收金额
    "FACCOUNTID",          # 我方银行账号
    "FCOMMENT",            # 摘要
    "FRECAMOUNTFOR_E",     # 收款金额
]

# 收款单明细名称列字段映射
ENTRY_NAME_FIELDS = {
    "FSETTLETYPEID#Name": "电汇",          # 结算方式#名称
    "FPURPOSEID#Name": "销售收款",         # 收款用途#名称
}

# ---- 收款单源单明细段字段（新版模板，按物料行展开）----
SRC_FIELDS = [
    "FSRCBILLNO",               # 源单编号（应收单编号）
    "F_ora_ysDate",             # 应收日期
    "FREALRECAMOUNT",           # 本次收款金额
    "FSRCMATERIALID",           # 物料编码#编码
    "FSRCPRICEUNITID",          # 计价单位#编码
    "FSRCMATERIALSEQ",          # 订单行号
    "FSRCPRICE",                # 含税单价
    "FSRCQTY",                  # 数量
    "FSETTLEAMOUNT",            # 结算金额（真正核销应收单的金额）
    "FREALRECAMOUNTFOR_S",      # 本次收款金额本位币
    "FSRCREMARK",               # 备注
    "FCUSTOMERID",              # 客户#编码（源单明细客户，与单据头一致）
    "F_ora_Brand",              # 品牌
]

# 源单明细名称列字段映射
SRC_NAME_FIELDS = {
    "FSRCMATERIALID#Name": "物料名称",      # 物料编码#名称（填入物料名称）
    "FSRCPRICEUNITID#Name": "Pcs",          # 计价单位#名称
    "FCUSTOMERID#Name": "客户名称",         # 客户#名称
}


def _path(filename):
    """拼接 DATA_DIR 下的完整路径，确保目录存在"""
    os.makedirs(DATA_DIR, exist_ok=True)
    return os.path.join(DATA_DIR, filename)


# ======================================================================
# 二、S3 每行对账命中 → 一张收款单（含多行源单明细）
# ======================================================================

def build_payment_bills(reconcile_df, detail_df, skd_date):
    """
    每行对账命中数据生成一张销售收款单（含多行源单明细，按物料行展开）。

    收款金额 = 对账金额(¥)（命中即 = 价税合计）。
    仅处理正数金额 → 销售收款单（SKDLX01_SYS）。
    负数金额（退货/红字应收单）→ 由 refund_data.py 的收款退款单模块处理。

    源单明细：按应收单「单据编号」从 detail_df 中匹配该单的所有物料明细行，
    每行一条源单明细，金额取「明细-价税合计」。

    :param reconcile_df: payment_bill 的「对账」DataFrame（含对账主表信息）
    :param detail_df: payment_bill 的「明细」DataFrame（含物料明细，总-前缀对账列 + 明细-前缀明细列）
    :param skd_date: 收款单业务日期
    :return: bills 列表，每项 {"seq", "head", "entry", "src_entries"}
    """
    bills = []
    skd_date = _normalize_date(skd_date)
    seq = 0

    # 预构建 单据编号 → 明细行列表 的映射，加速查找
    # detail_df 中 总-单据编号 = 金蝶单据编号，明细-* 为物料明细字段
    detail_map = {}
    if detail_df is not None and not detail_df.empty:
        for _, drow in detail_df.iterrows():
            bill_no = drow["总-单据编号"]
            if bill_no not in detail_map:
                detail_map[bill_no] = []
            detail_map[bill_no].append(drow)

    for _, row in reconcile_df.iterrows():
        amt = round(float(row["对账金额(¥)"]), 2)
        # 金额为0的跳过（既不收款也不退款）
        if amt == 0:
            continue
        # 负数金额属于退货/退款，由收款退款单模块处理，此处跳过
        if amt < 0:
            continue
        seq += 1  # 序号从1开始连续编号
        # 客户编码去除空格
        cust_code = str(row["客户编码"]).replace(" ", "")
        # 我方银行账号：无需发票 → 无需发票账户；其余 → 已开票账户
        fp_type = str(row["发票类型"]).strip() if "发票类型" in row.index else ""
        bank = BANK_ACCOUNT_NO_INVOICE if fp_type == "无需发票" else BANK_ACCOUNT_INVOICED
        # 客户名称（开思侧有客户名称）
        cust_name = row["客户名称"] if "客户名称" in row.index and pd.notna(row["客户名称"]) else ""

        # ---- 单据头 ----
        # 备注内容：收到XX客户XX元（与金蝶导出格式对齐）
        if cust_name:
            remark = f"收到{cust_name}{amt}元"
        else:
            remark = f"{PAY_COMMENT}，金额{amt}元"
        head = {
            "FBillTypeID": PAY_BILL_TYPE,
            "FPAYORGID": PAY_ORG_CODE,
            "FPAYORGID#Name": row["收款组织"],
            "FSETTLEORGID": SETTLE_ORG_CODE,
            "FSETTLEORGID#Name": row["结算组织"],
            "FSALEORGID": SALE_ORG_CODE,
            "FSALEORGID#Name": row["销售组织"],
            "FDATE": skd_date,
            "FCONTACTUNITTYPE": CONTACT_UNIT_TYPE,
            "FCONTACTUNIT": cust_code,
            "FCONTACTUNIT#Name": cust_name,
            "FPAYUNITTYPE": CONTACT_UNIT_TYPE,
            "FPAYUNIT": cust_code,
            "FPAYUNIT#Name": cust_name,
            "FCURRENCYID": CURRENCY_CODE,
            "FCURRENCYID#Name": "人民币",
            "FEXCHANGERATE": 1,         # 汇率=1（人民币）
            "FSETTLECUR": CURRENCY_CODE,
            "FSETTLECUR#Name": "人民币",
            "FSETTLERATE": 1,           # 结算汇率=1（人民币）
            "FREMARK": remark,
            "F_CUSTOMERID": cust_code,
            "F_CUSTOMERID#Name": cust_name,
        }
        # 出库单单号（填应收单编号，与金蝶导出一致；开思订单号作为备注用途不大）
        head["F_ora_Text"] = str(row["单据编号"])

        # ---- 收款单明细（第1行，与头段同行）----
        entry = {
            "FSETTLETYPEID": PAY_SETTLE_TYPE,
            "FSETTLETYPEID#Name": "电汇",
            "FPURPOSEID": PAY_PURPOSE,
            "FPURPOSEID#Name": "销售收款",
            "FRECTOTALAMOUNTFOR": amt,   # 应收金额 = 对账金额
            "FACCOUNTID": bank,
            "FCOMMENT": remark,           # 摘要与备注一致
            "FRECAMOUNTFOR_E": amt,       # 收款金额
        }

        # ---- 源单明细（按物料行展开）----
        bill_no = row["单据编号"]
        srcs = []
        if bill_no in detail_map:
            # 有明细数据 → 按每条物料生成一行源单明细
            line_no = 0
            for drow in detail_map[bill_no]:
                line_no += 1
                # 明细-价税合计 = 该行物料的金额（可能为负，退货单）
                line_amt = round(float(drow["明细-价税合计"]), 2) if pd.notna(drow["明细-价税合计"]) else 0
                # 物料编码
                material_code = str(drow["明细-物料编码"]) if pd.notna(drow["明细-物料编码"]) else ""
                # 物料名称
                material_name = str(drow["明细-物料名称"]) if pd.notna(drow["明细-物料名称"]) else ""
                # 含税单价
                price = round(float(drow["明细-含税单价"]), 2) if pd.notna(drow["明细-含税单价"]) else 0
                # 数量
                qty = drow["明细-计价数量"] if pd.notna(drow["明细-计价数量"]) else 0

                src = {
                    "FSRCBILLNO": bill_no,
                    "FREALRECAMOUNT": line_amt,
                    "FREALRECAMOUNTFOR_S": line_amt,   # 本位币金额=原币金额（人民币）
                    "FSETTLEAMOUNT": line_amt,           # 结算金额 = 本次收款金额（触发核销）
                    "FSRCMATERIALID": material_code,
                    "FSRCMATERIALID#Name": material_name,
                    "FSRCPRICEUNITID": "Pcs",           # 计价单位 Pcs
                    "FSRCPRICEUNITID#Name": "Pcs",
                    "FSRCMATERIALSEQ": line_no,         # 订单行号（按明细行顺序 1,2,3...）
                    "FSRCPRICE": price,
                    "FSRCQTY": qty,
                    "FSRCREMARK": remark,                # 源单明细备注（与单据头备注一致）
                    "FCUSTOMERID": cust_code,            # 客户#编码
                    "FCUSTOMERID#Name": cust_name,       # 客户#名称
                    "F_ora_Brand": "",                   # 品牌（暂空，待补充数据来源）
                }
                # 应收日期（从开思结算时间或业务日期取）
                if "结算时间" in row.index and pd.notna(row["结算时间"]):
                    settle_val = str(row["结算时间"]).strip()
                    if settle_val and settle_val != "-":
                        src["F_ora_ysDate"] = _normalize_date(settle_val)
                    else:
                        src["F_ora_ysDate"] = skd_date
                else:
                    src["F_ora_ysDate"] = skd_date
                srcs.append(src)
        else:
            # 无明细数据 → 退化为1行整单（兼容旧数据）
            srcs.append({
                "FSRCBILLNO": bill_no,
                "FREALRECAMOUNT": amt,
                "FREALRECAMOUNTFOR_S": amt,
                "FSETTLEAMOUNT": amt,
                "FSRCMATERIALSEQ": 1,
                "F_ora_ysDate": skd_date,
                "FCUSTOMERID": cust_code,
                "FCUSTOMERID#Name": cust_name,
            })

        bills.append({"seq": seq, "head": head, "entry": entry, "src_entries": srcs})
    return bills


# ======================================================================
# 三、S4 复制模板 + 写入（新版模板，列数更多）
# ======================================================================

def write_payment_template(bills, template_path, output_dir=None):
    """
    复制收款单模板（原件不动），从第3行追加：
    每张收款单 = 1行头+明细 + N行源单明细（头段重复填写，序号全局递增）。

    序号规则（全局递增，避免"序号有重复"错误）：
      - 单据头序号：同一张单的所有行（明细行+源单行）共享同一个单据头序号
      - 收款单明细序号：每行唯一，全局递增
      - 收款单源单明细序号：每行唯一，全局递增

    :param bills: build_payment_bills 的结果
    :param template_path: 模板文件路径
    :param output_dir: 输出目录（默认 DATA_DIR）
    :return: 输出文件路径
    """
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    if output_dir is None:
        output_dir = DATA_DIR
    os.makedirs(output_dir, exist_ok=True)
    out = os.path.join(output_dir, f"{OUT_PAY_PREFIX}_{ts}.xlsx")
    shutil.copy(template_path, out)
    wb = openpyxl.load_workbook(out)
    ws = wb[TEMPLATE_SHEET] if TEMPLATE_SHEET in wb.sheetnames else wb[wb.sheetnames[0]]

    row1 = [c.value for c in ws[1]]   # 英文字段名
    row2 = [c.value for c in ws[2]]   # 中文列名

    def ien(n):
        """按第1行英文字段名定位列下标（0基）"""
        for i, v in enumerate(row1):
            if v == n:
                return i
        raise KeyError(f"模板缺少字段：{n}")

    def icn(n):
        """按第2行中文列名定位列下标（0基）"""
        for i, v in enumerate(row2):
            if v == n:
                return i
        raise KeyError(f"模板缺少列：{n}")

    # ---- 定位各段序号列 ----
    h_seq = icn("*单据头(序号)")
    e_seq = icn("*收款单明细(序号)")
    s_seq = icn("*收款单源单明细(序号)")

    # ---- 定位各段字段列 ----
    # 单据头字段（编码列 + 名称列）
    hc = {f: ien(f) for f in HEAD_FIELDS}
    for name_field in HEAD_NAME_FIELDS:
        try:
            hc[name_field] = ien(name_field)
        except KeyError:
            pass  # 名称列可选，不存在则跳过

    # 收款单明细字段
    ec = {f: ien(f) for f in ENTRY_FIELDS}
    for name_field in ENTRY_NAME_FIELDS:
        try:
            ec[name_field] = ien(name_field)
        except KeyError:
            pass

    # 收款单源单明细字段
    sc = {f: ien(f) for f in SRC_FIELDS}
    for name_field in SRC_NAME_FIELDS:
        try:
            sc[name_field] = ien(name_field)
        except KeyError:
            pass

    # 金额字段集合：写入时强制保留 2 位小数，避免浮点精度导致显示 603.900000000...
    AMOUNT_FIELDS = {
        # 收款单明细段
        "FRECTOTALAMOUNTFOR", "FSETTLEDISTAMOUNTFOR", "FHANDLINGCHARGEFOR",
        "FTAXAMOUNTFOR", "FTAXAMOUNT", "FRECNOTAXAMOUNTFOR", "FRECNOTAXAMOUNT",
        "FWRITTENOFFTAXAMOUNTFOR", "FWRITTENOFFTAXAMOUNT", "FRECAMOUNTFOR_E",
        "FOVERUNDERAMOUNTFOR", "FPrice", "FQty",
        # 收款单源单明细段
        "FREALRECAMOUNT", "FREALRECAMOUNTFOR_S", "FSETTLEAMOUNT", "FSRCPRICE",
        "FSRCQTY", "FASSORDERAMOUNT",
    }

    def _write_cell(row_idx, col_idx, value, field_name=None):
        """写入单元格；金额字段统一保留 2 位小数并设置数值格式。"""
        cell = ws.cell(row_idx, col_idx, value)
        if field_name in AMOUNT_FIELDS and isinstance(value, (int, float)):
            # 先 round 消除 Python 浮点误差，再设置 Excel 数值格式
            cell.value = round(float(value), 2)
            cell.number_format = "0.00"
        return cell

    r = 3   # 第3行起追加，第1、2行表头不动
    seq = 0  # 明细序号/源单明细序号 全局递增
    for bill in bills:
        h_seq_val = bill["seq"]     # 单据头序号（同单共享）
        seq += 1                    # 明细行序号

        # ---- 第1行：头段 + 明细段（同一行）----
        # 头段序号 + 头段字段
        ws.cell(r, h_seq + 1, h_seq_val)
        for f, v in bill["head"].items():
            if f in hc:
                _write_cell(r, hc[f] + 1, v, f)
        # 明细段序号 + 明细段字段（与头段同一行）
        ws.cell(r, e_seq + 1, seq)
        for f, v in bill["entry"].items():
            if f in ec:
                _write_cell(r, ec[f] + 1, v, f)
        r += 1

        # ---- 后续行：源单明细段（头段字段重复填写）----
        for src in bill["src_entries"]:
            seq += 1                # 源单明细行序号
            # 头段字段重复（与金蝶引出格式一致）
            ws.cell(r, h_seq + 1, h_seq_val)
            for f, v in bill["head"].items():
                if f in hc:
                    _write_cell(r, hc[f] + 1, v, f)
            # 源单明细序号 + 源单明细字段
            ws.cell(r, s_seq + 1, seq)
            for f, v in src.items():
                if f in sc:
                    _write_cell(r, sc[f] + 1, v, f)
            r += 1

    wb.save(out)
    return out


# ======================================================================
# 四、主流程（调试用）
# ======================================================================

# if __name__ == "__main__":
#     skd_date = get_default_skd_date()
#     # S1 ks_process：开思合并数据
#     ks = merge_ks_data()
#     # S2 payment_bill：开思+金蝶 行级对账
#     reconcile_df, detail_df, ks_rest, ar_rest = build_merge_result_dual(ks=ks)
#     print(f"开思合并数据 {len(ks)} 行；对账命中 {len(reconcile_df)} 行；明细 {len(detail_df)} 行")
#     # S3 每行 → 一张收款单（含多行源单明细）
#     bills = build_payment_bills(reconcile_df, detail_df, skd_date)
#     # S4 复制模板写入
#     out = write_payment_template(bills, _path(PAY_TEMPLATE_FILE)) if bills else None
#     print(f"生成收款单 {len(bills)} 张")
#     print(f"导入文件：{out}")
