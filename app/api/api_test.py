# -*- coding:utf-8 -*-
# @Time    : 2026/4/3 17:05
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : wms_orders.py
# @Software: PyCharm
from flask import jsonify

from app.api import api_bp
from app.services.dashboard_crm_wms_services import wms_orders


@api_bp.route('/test', methods=['GET'])
def api_test():
    print("api_test")



    return jsonify({
        'code': 200,
        'msg': 'success',
        'data': "test成功"
    })