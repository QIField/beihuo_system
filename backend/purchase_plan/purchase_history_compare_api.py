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
            if not item.get('oe'):
                return jsonify({'code': 1, 'msg': f'第{idx + 1}条数据缺少OE号'}), 400
            if not item.get('brand'):
                return jsonify({'code': 1, 'msg': f'第{idx + 1}条数据缺少品牌'}), 400

        # 获取用户公司
        company = get_user_company()

        # 批量生成比对结果
        results = ProcurementCompareService.batch_generate_compare_results(items, company)

        if not results:
            return jsonify({'code': 1, 'msg': '没有查询到采购历史数据'}), 404
        
        # 生成Excel文件
        template_path = 'static/excel/compare_price.xlsx'
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_filename = f'purchase_history_compare_{timestamp}.xlsx'
        output_path = os.path.join(tempfile.gettempdir(), output_filename)
        
        PurchaseHistoryExcelWriter.generate_excel(results, template_path, output_path)
        
        # 返回文件
        return send_file(
            output_path,
            as_attachment=True,
            download_name=output_filename
        )
        
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"[ERROR] export_compare_excel: {str(e)}")
        print(error_trace)
        return jsonify({'code': 1, 'msg': f'生成失败: {str(e)}'}), 500
