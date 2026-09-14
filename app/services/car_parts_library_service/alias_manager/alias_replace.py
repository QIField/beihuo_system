
import functools

from app.core.cache_utils import get_default_cache
from app.dao.car_parts_library.benz_error_oe_dao import update_status_by_oe
from app.dao.car_parts_library.car_parts_alias_dao import (
    query_by_part_number_alias,
    query_page_group_by_part_number,
    query_by_part_number,
    insert,
    batch_insert,
)
from app.utils.orm.session import orm_session

_cache = get_default_cache()


def by_oe_alias(oe_alia):
    """
    根据OE别名查询记录，返回一条（带缓存）
    """
    key = f"alias:oe:{oe_alia}"
    cached = _cache.get(key)
    if cached is not None:
        return cached

    part_number = None
    try:
        with orm_session() as session:
            result = query_by_part_number_alias(oe_alia, session)
            part_number = result.part_number if result else oe_alia
    except Exception as e:
        part_number = oe_alia


    if part_number:  # pyright: ignore[reportGeneralTypeIssues]
        _cache.set(key, part_number, ttl=600)
    return part_number




def alias_replace(func):
    """
    装饰器：将入参 part_number 视为 OE 别名，先通过 by_oe_alias 转换为真实零件编号，再调用原函数。

    适用于形如 func(part_number, ...) 的函数，例如 mercedes_dalfsc_service.by_part_number_get_data。
    支持位置参数或关键字参数 part_number 两种传参方式。
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if 'part_number' in kwargs:
            kwargs['part_number'] = by_oe_alias(kwargs['part_number'])
        elif args:
            args = (by_oe_alias(args[0]),) + args[1:]
        return func(*args, **kwargs)
    return wrapper


def page_alias_list(page=1, page_size=10, keyword=None):
    """
    分页返回别名聚合数据（按 part_number 分组），供前端查看

    :param page: 页码，默认1
    :param page_size: 每页条数，默认10
    :param keyword: 关键字筛选（可选），模糊匹配配件编号
    :return: {'status': bool, 'msg': str, 'count': int, 'data': list}
    """
    try:
        with orm_session() as session:
            total, part_numbers, alias_rows = query_page_group_by_part_number(
                session,
                page=page,
                page_size=page_size,
                keyword=keyword,
            )
            # 按 part_number 分组组装别名
            grouped = {}
            for pn, alias in alias_rows:
                grouped.setdefault(pn, []).append(alias)
            rows = [
                {'part_number': pn, 'aliases': grouped.get(pn, [])}
                for pn in part_numbers
            ]
        return {'status': True, 'msg': '获取成功', 'count': total, 'data': rows}
    except Exception as e:
        return {'status': False, 'msg': f'获取别名列表失败: {str(e)}', 'count': 0, 'data': []}


def add_alias_record(part_number, part_number_alias, remark=None):
    """
    将错误 OE（别名）关联到奔驰标准 OE

    新增一条别名记录：part_number_alias（错误OE）映射到 part_number（奔驰标准OE），
    并将 benz_error_oe 中对应的错误 OE 记录标记为已入别名库（status=1），
    之后查询错误OE 时即可通过 by_oe_alias 用奔驰标准OE 替代。

    :param part_number: 奔驰标准OE
    :param part_number_alias: 错误OE（别名）
    :param remark: 备注（可选）
    :return: {'status': bool, 'msg': str}
    """
    if not part_number or not part_number_alias:
        return {'status': False, 'msg': '奔驰标准OE和错误OE不能为空'}

    try:
        with orm_session() as session:
            existing = query_by_part_number_alias(part_number_alias, session)
            if existing:
                return {'status': False, 'msg': f'该错误OE已关联: {part_number_alias}'}

            insert(session, part_number, part_number_alias, remark)
            # 将对应的错误 OE 记录标记为已入别名库
            update_status_by_oe(session, part_number_alias, 1)
            # 清理该错误OE的缓存，避免 by_oe_alias 命中旧的映射值
            _cache.delete(f"alias:oe:{part_number_alias}")

        return {'status': True, 'msg': '关联成功'}
    except Exception as e:
        return {'status': False, 'msg': f'关联失败: {str(e)}'}


def batch_add_alias_records(records):
    """
    批量将错误 OE（别名）关联到奔驰标准 OE

    逐条校验（标准OE/别名非空、别名是否已存在），可用的批量插入，
    并同步将对应错误 OE 记录标记为已入别名库、清理别名缓存。

    :param records: [{'part_number': 奔驰标准OE, 'part_number_alias': 错误OE, 'remark': 备注}, ...]
    :return: {'status': bool, 'msg': str, 'added_count': int, 'failed_count': int, 'failures': list}
    """
    if not records:
        return {'status': False, 'msg': '数据不能为空', 'added_count': 0, 'failed_count': 0, 'failures': []}

    try:
        with orm_session() as session:
            to_insert = []
            failures = []
            for idx, r in enumerate(records):
                pn = (r.get('part_number') or '').strip()
                alias = (r.get('part_number_alias') or '').strip()
                remark = r.get('remark')

                if not pn or not alias:
                    failures.append({'index': idx, 'msg': '奔驰标准OE和别名不能为空'})
                    continue

                if query_by_part_number_alias(alias, session):
                    failures.append({'index': idx, 'msg': f'该错误OE已关联: {alias}'})
                    continue

                to_insert.append({'part_number': pn, 'part_number_alias': alias, 'remark': remark})

            if to_insert:
                batch_insert(session, to_insert)
                for r in to_insert:
                    # 将对应的错误 OE 记录标记为已入别名库
                    update_status_by_oe(session, r['part_number_alias'], 1)
                    # 清理该错误OE的缓存
                    _cache.delete(f"alias:oe:{r['part_number_alias']}")

            added = len(to_insert)
            failed = len(failures)

        msg = f'成功添加 {added} 条'
        if failed:
            msg += f'，失败 {failed} 条'
        return {
            'status': True,
            'msg': msg,
            'added_count': added,
            'failed_count': failed,
            'failures': failures,
        }
    except Exception as e:
        return {
            'status': False,
            'msg': f'批量添加别名失败: {str(e)}',
            'added_count': 0,
            'failed_count': len(records),
            'failures': [],
        }


def get_aliases_by_part_number(part_number):
    """
    根据配件编号查询其下的所有别名记录

    :param part_number: 配件编号
    :return: {'status': bool, 'msg': str, 'data': list}
    """
    try:
        with orm_session() as session:
            rows = query_by_part_number(part_number, session)
            data = [row.to_dict() for row in rows]
        return {'status': True, 'msg': '获取成功', 'data': data}
    except Exception as e:
        return {'status': False, 'msg': f'获取别名详情失败: {str(e)}', 'data': []}
