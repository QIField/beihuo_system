# -*- coding:utf-8 -*-
# @Time    : 2026/4/25 09:19
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : customer_quota_manager_web.py
# @Software: PyCharm
from flask import render_template, Blueprint

customer_quota_manager_web_bp = Blueprint(
    "customer_quota_manager",  # 蓝图唯一标识
    __name__,
    template_folder="../templates",  # 模板路径（默认即可）
    static_folder="../static",        # 静态资源路径（默认即可）
    url_prefix='/views'
)








@customer_quota_manager_web_bp.route("/customer_quota")
def customer_quota():
    """客户额度管理"""
    return render_template("customer_quota_manager_web/views/customer_quota.html")


@customer_quota_manager_web_bp.route("/unpaid_customer")
def unpaid_customer():
    return render_template("customer_quota_manager_web/views/unpaid_customer.html")


@customer_quota_manager_web_bp.route("/expected_unpaid_customers")
def expected_unpaid_customers():
    return render_template("customer_quota_manager_web/views/expected_unpaid_customers.html")


@customer_quota_manager_web_bp.route("/transaction_sum")
def transaction_sum():

    return render_template("customer_quota_manager_web/views/transaction_sum.html")


@customer_quota_manager_web_bp.route("/display_unpaid_customer_limit")
def display_unpaid_customer_limit():
    """未付款客户额度展示"""
    return render_template("customer_quota_manager_web/views/display_unpaid_customer_limit.html")

@customer_quota_manager_web_bp.route("/customer_quota_manager_main_web")
def customer_quota_manager_main_web():
    """未付款客户额度展示"""
    return render_template("customer_quota_manager_web/customer_quota_manager_main_web.html")


@customer_quota_manager_web_bp.route("/customer_quota_settings")
def customer_quota_settings():
    """应收单数据导入设置"""
    return render_template("customer_quota_manager_web/views/customer_quota_settings_web.html")
