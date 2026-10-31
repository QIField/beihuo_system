# -*- coding:utf-8 -*-
# 客访管理 API 包：visit_api.py（列表/导入/绑定/拜访记录）+ visit_detail_api.py（客户详情聚合）
#                 + visit_follow_api.py（M7 跟进记录）+ visit_expense_api.py（费用分析模块）


from flask import Blueprint

# 创建 visit 子蓝图，URL前缀为 /visit
visit_bp = Blueprint('visit', __name__, url_prefix='/visit')

# 导入并注册路由
from . import visit_api, visit_detail_api, visit_follow_api, visit_expense_api
