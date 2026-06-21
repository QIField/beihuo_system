# -*- coding: utf-8 -*-
# @Time    : 2026/6/20
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : excel_download.py
# @Software: PyCharm
# @Desc    : Excel 文件下载专用蓝图
#            通用路由约定文件名格式为 {category}_{company}_{date_str}.xlsx
#            存放目录统一为 static/exports/

import os
from flask import Blueprint, send_file, abort

excel_download_bp = Blueprint('excel_download', __name__)

# Excel 导出文件统一存放目录
EXPORT_DIR = os.path.join('static', 'exports')


@excel_download_bp.route('/download_excel/<category>/<company>/<date_str>')
def download_excel(category, company, date_str):
    """
    通用 Excel 下载接口
    文件命名约定：static/exports/{category}_{company}_{date_str}.xlsx

    新增业务时无需新增路由，按命名规则把文件落到 static/exports/ 即可复用本接口。

    :param category: 业务分类（如 inventory / ks_nonself）
    :param company: 门店/组织代号
    :param date_str: 日期字符串
    """
    file_path = os.path.join(EXPORT_DIR, f'{category}_{company}_{date_str}.xlsx')
    if not os.path.exists(file_path):
        abort(404)
    return send_file(file_path, as_attachment=True)


@excel_download_bp.route('/download_inventory/<company>/<date_str>')
def download_inventory(company, date_str):
    """
    [兼容旧路由] 下载指定门店和日期的库存变动记录 Excel 文件
    历史推送消息中已写死该 URL，保留以避免链接失效。
    新业务请使用通用路由 /download_excel/<category>/<company>/<date_str>。
    """
    file_path = os.path.join(EXPORT_DIR, f'inventory_{company}_{date_str}.xlsx')
    if not os.path.exists(file_path):
        abort(404)
    return send_file(file_path, as_attachment=True)
