from flask import Blueprint, request, jsonify, render_template
from app.utils.region_by_number_query.suyuan_service import query_suyuan_data, get_suyuan_statistics

region_by_number_query_bp = Blueprint('region_by_number_query', __name__)


@region_by_number_query_bp.route('/region_by_number_query', methods=['GET'])
def region_by_number_query():
    """
    溯源查询接口

    参数:
        md: 组织编码 (默认: fs)
        b1: 开始溯源码 (默认: 11)
        b2: 结束溯源码 (默认: 11)

    返回:
        JSON格式的溯源结果
    """
    # 1. 获取前端传过来的参数（GET 请求）
    # 取不到参数时用默认值
    md = request.args.get('md', 'fs')
    b1 = request.args.get('b1', '11')
    b2 = request.args.get('b2', '11')

    # 2. 调用工具函数查询数据
    result = query_suyuan_data(md, b1, b2)

    # 3. 返回JSON结果
    return jsonify(result)


@region_by_number_query_bp.route('/suyuan_statistics', methods=['GET'])
def suyuan_statistics():
    """
    溯源码统计接口

    参数:
        md: 组织编码 (可选，不传则查询所有组织)

    返回:
        JSON格式的统计结果，包含 start_m, end_m, count
    """
    # 获取参数
    md = request.args.get('md')
    
    # 调用服务函数获取统计数据
    result = get_suyuan_statistics(md=md)
    
    # 返回JSON结果
    return jsonify({
        'code': 0,
        'msg': 'success',
        'data': result
    })


@region_by_number_query_bp.route('/region_by_number_query_page', methods=['GET'])
def region_by_number_query_page():
    """
    溯源查询页面

    返回:
        渲染溯源查询HTML页面
    """
    return render_template('region_by_number_query.html')

