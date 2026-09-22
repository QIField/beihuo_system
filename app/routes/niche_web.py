# -*- coding:utf-8 -*-
"""
商机模块前端页面路由

职责：
  1. 提供商机看板页面渲染

说明：
  - 数据接口统一放在 app/api/niche_api.py
  - 补货清单 Excel 下载已移除，商机数据由每日凌晨 2:00 定时任务自动刷新
"""

from flask import Blueprint, render_template

from app.core.permission.decorators import require_page_login


# 前端页面蓝图（挂载到 /web/niche_web）
niche_web_bp = Blueprint(
    "niche_web",
    __name__,
    template_folder="../templates",
    static_folder="../static",
    url_prefix='/niche_web'
)


# =============================================================================
# 页面路由
# =============================================================================

@niche_web_bp.route("/niche")
@require_page_login()
def niche_index_page():
    """商机看板页面"""
    return render_template("niche_web/index.html")
