# -*- coding:utf-8 -*-
"""
品牌别名池统一查询服务

职责：
1. 提供池内名称查询（给定一个名称，返回同池所有名称）
2. 提供匹配品牌列表（给定一个品牌，返回需要同时匹配的所有品牌）
3. 全局内存缓存，减少数据库往返
4. 支持缓存失效（数据变更后调用 clear_pool_cache）

用法：
    from app.services.pp_alias_service.pp_alias_pool_service import get_match_brands
    match_brands = get_match_brands("博世")  # 返回 ["博世", "BOSCH", ...]
"""

from typing import List, Optional, Dict
from collections import defaultdict

from app.utils.orm.session import orm_session
from app.utils.logger_config import get_task_logger

logger = get_task_logger('pp_alias_pool')

# ============ 进程级内存缓存 ============
_pool_cache: Optional[Dict[int, List[str]]] = None
_name_to_pool: Optional[Dict[str, int]] = None


def _load_pool_cache() -> Dict[int, List[str]]:
    """
    从数据库加载全量别名池到内存
    返回: {pool_id: [name1, name2, ...]}
    """
    global _pool_cache, _name_to_pool
    if _pool_cache is not None:
        return _pool_cache

    pool_map: Dict[int, List[str]] = defaultdict(list)
    name_to_pool: Dict[str, int] = {}
    with orm_session() as session:
        from app.models.orm_models.crm_pp_alias_pool import CrmPpAliasPool
        rows = session.query(CrmPpAliasPool).all()
        for row in rows:
            pool_map[row.pool_id].append(row.name)
            name_to_pool[row.name] = row.pool_id

    # 每个池内名称排序，保证输出稳定
    _pool_cache = {
        pid: sorted(names)
        for pid, names in pool_map.items()
    }
    _name_to_pool = name_to_pool
    logger.info(f"别名池缓存加载完成: {len(_pool_cache)} 个池, {len(_name_to_pool)} 个名称")
    return _pool_cache


def clear_pool_cache():
    """清除内存缓存（数据变更后调用）"""
    global _pool_cache, _name_to_pool
    _pool_cache = None
    _name_to_pool = None
    logger.info("别名池缓存已清除")


def get_pool_members(name: str) -> List[str]:
    """
    根据名称获取其所在别名池的所有成员

    :param name: 品牌名称
    :return: 同池所有名称列表（包含自身），未找到返回空列表
    """
    if not name:
        return []
    _load_pool_cache()
    pool_id = _name_to_pool.get(name)
    if pool_id is None:
        return []
    return _pool_cache.get(pool_id, [])


def get_match_brands(brand: str, oem_brands: Optional[List[str]] = None) -> List[str]:
    """
    获取需要匹配的品牌列表

    规则：
    1. 如果 brand 在 oem_brands 中，返回整个 oem_brands 列表
    2. 如果 brand 在别名池中，返回池内所有名称
    3. 否则返回 [brand] 自身

    :param brand: 原始品牌名
    :param oem_brands: 原厂品牌组，默认 ["原厂", "原厂国内4s件"]
    :return: 需要匹配的品牌列表
    """
    if not brand:
        return []
    oem_brands = oem_brands or ["原厂", "原厂国内4s件"]
    if brand in oem_brands:
        return oem_brands
    members = get_pool_members(brand)
    if members:
        return members
    return [brand]


def get_representative_name(name: str) -> str:
    """
    获取名称所在池的代表名（用于展示）

    策略：返回池内名称最短的（通常是最标准的名称）
    """
    members = get_pool_members(name)
    if not members:
        return name
    return min(members, key=lambda x: len(x))


def is_same_pool(name1: str, name2: str) -> bool:
    """判断两个名称是否属于同一别名池"""
    if not name1 or not name2:
        return False
    members = get_pool_members(name1)
    return name2 in members


def get_all_pools() -> Dict[int, List[str]]:
    """
    获取所有别名池（用于管理后台等全量场景）
    返回: {pool_id: [name1, name2, ...]}
    """
    return _load_pool_cache().copy()


def get_pools_by_search(name_keyword: str) -> Dict[int, List[str]]:
    """
    根据关键词搜索相关别名池
    返回名称包含关键词的池
    """
    if not name_keyword:
        return {}
    all_pools = _load_pool_cache()
    result = {}
    for pool_id, names in all_pools.items():
        if any(name_keyword in n for n in names):
            result[pool_id] = names
    return result
