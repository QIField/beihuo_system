# -*- coding:utf-8 -*-
# @Time    : 2026/09/03
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : order_share_web.py
# @Software: trae-cn

"""
订单分享公开页面路由

访问形式：GET /ddxx?dd=<加密订单号>
说明：本路由面向客户/终端用户，扫码或直接输入网址均可访问，不做登录校验
     （与内部页面的 require_page_login 装饰器区分开）。
"""

import logging

from flask import Blueprint, render_template, request

from app.services.order_share_service import crypto_service, order_view_service

logger = logging.getLogger(__name__)

order_share_web_bp = Blueprint(
    "order_share_web",
    __name__,
    template_folder="../templates",  # 回退使用根目录 templates/
)


@order_share_web_bp.route("/ddxx")
def order_share_page():
    """扫码/输入网址进入的订单信息页"""
    cipher = (request.args.get("dd") or "").strip()

    order_no = crypto_service.decrypt_order_no(cipher)
    order = order_view_service.get_order_basic_by_no(order_no) if order_no else None

    if order:
        logger.info("[订单分享] 页面访问成功 order_no=%s", order_no)
    else:
        logger.info("[订单分享] 页面访问失败（链接无效或订单不存在）")

    # 链接无效、解密失败、订单不存在，统一渲染友好提示页
    return render_template("order_share/order_detail.html", order=order)
