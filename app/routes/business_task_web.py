# -*- coding:utf-8 -*-
"""
业务任务管理前端页面路由

职责：将 design-prototype 目录下的静态页面接入 Flask，并做登录校验。
页面与 API 同域，可直接使用 session cookie 调用 /new/api 接口。
"""

from flask import Blueprint, render_template

from app.core.permission.decorators import require_page_login


business_task_web_bp = Blueprint(
    'business_task_web',
    __name__,
    url_prefix='/business-task',
)


@business_task_web_bp.route('/', defaults={'page': 'index'})
@business_task_web_bp.route('/<path:page>')
@require_page_login()
def serve_page(page):
    if not page.endswith('.html'):
        page += '.html'
    return render_template(f'business_task_web/{page}')
