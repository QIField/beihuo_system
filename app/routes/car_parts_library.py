from flask import Blueprint, render_template

car_parts_library_bp = Blueprint(
    "car_parts_library",  # 蓝图唯一标识
    __name__,
    template_folder="../templates",  # 模板路径
    static_folder="../static",        # 静态资源路径
    url_prefix='/car_parts_library'
)

@car_parts_library_bp.route("/main")
def car_parts_library_list():
    """汽车配件库主页面"""
    return render_template("car_parts_library/car_parts_library_main.html")

@car_parts_library_bp.route("/list")
def list_html():
    """列表页片段"""
    return render_template("car_parts_library/list.html")

@car_parts_library_bp.route("/detail")
def detail_html():
    """详情页片段"""
    return render_template("car_parts_library/detail.html")


