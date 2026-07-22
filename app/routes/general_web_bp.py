# -*- coding:utf-8 -*-
# @Time    : 2026/4/3 17:30
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : general_web.py
# @Software: PyCharm
from flask import Blueprint, render_template
from app.core.permission.decorators import require_page_login

# 创建蓝图：名称=main，模板文件夹默认继承app/templates
general_web_bp = Blueprint(
    "general_web",  # 蓝图唯一标识
    __name__,
    template_folder="../templates",  # 模板路径（默认即可）
    static_folder="../static"        # 静态资源路径（默认即可）
)




# @general_web_bp.route("/dashboard_crm_wms")
# def dashboard_crm_wms():
#     """仓库大屏"""
#     return render_template("crm_wms_web.html")


@general_web_bp.route("/system_config")
@require_page_login()
def system_config():
    """系统配置管理"""
    return render_template("system_setting_web/beihuo_system_config_web.html")


@general_web_bp.route("/transaction_sum_web")
@require_page_login()
def transaction_sum():
    return render_template("customer_quota_manager_web/transaction_sum_web.html")


@general_web_bp.route("/replace_number_edit")
def replace_number_edit_page():
    """替换号编辑页面"""
    return render_template("replace_number_edit.html")


@general_web_bp.route("/unpaid_customer_web")
@require_page_login()
def unpaid_customer():
    return render_template("customer_quota_manager_web/unpaid_customer_web.html")


@general_web_bp.route("/expected_unpaid_customers_web")
@require_page_login()
def expected_unpaid_customers():
    return render_template("customer_quota_manager_web/expected_unpaid_customers_web.html")


@general_web_bp.route("/customer_quota_web")
@require_page_login()
def customer_quota():
    """客户额度管理"""
    return render_template("customer_quota_manager_web/customer_quota_web.html")


@general_web_bp.route("/display_unpaid_customer_limit_web")
@require_page_login()
def display_unpaid_customer_limit():
    """未付款客户额度展示"""
    return render_template("customer_quota_manager_web/display_unpaid_customer_limit_web.html")


@general_web_bp.route("/ks_inquiry_records")
@require_page_login()
def ks_inquiry_records():
    """开思询价明细页面"""
    return render_template("ks_inquiry_records/ks_inquiry_records_main.html")