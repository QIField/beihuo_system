"""
替换号差异对比页面路由

专门存放 diff_replace_number 相关页面路由
"""

from flask import Blueprint, render_template

# 创建页面路由蓝图（根路径，无前缀）
diff_replace_number_bp = Blueprint('diff_replace_number', __name__, template_folder='../../templates')


@diff_replace_number_bp.route("/diff_replace_number")
def diff_replace_number_page():
    """替换号差异对比页面"""
    return render_template("diff_replace_number.html")
