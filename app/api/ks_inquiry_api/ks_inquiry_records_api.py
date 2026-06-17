# -*- coding:utf-8 -*-
"""
开思询价明细 API 接口
仅处理路由和参数，业务逻辑委托给服务层
"""

from flask import Blueprint, request, jsonify

from app.services.ks_inquiry_service import KsInquiryRecordsService

bp = Blueprint('ks_inquiry_records', __name__, url_prefix='/ks_inquiry')


@bp.route('/records', methods=['GET'])
def get_ks_inquiry_records():
    """
    获取开思询价明细列表（支持分页）

    Query Parameters:
        inquiry_id: 询价单号
        parts_num: OE号
        parts_name: 配件名称
        brand_name: 品牌
        seller_status: 卖家状态
        begin_date: 开始日期 (yyyy-MM-dd)
        end_date: 结束日期 (yyyy-MM-dd)
        page: 页码（默认1）
        page_size: 每页条数（默认200）

    Returns:
        JSON: {code: 0, data: {list: [...], total: 总条数, page: 当前页, page_size: 每页条数}, message: 'success'}
    """
    try:
        # 获取查询参数
        inquiry_id = request.args.get('inquiry_id', '').strip()
        parts_num = request.args.get('parts_num', '').strip()
        parts_name = request.args.get('parts_name', '').strip()
        brand_name = request.args.get('brand_name', '').strip()
        brand = request.args.get('brand', '').strip()  # 品牌筛选（brandNormalized）
        seller_status = request.args.get('seller_status', '').strip()
        car_brand_name = request.args.get('car_brand_name', '').strip()  # 车辆品牌筛选
        begin_date = request.args.get('begin_date', '').strip()
        end_date = request.args.get('end_date', '').strip()
        company = request.args.get('company', '').strip()  # 用户门店/组织

        # 获取分页参数
        try:
            page = int(request.args.get('page', 1))
            page_size = int(request.args.get('page_size', 200))
        except ValueError:
            page = 1
            page_size = 200

        # 限制每页最大条数
        if page_size > 1000:
            page_size = 1000
        if page_size < 1:
            page_size = 200
        if page < 1:
            page = 1

        # 调用服务层获取数据
        result = KsInquiryRecordsService.get_records(
            inquiry_id=inquiry_id,
            parts_num=parts_num,
            parts_name=parts_name,
            brand_name=brand_name,
            brand=brand,  # 品牌筛选（brandNormalized）
            seller_status=seller_status,
            car_brand_name=car_brand_name,  # 车辆品牌筛选
            begin_date=begin_date,
            end_date=end_date,
            company=company,
            page=page,
            page_size=page_size
        )

        return jsonify({
            'code': 0,
            'message': 'success',
            'data': result
        })

    except Exception as e:
        import traceback
        print(f"[KsInquiryRecordsAPI] 错误: {str(e)}")
        print(f"[KsInquiryRecordsAPI] 堆栈: {traceback.format_exc()}")
        return jsonify({
            'code': 500,
            'message': f'查询失败: {str(e)}',
            'data': {'list': [], 'total': 0, 'page': 1, 'page_size': 200}
        }), 500


@bp.route('/seller_status', methods=['GET'])
def get_seller_status_options():
    """
    获取卖家状态选项列表（用于下拉筛选）

    Returns:
        JSON: {code: 0, data: ['SALABLE', ...], message: 'success'}
    """
    try:
        status_list = KsInquiryRecordsService.get_distinct_seller_status()
        return jsonify({
            'code': 0,
            'message': 'success',
            'data': status_list
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'message': f'查询失败: {str(e)}',
            'data': []
        }), 500


@bp.route('/records/oe_stats', methods=['GET'])
def get_oe_stats():
    """
    获取OE号统计维度（按partsNum分组聚合）

    Query Parameters:
        与 /records 接口一致

    Returns:
        JSON: {code: 0, data: {list: [{partsNum, count, partsName}], total, page, page_size}, message}
    """
    try:
        inquiry_id = request.args.get('inquiry_id', '').strip()
        parts_num = request.args.get('parts_num', '').strip()
        parts_name = request.args.get('parts_name', '').strip()
        brand_name = request.args.get('brand_name', '').strip()
        brand = request.args.get('brand', '').strip()
        seller_status = request.args.get('seller_status', '').strip()
        begin_date = request.args.get('begin_date', '').strip()
        end_date = request.args.get('end_date', '').strip()
        company = request.args.get('company', '').strip()

        try:
            page = int(request.args.get('page', 1))
            page_size = int(request.args.get('page_size', 200))
        except ValueError:
            page = 1
            page_size = 200

        if page_size > 1000:
            page_size = 1000
        if page_size < 1:
            page_size = 200
        if page < 1:
            page = 1

        result = KsInquiryRecordsService.get_oe_stats(
            inquiry_id=inquiry_id,
            parts_num=parts_num,
            parts_name=parts_name,
            brand_name=brand_name,
            brand=brand,
            seller_status=seller_status,
            begin_date=begin_date,
            end_date=end_date,
            company=company,
            page=page,
            page_size=page_size
        )

        return jsonify({
            'code': 0,
            'message': 'success',
            'data': result
        })

    except Exception as e:
        import traceback
        print(f"[KsInquiryRecordsAPI] OE统计错误: {str(e)}")
        print(f"[KsInquiryRecordsAPI] 堆栈: {traceback.format_exc()}")
        return jsonify({
            'code': 500,
            'message': f'查询失败: {str(e)}',
            'data': {'list': [], 'total': 0, 'page': 1, 'page_size': 200}
        }), 500


@bp.route('/records/engine_chassis', methods=['GET'])
def get_engine_chassis():
    """
    获取发动机及底盘维度列表（按engine+chassis组合展示，不去重）

    Query Parameters:
        engine: 发动机型号
        chassis: 底盘型号
        vin: VIN码
        begin_date: 开始日期 (yyyy-MM-dd)
        end_date: 结束日期 (yyyy-MM-dd)
        page: 页码（默认1）
        page_size: 每页条数（默认200）

    Returns:
        JSON: {code: 0, data: {list: [{engine, chassis, vin, vehicleProductionDate}], total, page, page_size}, message}
    """
    try:
        engine = request.args.get('engine', '').strip()
        chassis = request.args.get('chassis', '').strip()
        vin = request.args.get('vin', '').strip()
        begin_date = request.args.get('begin_date', '').strip()
        end_date = request.args.get('end_date', '').strip()
        company = request.args.get('company', '').strip()

        try:
            page = int(request.args.get('page', 1))
            page_size = int(request.args.get('page_size', 200))
        except ValueError:
            page = 1
            page_size = 200

        if page_size > 1000:
            page_size = 1000
        if page_size < 1:
            page_size = 200
        if page < 1:
            page = 1

        result = KsInquiryRecordsService.get_engine_chassis_list(
            engine=engine,
            chassis=chassis,
            vin=vin,
            begin_date=begin_date,
            end_date=end_date,
            company=company,
            page=page,
            page_size=page_size
        )

        return jsonify({
            'code': 0,
            'message': 'success',
            'data': result
        })

    except Exception as e:
        import traceback
        print(f"[KsInquiryRecordsAPI] 发动机底盘错误: {str(e)}")
        print(f"[KsInquiryRecordsAPI] 堆栈: {traceback.format_exc()}")
        return jsonify({
            'code': 500,
            'message': f'查询失败: {str(e)}',
            'data': {'list': [], 'total': 0, 'page': 1, 'page_size': 200}
        }), 500


@bp.route('/records/garage_chassis_stats', methods=['GET'])
def get_garage_chassis_stats():
    """
    按修理厂统计底盘出现次数

    Query Parameters:
        garage_name: 修理厂名称（必填）
        company: 用户门店/组织
        begin_date: 开始日期 (yyyy-MM-dd)
        end_date: 结束日期 (yyyy-MM-dd)

    Returns:
        JSON: {code: 0, data: {list: [{carBrandName, chassis, count}]}, message}
    """
    try:
        garage_name = request.args.get('garage_name', '').strip()
        company = request.args.get('company', '').strip()
        begin_date = request.args.get('begin_date', '').strip()
        end_date = request.args.get('end_date', '').strip()

        if not garage_name:
            return jsonify({
                'code': 400,
                'message': '修理厂名称不能为空',
                'data': {'list': []}
            }), 400

        result = KsInquiryRecordsService.get_garage_chassis_stats(
            garage_name=garage_name,
            company=company,
            begin_date=begin_date,
            end_date=end_date
        )

        return jsonify({
            'code': 0,
            'message': 'success',
            'data': result
        })

    except Exception as e:
        import traceback
        print(f"[KsInquiryRecordsAPI] 修理厂底盘统计错误: {str(e)}")
        print(f"[KsInquiryRecordsAPI] 堆栈: {traceback.format_exc()}")
        return jsonify({
            'code': 500,
            'message': f'查询失败: {str(e)}',
            'data': {'list': []}
        }), 500


@bp.route('/records/garage_engine_stats', methods=['GET'])
def get_garage_engine_stats():
    """
    按修理厂统计发动机出现次数

    Query Parameters:
        garage_name: 修理厂名称（必填）
        company: 用户门店/组织
        begin_date: 开始日期 (yyyy-MM-dd)
        end_date: 结束日期 (yyyy-MM-dd)

    Returns:
        JSON: {code: 0, data: {list: [{carBrandName, engine, count}]}, message}
    """
    try:
        garage_name = request.args.get('garage_name', '').strip()
        company = request.args.get('company', '').strip()
        begin_date = request.args.get('begin_date', '').strip()
        end_date = request.args.get('end_date', '').strip()

        if not garage_name:
            return jsonify({
                'code': 400,
                'message': '修理厂名称不能为空',
                'data': {'list': []}
            }), 400

        result = KsInquiryRecordsService.get_garage_engine_stats(
            garage_name=garage_name,
            company=company,
            begin_date=begin_date,
            end_date=end_date
        )

        return jsonify({
            'code': 0,
            'message': 'success',
            'data': result
        })

    except Exception as e:
        import traceback
        print(f"[KsInquiryRecordsAPI] 修理厂发动机统计错误: {str(e)}")
        print(f"[KsInquiryRecordsAPI] 堆栈: {traceback.format_exc()}")
        return jsonify({
            'code': 500,
            'message': f'查询失败: {str(e)}',
            'data': {'list': []}
        }), 500


@bp.route('/records/garage_oenum_stats', methods=['GET'])
def get_garage_oenum_stats():
    """
    按修理厂统计OE号码出现次数

    Query Parameters:
        garage_name: 修理厂名称（必填）
        company: 用户门店/组织
        begin_date: 开始日期 (yyyy-MM-dd)
        end_date: 结束日期 (yyyy-MM-dd)

    Returns:
        JSON: {code: 0, data: {list: [{carBrandName, partsNum, count}]}, message}
    """
    try:
        garage_name = request.args.get('garage_name', '').strip()
        company = request.args.get('company', '').strip()
        begin_date = request.args.get('begin_date', '').strip()
        end_date = request.args.get('end_date', '').strip()

        if not garage_name:
            return jsonify({
                'code': 400,
                'message': '修理厂名称不能为空',
                'data': {'list': []}
            }), 400

        result = KsInquiryRecordsService.get_garage_oenum_stats(
            garage_name=garage_name,
            company=company,
            begin_date=begin_date,
            end_date=end_date
        )

        return jsonify({
            'code': 0,
            'message': 'success',
            'data': result
        })

    except Exception as e:
        import traceback
        print(f"[KsInquiryRecordsAPI] 修理厂OE号码统计错误: {str(e)}")
        print(f"[KsInquiryRecordsAPI] 堆栈: {traceback.format_exc()}")
        return jsonify({
            'code': 500,
            'message': f'查询失败: {str(e)}',
            'data': {'list': []}
        }), 500


@bp.route('/brands', methods=['GET'])
def get_brand_options():
    """
    获取品牌选项列表（brandNormalized，用于下拉筛选）

    Query Parameters:
        company: 用户门店/组织

    Returns:
        JSON: {code: 0, data: ['曼牌', '原厂', ...], message: 'success'}
    """
    try:
        company = request.args.get('company', '').strip()
        print(f"[KsInquiryRecordsAPI] 获取品牌列表, company={company}")
        brand_list = KsInquiryRecordsService.get_distinct_brands(company)
        print(f"[KsInquiryRecordsAPI] 品牌列表: {len(brand_list)} 条")
        return jsonify({
            'code': 0,
            'message': 'success',
            'data': brand_list
        })
    except Exception as e:
        import traceback
        print(f"[KsInquiryRecordsAPI] 错误: {e}")
        print(traceback.format_exc())
        return jsonify({
            'code': 500,
            'message': f'查询失败: {str(e)}',
            'data': []
        }), 500
