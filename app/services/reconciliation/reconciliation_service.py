# -*- coding:utf-8 -*-
"""
reconciliation_service.py —— 开思对账服务（业务层）

封装完整对账流程：
  1. 接收上传的 3 个文件：
     - 开思电子对账单.xlsx
     - 订单结算明细.xlsx
     - 应收单.xlsx
     （收款单导入模板为固定路径，无需上传）
  2. 执行开思数据合并 → 开思vs金蝶行级对账 → 生成收款单
  3. 结果落盘 static/excel/reconciliation/temp/<task_id>/，并控制最多保留 MAX_KEEP 份
  4. 构造下载 URL，返回给调用方

异常策略：
  - 参数/业务问题：抛出 BeihuoBaseException 子类（ParameterError / BusinessError）
  - 数据处理问题：抛出 DataError / DataParseError
  - 本模块只负责业务逻辑，不涉及 HTTP 请求处理
"""
import os
import datetime
import tempfile
import shutil
import uuid

import pandas as pd

from app.exceptions import (
    ParameterError,
    BusinessError,
    DataError,
    DataParseError,
)

from .ks_process import merge_ks_data
from .payment_bill import (
    build_merge_result,
    MERGED_OUT_COLS,
    KS_OUT_COLS,
    AR_OUT_COLS,
    OUT_MERGED_PREFIX,
    _keep_cols,
)
from .push_data import build_payment_bills, write_payment_template, get_default_skd_date
from .reconciliation_storage_service import (
    get_result_dir,
    get_pay_template_path,
    cleanup_old_results,
    build_result_url,
    MAX_KEEP,
)


# ======================================================================
# 一、对账主流程
# ======================================================================

def run_reconciliation(
    stmt_file,
    detail_file,
    ar_file,
    template_path,
    output_dir=None,
    skd_date=None,
):
    """
    执行完整对账流程，生成结果文件。

    :param stmt_file: 开思电子对账单文件路径（str）或 FileStorage 对象
    :param detail_file: 订单结算明细文件路径（str）或 FileStorage 对象
    :param ar_file: 应收单文件路径（str）或 FileStorage 对象
    :param template_path: 收款单导入模板文件路径
    :param output_dir: 输出目录（默认临时目录）
    :param skd_date: 收款单业务日期（默认取当天 get_default_skd_date()）
    :return: dict，包含 merge_result_path / payment_bill_path / stats / work_dir
    :raises ParameterError: 参数缺失
    :raises BusinessError: 模板缺失等业务问题
    :raises DataError: 数据读取/解析/处理失败
    """
    if not template_path:
        raise ParameterError("收款单导入模板路径不能为空")
    if not os.path.exists(template_path):
        raise BusinessError(f"找不到收款单模板文件：{template_path}")

    # ---- 准备临时工作目录 ----
    work_dir = tempfile.mkdtemp(prefix="reconciliation_")
    try:
        # ---- 保存上传文件到工作目录 ----
        def _save(file_obj, default_name):
            if isinstance(file_obj, str):
                return file_obj
            save_name = getattr(file_obj, "filename", default_name) or default_name
            save_path = os.path.join(work_dir, save_name)
            file_obj.save(save_path)
            return save_path

        stmt_path = _save(stmt_file, "开思电子对账单.xlsx")
        detail_path = _save(detail_file, "订单结算明细.xlsx")
        ar_path = _save(ar_file, "应收单.xlsx")

        # ---- 确定输出目录 ----
        if output_dir is None:
            output_dir = work_dir
        os.makedirs(output_dir, exist_ok=True)

        if skd_date is None:
            skd_date = get_default_skd_date()

        # ---- S1：开思数据合并 ----
        try:
            ks_merged = merge_ks_data(stmt_path=stmt_path, detail_path=detail_path)
        except Exception as e:
            raise DataParseError(f"开思数据合并失败: {e}") from e
        ks_count = len(ks_merged)

        # ---- S2：开思 vs 金蝶 行级对账 ----
        try:
            merged, ks_rest, ar_rest = build_merge_result(ks=ks_merged, ar_path=ar_path)
        except Exception as e:
            raise DataError(f"开思与金蝶应收单对账失败: {e}") from e

        merged_count = len(merged)
        ks_rest_count = len(ks_rest)
        ar_rest_count = len(ar_rest)

        # ---- 输出对账结果 Excel（3 个 sheet） ----
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        merge_result_path = os.path.join(output_dir, f"{OUT_MERGED_PREFIX}_{ts}.xlsx")
        m_out = _keep_cols(merged, MERGED_OUT_COLS)
        ks_out = _keep_cols(ks_rest, KS_OUT_COLS)
        ar_out = _keep_cols(ar_rest, AR_OUT_COLS)

        try:
            with pd.ExcelWriter(merge_result_path, engine="openpyxl") as writer:  # pyright: ignore[reportAbstractUsage]
                m_out.to_excel(writer, sheet_name="合并数据", index=False)
                ks_out.to_excel(writer, sheet_name="开思剩下", index=False)
                ar_out.to_excel(writer, sheet_name="金蝶剩下", index=False)
        except Exception as e:
            raise DataError(f"生成对账结果 Excel 失败: {e}") from e

        # ---- S3：生成收款单 ----
        payment_bill_path = None
        payment_count = 0
        if merged_count > 0:
            try:
                bills = build_payment_bills(merged, skd_date)
                payment_count = len(bills)
                payment_bill_path = write_payment_template(
                    bills, template_path, output_dir=output_dir
                )
            except Exception as e:
                raise DataError(f"生成收款单导入文件失败: {e}") from e

        # ---- 统计信息 ----
        stats = {
            "开思合并行数": ks_count,
            "合并命中行数": merged_count,
            "开思剩下行数": ks_rest_count,
            "金蝶剩下行数": ar_rest_count,
            "生成收款单数": payment_count,
            "开思剩下原因": ks_rest["剩余原因"].value_counts().to_dict() if ks_rest_count > 0 else {},
            "金蝶剩下原因": ar_rest["剩余原因"].value_counts().to_dict() if ar_rest_count > 0 else {},
        }

        return {
            "merge_result_path": merge_result_path,
            "payment_bill_path": payment_bill_path,
            "stats": stats,
            "work_dir": work_dir,
        }

    except Exception:
        # 出错时清理工作目录
        shutil.rmtree(work_dir, ignore_errors=True)
        raise


# ======================================================================
# 三、对外统一入口（API 层只调用本函数）
# ======================================================================

def process_reconciliation(stmt_file, detail_file, ar_file, skd_date=None):
    """
    开思对账统一业务入口。

    内部完成全部业务处理：
      1. 校验固定收款单模板存在
      2. 落盘前清理：temp 目录先清理到 MAX_KEEP-1（4）份，留出本次落盘名额
      3. 生成任务 ID 并创建结果落盘目录
      4. 执行对账（run_reconciliation）
      5. 成功后清理上传临时文件
      6. 构造下载 URL

    :param stmt_file: 开思电子对账单 FileStorage 对象或路径
    :param detail_file: 订单结算明细 FileStorage 对象或路径
    :param ar_file: 应收单 FileStorage 对象或路径
    :param skd_date: 可选，收款单业务日期（默认取当天 get_default_skd_date()）
    :return: dict，包含 task_id / stats / merge_result_url / payment_bill_url
    :raises ParameterError: 上传文件缺失
    :raises BusinessError: 模板缺失等业务问题
    :raises DataError: 数据处理失败
    """
    if not stmt_file:
        raise ParameterError("缺少开思电子对账单文件")
    if not detail_file:
        raise ParameterError("缺少订单结算明细文件")
    if not ar_file:
        raise ParameterError("缺少应收单文件")

    # ---- 校验固定模板存在 ----
    pay_template_path = get_pay_template_path()
    if not os.path.exists(pay_template_path):
        raise BusinessError(f"服务器缺少收款单导入模板文件: {pay_template_path}")

    result_dir = get_result_dir()

    # ---- 落盘前清理：先保留 MAX_KEEP-1 份，本次落盘后正好 MAX_KEEP（5）份 ----
    # 若先删到 MAX_KEEP 份再落盘，落盘后会是 MAX_KEEP+1（6）份，超限
    cleanup_old_results(result_dir, max_keep=MAX_KEEP - 1)

    # ---- 生成任务 ID 并创建结果落盘目录 ----
    task_id = uuid.uuid4().hex[:12]
    task_output_dir = os.path.join(result_dir, task_id)
    os.makedirs(task_output_dir, exist_ok=True)

    try:
        result = run_reconciliation(
            stmt_file=stmt_file,
            detail_file=detail_file,
            ar_file=ar_file,
            template_path=pay_template_path,
            output_dir=task_output_dir,
            skd_date=skd_date,
        )
    except Exception:
        # 失败时清理本次结果目录
        shutil.rmtree(task_output_dir, ignore_errors=True)
        raise

    # 成功后清理上传临时文件（run_reconciliation 内部创建的 work_dir）
    work_dir = result.get("work_dir")
    if work_dir:
        shutil.rmtree(work_dir, ignore_errors=True)

    # ---- 构造下载 URL ----
    merge_path = result.get("merge_result_path")
    pay_path = result.get("payment_bill_path")

    merge_url = None
    pay_url = None
    if merge_path and os.path.exists(merge_path):
        merge_url = build_result_url(task_id, os.path.basename(merge_path))
    if pay_path and os.path.exists(pay_path):
        pay_url = build_result_url(task_id, os.path.basename(pay_path))

    return {
        "task_id": task_id,
        "stats": result.get("stats", {}),
        "merge_result_url": merge_url,
        "payment_bill_url": pay_url,
    }
