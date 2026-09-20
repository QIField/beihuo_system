# -*- coding:utf-8 -*-
"""
飞书任务同步 - 回调接口

飞书任务状态变更事件推送入口。
"""

from flask import Blueprint, request, jsonify

from app.utils.logger_config import get_task_logger
from app.services.lark_task_sync.sync_service import handle_lark_webhook, sync_task_status_from_lark

logger = get_task_logger('lark_task_sync')

lark_task_bp = Blueprint("lark_task", __name__, url_prefix="/lark-task")


@lark_task_bp.route("/webhook", methods=["POST"])
def webhook():
    """
    飞书事件订阅回调入口。

    飞书会对请求体进行加密，需用 lark_encrypt_key 解密。
    事件处理幂等，重复事件自动忽略。
    """
    try:
        raw_body = request.get_data(as_text=True)
        logger.info(
            f"[飞书回调] 收到请求, path={request.path}, "
            f"method={request.method}, remote_addr={request.remote_addr}, "
            f"content_type={request.content_type}, "
            f"headers={dict(request.headers)}, body={raw_body}"
        )

        payload = request.get_json(silent=True) or {}
        logger.info(f"[飞书回调] 解析后 payload={payload}")
        result = handle_lark_webhook(payload)
        logger.info(f"[飞书回调] 处理结果, result={result}")

        # URL 验证时返回 {challenge: xxx}
        if isinstance(result, dict) and 'challenge' in result:
            return jsonify(result)

        return jsonify({"code": 0, "msg": "success"})
    except Exception:
        logger.exception("[飞书回调] 处理异常")
        # 回调接口不要抛 500，避免飞书重试风暴
        return jsonify({"code": 0, "msg": "success"})


@lark_task_bp.route("/sync-status", methods=["POST"])
def sync_status():
    """
    主动从飞书同步任务状态。

    请求体为空时同步所有未完成任务；传入 {"business_id": 1} 时只同步指定任务。
    """
    try:
        data = request.get_json(silent=True) or {}
        business_id = data.get("business_id")
        result = sync_task_status_from_lark(business_id=business_id)
        return jsonify(result)
    except Exception as e:
        logger.exception("[飞书状态同步] 接口异常")
        return jsonify({"code": 500, "msg": f"同步失败: {str(e)}"}), 500
