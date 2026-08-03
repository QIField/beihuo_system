"""
采购历史比对接口
用于生成OE+品牌的采购历史比对Excel
"""
from functools import wraps
from flask import Blueprint, jsonify, request, session, send_file
import os
import tempfile
import traceback
from datetime import datetime

from app.services.compare_service.procurement_compare_service import ProcurementCompareService
from app.utils.export_tools.purchase_history_excel_writer import PurchaseHistoryExcelWriter
from app.core.async_task_store import submit_excel_task, get_task_status
from app.utils.logger_config import get_task_logger

logger = get_task_logger('purchase_history_compare')

# 创建蓝图
bp = Blueprint('purchase_history_compare', __name__)


def login_required(f):
    """登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return jsonify({'code': 1, 'msg': '未登录，请先登录'}), 401
        return f(*args, **kwargs)
    return decorated_function


def get_user_company():
    """获取用户当前的公司/门店代码"""
    user_store = session.get('store', 'fsbbr')
    current_org = session.get('current_org', user_store)
    if not current_org or current_org in ('all', 'none', 'undefined', ''):
        return user_store
    return current_org


@bp.route('/export', methods=['POST'])
@login_required
def export_compare_excel():
    """
    导出采购历史比对Excel
    
    请求参数:
    {
        "items": [
            {"oe": "12345", "brand": "博世"},
            {"oe": "67890", "brand": "法雷奥"}
        ]
    }
    
    返回:
        Excel文件下载
    """
    try:
        data = request.get_json()
        if not data or 'items' not in data:
            return jsonify({'code': 1, 'msg': '缺少参数: items'}), 400
        
        items = data['items']
        if not items or not isinstance(items, list):
            return jsonify({'code': 1, 'msg': 'items不能为空'}), 400

        # 校验每个 item 必须有 oe 和 brand
        for idx, item in enumerate(items):
            if not item or not isinstance(item, dict):
                return jsonify({'code': 1, 'msg': f'第{idx + 1}条数据格式错误'}), 400
            has_oe_brand = bool(item.get('oe') and item.get('brand'))
            has_brand_code = bool(item.get('brand_code'))
            if not (has_oe_brand or has_brand_code):
                return jsonify({'code': 1, 'msg': f'第{idx + 1}条数据缺少OE+品牌或品牌号'}), 400

        # 获取用户公司
        company = get_user_company()

        # 批量生成比对结果
        results = ProcurementCompareService.batch_generate_compare_results(items, company)

        if not results:
            return jsonify({'code': 1, 'msg': '没有查询到采购历史数据'}), 404
        
        # 生成Excel文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_filename = f'purchase_history_compare_{timestamp}.xlsx'
        output_path = os.path.join(tempfile.gettempdir(), output_filename)

        PurchaseHistoryExcelWriter.generate_excel(results, output_path)

        # 返回文件
        return send_file(
            output_path,
            as_attachment=True,
            download_name=output_filename
        )

    except Exception as e:
        error_trace = traceback.format_exc()
        logger.exception(f"[ERROR] export_compare_excel: {str(e)}")
        return jsonify({'code': 1, 'msg': f'生成失败: {str(e)}'}), 500


def _async_generate_excel(items, company, progress_callback=None):
    """
    异步生成采购历史比对 Excel
    供 submit_excel_task 调用
    """
    results = ProcurementCompareService.batch_generate_compare_results(
        items, company, progress_callback=progress_callback
    )
    if not results:
        raise ValueError('没有查询到采购历史数据')

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_filename = f'purchase_history_compare_{timestamp}.xlsx'
    output_path = os.path.join(tempfile.gettempdir(), output_filename)

    PurchaseHistoryExcelWriter.generate_excel(results, output_path)
    return output_path


@bp.route('/export_async', methods=['POST'])
@login_required
def export_compare_excel_async():
    """
    异步提交采购历史比对 Excel 生成任务

    请求参数:
    {
        "items": [
            {"oe": "12345", "brand": "博世"},
            ...
        ]
    }

    返回:
    {
        "code": 0,
        "data": {"task_id": "excel_xxx"}
    }
    """
    try:
        data = request.get_json()
        if not data or 'items' not in data:
            return jsonify({'code': 1, 'msg': '缺少参数: items'}), 400

        items = data['items']
        if not items or not isinstance(items, list):
            return jsonify({'code': 1, 'msg': 'items不能为空'}), 400

        for idx, item in enumerate(items):
            if not item or not isinstance(item, dict):
                return jsonify({'code': 1, 'msg': f'第{idx + 1}条数据格式错误'}), 400
            has_oe_brand = bool(item.get('oe') and item.get('brand'))
            has_brand_code = bool(item.get('brand_code'))
            if not (has_oe_brand or has_brand_code):
                return jsonify({'code': 1, 'msg': f'第{idx + 1}条数据缺少OE+品牌或品牌号'}), 400

        company = get_user_company()
        task_id = submit_excel_task(_async_generate_excel, items, company)

        return jsonify({'code': 0, 'msg': '任务已提交', 'data': {'task_id': task_id}})

    except Exception as e:
        error_trace = traceback.format_exc()
        logger.exception(f"[ERROR] export_compare_excel_async: {str(e)}")
        return jsonify({'code': 1, 'msg': f'提交失败: {str(e)}'}), 500


@bp.route('/export_status/<task_id>', methods=['GET'])
@login_required
def export_compare_excel_status(task_id):
    """
    查询异步任务状态和进度
    """
    try:
        task = get_task_status(task_id)
        if not task:
            return jsonify({'code': 1, 'msg': '任务不存在'}), 404
        return jsonify({'code': 0, 'msg': 'ok', 'data': task})
    except Exception as e:
        logger.warning(f"[ERROR] export_compare_excel_status: {str(e)}")
        return jsonify({'code': 1, 'msg': f'查询失败: {str(e)}'}), 500


@bp.route('/export_download/<task_id>', methods=['GET'])
@login_required
def export_compare_excel_download(task_id):
    """
    下载已完成的异步任务 Excel 文件
    """
    try:
        task = get_task_status(task_id)
        if not task:
            return jsonify({'code': 1, 'msg': '任务不存在'}), 404
        if task.get('status') != 'completed':
            return jsonify({'code': 1, 'msg': '任务未完成'}), 400

        result_file = task.get('result_file')
        if not result_file or not os.path.exists(result_file):
            return jsonify({'code': 1, 'msg': '文件不存在或已过期'}), 404

        return send_file(
            result_file,
            as_attachment=True,
            download_name=os.path.basename(result_file)
        )
    except Exception as e:
        logger.warning(f"[ERROR] export_compare_excel_download: {str(e)}")
        return jsonify({'code': 1, 'msg': f'下载失败: {str(e)}'}), 500
