# -*- coding:utf-8 -*-
# @Time    : 2026/5/20
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : benz_parts_api.py
# @Software: PyCharm

"""
奔驰汽车配件库API接口
负责处理配件库的HTTP请求
"""

from flask import Blueprint, request, jsonify, send_file, session
from app.core.permission.decorators import require_authentication
from app.services.car_parts_library_service.car_parts_library_benz_service import get_part_by_number, get_parts_list_page, data_refresh, add_part, update_part, delete_part, import_parts, download_template
from app.services.car_parts_library_service.car_parts_favorite_service import batch_add_to_favorites
from app.services.car_parts_library_service.mercedes_dalfsc_service import by_part_number_get_data
import time

benz_parts_bp = Blueprint('benz_parts', __name__)


@benz_parts_bp.route('/list', methods=['GET'])
@require_authentication()
def get_parts_list():
    """
    获取配件列表（分页）

    参数:
        page: 页码，默认1
        page_size: 每页条数，默认20
        part_number: 配件编号筛选（可选）

    返回:
        {
            "code": 200,
            "msg": "success",
            "data": {
                "status": 操作状态,
                "msg": 提示信息,
                "parts_count": 零件信息条数,
                "stock_count": 库存信息条数
            }
        }
    """
    try:
        # 获取参数
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        part_number = request.args.get('part_number')

        # 查询数据
        result = get_parts_list_page(
            page=page,
            page_size=page_size,
            part_number=part_number
        )

        return jsonify({
            'code': 200,
            'msg': 'success',
            'data': result
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'查询失败: {str(e)}',
            'data': None
        })


@benz_parts_bp.route('/detail', methods=['GET'])
@require_authentication()
def get_part_detail():
    """
    获取配件详情

    参数:
        part_number: 配件编号（查询参数）

    返回:
        {
            "code": 200,
            "msg": "success",
            "data": {...}
        }
    """
    try:
        part_number = request.args.get('part_number')
        if not part_number:
            return jsonify({
                'code': 400,
                'msg': '配件编号不能为空',
                'data': None
            })
        
        part = get_part_by_number(part_number)
        if part:
            return jsonify({
                'code': 200,
                'msg': 'success',
                'data': part
            })
        else:
            return jsonify({
                'code': 404,
                'msg': '配件不存在',
                'data': None
            })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'查询失败: {str(e)}',
            'data': None
        })


@benz_parts_bp.route('/batch-refresh', methods=['POST'])
@require_authentication()
def batch_refresh_parts_data():
    """
    批量刷新配件数据 API

    请求参数:
    {
        "part_numbers": ["配件编号1", "配件编号2", ...]
    }

    返回:
    {
        "code": 200,
        "msg": "刷新成功",
        "data": {
            "status": true,
            "msg": "数据刷新成功",
            "parts_count": 零件信息条数,
            "stock_count": 库存信息条数
        }
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'code': 400,
                'msg': '请求参数不能为空',
                'data': None
            })
        
        part_numbers = data.get('part_numbers', [])
        
        if not part_numbers or len(part_numbers) == 0:
            return jsonify({
                'code': 400,
                'msg': '配件编号列表不能为空',
                'data': None
            })
        
        result = data_refresh(part_numbers)
        
        if result and result.get('status'):
            return jsonify({
                'code': 200,
                'msg': result.get('msg', '刷新成功'),
                'data': result
            })
        else:
            return jsonify({
                'code': 400,
                'msg': result.get('msg', '刷新失败'),
                'data': result
            })
        
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'批量刷新失败: {str(e)}',
            'data': None
        })


@benz_parts_bp.route('/add', methods=['POST'])
@require_authentication()
def add_part_api():
    """
    添加配件
    请求参数: 配件数据字典
    返回: 操作结果
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'code': 400,
                'msg': '请求参数不能为空',
                'data': None
            })
        
        # 验证配件编号是否存在
        if not data.get('part_number'):
            return jsonify({
                'code': 400,
                'msg': '配件编号不能为空',
                'data': None
            })
        
        result = add_part(data)
        
        if result.get('status'):
            return jsonify({
                'code': 200,
                'msg': result.get('msg', '添加成功'),
                'data': None
            })
        else:
            return jsonify({
                'code': 400,
                'msg': result.get('msg', '添加失败'),
                'data': None
            })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'添加失败: {str(e)}',
            'data': None
        })


@benz_parts_bp.route('/update', methods=['POST'])
@require_authentication()
def update_part_api():
    """
    更新配件
    请求参数: part_number和更新的数据
    返回: 操作结果
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'code': 400,
                'msg': '请求参数不能为空',
                'data': None
            })
        
        part_number = data.get('part_number')
        if not part_number:
            return jsonify({
                'code': 400,
                'msg': '配件编号不能为空',
                'data': None
            })
        
        result = update_part(part_number, data)
        
        if result.get('status'):
            return jsonify({
                'code': 200,
                'msg': result.get('msg', '更新成功'),
                'data': None
            })
        else:
            return jsonify({
                'code': 400,
                'msg': result.get('msg', '更新失败'),
                'data': None
            })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'更新失败: {str(e)}',
            'data': None
        })


@benz_parts_bp.route('/delete', methods=['POST'])
@require_authentication()
def delete_part_api():
    """
    删除配件
    请求参数: part_number
    返回: 操作结果
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'code': 400,
                'msg': '请求参数不能为空',
                'data': None
            })
        
        part_number = data.get('part_number')
        if not part_number:
            return jsonify({
                'code': 400,
                'msg': '配件编号不能为空',
                'data': None
            })
        
        result = delete_part(part_number)
        
        if result.get('status'):
            return jsonify({
                'code': 200,
                'msg': result.get('msg', '删除成功'),
                'data': None
            })
        else:
            return jsonify({
                'code': 400,
                'msg': result.get('msg', '删除失败'),
                'data': None
            })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'删除失败: {str(e)}',
            'data': None
        })


@benz_parts_bp.route('/import', methods=['POST'])
@require_authentication()
def import_parts_api():
    """
    批量导入配件（插入更新模式）
    请求参数: file（Excel/CSV文件）
    返回: 操作结果
    """
    try:
        # 检查文件是否存在
        if 'file' not in request.files:
            return jsonify({
                'code': 400,
                'msg': '请选择要上传的文件',
                'data': None
            })

        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'code': 400,
                'msg': '请选择要上传的文件',
                'data': None
            })
        
        # car_type = data.get('car_type')
        user_id = session.get('user_id')



        # 调用服务层处理
        result = import_parts(file, file.filename)

        # 如果导入成功且用户已登录，将成功的配件添加到收藏
        if result.get('status') and 'logged_in' in session:
            user_id = session.get('user_id')
            if user_id:
                success_part_numbers = result.get('data', {}).get('success_part_numbers', [])
                if success_part_numbers:
                    # 生成分类名：excel_奔驰 + 秒级时间戳
                    category = f'excel_benz_{user_id}_{int(time.time())}'
                    batch_add_to_favorites(user_id, success_part_numbers, category)

        if result.get('status'):
            return jsonify({
                'code': 200,
                'msg': result.get('msg', '导入成功'),
                'data': result.get('data')
            })
        else:
            return jsonify({
                'code': 400,
                'msg': result.get('msg', '导入失败'),
                'data': result.get('data')
            })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'导入失败: {str(e)}',
            'data': None
        })


@benz_parts_bp.route('/template', methods=['GET'])
@require_authentication()
def download_template_api():
    """
    下载Excel导入模板
    返回: Excel文件
    """
    try:
        template_file = download_template()
        return send_file(
            template_file,
            as_attachment=True,
            download_name='配件导入模板.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'下载模板失败: {str(e)}',
            'data': None
        })


@benz_parts_bp.route('/fetch-realtime', methods=['POST'])
#@require_authentication()
def fetch_realtime_data():
    """
    实时获取零件信息和库存信息（不入库）
    
    请求参数:
        {
            "key": "密钥",
            "part_number": "零件编号"
        }
    
    返回:
        {
            "code": 200,
            "msg": "success",
            "data": {
                "part_number": "零件编号",
                "part_info": {...零件信息...},
                "stock_info": [...库存信息列表...]
            }
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'code': 400,
                'msg': '请求参数不能为空',
                'data': None
            })

        key = data.get('key')
        if not key:
            return jsonify({
                'code': 400,
                'msg': '密钥不能为空',
                'data': None
            })
        if key != '7Y4Y6RNdkDCwTJDJEBWz':
            return jsonify({
                'code': 403,
                'msg': '密钥验证失败',
                'data': None
            })

        part_number = data.get('part_number')
        if not part_number:
            return jsonify({
                'code': 400,
                'msg': '零件编号不能为空',
                'data': None
            })
        
        result = by_part_number_get_data(part_number)
        
        return jsonify({
            'code': 200,
            'msg': '获取成功',
            'data': result
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'获取数据失败: {str(e)}',
            'data': None
        })
