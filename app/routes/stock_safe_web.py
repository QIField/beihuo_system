



from flask import Blueprint, render_template

from app.core.permission.decorators import require_page_login



stock_safe_web_bp = Blueprint(
    "stock_safe_web",  # 蓝图唯一标识
    __name__,
    template_folder="../templates",  # 模板路径
    static_folder="../static",        # 静态资源路径
    url_prefix='/stock_safe_web'
)



@stock_safe_web_bp.route("/stock_safe")
@require_page_login()
def stock_safe_page():
    """安全库存看板页面"""
    return render_template("stock_safe.html")