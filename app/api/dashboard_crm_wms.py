# -*- coding:utf-8 -*-
# @Time    : 2026/4/3 17:17
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : dashboard_crm_wms.py
# @Software: PyCharm
import json

from flask import request, Response, jsonify

from app.api import api_bp
from app.services.dashboard_crm_wms_services.dashboard_crm_wms import crawl_data_crm_wms


@api_bp.route('/dashboard_crm_wms')
def dashboard_crm_wms():
    print("dashboard_crm_wms")


    # 获取参数
    start_date = request.args.get('start_date')  # 必传
    end_date = request.args.get('end_date')  # 有默认值，可不传

    data= crawl_data_crm_wms(start_date,end_date)

    return jsonify({
        'code': 200,
        'msg': 'success',
        'data': data
    })


