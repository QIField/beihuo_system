# -*- coding:utf-8 -*-
# @Time    : 2026/4/29 11:37
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : data_gzbbr_api.py
# @Software: PyCharm
from flask import jsonify

from app.api.cookie import cookie_bp
from config.config_list_manager.config_cache import get_config_value


@cookie_bp.route('/<company>', methods=['GET'])
def get_company_cookie(company):
    """
    获取指定公司的 cookie/token（无需登录）
    :param company: 公司简称：fs(佛山), zh(珠海), zs(中山), by(东莞百业), hf(东莞合峰)
    """
    # 定义 company 到 config_key 的映射
    company_map = {
        'fs': 'data_gzbbr_com_fs',
        'zh': 'data_gzbbr_com_zh',
        'zs': 'data_gzbbr_com_zs',
        'by': 'data_gzbbr_com_by',
        'hf': 'data_gzbbr_com_hf'
    }

    # 如果 company 不在映射中，返回 404
    if company not in company_map:
        return jsonify({
            'code': 404,
            'msg': f'Company {company} not found. Supported: fs, zh, zs, by, hf',
            'data': None
        }), 404

    config_key = company_map[company]
    cookie = get_config_value(config_key)

    if cookie is None:
        return jsonify({
            'code': 404,
            'msg': f'Cookie for {company} not found',
            'data': None
        }), 404

    return jsonify({
        'code': 200,
        'msg': 'success',
        'data': {
            'company': company,
            'config_key': config_key,
            'token': cookie
        }
    })
