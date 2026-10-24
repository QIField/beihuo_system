"""用户权限标志注册表

主项目 crmapp_users 的 can_xxx 权限字段统一在此登记。
登录 session、current_user 返回、用户增改查、启动补列、前端菜单/弹窗/表格
均循环本清单处理；新增权限只需在后端清单和前端清单各加一行。
"""
from functools import wraps

from flask import jsonify, session


# admin_default: 登录账号为 admin 时该权限默认开启（与历史行为一致）
USER_PERMISSION_FLAGS = [
    {"field": "can_delete_cart", "label": "删除购物车", "width": 90, "admin_default": False},
    {"field": "can_process_orders", "label": "处理单据", "width": 80, "admin_default": True},
    {"field": "can_inquiry_module", "label": "询价模块", "width": 80, "admin_default": True},
    {"field": "can_compare_module", "label": "比价模块", "width": 80, "admin_default": True},
    {"field": "can_update_crm", "label": "更新CRM", "width": 80, "admin_default": True},
    {"field": "can_multi_channel_quote_adjust", "label": "多渠道报价", "width": 90, "admin_default": True},
    {"field": "can_cass_inquiry", "label": "修理厂询价单", "width": 105, "admin_default": False},
    {"field": "can_business_task", "label": "企业业务系统", "width": 105, "admin_default": False},
]


def flag_required(flag, msg=None):
    """页面/接口权限拦截：session 中无该标志时返回 403"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not session.get(flag):
                return jsonify({'code': 1, 'msg': msg or '您没有权限访问该功能'}), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator
