# -*- coding:utf-8 -*-
# @Time    : 2026/4/28 16:33
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : report_wx_quote_data_api.py
# @Software: PyCharm

from flask import jsonify, request

from app.core.permission.decorators import require_authentication

from . import report_wx_quote_data_bp
from app.services.report_wx_quote_data_services import wechat_daily_quote_detail_service
from app.services.report_wx_quote_data_services import quote_summary_service
from app.services.report_wx_quote_data_services import wechat_daily_quote_detail_subsidiary
from app.services.report_wx_quote_data_services.create_link import crawl_products_by_oe_brand
from app.exceptions.data_exceptions import DataNotFoundError


@report_wx_quote_data_bp.route('/weixin_decoding_result_list_api', methods=['GET'])
@require_authentication()
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
        
        # 处理空值，如果日期是空字符串，设置为None
        if start_date == '':
            start_date = None
        if end_date == '':
            end_date = None
        if groupname == '':
            groupname = None
        # "全部"也当作None处理
        if groupname == '全部':
            groupname = None
        if nickname == '':
            nickname = None
        if nickname == '全部':
            nickname = None
        # 处理deal_status，空字符串转为None
        if deal_status == '':
            deal_status = None
        # deal_status需要转成整数
        if deal_status is not None:
            try:
                deal_status = int(deal_status)
            except (ValueError, TypeError):
                deal_status = None
            
        # 如果只给了一个日期，默认查询当天
        if start_date and not end_date:
            end_date = start_date
        
        result = wechat_daily_quote_detail_service.fetch_data_paged(
            start_date=start_date,
            end_date=end_date,
            groupname=groupname,
            nickname=nickname,
            deal_status=deal_status,
            page=page,
            limit=limit
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


@report_wx_quote_data_bp.route('/daily_summary_list_api', methods=['GET'])
@require_authentication()
def daily_summary_list_api():
    """
    获取每日汇总列表 API
    """
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 20, type=int)
        date = request.args.get('date')
        groupname = request.args.get('groupname')
        nickname = request.args.get('nickname')
        
        # 处理空值
        if groupname == '' or groupname == '全部':
            groupname = None
        if nickname == '' or nickname == '全部':
            nickname = None
        
        if not date:
            return jsonify({
                'code': 400,
                'msg': '日期不能为空',
                'data': None
            })
        
        result = quote_summary_service.summarize_oe_codes_daily(
            start_date=date,
            end_date=date,
            groupname=groupname,
            nickname=nickname,
            page=page,
            limit=limit
        )
        return jsonify({
            'code': 200,
            'msg': '获取每日汇总成功',
            'data': result
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'获取每日汇总失败: {str(e)}',
            'data': None
        })


@report_wx_quote_data_bp.route('/monthly_summary_list_api', methods=['GET'])
@require_authentication()
def monthly_summary_list_api():
    """
    获取每月汇总列表 API
    """
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 20, type=int)
        month = request.args.get('month')
        groupname = request.args.get('groupname')
        
        # 处理空值
        if groupname == '' or groupname == '全部':
            groupname = None
        
        if not month:
            return jsonify({
                'code': 400,
                'msg': '月份不能为空',
                'data': None
            })
        
        result = quote_summary_service.summarize_oe_codes_monthly(
            month_str=month,
            groupname=groupname,
            page=page,
            limit=limit
        )
        return jsonify({
            'code': 200,
            'msg': '获取每月汇总成功',
            'data': result
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'获取每月汇总失败: {str(e)}',
            'data': None
        })


@report_wx_quote_data_bp.route('/groupname_list_api', methods=['GET'])
@require_authentication()
def groupname_list_api():
    """
    获取所有群名称列表 API
    """
    try:
        result = wechat_daily_quote_detail_service.fetch_groupname_list()
        return jsonify({
            'code': 200,
            'msg': '获取群名称列表成功',
            'data': result
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'获取群名称列表失败: {str(e)}',
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
        
        # 处理空值
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





@report_wx_quote_data_bp.route('/fetch_data_and_save_to_database_api', methods=['POST'])
@require_authentication()
def fetch_data_and_save_to_database_api():
    """
    获取并保存数据到数据库 API
    按10天分批处理指定日期范围的数据
    """
    try:
        from flask import request
        start_date = request.json.get('start_date')  # pyright: ignore[reportOptionalMemberAccess]
        end_date = request.json.get('end_date')  # pyright: ignore[reportOptionalMemberAccess]
        
        if not start_date or not end_date:
            return jsonify({
                'code': 400,
                'msg': '开始日期和结束日期不能为空',
                'data': None
            })
        
        # 调用服务函数
        wechat_daily_quote_detail_service.fetch_data_and_save_to_database(
            start_date=start_date,
            end_date=end_date
        )
        
        return jsonify({
            'code': 200,
            'msg': '数据获取并保存成功',
            'data': None
        })
        
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'数据获取并保存失败: {str(e)}',
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



