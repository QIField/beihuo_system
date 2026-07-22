# -*- coding:utf-8 -*-
# @Time    : 2026/4/28 16:33
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : weixin_decoding_result_api.py
# @Software: PyCharm

from flask import jsonify, request, session

from app.core.permission.decorators import require_authentication
from app.core.permission.decorators_plus import require_param_permission

from . import report_wx_quote_data_bp
from app.services.report_wx_quote_data_services import wechat_daily_quote_detail_service
from app.services.report_wx_quote_data_services import wechat_daily_quote_detail_subsidiary
from app.services.report_wx_quote_data_services.create_link import crawl_products_by_oe_brand
from app.exceptions.data_exceptions import DataNotFoundError


@report_wx_quote_data_bp.route('/weixin_decoding_result_list_api', methods=['GET'])
@require_param_permission(
    param_name='groupname',
    permission_value_map={
        # ============================================================
        # 权限编码与群名称的映射配置
        # 格式: '权限编码': '群名称'
        # 用户拥有对应权限，才能查询该群的数据
        # 无权限时返回 403 错误: "权限不足，需要权限: xxx"
        # ============================================================
        # 示例配置（请根据实际需求修改或删除）：
        # 'wx_group:view_all': None,           # 查看全部群数据（groupname=None 时）
        # 'wx_group:view_group_a': 'A群',       # 查看"A群"的数据
        # 'wx_group:view_group_b': 'B群',       # 查看"B群"的数据
        # 'wx_group:view_group_c': 'C群',       # 查看"C群"的数据
        # ============================================================
        # TODO: 在此添加实际的权限-群名映射


        'wx_group':'全部',
        'wx_group:view_group_f3': 'F3查询群',
       
        'wx_group:view_group_fs_nb': '佛山巴博瑞内部查询群',
        'wx_group:view_group_fs_crm':'佛山报价CRM中台数据',
        'wx_group:view_group_fs_zt': '佛山报价中台数据',

        'wx_group:view_group_fs_kc': '查佛山库存卖价',

        'wx_group:view_group_hf_nb': '合峰内部查询群',
        'wx_group:view_group_kd':'开单群',
        'wx_group:view_group_hl':'湖南巴博瑞自动报价',
       
        
        'wx_group:view_group_zh_nb': '珠海巴博瑞内部查询群',



        'wx_group:view_group_gx_nb': '广西嘉昊内部查询群',
        'wx_group:view_group_gx_proxy':'广西嘉昊-代理价',
        'wx_group:view_group_gx_wholesale':'广西嘉昊-批发价',
        'wx_group:view_group_gx_retail':'广西嘉昊-零售价',

    },
    bypass_permission='wx_group:view_group_all',
)
def weixin_decoding_result_list_api():
    """
    获取每日报价明细列表 API
    """
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 20, type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        groupname = request.args.get('groupname')
        nickname = request.args.get('nickname')
        deal_status = request.args.get('deal_status')
        
        if start_date == '':
            start_date = None
        if end_date == '':
            end_date = None
        if groupname == '' or groupname == '全部':
            groupname = None   
        if nickname == '' or nickname == '全部':
            nickname = None     
        if deal_status == '':
            deal_status = None
        if deal_status is not None:
            try:
                deal_status = int(deal_status)
            except (ValueError, TypeError):
                deal_status = None
            
        if start_date and not end_date:
            end_date = start_date
        
        user_id = session.get('user_id')
        
        result = wechat_daily_quote_detail_service.fetch_data_paged(
            start_date=start_date,
            end_date=end_date,
            groupname=groupname,
            nickname=nickname,
            deal_status=deal_status,
            page=page,
            limit=limit,
            user_id=user_id
        )
        return jsonify({
            'code': 200,
            'msg': '获取每日报价明细成功',
            'data': result
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'获取每日报价明细失败: {str(e)}',
            'data': None
        })


@report_wx_quote_data_bp.route('/search_crm_customer_api', methods=['GET'])
@require_authentication()
def search_crm_customer_api():
    """
    搜索CRM客户 API
    根据客户名称关键词在合作伙伴表中进行模糊搜索
    """
    try:
        keyword = request.args.get('keyword', '')
        
        if keyword == '':
            return jsonify({
                'code': 200,
                'msg': '获取CRM客户列表成功',
                'data': []
            })
        
        result = wechat_daily_quote_detail_subsidiary.get_crm_customer(keyword)
        
        return jsonify({
            'code': 200,
            'msg': '获取CRM客户列表成功',
            'data': result
        })
    except Exception as e:
        return jsonify({
                'code': 500,
                'msg': f'获取CRM客户列表失败: {str(e)}',
                'data': None
            })


@report_wx_quote_data_bp.route('/update_inquiry_customer_api', methods=['POST'])
@require_authentication()
def update_inquiry_customer_api():
    """
    更新询价客户 API
    只更新 inquiry_customer_id 和 inquiry_customer 字段
    根据 weixin_decoding_result_id 更新所有匹配的记录
    """
    try:
        from flask import request
        weixin_decoding_result_id = request.json.get('weixin_decoding_result_id')  # pyright: ignore[reportOptionalMemberAccess]
        inquiry_customer_id = request.json.get('inquiry_customer_id')  # pyright: ignore[reportOptionalMemberAccess]
        inquiry_customer = request.json.get('inquiry_customer')  # pyright: ignore[reportOptionalMemberAccess]
        
        if weixin_decoding_result_id is None:
            return jsonify({
                'code': 400,
                'msg': 'weixin_decoding_result_id不能为空',
                'data': None
            })
        
        updated_count = wechat_daily_quote_detail_subsidiary.update_inquiry_customer(
            weixin_decoding_result_id=weixin_decoding_result_id,
            inquiry_customer_id=inquiry_customer_id,
            inquiry_customer=inquiry_customer
        )
        
        if updated_count > 0:
            return jsonify({
                'code': 200,
                'msg': f'保存成功，更新了{updated_count}条记录',
                'data': None
            })
        else:
            return jsonify({
                'code': 400,
                'msg': '保存失败，未找到记录',
                'data': None
            })
            
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'保存失败: {str(e)}',
            'data': None
        })


@report_wx_quote_data_bp.route('/generate_draft_link_api', methods=['POST'])
@require_authentication()
def generate_draft_link_api():
    """
    生成草稿链接 API
    根据选中的配件生成草稿链接，并更新到数据库
    """
    try:
        from flask import request
        weixin_decoding_result_id = request.json.get('weixin_decoding_result_id')  # pyright: ignore[reportOptionalMemberAccess]
        items = request.json.get('items')  # pyright: ignore[reportOptionalMemberAccess]
        extra_items = request.json.get('extra_items')  # pyright: ignore[reportOptionalMemberAccess]
        
        if not weixin_decoding_result_id:
            return jsonify({
                'code': 400,
                'msg': 'weixin_decoding_result_id不能为空',
                'data': None
            })
        
        if (not items or not isinstance(items, list)) and (not extra_items or not isinstance(extra_items, list)):
            return jsonify({
                'code': 400,
                'msg': '请选择至少一个配件',
                'data': None
            })
        
        result = wechat_daily_quote_detail_subsidiary.generate_draft_link(
            weixin_decoding_result_id=weixin_decoding_result_id,
            items=items,
            extra_items=extra_items
        )
        
        return jsonify({
            'code': 200,
            'msg': '生成成功',
            'data': {'draft_link': result}
        })
        
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'生成草稿链接失败: {str(e)}',
            'data': None
        })


@report_wx_quote_data_bp.route('/search_oe_product_api', methods=['GET'])
@require_authentication()
def search_oe_product_api():
    """
    搜索OE产品 API
    根据OE号查询相关产品列表，用于添加额外品牌时选择产品
    """
    try:
        oe_code = request.args.get('oe_code', '')
        
        if not oe_code:
            return jsonify({
                'code': 400,
                'msg': 'OE码不能为空',
                'data': None
            })
        
        result = crawl_products_by_oe_brand(oe_code)
        
        if not result:
            return jsonify({
                'code': 404,
                'msg': '未找到匹配的产品',
                'data': []
            })
        
        return jsonify({
            'code': 200,
            'msg': '搜索成功',
            'data': result
        })
        
    except DataNotFoundError as e:
        return jsonify({
            'code': 404,
            'msg': str(e),
            'data': []
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'搜索OE产品失败: {str(e)}',
            'data': None
        })
