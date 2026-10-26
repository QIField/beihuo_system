# -*- coding:utf-8 -*-
# @Time    : 2026/10/11 10:00
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : visit_manage_web.py
# @Software: PyCharm
# 客访管理页面路由（模板拆分见 templates/visit_manage/，设计文档见 doc/客访管理/）
from flask import render_template, Blueprint, abort

from app.core.permission.decorators import require_page_login

visit_manage_web_bp = Blueprint(
    "visit_manage_web",          # 蓝图唯一标识
    __name__,
    template_folder="../templates",  # 模板路径（默认即可）
    static_folder="../static",       # 静态资源路径（默认即可）
    url_prefix="/visit_manage"       # 子蓝图前缀，注册到 common_web_bp 后实际为 /web/visit_manage
)

# 子页面片段白名单（主页面 hash 路由按需加载，禁止渲染白名单外的模板）
VISIT_MANAGE_VIEW_TPLS = {
    "customer_list.html":      "visit_manage/views/customer_list.html",       # M1 客户列表
    "customer_detail.html":    "visit_manage/views/customer_detail.html",     # M2+M3 详情头部+指标卡
    "detail_visit_tab.html":   "visit_manage/views/detail_visit_tab.html",    # M4 拜访历史
    "detail_order_tab.html":   "visit_manage/views/detail_order_tab.html",    # M5 拿货订单
    "detail_info_tab.html":    "visit_manage/views/detail_info_tab.html",     # M6 基础档案
    "detail_follow_tab.html":  "visit_manage/views/detail_follow_tab.html",   # M7 跟进记录
    "settings.html":           "visit_manage/views/settings.html",            # 设置（高德客户Excel上传）
}


@visit_manage_web_bp.route("/")
@require_page_login()
def visit_manage_main():
    """客访管理主页面

    注意：URL 以 / 结尾（目录形态）。主页面内片段相对路径 'views/xxx.html'
    依赖当前目录解析为 /web/visit_manage/views/xxx.html，请勿改为无斜杠路由。
    访问 /web/visit_manage 时 Flask 会自动 308 重定向到 /web/visit_manage/。
    """
    return render_template("visit_manage/visit_manage_main_web.html")


@visit_manage_web_bp.route("/views/<view_name>")
@require_page_login()
def visit_manage_view(view_name):
    """客访管理子页面片段（HTML 片段，由主页面 $.load 注入渲染）"""
    tpl = VISIT_MANAGE_VIEW_TPLS.get(view_name)
    if tpl is None:
        abort(404)
    return render_template(tpl)
