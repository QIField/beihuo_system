# coding:utf-8
"""
push_data.py —— 复制收款单模板，生成最终导入数据

依据：
- 08_最终完整方案.md（收款单引入模板结构：头段/明细段/源单明细段，同一序号）
- payment_bill.py 合并结果（合并数据 = 开思订单 ↔ 金蝶应收单 按客户+价格命中）

流程：
  S1 调 ks_process.merge_ks_data()                （开思合并数据）
  S2 调 payment_bill.build_merge_result()          （开思+金蝶 行级合并，取「合并数据」）
  S3 每行合并数据 → 一张收款单：头1行 + 明细1行 + 源单明细1行，同一序号
  S4 复制「收款单导入模板.xlsx」，从第3行追加 → 收款单_批量导入_时间戳.xlsx
"""
import datetime
import os
import shutil

import openpyxl
import pandas as pd

from ks_process import merge_ks_data
from payment_bill import build_merge_result


# ======================================================================
# 一、参数与常量
# ======================================================================

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")

PAY_TEMPLATE_FILE = "收款单导入模板.xlsx"     # 收款单引入模板（只复制，不改原件）
OUT_PAY_PREFIX = "收款单_批量导入"
SKD_DATE = "2025/9/30"                       # 收款单业务日期

# ---- 枚举编码（方案默认值，如与实际不符改这里） ----
PAY_BILL_TYPE = "SKDLX01_SYS"      # 单据类型（销售收款单）
PAY_SETTLE_TYPE = "JSFS01_DH"      # 结算方式 = 电汇
PAY_PURPOSE = "SKYT01"             # 收款用途
CONTACT_UNIT_TYPE = "BD_Customer"  # 往来/付款单位类型（客户）
PAY_COMMENT = "开思对账自动生成"      # 摘要
BANK_ACCOUNT = "6214860209811922"  # 我方银行账号

# ---- 收款单模板三实体段字段（d4 结构，第1行英文字段名） ----
TEMPLATE_SHEET = "收款单#单据头(FBillHead)"
HEAD_FIELDS = ["FBillTypeID", "FPAYORGID", "FSETTLEORGID", "FSALEORGID", "FDATE",
               "FCONTACTUNITTYPE", "FCONTACTUNIT", "FPAYUNITTYPE", "FPAYUNIT",
               "FCURRENCYID", "FSETTLECUR", "FBUSINESSTYPE"]
ENTRY_FIELDS = ["FSETTLETYPEID", "FPURPOSEID", "FRECTOTALAMOUNTFOR",
                "FACCOUNTID", "FCOMMENT", "FRECAMOUNTFOR_E"]
SRC_FIELDS = ["FSRCBILLNO", "FREALRECAMOUNT", "FSRCMATERIALSEQ", "FSRCORDERENTRYID"]


def _path(filename):
    """拼接 DATA_DIR 下的完整路径，确保目录存在"""
    os.makedirs(DATA_DIR, exist_ok=True)
    return os.path.join(DATA_DIR, filename)


# ======================================================================
# 二、S3 每行合并数据 → 一张收款单
# ======================================================================

def build_payment_bills(merged, skd_date):
    """
    每行合并数据生成一张收款单（头1行 + 明细1行 + 源单明细1行，同一序号）。
    本次收款金额 = 对账金额(¥)（合并命中即 = 价税合计）。

    :param merged: payment_bill 的「合并数据」DataFrame
    :param skd_date: 收款单业务日期
    :return: bills 列表，每项 {"seq", "head", "entry", "src_entries"}
    """
    bills = []
    for seq, (_, row) in enumerate(merged.iterrows(), start=1):
        amt = round(float(row["对账金额(¥)"]), 2)
        head = {
            "FBillTypeID": PAY_BILL_TYPE,
            "FPAYORGID": row["收款组织"],
            "FSETTLEORGID": row["结算组织"],
            "FSALEORGID": row["销售组织"],
            "FDATE": skd_date,
            "FCONTACTUNITTYPE": CONTACT_UNIT_TYPE,
            "FCONTACTUNIT": row["客户代码"],
            "FPAYUNITTYPE": CONTACT_UNIT_TYPE,
            "FPAYUNIT": row["客户代码"],
            "FCURRENCYID": row["币别"],
            "FSETTLECUR": row["币别"],
            "FBUSINESSTYPE": row["业务类型"],
        }
        entry = {
            "FSETTLETYPEID": PAY_SETTLE_TYPE,
            "FPURPOSEID": PAY_PURPOSE,
            "FRECTOTALAMOUNTFOR": amt,
            "FACCOUNTID": BANK_ACCOUNT,
            "FCOMMENT": PAY_COMMENT,
            "FRECAMOUNTFOR_E": amt,
        }
        srcs = [{
            "FSRCBILLNO": row["单据编号"],
            "FREALRECAMOUNT": amt,
            "FSRCMATERIALSEQ": "",
            "FSRCORDERENTRYID": "",
        }]
        bills.append({"seq": seq, "head": head, "entry": entry, "src_entries": srcs})
    return bills


# ======================================================================
# 三、S4 复制模板 + 写入
# ======================================================================

def write_payment_template(bills, template_path):
    """
    复制收款单模板（原件不动），从第3行追加：
    头1行 + 明细1行 + 源单明细N行（同序号）；#Name 与 *Split* 列不填。

    :param bills: build_payment_bills 的结果
    :param template_path: 模板文件路径
    :return: 输出文件路径
    """
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    out = _path(f"{OUT_PAY_PREFIX}_{ts}.xlsx")
    shutil.copy(template_path, out)
    wb = openpyxl.load_workbook(out)
    ws = wb[TEMPLATE_SHEET] if TEMPLATE_SHEET in wb.sheetnames else wb[wb.sheetnames[0]]

    row1 = [c.value for c in ws[1]]
    row2 = [c.value for c in ws[2]]

    def ien(n):
        """按第1行英文字段名定位列下标"""
        for i, v in enumerate(row1):
            if v == n:
                return i
        raise KeyError(f"模板缺少字段：{n}")

    def icn(n):
        """按第2行中文列名定位列下标"""
        for i, v in enumerate(row2):
            if v == n:
                return i
        raise KeyError(f"模板缺少列：{n}")

    # 三段序号列 + 各段字段列
    h_seq = icn("*单据头(序号)")
    e_seq = icn("*收款单明细(序号)")
    s_seq = icn("*收款单源单明细(序号)")
    hc = {f: ien(f) for f in HEAD_FIELDS}
    ec = {f: ien(f) for f in ENTRY_FIELDS}
    sc = {f: ien(f) for f in SRC_FIELDS}

    r = 3   # 第3行起追加，第1、2行表头不动
    for bill in bills:
        seq = bill["seq"]
        ws.cell(r, h_seq + 1, seq)
        for f, v in bill["head"].items():
            ws.cell(r, hc[f] + 1, v)
        r += 1
        ws.cell(r, e_seq + 1, seq)
        for f, v in bill["entry"].items():
            ws.cell(r, ec[f] + 1, v)
        r += 1
        for src in bill["src_entries"]:
            ws.cell(r, s_seq + 1, seq)
            for f, v in src.items():
                ws.cell(r, sc[f] + 1, v)
            r += 1
    wb.save(out)
    return out


# ======================================================================
# 四、主流程
# ======================================================================

# if __name__ == "__main__":
#     skd_date = SKD_DATE
#     # S1 ks_process：开思合并数据
#     ks = merge_ks_data()
#     # S2 payment_bill：开思+金蝶 行级合并，取「合并数据」
#     merged, _, _ = build_merge_result(ks=ks)
#     print(f"开思合并数据 {len(ks)} 行；合并数据（命中）{len(merged)} 行")
#     # S3 每行 → 一张收款单
#     bills = build_payment_bills(merged, skd_date)
#     # S4 复制模板写入
#     out = write_payment_template(bills, _path(PAY_TEMPLATE_FILE)) if bills else None
#     print(f"生成收款单 {len(bills)} 张")
#     print(f"导入文件：{out}")
  
