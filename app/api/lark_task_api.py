# -*- coding:utf-8 -*-
"""
飞书任务同步 - 回调接口

飞书任务状态变更事件推送入口。
"""

from flask import Blueprint, request, jsonify

from app.services.lark_task_sync.sync_service import handle_lark_webhook

lark_task_bp = Blueprint("lark_task", __name__, url_prefix="/lark-task")


@lark_task_bp.route("/webhook", methods=["POST"])
def webhook():
    """
    飞书事件订阅回调入口。

    飞书会对请求体进行加密，需用 lark_encrypt_key 解密。
    事件处理幂等，重复事件自动忽略。
    """
    try:
        payload = request.get_json(silent=True) or {}
        result = handle_lark_webhook(payload)

        # URL 验证时返回 {challenge: xxx}
        if isinstance(result, dict) and 'challenge' in result:
            return jsonify(result)

        return jsonify({"code": 0, "msg": "success"})
    except Exception:
        # 回调接口不要抛 500，避免飞书重试风暴
        return jsonify({"code": 0, "msg": "success"})
