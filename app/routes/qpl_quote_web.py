# -*- coding:utf-8 -*-
# @Time    : 2026/6/5
# @Author  : system
# @Project : beihuo_system
# @File    : qpl_quote_web.py
# @Software: PyCharm

from flask import Blueprint, render_template

qpl_quote_web_bp = Blueprint(
    "qpl_quote_web",
    __name__,
    template_folder="../templates",
    static_folder="../static"
)


@qpl_quote_web_bp.route("/qpl_quote_records")
def qpl_quote_records():
    """汽配龙自动报价记录页面"""
    return render_template("qpl_quote_record.html")
