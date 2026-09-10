# -*- coding:utf-8 -*-
# @Time    : 2026/09/03
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : order_share_web.py
# @Software: trae-cn

"""
订单分享公开页面路由

访问形式：GET /order/view?no=<加密订单号>
说明：本路由面向客户/终端用户，扫码或直接输入网址均可访问，不做登录校验
     （与内部页面的 require_page_login 装饰器区分开）。
"""

import logging
import time

from flask import Blueprint, render_template, request

from app.services.order_share_service import crypto_service, order_view_service

logger = logging.getLogger("order_share")

order_share_web_bp = Blueprint(
    "order_share_web",
    __name__,
    template_folder="../templates",  # 回退使用根目录 templates/
)


@order_share_web_bp.route("/order/view")
def order_share_page():
    """扫码/输入网址进入的订单信息页"""
    start = time.time()
    cipher = (request.args.get("no") or "").strip()
    logger.info("[订单分享] 收到请求 cipher=%s...", cipher[:20])

    try:
        order_no = crypto_service.decrypt_order_no(cipher)
    except Exception as e:
        logger.exception("[订单分享] 解密失败: %s", e)
        order_no = None

    if order_no:
        order = order_view_service.get_order_basic_by_no(order_no)
    else:
        order = None

    elapsed = (time.time() - start) * 1000
    if order:
        logger.info("[订单分享] 页面访问成功 order_no=%s cost=%.0fms", order_no, elapsed)
    else:
        logger.info("[订单分享] 页面访问失败（链接无效或订单不存在）cost=%.0fms", elapsed)

    # 链接无效、解密失败、订单不存在，统一渲染友好提示页
    return render_template("order_share/order_detail.html", order=order)
