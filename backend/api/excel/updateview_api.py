"""
UpdateView API接口
提供批量更新CRM产品视图信息的异步处理功能
"""
import os
import tempfile
from flask import request, jsonify, send_file
from datetime import datetime


def register_updateview_routes(app):
    """注册UpdateView相关的路由"""
    from functools import wraps
    from flask import session, jsonify
    
    def login_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'logged_in' not in session:
                return jsonify({'code': 1, 'msg': '未登录，请先登录'}), 401
            return f(*args, **kwargs)
        return decorated_function
    
    @app.route('/api/excel/async/update_crm_product', methods=['POST'])
    @login_required
    def async_update_crm_product():
        """
        异步提交更新CRM产品信息任务
        提交任务后立即返回task_id，前端通过task_id轮询状态
        
        请求参数:
        - file: 上传的Excel文件（必须包含：配件编码、品牌、品牌号、开思描述、开思价、同行价、汽配龙价格）
        
        响应:
        - code: 0成功，1失败
        - msg: 提示信息
        - data.task_id: 任务ID，用于查询状态和下载结果
        """
        try:
            # 检查权限
            if not session.get('can_update_crm', False):
                return jsonify({'code': 1, 'msg': '权限不足，无法更新CRM信息'}), 403
            
            # 检查文件
            if 'file' not in request.files:
                return jsonify({'code': 1, 'msg': '没有上传文件'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'code': 1, 'msg': '文件名为空'}), 400
            
            # 验证文件类型
            allowed_extensions = {'.xlsx', '.xls', '.csv'}
            file_ext = os.path.splitext(file.filename)[1].lower()
            if file_ext not in allowed_extensions:
                return jsonify({
                    'code': 1,
                    'msg': f'不支持的文件格式，仅支持: {", ".join(allowed_extensions)}'
                }), 400
            
            # 保存临时文件
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            temp_filename = f"updateview_{timestamp}_{file.filename}"
            temp_file_path = os.path.join(tempfile.gettempdir(), temp_filename)
            file.save(temp_file_path)
            
            # 提交异步任务
            from app.core.async_task_store import submit_excel_task
            from app.services.updateview_service import process_update_crm_product_async
            
            task_id = submit_excel_task(process_update_crm_product_async, temp_file_path)
            
            return jsonify({
                'code': 0,
                'msg': '任务已提交',
                'data': {'task_id': task_id}
            })
            
        except Exception as e:
            return jsonify({'code': 1, 'msg': f'提交失败: {str(e)}'}), 500
    
    @app.route('/api/excel/template/updateview', methods=['GET'])
    def download_updateview_template():
        """
        下载UpdateView模板文件
        模板文件路径: static/excel/updateview.xlsx
        """
        try:
            # 使用当前工作目录计算模板路径
            template_path = os.path.join(os.getcwd(), 'static', 'excel', 'updateview.xlsx')
            
            print(f"[UpdateView API] 模板路径: {template_path}")
            
            if not os.path.exists(template_path):
                return jsonify({
                    'code': 1,
                    'msg': f'模板文件不存在: {template_path}'
                }), 404
            
            return send_file(
                template_path,
                as_attachment=True,
                download_name='updateview_template.xlsx'
            )
            
        except Exception as e:
            return jsonify({
                'code': 1,
                'msg': f'下载模板失败: {str(e)}'
            }), 500
    
    @app.route('/api/excel/modes', methods=['GET'])
    def get_excel_modes():
        """
        获取支持的Excel处理模式列表（扩展已有接口）
        在原有模式基础上添加 update_crm_product 模式
        """
        return jsonify({
            'code': 0,
            'msg': '获取成功',
            'data': [
                {
                    'mode': 'two_column',
                    'name': '两列模式',
                    'description': '处理oe和brand两列数据',
                    'required_columns': ['oe', 'brand'],
                    'column_aliases': {
                        'oe': ['oe', 'OE', '物料条码', 'barcode'],
                        'brand': ['brand', '品牌', '品牌名称']
                    }
                },
                {
                    'mode': 'three_column',
                    'name': '三列模式',
                    'description': '处理oe、brand和brand_code三列数据',
                    'required_columns': ['oe', 'brand', 'brand_code'],
                    'column_aliases': {
                        'oe': ['oe', 'OE', '物料条码', 'barcode'],
                        'brand': ['brand', '品牌', '品牌名称'],
                        'brand_code': ['brand_code', '条码', '物料条码']
                    }
                },
                {
                    'mode': 'update_crm_product',
                    'name': '更新CRM产品信息',
                    'description': '批量更新CRM产品视图信息（开思描述、价格等）',
                    'required_columns': ['配件编码', '品牌'],
                    'optional_columns': ['品牌号', '开思描述', '开思价', '同行价', '汽配龙价格'],
                    'template_url': '/api/excel/template/updateview'
                }
            ]
        })
