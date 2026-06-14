# -*- coding:utf-8 -*-
"""
用户-角色管理 API

提供用户列表查询、用户角色分配、查询等接口。

响应格式（和项目其他 API 保持一致）：
    {
        "code": 200,
        "msg": "success",
        "data": {
            "total": 100,
            "data_list": [...]
        }
    }
"""

from flask import Blueprint, jsonify, request
from app.core.permission.decorators import require_admin
from app.services.permission_service import (
    UserRoleManagementService,
    PermissionService
)


user_role_bp = Blueprint('user_role_api', __name__, url_prefix='/user-roles')


# ============================================================================
# 用户列表（用于用户角色分配页面的"左侧用户列表"）
# ============================================================================

@user_role_bp.route('/users', methods=['GET'])
@require_admin()
def get_user_list():
    """
    获取用户列表（分页 + 搜索）

    Query Parameters:
        page: 页码，默认 1
        limit: 每页数量，默认 10（Layui 表格参数名）
        keyword: 搜索关键词（用户名/门店/部门/职级模糊匹配）

    Returns:
        {
            "code": 200,
            "msg": "success",
            "data": {
                "total": 100,
                "data_list": [...]
            }
        }
    """
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('limit', 10))
        keyword = request.args.get('keyword', '').strip() or None

        user_list, total = UserRoleManagementService.get_user_list(
            page=page,
            page_size=page_size,
            keyword=keyword,
        )

        return jsonify({
            'code': 200,
            'msg': 'success',
            'data': {
                'total': total,
                'data_list': user_list
            }
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'查询失败: {str(e)}',
            'data': None
        })


# ============================================================================
# 用户角色管理
# ============================================================================

@user_role_bp.route('/user/<int:user_id>/roles', methods=['GET'])
@require_admin()
def get_user_roles(user_id):
    """
    获取指定用户的"所有角色 + 是否已分配标记"列表

    用于用户角色分配页面：点击左侧用户后，右侧显示所有角色的勾选状态。

    Args:
        user_id: 用户ID

    Returns:
        {
            "code": 200,
            "msg": "success",
            "data": [
                {"id": 1, "role_name": "超级管理员", "role_code": "super_admin", "assigned": true},
                {"id": 2, "role_name": "业务人员", "role_code": "business_manager", "assigned": false},
                ...
            ]
        }
    """
    try:
        roles = UserRoleManagementService.get_user_roles_with_all(user_id)
        return jsonify({
            'code': 200,
            'msg': 'success',
            'data': roles
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'查询失败: {str(e)}',
            'data': None
        })


@user_role_bp.route('/user/<int:user_id>/roles', methods=['PUT'])
@require_admin()
def assign_roles_to_user(user_id):
    """
    为用户批量分配角色（覆盖式，先删除后插入）

    Request Body:
        {
            "role_ids": [1, 2, 3]
        }

    Args:
        user_id: 用户ID

    Returns:
        {
            "code": 200,
            "msg": "角色分配成功",
            "data": null
        }
    """
    try:
        data = request.get_json() or {}
        role_ids = data.get('role_ids', []) or []

        # 转换为整数列表（容错：过滤空值）
        role_ids = [
            int(rid) for rid in role_ids
            if rid is not None and str(rid).strip() != ''
        ]

        success, msg = UserRoleManagementService.assign_roles_to_user(
            user_id=user_id,
            role_ids=role_ids
        )
        if success:
            # 清除权限缓存，使角色分配立即生效
            PermissionService.clear_cache(user_id)
            return jsonify({
                'code': 200,
                'msg': msg,
                'data': None
            })
        else:
            return jsonify({
                'code': 400,
                'msg': msg,
                'data': None
            })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'分配失败: {str(e)}',
            'data': None
        })


@user_role_bp.route('/user/<int:user_id>/role/<int:role_id>', methods=['DELETE'])
@require_admin()
def remove_role_from_user(user_id, role_id):
    """
    移除用户的指定角色（单个移除，保留其他角色）

    Args:
        user_id: 用户ID
        role_id: 角色ID

    Returns:
        {
            "code": 200,
            "msg": "角色移除成功",
            "data": null
        }
    """
    try:
        success, msg = UserRoleManagementService.remove_role_from_user(
            user_id=user_id,
            role_id=role_id
        )
        if success:
            PermissionService.clear_cache(user_id)
            return jsonify({
                'code': 200,
                'msg': msg,
                'data': None
            })
        else:
            return jsonify({
                'code': 400,
                'msg': msg,
                'data': None
            })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'移除失败: {str(e)}',
            'data': None
        })
