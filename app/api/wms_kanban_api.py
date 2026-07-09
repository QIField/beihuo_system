# -*- coding:utf-8 -*-
# @Time    : 2026/06/26 14:57
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : crm_kanban_api.py
# @Software: trae-cn




from flask import Blueprint, request
from flask.json import jsonify

from app.core.permission.decorators import require_authentication
from app.services.dashboard_crm_wms_services.dashboard_crm_wms_services import get_dashboard_crm_wms_data

# 创建看板主蓝图（保持与原文件相同的名称，确保API地址不变）
wms_kanban_api_bp = Blueprint('wms_kanban_api', __name__, url_prefix='/wms_kanban')



@wms_kanban_api_bp.route('/screen_data', methods=['GET'])
@require_authentication()
def wms_kanban_screen_api():
    """
    获取看板屏幕数据
    """

    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    keyword = request.args.get('keyword', '')
    status = request.args.get('status', '')
    data = get_dashboard_crm_wms_data(start_date, end_date, keyword, status)
    return jsonify({
        'code': 200,
        'msg': '查询成功',
        'data': data
    })
