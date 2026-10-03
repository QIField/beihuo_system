# coding:utf-8
"""
create_excel.py —— 开思对账数据处理脚本

功能：
  1. 读取开思电子对账单 + 订单结算明细，合并为开思数据；
  2. 读取金蝶应收单（主表行，无明细），与开思数据按行对账；
  3. 输出对账结果 Excel（对账结果/模拟点击数据源/开思卷明细/开思人工核对/金蝶人工核对 5 个 sheet）。

使用方式：
  python tests/script/reconciliation/create_excel.py

默认读取本脚本所在目录下的：
  - 开思电子对账单*.xlsx（按前缀自动匹配）
  - 订单结算明细*.xlsx（按前缀自动匹配）
  - 应收单*.xlsx（按前缀自动匹配）

输出到本脚本所在目录下：
  - 开思对账_行合并_时间戳.xlsx

模拟点击下推收款单由 v5_automation.py 负责（数据处理与模拟点击分离）。
"""
import datetime
import os
import sys

import pandas as pd

# 把本脚本所在目录加入 sys.path，确保可以直接 import 同级模块
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from coupon_detail import build_coupon_detail_sheet
from ks_process import merge_ks_data
from payment_bill import build_merge_result_dual


def get_default_skd_date():
    """获取默认收款单业务日期 = 今天，格式 YYYY-MM-DD。"""
    now = datetime.datetime.now()
    return f"{now.year}-{now.month:02d}-{now.day:02d}"


# 输出文件放在本脚本所在目录下的 data 子目录（输入文件仍放在脚本所在目录）
DATA_DIR = os.path.join(BASE_DIR, "data")


def _data_path(filename):
    """拼接 DATA_DIR 下的完整路径。"""
    os.makedirs(DATA_DIR, exist_ok=True)
    return os.path.join(DATA_DIR, filename)


def _ts():
    """当前时间戳字符串。"""
    return datetime.datetime.now().strftime("%Y%m%d_%H%M")


def run_reconciliation(skd_date=None):
    """
    执行对账并生成对账结果 Excel。

    :param skd_date: 收款单业务日期，默认今天
    :return: 生成的文件路径字典
    """
    skd_date = skd_date or get_default_skd_date()

    # S1: 合并开思数据
    print("[1/3] 合并开思数据...")
    ks = merge_ks_data()
    print(f"       开思合并后 {len(ks)} 行")

    # S2: 开思 vs 金蝶 对账
    print("[2/3] 开思 vs 金蝶 对账...")
    duizhang_result, moshi_datasource, ks_manual, ar_manual = build_merge_result_dual(ks=ks)
    print(f"       对账结果 {len(duizhang_result)} 行")
    print(f"       模拟点击数据源 {len(moshi_datasource)} 行")
    print(f"       开思人工核对 {len(ks_manual)} 行；金蝶人工核对 {len(ar_manual)} 行")

    # S3: 生成开思券明细（仅包含有开思券且状态正常的订单）
    print("[3/3] 生成开思券明细...")
    coupon_detail = build_coupon_detail_sheet(moshi_datasource)
    print(f"       开思卷明细 {len(coupon_detail)} 行")

    # S4: 输出对账结果 Excel
    print("[4/4] 输出对账结果 Excel...")
    out_reconcile = _data_path(f"开思对账_行合并_{_ts()}.xlsx")
    with pd.ExcelWriter(out_reconcile, engine="openpyxl") as writer:  # pyright: ignore[reportAbstractUsage]
        duizhang_result.to_excel(writer, sheet_name="对账结果", index=False)
        moshi_datasource.to_excel(writer, sheet_name="模拟点击数据源", index=False)
        coupon_detail.to_excel(writer, sheet_name="开思卷明细", index=False)
        ks_manual.to_excel(writer, sheet_name="开思人工核对", index=False)
        ar_manual.to_excel(writer, sheet_name="金蝶人工核对", index=False)
    print(f"       -> {out_reconcile}")

    return {"reconcile": out_reconcile}


def main_generate_excel(skd_date=None):
    """生成对账 Excel，不启动浏览器。"""
    skd_date = skd_date or get_default_skd_date()
    paths = run_reconciliation(skd_date=skd_date)
    print("\n生成文件：")
    for k, v in paths.items():
        print(f"  {k}: {v}")
    return paths


if __name__ == "__main__":
    # 本脚本只负责数据处理：生成对账 Excel。
    # 模拟点击下推收款单请单独运行 v5_automation.py（数据处理与模拟点击分离）。
    main_generate_excel()
