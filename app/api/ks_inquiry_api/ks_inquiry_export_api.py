# -*- coding:utf-8 -*-
"""
开思询价导出 API 接口
仅处理路由和参数，业务逻辑委托给服务层与通用导出模块
"""

import json
import os
from typing import Any, Dict, List, Optional

from flask import Blueprint, after_this_request, jsonify, request, send_file

from app.core.async_task_store import get_task_status
from app.services.ks_inquiry_service import KsInquiryRecordsService, KsInquiryStatsService
from app.utils.export_tools import ExportConfig, submit_export_task, submit_multi_sheet_export_task
from app.utils.export_tools.async_export import remove_export_file
from app.utils.logger_config import get_task_logger

bp = Blueprint('ks_inquiry_export', __name__)
logger = get_task_logger('ks_inquiry_export')


# ==================== 通用工具函数 ====================

def _parse_str_param(name: str, default: str = '') -> str:
    """解析字符串查询参数并去除首尾空格。"""
    return request.args.get(name, default).strip()


def _parse_column_filters(param_name: str = 'column_filters') -> Optional[Dict[str, List[str]]]:
    """解析列头下拉筛选条件（JSON 字符串）。"""
    raw = request.args.get(param_name, '').strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def _build_common_search_params() -> Dict[str, Any]:
    """构建通用搜索参数（日期范围、客户名称、门店）。"""
    return {
        'begin_date': _parse_str_param('begin_date'),
        'end_date': _parse_str_param('end_date'),
        'garage_name': _parse_str_param('garage_name'),
        'company': _parse_str_param('company'),
    }


def _add_sort_params(params: Dict[str, Any], prefix: str = '') -> None:
    """添加排序参数到搜索条件。"""
    sort_column = _parse_str_param(f'{prefix}sort_column')
    sort_dir = _parse_str_param(f'{prefix}sort_dir')
    if sort_column:
        params['sort_column'] = sort_column
        params['sort_dir'] = sort_dir


def _add_column_filters(params: Dict[str, Any], prefix: str = '') -> None:
    """添加列头下拉筛选条件到搜索条件。"""
    column_filters = _parse_column_filters(f'{prefix}column_filters')
    if column_filters:
        params['column_filters'] = column_filters


# ==================== 导出配置 ====================

def _build_detail_export_config() -> ExportConfig:
    """配件作战明细导出配置。"""
    return ExportConfig(
        fields=[
            'rowNumber', 'inquiryId', 'customerName', 'carBrandName', 'vin', 'engine',
            'productionDate', 'chassis', 'resolve_parts_name', 'partsNum', 'brandName',
            'brandNormalized', 'brandId', 'sellerPrice', 'sellerBtPrice',
            'displaySellerStatus', 'locationName', 'arrivalTime', 'remark'
        ],
        headers={
            'rowNumber': '行号',
            'inquiryId': '询价单号',
            'customerName': '客户名称',
            'carBrandName': '车辆品牌',
            'vin': '车架号',
            'engine': '发动机',
            'productionDate': '车辆生产日期',
            'chassis': '底盘',
            'resolve_parts_name': '配件名称',
            'partsNum': 'OE号',
            'brandName': '品牌',
            'brandNormalized': '标准化品牌',
            'brandId': '品牌ID',
            'sellerPrice': '含税价',
            'sellerBtPrice': '不含税价',
            'displaySellerStatus': '订单状态',
            'locationName': '发货地',
            'arrivalTime': '备货时间',
            'remark': '备注',
        },
        filename_template='指挥总看板_配件作战明细_{timestamp}.xlsx',
        sheet_name='配件作战明细',
    )


def _build_oe_export_config() -> ExportConfig:
    """OE军备统计导出配置。"""
    return ExportConfig(
        fields=['resolve_parts_num', 'count', 'carBrandName', 'partsName', 'unquotedProducts'],
        headers={
            'resolve_parts_num': 'OE号',
            'count': '出现次数',
            'carBrandName': '车辆品牌',
            'partsName': '配件名称',
            'unquotedProducts': '未报价商品数',
        },
        filename_template='指挥总看板_OE军备统计_{timestamp}.xlsx',
        sheet_name='OE军备统计',
    )


def _build_sheet_config(sheet_name: str, fields: List[str], headers: Dict[str, str]) -> ExportConfig:
    """构建多 Sheet 导出中单个 Sheet 的配置。"""
    return ExportConfig(
        fields=fields,
        headers=headers,
        filename_template='_{timestamp}.xlsx',
        sheet_name=sheet_name,
    )


def _build_customer_export_config() -> ExportConfig:
    """合作单位分析客户主表导出配置。"""
    return ExportConfig(
        fields=['customerName', 'count', 'orderedCount', 'unorderedCount', 'conversionRate'],
        headers={
            'customerName': '客户',
            'count': '询价次数',
            'orderedCount': '下单数量',
            'unorderedCount': '未下单数量',
            'conversionRate': '转换率',
        },
        filename_template='指挥总看板_合作单位分析_{timestamp}.xlsx',
        sheet_name='客户统计',
    )


# ==================== 数据获取函数 ====================

def _fetch_detail_export(progress_callback=None, **search_params) -> List[Dict[str, Any]]:
    """获取配件作战明细完整数据并生成行号。"""
    data = KsInquiryRecordsService.get_all_records(**search_params)
    for idx, item in enumerate(data, 1):
        item['rowNumber'] = idx
    return data


def _fetch_oe_export(progress_callback=None, **search_params) -> List[Dict[str, Any]]:
    """获取 OE 军备统计完整数据。"""
    return KsInquiryStatsService.get_all_oe_stats(**search_params)


def _fetch_engine_chassis(progress_callback=None, **search_params) -> List[Dict[str, Any]]:
    """获取底盘统计完整数据。"""
    return KsInquiryStatsService.get_garage_chassis_stats(**search_params).get('list', [])


def _fetch_engine_engine(progress_callback=None, **search_params) -> List[Dict[str, Any]]:
    """获取发动机统计完整数据。"""
    return KsInquiryStatsService.get_garage_engine_stats(**search_params).get('list', [])


def _fetch_engine_oenum(progress_callback=None, **search_params) -> List[Dict[str, Any]]:
    """获取 OE 号码统计完整数据。"""
    return KsInquiryStatsService.get_garage_oenum_stats(**search_params).get('list', [])


def _fetch_customer_main(progress_callback=None, **search_params) -> List[Dict[str, Any]]:
    """获取合作单位分析主表完整数据。"""
    return KsInquiryStatsService.get_all_customer_stats(**search_params)


def _fetch_customer_oenum(progress_callback=None, **search_params) -> List[Dict[str, Any]]:
    """获取客户维度 OE 统计完整数据。"""
    return KsInquiryStatsService.get_customer_oenum_stats(**search_params).get('list', [])


def _build_engine_search_params(prefix: str = '') -> Dict[str, Any]:
    """构建动力底盘研判单个 Sheet 的搜索参数。"""
    params = _build_common_search_params()
    _add_sort_params(params, prefix)
    _add_column_filters(params, prefix)
    return params


# ==================== 路由接口 ====================

@bp.route('/records/export/detail', methods=['GET'])
def export_detail():
    """导出配件作战明细（单 Sheet，异步）。"""
    try:
        search_params = {
            'inquiry_id': _parse_str_param('inquiry_id'),
            'parts_num': _parse_str_param('parts_num'),
            'parts_name': _parse_str_param('parts_name'),
            'brand_name': _parse_str_param('brand_name'),
            'brand': _parse_str_param('brand'),
            'seller_status': _parse_str_param('seller_status'),
            'car_brand_name': _parse_str_param('car_brand_name'),
            **_build_common_search_params()
        }
        _add_sort_params(search_params)
        _add_column_filters(search_params)

        config = _build_detail_export_config()
        task_id = submit_export_task(config, _fetch_detail_export, search_params)
        return jsonify({'code': 0, 'msg': '导出任务已提交', 'data': {'task_id': task_id}})
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'导出任务提交失败: {str(e)}'}), 500


@bp.route('/records/export/oe', methods=['GET'])
def export_oe():
    """导出 OE 军备统计（单 Sheet，异步）。"""
    try:
        search_params = {
            'inquiry_id': _parse_str_param('inquiry_id'),
            'resolve_parts_num': _parse_str_param('resolve_parts_num'),
            'parts_name': _parse_str_param('parts_name'),
            'brand_name': _parse_str_param('brand_name'),
            'brand': _parse_str_param('brand'),
            'seller_status': _parse_str_param('seller_status'),
            'car_brand_name': _parse_str_param('car_brand_name'),
            **_build_common_search_params()
        }
        _add_sort_params(search_params)
        _add_column_filters(search_params)

        config = _build_oe_export_config()
        task_id = submit_export_task(config, _fetch_oe_export, search_params)
        return jsonify({'code': 0, 'msg': '导出任务已提交', 'data': {'task_id': task_id}})
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'导出任务提交失败: {str(e)}'}), 500


@bp.route('/records/export/engine', methods=['GET'])
def export_engine():
    """导出动力底盘研判（多 Sheet：底盘/发动机/OE号码，异步）。"""
    try:
        common_params = _build_common_search_params()

        sheets_config = [
            {
                'sheet_name': '底盘统计',
                'config': _build_sheet_config(
                    '底盘统计',
                    ['carBrandName', 'chassis', 'count'],
                    {'carBrandName': '车辆品牌', 'chassis': '底盘', 'count': '出现次数'},
                ),
                'fetcher': _fetch_engine_chassis,
                'search_params': {**common_params, **_build_engine_search_params('chassis_')},
            },
            {
                'sheet_name': '发动机统计',
                'config': _build_sheet_config(
                    '发动机统计',
                    ['carBrandName', 'engine', 'count'],
                    {'carBrandName': '车辆品牌', 'engine': '发动机代码', 'count': '出现次数'},
                ),
                'fetcher': _fetch_engine_engine,
                'search_params': {**common_params, **_build_engine_search_params('engine_')},
            },
            {
                'sheet_name': 'OE号码统计',
                'config': _build_sheet_config(
                    'OE号码统计',
                    ['carBrandName', 'partsNum', 'count'],
                    {'carBrandName': '车辆品牌', 'partsNum': 'OE号码', 'count': '出现次数'},
                ),
                'fetcher': _fetch_engine_oenum,
                'search_params': {**common_params, **_build_engine_search_params('oenum_')},
            },
        ]

        task_id = submit_multi_sheet_export_task(
            sheets_config,
            '指挥总看板_动力底盘研判_{timestamp}.xlsx',
        )
        return jsonify({'code': 0, 'msg': '导出任务已提交', 'data': {'task_id': task_id}})
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'导出任务提交失败: {str(e)}'}), 500


@bp.route('/records/export/customer', methods=['GET'])
def export_customer():
    """导出合作单位分析（多 Sheet：客户/发动机/底盘/OE，异步）。"""
    try:
        common_params = _build_common_search_params()

        # 主表搜索参数
        main_params = dict(common_params)
        _add_sort_params(main_params)
        _add_column_filters(main_params)

        # 副表搜索参数：按当前筛选条件过滤后，导出所有客户的三类统计
        sub_common_params = {
            'begin_date': common_params.get('begin_date', ''),
            'end_date': common_params.get('end_date', ''),
            'company': common_params.get('company', ''),
            'garage_name': '',
        }

        sheets_config = [
            {
                'sheet_name': '客户统计',
                'config': _build_customer_export_config(),
                'fetcher': _fetch_customer_main,
                'search_params': main_params,
            },
            {
                'sheet_name': '发动机统计',
                'config': _build_sheet_config(
                    '发动机统计',
                    ['carBrandName', 'engine', 'count'],
                    {'carBrandName': '车辆品牌', 'engine': '发动机', 'count': '次数'},
                ),
                'fetcher': _fetch_engine_engine,
                'search_params': {
                    **sub_common_params,
                    **_build_engine_search_params('engine_')
                },
            },
            {
                'sheet_name': '底盘统计',
                'config': _build_sheet_config(
                    '底盘统计',
                    ['carBrandName', 'chassis', 'count'],
                    {'carBrandName': '车辆品牌', 'chassis': '底盘代码', 'count': '次数'},
                ),
                'fetcher': _fetch_engine_chassis,
                'search_params': {
                    **sub_common_params,
                    **_build_engine_search_params('chassis_')
                },
            },
            {
                'sheet_name': 'OE统计',
                'config': _build_sheet_config(
                    'OE统计',
                    ['carBrandName', 'partsNum', 'partsName', 'count'],
                    {'carBrandName': '车辆品牌', 'partsNum': 'OE', 'partsName': '配件名称', 'count': '次数'},
                ),
                'fetcher': _fetch_customer_oenum,
                'search_params': {
                    **sub_common_params,
                    **_build_engine_search_params('oenum_')
                },
            },
        ]

        task_id = submit_multi_sheet_export_task(
            sheets_config,
            '指挥总看板_合作单位分析_{timestamp}.xlsx',
        )
        return jsonify({'code': 0, 'msg': '导出任务已提交', 'data': {'task_id': task_id}})
    except Exception as e:
        return jsonify({'code': 500, 'msg': f'导出任务提交失败: {str(e)}'}), 500


@bp.route('/records/export/status/<task_id>', methods=['GET'])
def export_status(task_id):
    """查询异步导出任务状态。"""
    try:
        task = get_task_status(task_id)
        if not task:
            return jsonify({'code': 404, 'msg': '任务不存在'}), 404

        # 业务异常：无数据可导出
        if task.get('status') == 'failed' and '没有数据可导出' in (task.get('error') or ''):
            return jsonify({'code': 1, 'msg': '没有数据可导出', 'data': task})

        return jsonify({'code': 0, 'msg': 'success', 'data': task})
    except Exception as e:
        logger.exception('查询导出任务状态失败: %s', e)
        return jsonify({'code': 500, 'msg': f'查询任务状态失败: {str(e)}'}), 500


@bp.route('/records/export/download/<task_id>', methods=['GET'])
def export_download(task_id):
    """下载异步导出结果文件。"""
    try:
        task = get_task_status(task_id)
        if not task:
            return jsonify({'code': 404, 'msg': '任务不存在'}), 404
        if task.get('status') != 'completed':
            return jsonify({
                'code': 400,
                'msg': '任务尚未完成',
                'data': {'status': task.get('status')}
            }), 400

        file_path = task.get('result_file')
        if not file_path or not os.path.exists(file_path):
            return jsonify({'code': 404, 'msg': '导出文件不存在'}), 404

        @after_this_request
        def remove_file(response):
            remove_export_file(file_path)
            return response

        return send_file(file_path, as_attachment=True)
    except Exception as e:
        logger.exception('下载导出文件失败: %s', e)
        return jsonify({'code': 500, 'msg': f'下载导出文件失败: {str(e)}'}), 500
