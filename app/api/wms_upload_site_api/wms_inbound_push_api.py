# -*- coding:utf-8 -*-
# @Time    : 2026/5/5 16:48
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : wms_inbound_push_api.py
# @Software: PyCharm
from flask import jsonify, request

from . import wms_upload_site_bp
from ...services.wms_upload_site_service.wms_inbound_push import wms_get_return_items_data, wms_get_return_items_from_db, get_cassmall_product_list_search, inventory_sync, inventory_sync_batch, set_cookie


@wms_upload_site_bp.route('/get_return_items_api', methods=['GET'])
def get_return_items_api():
    """
    获取采购入库单数据 API - 重新爬取数据并更新数据库，不返回数据
    :return: JSON 响应
    """
    try:
        # 调用 service 层爬取数据并更新数据库
        wms_get_return_items_data()
        
        return jsonify({
            'code': 200,
            'msg': '重新爬取采购入库单数据成功',
            'data': [],
            'count': 0
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'重新爬取采购入库单数据失败: {str(e)}',
            'data': [],
            'count': 0
        })


@wms_upload_site_bp.route('/get_return_items_from_db_api', methods=['GET'])
def get_return_items_from_db_api():
    """
    获取采购入库单数据 API - 从数据库获取（分页，只返回status=0的数据）
    :return: JSON 响应
    """
    try:
        # 获取分页参数
        page = request.args.get('page', type=int, default=1)
        limit = request.args.get('limit', type=int, default=20)
        # 获取筛选参数
        has_pushed_ks = request.args.get('has_pushed_ks', type=str, default='')
        
        # 调用 service 层从数据库获取数据
        return_items, total = wms_get_return_items_from_db(page=page, limit=limit, has_pushed_ks=has_pushed_ks)
        
        return jsonify({
            'code': 200,
            'msg': '从数据库获取采购入库单数据成功',
            'data': return_items,
            'count': total
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'从数据库获取采购入库单数据失败: {str(e)}',
            'data': None,
            'count': 0
        })


@wms_upload_site_bp.route('/cassmall_product_list_search_api', methods=['GET'])
def cassmall_product_list_search_api():
    """
    调用 cassmall 商品搜索 API
    :return: JSON 响应
    """
    try:
        # 获取 frey_no 参数
        frey_no = request.args.get('frey_no', type=str, default='')
        
        if not frey_no:
            return jsonify({
                'code': 400,
                'msg': '缺少 frey_no 参数',
                'data': None
            })
        
        # 调用 service 层
        result = get_cassmall_product_list_search(frey_no)
        
        if result:
            return jsonify({
                'code': 200,
                'msg': '查询成功',
                'data': result
            })
        else:
            return jsonify({
                'code': 404,
                'msg': '未找到相关数据',
                'data': None
            })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'查询失败: {str(e)}',
            'data': None
        })


@wms_upload_site_bp.route('/inventory_sync_api', methods=['GET'])
def inventory_sync_api():
    """
    同步开思mall库存 API
    :return: JSON 响应
    """
    try:
        # 获取请求参数
        product_id = request.args.get('product_id')
        availableToPromiseTotal = request.args.get('availableToPromiseTotal')
        record_id = request.args.get('record_id')
        
        if not product_id:
            return jsonify({
                'code': 400,
                'msg': '缺少 product_id 参数',
                'data': None
            })
        
        if availableToPromiseTotal is None:
            return jsonify({
                'code': 400,
                'msg': '缺少 availableToPromiseTotal 参数',
                'data': None
            })
        
        # 转换为整数
        try:
            availableToPromiseTotal = int(availableToPromiseTotal)
            if record_id:
                record_id = int(record_id)
        except (ValueError, TypeError):
            return jsonify({
                'code': 400,
                'msg': '参数必须是整数',
                'data': None
            })
        
        # 调用 service 层
        result = inventory_sync(product_id, availableToPromiseTotal, record_id)
        
        # 根据 service 层的返回结果处理响应
        message = result.get('message', '')
        
        # 检查是否成功（根据 message 内容判断
        if '更新库存成功' in message:
            return jsonify({
                'code': 200,
                'msg': message,
                'data': result.get('data')
            })
        else:
            return jsonify({
                'code': 400,
                'msg': message,
                'data': result.get('data')
            })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'库存同步失败: {str(e)}',
            'data': None
        })


@wms_upload_site_bp.route('/inventory_sync_batch_api', methods=['POST'])
def inventory_sync_batch_api():
    """
    批量同步卡思mall库存 API
    :return: JSON 响应
    """
    try:
        # 获取请求参数
        data = request.get_json()
        
        if not data or 'items' not in data:
            return jsonify({
                'code': 400,
                'msg': '缺少 items 参数',
                'data': None
            })
        
        items = data['items']
        
        if not isinstance(items, list) or len(items) == 0:
            return jsonify({
                'code': 400,
                'msg': 'items 必须是非空数组',
                'data': None
            })
        
        # 验证每个item的参数
        for idx, item in enumerate(items):
            if 'product_id' not in item or not item['product_id']:
                return jsonify({
                    'code': 400,
                    'msg': f'第 {idx + 1} 条数据缺少 product_id 参数',
                    'data': None
                })
            if 'availableToPromiseTotal' not in item:
                return jsonify({
                    'code': 400,
                    'msg': f'第 {idx + 1} 条数据缺少 availableToPromiseTotal 参数',
                    'data': None
                })
            # 转换为整数
            try:
                item['availableToPromiseTotal'] = int(item['availableToPromiseTotal'])
                if item.get('record_id'):
                    item['record_id'] = int(item['record_id'])
            except (ValueError, TypeError):
                return jsonify({
                    'code': 400,
                    'msg': f'第 {idx + 1} 条数据的参数必须是整数',
                    'data': None
                })
        
        # 调用 service 层
        result = inventory_sync_batch(items)
        
        # 根据 service 层的返回结果处理响应
        message = result.get('message', '')
        
        # 检查是否成功（根据 message 内容判断
        if '更新库存成功' in message or '批量同步完成' in message:
            return jsonify({
                'code': 200,
                'msg': message,
                'data': result.get('data')
            })
        else:
            return jsonify({
                'code': 400,
                'msg': message,
                'data': result.get('data')
            })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'批量库存同步失败: {str(e)}',
            'data': None
        })


@wms_upload_site_bp.route('/set_cookie_api', methods=['POST'])
def set_cookie_api():
    """
    设置 Cookie 配置 API
    :return: JSON 响应
    """
    try:
        # 获取请求参数
        data = request.get_json()
        
        if not data or 'cookie' not in data:
            return jsonify({
                'code': 400,
                'msg': '缺少 cookie 参数',
                'data': None
            })
        
        cookie = data['cookie']
        
        if not cookie or cookie.strip() == '':
            return jsonify({
                'code': 400,
                'msg': 'Cookie不能为空',
                'data': None
            })
        
        # 调用 service 层
        result = set_cookie(cookie)
        
        if result.get('code') == 200:
            return jsonify({
                'code': 200,
                'msg': result.get('message', '保存成功'),
                'data': None
            })
        else:
            return jsonify({
                'code': 500,
                'msg': result.get('message', '保存失败'),
                'data': None
            })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'设置Cookie失败: {str(e)}',
            'data': None
        })

