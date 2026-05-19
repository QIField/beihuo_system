# -*- coding:utf-8 -*-
# @Time    : 2026/4/27 13:11
# @Author  : xingkongtub
# @Project  : beihuo_system
# @File  : weixin_decoding_result_service.py
# @Software: PyCharm


from app.utils.orm.session import orm_session
from app.models.orm_models.weixin_decoding_result import WeixinDecodingResult


def fetch_groupname_list():
    """
    获取所有群名称列表（去重）
    
    Returns:
        群名称列表
    """
    from sqlalchemy import distinct
    
    with orm_session() as session:
        # 查询所有不重复的群名称
        groupnames = session.query(distinct(WeixinDecodingResult.groupname)).filter(
            WeixinDecodingResult.groupname.isnot(None),
            WeixinDecodingResult.groupname != ''
        ).all()
        
        # 转换为列表并排序
        groupname_list = [gn[0] for gn in groupnames]
        groupname_list.sort()
        
        return groupname_list


def fetch_nickname_list():
    """
    获取所有业务员（nickname）列表（去重）
    
    Returns:
        业务员列表
    """
    from sqlalchemy import distinct
    
    with orm_session() as session:
        # 查询所有不重复的业务员
        nicknames = session.query(distinct(WeixinDecodingResult.nickname)).filter(
            WeixinDecodingResult.nickname.isnot(None),
            WeixinDecodingResult.nickname != ''
        ).all()
        
        # 转换为列表并排序
        nickname_list = [nn[0] for nn in nicknames]
        nickname_list.sort()
        
        return nickname_list






