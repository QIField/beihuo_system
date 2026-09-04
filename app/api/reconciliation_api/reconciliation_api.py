# -*- coding:utf-8 -*-
"""
reconciliation_api.py —— 开思对账 API 接口

职责：只负责参数校验 + 返回响应。
所有业务处理（对账、落盘、清理、URL 构造等）统一委托给业务层
process_reconciliation()，本层不做任何业务逻辑。

异常处理：
  - 通过 _handle_api_exceptions 装饰器统一捕获异常
  - BeihuoBaseException 子类 → 业务/参数错误（4xx）
  - 其他 Exception → 服务器异常（500）
"""
import functools

from flask import request, jsonify, send_file

from . import reconciliation_bp
from app.exceptions import (
    BeihuoBaseException,
    ParameterError,
)
from app.services.reconciliation.reconciliation_service import process_reconciliation
from app.services.reconciliation.reconciliation_storage_service import resolve_result_file


# ======================================================================
# 一、统一响应与异常处理
# ======================================================================

def _json_response(code=0, msg="success", data=None):
    """统一 JSON 响应格式"""
    return jsonify({"code": code, "msg": msg, "data": data})


def _handle_api_exceptions(func):
    """
    统一异常处理装饰器。

    - ParameterError / 业务校验失败 → code=1, HTTP 400
    - 其他 BeihuoBaseException → code=1, HTTP 400
    - 未知异常 → code=1, HTTP 500
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ParameterError as e:
            return _json_response(code=1, msg=str(e), data=None), 400
        except BeihuoBaseException as e:
            return _json_response(code=1, msg=str(e), data=None), 400
        except Exception as e:
            return _json_response(code=1, msg=f"服务器异常: {str(e)}", data=None), 500
    return wrapper


# ======================================================================
# 二、接口
# ======================================================================

@reconciliation_bp.route('/upload-and-process', methods=['POST'])
@_handle_api_exceptions
def api_upload_and_process():
    """
    上传文件并执行对账处理

    请求（multipart/form-data）：
        - ks_statement: 开思电子对账单.xlsx
        - ks_detail: 订单结算明细.xlsx
        - ar_bill: 应收单.xlsx
        - skd_date: 可选，收款单业务日期（默认 2025/9/30）
        （收款单导入模板为固定文件，无需上传）

    返回：
        {
            "code": 0,
            "msg": "success",
            "data": {
                "task_id": "xxx",
                "stats": { ... },
                "merge_result_url": "/static/excel/reconciliation/temp/xxx/xxx.xlsx",
                "payment_bill_url": "/static/excel/reconciliation/temp/xxx/xxx.xlsx"
            }
        }
    """
    # ---- 参数校验：必传 3 个文件 ----
    required_files = {
        "ks_statement": "开思电子对账单",
        "ks_detail": "订单结算明细",
        "ar_bill": "应收单",
    }

    missing = []
    for key, name in required_files.items():
        file = request.files.get(key)
        if not file or not file.filename:
            missing.append(name)

    if missing:
        raise ParameterError(f"缺少必要文件: {', '.join(missing)}")

    # ---- 调用业务层统一入口 ----
    data = process_reconciliation(
        stmt_file=request.files["ks_statement"],
        detail_file=request.files["ks_detail"],
        ar_file=request.files["ar_bill"],
        skd_date=request.form.get("skd_date") or None,
    )

    return _json_response(code=0, msg="success", data=data)


@reconciliation_bp.route('/download/<task_id>/<filename>', methods=['GET'])
@_handle_api_exceptions
def api_download_result(task_id, filename):
    """
    下载对账结果文件（备用接口，也可以直接访问 static URL）

    路径参数：
        - task_id: 任务 ID
        - filename: 文件名
    """
    # ---- 参数校验：防止路径穿越 ----
    if ".." in task_id or ".." in filename or "/" in filename or "\\" in filename:
        raise ParameterError("非法参数")

    # ---- 调用业务层解析文件路径 ----
    file_path = resolve_result_file(task_id, filename)
    if not file_path:
        return _json_response(code=1, msg="文件不存在或已过期", data=None), 404

    return send_file(file_path, as_attachment=True)
