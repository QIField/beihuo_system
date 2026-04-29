# -*- coding:utf-8 -*-
# @Time    : 2026/4/28 17:30
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : report_wx_quote_data_web.py
# @Software: PyCharm
from flask import render_template, Blueprint

report_wx_quote_data_web_bp = Blueprint(
    "report_wx_quote_data",  # 蓝图唯一标识
    __name__,
    template_folder="../templates",  # 模板路径（默认即可）
    static_folder="../static",        # 静态资源路径（默认即可）
    url_prefix='/views'
)


@report_wx_quote_data_web_bp.route("/weixin_decoding_result")
def weixin_decoding_result():
    """每日报价明细"""
    return render_template("report_wx_quote_data_web/weixin_decoding_result_web.html")


@report_wx_quote_data_web_bp.route("/daily_summary")
def daily_summary():
    """每日汇总"""
    return render_template("report_wx_quote_data_web/daily_summary_web.html")


@report_wx_quote_data_web_bp.route("/monthly_summary")
def monthly_summary():
    """每月汇总"""
    return render_template("report_wx_quote_data_web/monthly_summary_web.html")


@report_wx_quote_data_web_bp.route("/report_wx_quote_data_main_web")
def report_wx_quote_data_main_web():
    """微信报价数据报告主页面"""
    return render_template("report_wx_quote_data_web/report_wx_quote_data_main_web.html")
