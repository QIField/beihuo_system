# -*- coding:utf-8 -*-
# @Time    : 2026/8/20
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : engine_chassis_stats_service.py
# @Software: PyCharm

from sqlalchemy import func, collate
from app.models.orm_models.weixin_decoding_vin import WeixinDecodingVin
from app.models.orm_models.vin_vehicle_full_info import VinVehicleFullInfo
from app.utils.orm.session import orm_session


def _format_datetime(value):
    """将日期时间格式化为字符串"""
    if value is None:
        return ''
    if hasattr(value, 'strftime'):
        return value.strftime('%Y-%m-%d %H:%M:%S')
    return str(value)


def _build_base_query(session, start_date=None, end_date=None):
    """
    构建 weixin_decoding_vin 与 vin_vehicle_full_info 的关联查询

    :param session: SQLAlchemy Session
    :param start_date: 开始日期（字符串或 datetime）
    :param end_date: 结束日期（字符串或 datetime）
    :return: Query 对象
    """
    query = session.query(WeixinDecodingVin, VinVehicleFullInfo).\
        join(
            VinVehicleFullInfo,
            collate(WeixinDecodingVin.vin, 'utf8mb4_unicode_ci') == VinVehicleFullInfo.vin_code
        )

    if start_date:
        query = query.filter(WeixinDecodingVin.creation_date >= start_date)

    if end_date:
        query = query.filter(WeixinDecodingVin.creation_date <= end_date)

    return query


def _group_by_field(base_query, field):
    """
    按指定字段分组统计出现次数，并过滤空值

    :param base_query: 已关联的基础查询
    :param field: 待统计的字段对象
    :return: [(value, count), ...]
    """
    return base_query.with_entities(
        field,
        func.count().label('count')
    ).filter(
        field.isnot(None),
        field != ''
    ).group_by(field).order_by(func.count().desc()).all()


def get_engine_chassis_stats(start_date=None, end_date=None):
    """
    获取发动机/底盘型号频次统计

    按 weixin_decoding_vin.creation_date 过滤日期范围，
    精确匹配 vin_vehicle_full_info.vin_code，
    分别统计 engine 和 chassis 的出现次数，并按次数降序排列。

    :param start_date: 开始日期，格式 YYYY-MM-DD 或 datetime
    :param end_date: 结束日期，格式 YYYY-MM-DD 或 datetime
    :return: {
        'engine_stats': [{'engine': ..., 'count': ...}, ...],
        'chassis_stats': [{'chassis': ..., 'count': ...}, ...]
    }
    """
    with orm_session() as session:
        base_query = _build_base_query(session, start_date, end_date)

        engine_rows = _group_by_field(base_query, VinVehicleFullInfo.engine)
        chassis_rows = _group_by_field(base_query, VinVehicleFullInfo.chassis)

    return {
        'engine_stats': [
            {'engine': row[0], 'count': row[1]}
            for row in engine_rows
        ],
        'chassis_stats': [
            {'chassis': row[0], 'count': row[1]}
            for row in chassis_rows
        ]
    }
