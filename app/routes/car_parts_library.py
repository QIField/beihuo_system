from flask import Blueprint, render_template

car_parts_library_bp = Blueprint(
    "car_parts_library",  # 蓝图唯一标识
    __name__,
    template_folder="../templates",  # 模板路径
    static_folder="../static",        # 静态资源路径
    url_prefix='/car_parts_library'
)


@car_parts_library_bp.route("/cart")
def cart_html():
    """购物车页片段（沿用 combined 页面风格）"""
    return render_template("car_parts_library/car_parts_library_combined.html")


# ==================== 华晨宝马（BMW Brilliance）配件库页面路由 ====================

@car_parts_library_bp.route("/bmw")
def bmw_main_page():
    """
    宝马配件库主页面（单页 Tab 结构：
    - 列表页作为主 Tab（搜索 + 工具栏 + 表格）
    - 点击配件编号打开详情 Tab（基本信息、多仓库库存、采购历史）
    - 新增/编辑功能已移除
    页面路径: /car_parts_library/bmw
    """
    return render_template("car_parts_library/bmw_parts_main.html")


@car_parts_library_bp.route("/bmw_detail")
def bmw_detail_page():
    """
    宝马配件库详情页面（单页 Tab 结构：
    - 基本信息 Tab（基本信息、多仓库库存、采购历史）
    - 多仓库库存 Tab（多仓库库存详情）
    - 采购历史 Tab（采购历史记录）
    页面路径: /car_parts_library/bmw_detail
    """
    return render_template("car_parts_library/bmw_parts_detail.html")

@car_parts_library_bp.route("/benz_detail")
def benz_detail_page():
    """
    宝马配件库收藏页面（单页 Tab 结构：
    - 收藏列表 Tab（显示所有收藏的配件）
    - 收藏详情 Tab（点击收藏项打开详情 Tab）
    页面路径: /car_parts_library/bmw_favorites
    """
    return render_template("car_parts_library/benz_parts_detail.html")
