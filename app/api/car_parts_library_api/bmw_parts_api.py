# -*- coding:utf-8 -*-
# @Time    : 2026/6/16
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : bmw_parts_api.py
# @Software: PyCharm

"""
华晨宝马（BMW Brilliance）汽车配件库 API 接口
负责处理宝马配件库的 HTTP 请求：查询、分页、数据刷新、CRUD 操作
"""

from flask import Blueprint, request, jsonify
from app.core.permission.decorators import require_authentication
from app.exceptions.crawler_exceptions import CrawlerTokenError
from app.services.car_parts_library_service.car_parts_library_bmw_service import (
    get_part_by_number,
    get_parts_list_page,
    data_refresh,
    add_part,
    update_part,
    delete_part,
)
from app.services.car_parts_library_service.bmw_crawler import data_crawler, external_data_crawler
from app.exceptions import (
    ParameterError,
    CrawlerError,
    DataError,
    DataParseError,
    DataNotFoundError,
    DataPersistenceError,
    BeihuoBaseException,
)


# 创建宝马配件库蓝图
bmw_parts_bp = Blueprint('bmw_parts', __name__, url_prefix='/bmw')


# ====================================================
# 接口一：根据零件号查询单条配件详情（含库存信息）
# ====================================================
@bmw_parts_bp.route('/detail', methods=['GET'])
@require_authentication()
def get_part_detail():
    """
    根据零件号查询宝马配件详情（包含库存信息）

    参数（Query String）:
        part_number: 零件号（OE号），必填

    返回:
        {
            "code": 200,
            "msg": "success",
            "data": {
                "part_number": "xxx",
                "part_name": "xxx",
                ...
                "stock_info": { ... }
            }
        }
    """
    try:
        part_number = request.args.get('part_number')
        if not part_number or not str(part_number).strip():
            return jsonify({
                'code': 400,
                'msg': '零件号不能为空',
                'data': None,
            })

        part = get_part_by_number(str(part_number).strip())
        if part:
            return jsonify({
                'code': 200,
                'msg': 'success',
                'data': part,
            })
        else:
            return jsonify({
                'code': 404,
                'msg': '配件不存在',
                'data': None,
            })

    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'查询失败: {str(e)}',
            'data': None,
        })


# ====================================================
# 接口二：分页查询零件列表（支持按零件号筛选）
# ====================================================
@bmw_parts_bp.route('/list', methods=['GET'])
@require_authentication()
def get_parts_list():
    """
    获取宝马配件列表（分页 + 搜索）

    参数（Query String）:
        page:       页码，默认 1
        page_size:  每页条数，默认 20
        part_number: 零件号（模糊匹配），必填

    返回:
        {
            "code": 200,
            "msg": "success",
            "data": {
                "status": True,
                "msg": "查询成功",
                "count": 100,
                "data": [ ... ]
            }
        }
    """
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        part_number = request.args.get('part_number')

        result = get_parts_list_page(
            page=page,
            page_size=page_size,
            part_number=part_number,
        )

        return jsonify({
            'code': 200,
            'msg': 'success',
            'data': result,
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'查询失败: {str(e)}',
            'data': None,
        })


# ====================================================
# 接口三：批量刷新零件数据（爬虫 + 入库）
# ====================================================
@bmw_parts_bp.route('/batch-refresh', methods=['POST'])
@require_authentication()
def batch_refresh_parts_data():
    """
    批量刷新宝马零件数据
    对每个零件号执行：爬取 BMW Brilliance 官方数据 → upsert 到数据库

    请求体 (JSON):
        {
            "part_numbers": ["part1", "part2", ...]
        }

    返回:
        {
            "code": 200,
            "msg": "数据刷新完成",
            "data": {
                "status": True,
                "parts_count": 10,
                "stock_count": 10,
                "failed": [ ... ]
            }
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'code': 400,
                'msg': '请求参数不能为空',
                'data': None,
            })

        part_numbers = data.get('part_numbers', [])

        if not part_numbers or not isinstance(part_numbers, list) or len(part_numbers) == 0:
            return jsonify({
                'code': 400,
                'msg': '零件号列表不能为空',
                'data': None,
            })

        result = data_refresh(part_numbers)

        if result and result.get('status'):
            return jsonify({
                'code': 200,
                'msg': result.get('msg', '刷新成功'),
                'data': result,
            })
        else:
            return jsonify({
                'code': 400,
                'msg': result.get('msg', '刷新失败'),
                'data': result,
            })

    except Exception as e:
        msg = f'批量刷新宝马零件数据接口异常: {str(e)}'
        print(msg)
        return jsonify({
            'code': 500,
            'msg': msg,
            'data': None,
        })


# ====================================================
# 接口四：新增配件
# ====================================================
@bmw_parts_bp.route('/add', methods=['POST'])
@require_authentication()
def add_part_api():
    """
    新增宝马配件

    请求体 (JSON):
        {
            "part_number": "零件号",
            "part_name": "零件名称",
            "sales_unit": "单位",
            ...
        }

    返回:
        { "code": 200, "msg": "添加成功" }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'code': 400,
                'msg': '请求参数不能为空',
                'data': None,
            })

        if not data.get('part_number'):
            return jsonify({
                'code': 400,
                'msg': '零件号不能为空',
                'data': None,
            })

        result = add_part(data)

        if result.get('status'):
            return jsonify({
                'code': 200,
                'msg': result.get('msg', '添加成功'),
                'data': None,
            })
        else:
            return jsonify({
                'code': 400,
                'msg': result.get('msg', '添加失败'),
                'data': None,
            })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'添加失败: {str(e)}',
            'data': None,
        })


# ====================================================
# 接口五：更新配件
# ====================================================
@bmw_parts_bp.route('/update', methods=['POST'])
@require_authentication()
def update_part_api():
    """
    更新宝马配件信息

    请求体 (JSON):
        {
            "part_number": "零件号（主键，不可修改）",
            "part_name": "零件名称",
            "sales_unit": "单位",
            ...
        }

    返回:
        { "code": 200, "msg": "更新成功" }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'code': 400,
                'msg': '请求参数不能为空',
                'data': None,
            })

        part_number = data.get('part_number')
        if not part_number:
            return jsonify({
                'code': 400,
                'msg': '零件号不能为空',
                'data': None,
            })

        result = update_part(part_number, data)

        if result.get('status'):
            return jsonify({
                'code': 200,
                'msg': result.get('msg', '更新成功'),
                'data': None,
            })
        else:
            return jsonify({
                'code': 400,
                'msg': result.get('msg', '更新失败'),
                'data': None,
            })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'更新失败: {str(e)}',
            'data': None,
        })


# ====================================================
# 接口六：删除配件
# ====================================================
@bmw_parts_bp.route('/delete', methods=['POST'])
@require_authentication()
def delete_part_api():
    """
    删除宝马配件（同时删除库存表中关联记录）

    请求体 (JSON):
        { "part_number": "零件号" }

    返回:
        { "code": 200, "msg": "删除成功" }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'code': 400,
                'msg': '请求参数不能为空',
                'data': None,
            })

        part_number = data.get('part_number')
        if not part_number:
            return jsonify({
                'code': 400,
                'msg': '零件号不能为空',
                'data': None,
            })

        result = delete_part(part_number)

        if result.get('status'):
            return jsonify({
                'code': 200,
                'msg': result.get('msg', '删除成功'),
                'data': None,
            })
        else:
            return jsonify({
                'code': 400,
                'msg': result.get('msg', '删除失败'),
                'data': None,
            })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'删除失败: {str(e)}',
            'data': None,
        })


# ====================================================
# 接口七：实时获取零件信息和库存信息（不入库）
# ====================================================
@bmw_parts_bp.route('/fetch-realtime', methods=['POST'])
@require_authentication()
def fetch_realtime_data():
    """
    实时获取宝马零件信息和库存信息（不入库）

    请求参数 (JSON):
        {
            "key": "密钥",
            "part_number": "零件编号（OE号）",
            "cookie": "BMW Brilliance 登录态 Cookie（可选，不传则使用配置中的 cookie）"
        }

    返回:
        {
            "code": 200,
            "msg": "success",
            "data": {
                "part_number": "零件编号",
                "part_info": {...零件详情...},
                "stock_info": {...库存信息...}
            }
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'code': 400,
                'msg': '请求参数不能为空',
                'data': None,
            })

        key = data.get('key')
        if not key:
            return jsonify({
                'code': 400,
                'msg': '密钥不能为空',
                'data': None,
            })
        if key != '7Y4Y6RNdkDCwTJDJEBWz':
            return jsonify({
                'code': 403,
                'msg': '密钥验证失败',
                'data': None,
            })

        part_number = data.get('part_number')
        if not part_number or not str(part_number).strip():
            return jsonify({
                'code': 400,
                'msg': '零件编号不能为空',
                'data': None,
            })

        oe_clean = str(part_number).strip()
        cookie = data.get('cookie')

        # data_crawler 内部调用的清洗函数已改为直接抛异常，
        # 此处不再检查 detail/stock 中的 error 字段，失败时异常会直接向上传播
        result = external_data_crawler(oe_clean, cookie, is_unit=True)

       

        return jsonify({
            'code': 200,
            'msg': '获取成功',
            'data':result,
        })
    except ParameterError as e:
        # 参数校验失败（零件号为空等）
        return jsonify({
            'code': 400,
            'msg': '参数错误: {}'.format(str(e)),
            'data': None,
        })
    except DataNotFoundError as e:
        # 零件不存在或未激活（上游清洗函数抛出）
        return jsonify({
            'code': 404,
            'msg': '数据未查询到: {}'.format(str(e)),
            'data': None,
        })
    except DataParseError as e:
        # HTML 结构异常、解析失败（页面结构变更等）
        return jsonify({
            'code': 502,
            'msg': '数据解析(请查看是否cookie不正确)失败: {}'.format(str(e)),
            'data': None,
        })
    except CrawlerTokenError as e:
        # Token 失效/无效
        return jsonify({
            'code': 403,
            'msg': 'Token 失效/无效: {}'.format(str(e)),
            'data': None,
        })
    except DataPersistenceError as e:
        # 数据入库失败（当前接口不涉及入库，保留以防御性捕获）
        return jsonify({
            'code': 500,
            'msg': '数据持久化失败: {}'.format(str(e)),
            'data': None,
        })
    except CrawlerError as e:
        # 爬虫请求失败（Cookie 失效、网络问题等）
        return jsonify({
            'code': 502,
            'msg': '爬虫异常: {}'.format(str(e)),
            'data': None,
        })
    except DataError as e:
        # 其他数据层异常（兜底）
        return jsonify({
            'code': 500,
            'msg': '数据异常: {}'.format(str(e)),
            'data': None,
        })
    except BeihuoBaseException as e:
        # 其他自定义业务异常
        return jsonify({
            'code': 500,
            'msg': '业务异常: {}'.format(str(e)),
            'data': None,
        })
    except Exception as e:
        # 未预见的异常
        return jsonify({
            'code': 500,
            'msg': '获取数据失败: {}'.format(str(e)),
            'data': None,
        })


__all__ = ['bmw_parts_bp']
