



import os
from datetime import datetime
from flask import Blueprint, render_template, send_file, request, jsonify, abort

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


# ---------- 安全库存 Excel 导出（实时生成 + 下载） ----------

# Excel 导出文件统一存放目录
EXPORT_DIR = os.path.join('static', 'exports')


@stock_safe_web_bp.route('/generate_stock_safe_excel', methods=['GET', 'POST'])
def generate_stock_safe_excel():
    """
    【实时生成并下载】安全库存 Excel

    从 stock_safe 表查询数据 -> 写入 static/exports/ -> 返回文件流下载。
    支持与列表页一致的筛选参数（keyword / stock_status / abc_classification 等）。

    Query 参数:
        company:           门店/组织代号，默认 fsbbr
        date_str:          日期字符串（用于文件名），默认当天 YYYY-MM-DD
        keyword:           搜索关键词（匹配 OE号/品牌/产品名称/条码）
        stock_status:      库存状态筛选
        abc_classification: ABC 分类筛选（A/B/C）
        sort_field:        排序字段名
        sort_order:        排序方向 asc / desc
        return_url:        传 1 时不直接下载文件，仅返回 JSON 包含 download_url（供微信推送场景）
    """
    try:
        # 兼容 GET 和 POST：统一从 values 取参数
        args = request.values
        company = args.get('company', 'fsbbr')
        date_str = args.get('date_str') or datetime.now().strftime("%Y-%m-%d")
        keyword = args.get('keyword', '') or ''
        stock_status = args.get('stock_status', '') or ''
        abc_classification = args.get('abc_classification', '') or ''
        sort_field = args.get('sort_field', '') or ''
        sort_order = args.get('sort_order', 'asc') or 'asc'
        return_url = args.get('return_url', '0') == '1'

        # 延迟导入，避免循环依赖
        from app.services.stock_safe_service.create_excel import generate_stock_safe_excel as _gen

        result = _gen(
            company=company,
            date_str=date_str,
            keyword=keyword,
            stock_status=stock_status,
            abc_classification=abc_classification,
            sort_field=sort_field,
            sort_order=sort_order,
        )

        if not result.get('success'):
            return jsonify({'code': 1, 'msg': result.get('msg', '导出失败')}), 400

        # 如果指定 return_url=1，则返回 JSON 结果（供后台任务或推送使用）
        if return_url:
            return jsonify({
                'code': 0,
                'msg': 'success',
                'data': {
                    'file_name': result.get('file_name'),
                    'file_path': result.get('file_path'),
                    'download_url': result.get('download_url'),
                    'record_count': result.get('record_count'),
                },
            })

        # 否则直接返回文件流下载
        file_path = result.get('file_path')
        if not file_path or not os.path.exists(file_path):
            return jsonify({'code': 1, 'msg': '文件生成失败或不存在'}), 500

        return send_file(file_path, as_attachment=True)

    except Exception as e:
        from app.utils.logger_config import get_task_logger
        logger = get_task_logger('stock_safe')
        logger.exception(f"[安全库存Excel路由] 异常: {e}")
        return jsonify({'code': 1, 'msg': f'服务器异常: {str(e)}'}), 500