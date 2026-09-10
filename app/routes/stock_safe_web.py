



import os
from datetime import datetime
from flask import Blueprint, render_template, send_file, request, jsonify, abort, url_for

from app.core.permission.decorators import require_page_login
from app.services.stock_safe_service.replenish import get_replenish_file_path



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
    return render_template("stock_safe/stock_safe.html")


@stock_safe_web_bp.route("/download_replenish_excel/<timestamp>")
def download_replenish_excel(timestamp):
    """
    补货清单 Excel 下载页

    时间戳格式：YYYYMMDD_HHMMSS，对应文件 补货清单_YYYYMMDD_HHMMSS.xlsx。
    文件存在时展示“下载中”页面并自动触发下载；文件不存在或文件名非法时展示错误提示。
    """
    file_name = f"补货清单_{timestamp}.xlsx"
    file_path = get_replenish_file_path(file_name)

    if not file_path:
        return render_template(
            "stock_safe/download_replenish_error.html",
            message="文件不存在或文件名非法，请重新生成补货清单后再试。",
        )

    download_url = url_for(
        "common_web.stock_safe_web.download_replenish_excel_file",
        timestamp=timestamp,
    )
    return render_template(
        "stock_safe/download_replenish_excel.html",
        download_url=download_url,
    )


@stock_safe_web_bp.route("/download_replenish_excel_file/<timestamp>")
def download_replenish_excel_file(timestamp):
    """
    补货清单 Excel 文件下载（返回文件流）

    时间戳格式：YYYYMMDD_HHMMSS，对应文件 补货清单_YYYYMMDD_HHMMSS.xlsx。
    文件不存在或文件名非法时返回 404。
    """
    file_name = f"补货清单_{timestamp}.xlsx"
    file_path = get_replenish_file_path(file_name)

    if not file_path:
        abort(404)

    return send_file(file_path, as_attachment=True, download_name=file_name)


