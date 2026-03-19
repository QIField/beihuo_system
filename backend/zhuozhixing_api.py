# -*- coding: utf-8 -*-
"""
卓之星数据同步API

提供HTTP接口用于：
1. 手动触发数据同步
2. 查询已同步的数据
"""

from flask import Blueprint, request, jsonify
from datetime import datetime

from app.external_services.zhuozhixing_sync import sync_all_suppliers, sync_supplier, SUPPLIERS
from app.external_services.zhuozhixing_sync.db_service import query_data, get_data_count

# 创建蓝图
zhuozhixing_bp = Blueprint('zhuozhixing', __name__, url_prefix='/api/zhuozhixing')


@zhuozhixing_bp.route('/sync', methods=['POST'])
def trigger_sync():
    """
    手动触发数据同步

    请求参数（JSON，可选）：
        - supplier: 供应商名称（'广星' 或 '鑫峰'），不传则同步全部

    返回：
        同步结果
    """
    try:
        data = request.get_json() or {}
        supplier = data.get('supplier')

        # 如果指定了供应商，只同步该供应商
        if supplier:
            if supplier not in SUPPLIERS:
                return jsonify({
                    'success': False,
                    'message': f'无效的供应商: {supplier}，可选: {list(SUPPLIERS.keys())}'
                }), 400

            result = sync_supplier(supplier, SUPPLIERS[supplier]['gsign'])
            return jsonify({
                'success': result['success'],
                'message': result['message'],
                'data': result
            })

        # 否则同步全部
        else:
            results = sync_all_suppliers()
            success = all(r['success'] for r in results)
            total_count = sum(r['count'] for r in results)

            return jsonify({
                'success': success,
                'message': '全量同步完成' if success else '部分同步失败',
                'data': {
                    'total_count': total_count,
                    'results': results
                }
            })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'同步失败: {str(e)}'
        }), 500


@zhuozhixing_bp.route('/data', methods=['GET'])
def get_data():
    """
    查询已同步的数据

    查询参数：
        - supplier: 供应商名称（可选，不传查询全部）
        - limit: 返回条数（默认100，最大1000）
        - offset: 偏移量（默认0）

    返回：
        数据列表和总数
    """
    try:
        # 获取参数
        supplier = request.args.get('supplier')
        limit = min(int(request.args.get('limit', 100)), 1000)
        offset = int(request.args.get('offset', 0))

        # 验证供应商
        if supplier and supplier not in SUPPLIERS:
            return jsonify({
                'success': False,
                'message': f'无效的供应商: {supplier}'
            }), 400

        # 查询数据
        data = query_data(supplier, limit, offset)
        total = get_data_count(supplier)

        # 格式化时间字段
        for item in data:
            if 'sync_time' in item and item['sync_time']:
                if isinstance(item['sync_time'], datetime):
                    item['sync_time'] = item['sync_time'].strftime('%Y-%m-%d %H:%M:%S')

        return jsonify({
            'success': True,
            'message': '查询成功',
            'data': {
                'list': data,
                'total': total,
                'limit': limit,
                'offset': offset
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'查询失败: {str(e)}'
        }), 500


@zhuozhixing_bp.route('/status', methods=['GET'])
def get_status():
    """
    获取同步状态

    返回：
        各供应商的数据统计
    """
    try:
        status = []
        for supplier_name in SUPPLIERS.keys():
            count = get_data_count(supplier_name)
            status.append({
                'supplier': supplier_name,
                'count': count
            })

        total = get_data_count()

        return jsonify({
            'success': True,
            'message': '获取成功',
            'data': {
                'suppliers': status,
                'total': total
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取状态失败: {str(e)}'
        }), 500


def register_zhuozhixing_routes(app):
    """
    注册卓之星API路由到Flask应用

    Args:
        app: Flask应用实例
    """
    app.register_blueprint(zhuozhixing_bp)
    print("[ZhuoZhiXing] API路由已注册")
