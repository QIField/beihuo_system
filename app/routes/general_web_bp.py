# -*- coding:utf-8 -*-
# @Time    : 2026/4/3 17:30
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : general_web.py
# @Software: PyCharm
from flask import Blueprint, render_template

# 创建蓝图：名称=main，模板文件夹默认继承app/templates
general_web_bp = Blueprint(
    "general_web",  # 蓝图唯一标识
    __name__,
    template_folder="../templates",  # 模板路径（默认即可）
    static_folder="../static"        # 静态资源路径（默认即可）
)




@general_web_bp.route("/dashboard_crm_wms")
def dashboard_crm_wms():
    """仓库大屏"""
    return render_template("crm_wms_web.html")


@general_web_bp.route("/system_config")
def system_config():
    """系统配置管理"""
    return render_template("system_setting_web/beihuo_system_config_web.html")


@general_web_bp.route("/transaction_sum_web")
def transaction_sum():

    return render_template("customer_quota_manager_web/transaction_sum_web.html")


@general_web_bp.route("/diff_replace_number")
def diff_replace_number_page():
    """替换号差异对比页面"""
    return render_template("diff_replace_number.html")