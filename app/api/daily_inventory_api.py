# -*- coding:utf-8 -*-
# @Time    : 2026/06/07 11:45
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : daily_inventory_api.py
# @Software: trae-cn

"""
每日库存 API 接口
提供采购订单列表及其明细的查询接口
"""

from flask import Blueprint, request, jsonify, session
from app.core.permission.decorators import require_authentication, require_permission
from app.services.daily_inventory_service.daily_inventory_service import get_purchase_order_list_with_details
from app.services.daily_inventory_service.daily_inventory_crawler import daily_inventory_crawler_service
from app.services.daily_inventory_service.daily_inventory_service import mark_order_detail_viewed



# 创建 system_inventory_api 子蓝图，URL前缀为 /daily_inventory
daily_inventory_bp = Blueprint('daily_inventory_bp', __name__, url_prefix='/daily_inventory')


@daily_inventory_bp.route('/purchase-orders', methods=['GET'])
# @require_permission('daily_inventory:update')
def api_get_purchase_orders():
    """
    获取采购订单列表及其明细（按订单分页）
    
    请求参数:
        - page: 页码（可选，默认1）
        - page_size: 每页条数（可选，默认10）
        - date: 日期（可选，格式：yyyy-MM-dd）
        - keyword: 搜索关键词（可选，用于搜索采购单号）
        - order_type: 订单类型（可选，1:采购入库单，2:采购退货单）
        - business_type: 业务类型（可选，1:外购，2:普通，3:调货）
    
    返回:
        {
            "code": 0,
            "msg": "success",
            "data": {
                "list": [...],  // 数据列表
                "total": 100,   // 总订单数
                "page": 1,      // 当前页码
                "page_size": 10 // 每页条数
            }
        }
    """
    try:
        # 获取请求参数
        page = request.args.get('page', '1').strip()
        page_size = request.args.get('limit', '10').strip()
        date = request.args.get('date', '').strip()
        keyword = request.args.get('keyword', '').strip()
        order_type = request.args.get('order_type', '').strip()
        business_type = request.args.get('business_type', '').strip()
        
        # 参数转换和验证
        try:
            page = int(page) if page else 1
            page_size = int(page_size) if page_size else 10
        except ValueError:
            return jsonify({
                'code': 400,
                'msg': '页码和每页条数必须是整数',
                'data': None
            }), 400
        
        # 限制参数范围
       
        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        
        # 调用服务层查询数据
        result = get_purchase_order_list_with_details(
            page=page,
            page_size=page_size,
            date=date,
            keyword=keyword,
            order_type=order_type,
            business_type=business_type
        )
        
        if result and result.get('status'):
            return jsonify({
                'code': 200,
                'msg': result.get('msg', 'success'),
                'data': {
                    'list': result.get('data', []),
                    'total': result.get('count', 0),
                    'page': page,
                    'page_size': page_size
                }
            })
        else:
            return jsonify({
                'code': 500,
                'msg': result.get('msg', '查询失败'),  # pyright: ignore[reportOptionalMemberAccess]
                'data': None
            }), 500
            
    except Exception as e:
        print(f'[daily_inventory_api] 异常: {str(e)}')
        return jsonify({
            'code': 500,
            'msg': f'查询失败: {str(e)}',
            'data': None
        }), 500


@daily_inventory_bp.route('/update-data', methods=['POST'])
# @require_permission('daily_inventory:update')
def api_update_daily_inventory():
    """
    触发每日库存数据更新（同步执行）
    
    请求参数:
        - date: 日期（可选，格式：yyyy-MM-dd）
        - cookies_key: cookies的key（可选，默认'fs'）
    
    返回:
        {
            "code": 0,
            "msg": "success",
            "data": null
        }
    """
    try:
        # 获取请求参数
        date = request.json.get('date', '').strip() if request.json else request.form.get('date', '').strip()
        cookies_key = request.json.get('cookies_key', 'fs') if request.json else request.form.get('cookies_key', 'fs')
        
        # 同步执行数据更新任务
        if date:
            daily_inventory_crawler_service(
                cookies_key=cookies_key,
                create_date_start=date,
                create_date_end=date
            )
        else:
            daily_inventory_crawler_service(cookies_key=cookies_key)
        
        return jsonify({
            'code': 200,
            'msg': '数据更新完成',
            'data': None
        })
        
    # except ValueError as e:
    #     if str(e) == "暂无更新数据":
    #         return jsonify({
    #             'code': 204,
    #             'msg': '暂无更新数据',
    #             'data': None
    #         })
    #     else:
    #         print(f'[daily_inventory_api] 触发更新异常: {str(e)}')
    #         return jsonify({
    #             'code': 500,
    #             'msg': f'触发更新失败: {str(e)}',
    #             'data': None
    #         }), 500
    except Exception as e:
        print(f'[daily_inventory_api] 触发更新异常: {str(e)}')
        return jsonify({
            'code': 500,
            'msg': f'触发更新失败: {str(e)}',
            'data': None
        })


@daily_inventory_bp.route('/mark-viewed', methods=['POST'])
@require_permission('daily_inventory:tag_view')
def api_mark_order_detail_viewed():
    """
    标记订单明细为已查看，更新操作人字段为当前登录用户

    请求参数 (JSON body):
        - purchase_order_line_id: 订单明细ID（必需）

    返回:
        {
            "code": 200,
            "msg": "确认查看成功",
            "data": {
                "purchase_order_line_id": 123,
                "operator": "username"
            }
        }
    """
    try:
        # 检查用户是否登录
        if 'logged_in' not in session:
            return jsonify({
                'code': 401,
                'msg': '未登录，请先登录',
                'data': None
            }), 401

        # 获取当前登录用户ID
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({
                'code': 401,
                'msg': '用户信息异常，请重新登录',
                'data': None
            }), 401

        # 将user_id转换为整数
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            return jsonify({
                'code': 401,
                'msg': '用户ID格式异常，请重新登录',
                'data': None
            }), 401

        # 获取请求参数
        data = request.get_json() or {}
        purchase_order_line_id = data.get('purchase_order_line_id')

        # 参数验证
        if not purchase_order_line_id:
            return jsonify({
                'code': 400,
                'msg': '订单明细ID不能为空',
                'data': None
            }), 400

        # 转换ID为整数
        try:
            purchase_order_line_id = int(purchase_order_line_id)
        except (ValueError, TypeError):
            return jsonify({
                'code': 400,
                'msg': '订单明细ID必须是整数',
                'data': None
            }), 400

        # 调用服务层更新操作人（传入user_id，服务层会查询用户名）
        result = mark_order_detail_viewed(purchase_order_line_id, user_id)

        if result and result.get('status'):
            return jsonify({
                'code': 200,
                'msg': result.get('msg', '确认查看成功'),
                'data': result.get('data')
            })
        else:
            return jsonify({
                'code': 500,
                'msg': result.get('msg', '确认查看失败') if result else '确认查看失败',
                'data': None
            }), 500

    except Exception as e:
        print(f'[daily_inventory_api] 标记查看异常: {str(e)}')
        return jsonify({
            'code': 500,
            'msg': f'确认查看失败: {str(e)}',
            'data': None
        }), 500





