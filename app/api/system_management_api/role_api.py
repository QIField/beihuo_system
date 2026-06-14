# -*- coding:utf-8 -*-
"""
角色管理 API

提供角色的增删改查、角色-权限管理等接口。

响应格式（和项目其他 API 保持一致）：
    {
        "code": 200,
        "msg": "success",
        "data": {
            "total": 100,
            "data_list": [...]
        }
    }

Layui 表格请求参数：
    page: 页码
    limit: 每页数量（Layui 默认参数名）
"""

from flask import Blueprint, jsonify, request
from app.core.permission.decorators import require_admin
from app.services.permission_service import RoleManagementService


role_bp = Blueprint('role_api', __name__, url_prefix='/roles')


@role_bp.route('', methods=['GET'])
@require_admin()
def get_roles():
    """
    获取角色列表（分页 + 搜索）

    Query Parameters:
        page: 页码，默认 1
        limit: 每页数量，默认 10（Layui 表格参数名）
        keyword: 搜索关键词（角色名称/编码）

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

        roles, total = RoleManagementService.get_role_list(
            page=page,
            page_size=page_size,
            keyword=keyword  # pyright: ignore[reportArgumentType]
        )

        return jsonify({
            'code': 200,
            'msg': 'success',
            'data': {
                'total': total,
                'data_list': roles
            }
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'查询失败: {str(e)}',
            'data': None
        })


@role_bp.route('/all', methods=['GET'])
@require_admin()
def get_all_roles():
    """
    获取所有角色（用于下拉选择、用户角色分配等场景）

    Returns:
        {
            "code": 200,
            "msg": "success",
            "data": [...]
        }
    """
    try:
        roles = RoleManagementService.get_all_roles()
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


@role_bp.route('/<int:role_id>', methods=['GET'])
@require_admin()
def get_role_detail(role_id):
    """
    获取角色详情

    Args:
        role_id: 角色ID

    Returns:
        {
            "code": 200,
            "msg": "success",
            "data": {...}
        }
    """
    try:
        role = RoleManagementService.get_role_by_id(role_id)
        if not role:
            return jsonify({
                'code': 404,
                'msg': '角色不存在',
                'data': None
            })

        return jsonify({
            'code': 200,
            'msg': 'success',
            'data': role
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'查询失败: {str(e)}',
            'data': None
        })


@role_bp.route('', methods=['POST'])
@require_admin()
def create_role():
    """
    创建角色

    Request Body:
        {
            "role_name": "业务经理",
            "role_code": "business_manager",
            "description": "业务部门经理角色",
            "parent_role_id": null,
            "status": 1
        }

    Returns:
        {
            "code": 200,
            "msg": "创建成功",
            "data": {"role_id": 10}
        }
    """
    try:
        data = request.get_json() or {}

        role_name = data.get('role_name', '').strip()
        role_code = data.get('role_code', '').strip()
        description = data.get('description', '').strip()
        parent_role_id = data.get('parent_role_id')
        status = int(data.get('status', 1))

        success, msg, role_id = RoleManagementService.create_role(
            role_name=role_name,
            role_code=role_code,
            description=description,
            parent_role_id=parent_role_id,  # pyright: ignore[reportArgumentType]
            status=status
        )

        if success:
            return jsonify({
                'code': 200,
                'msg': msg,
                'data': {'role_id': role_id}
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
            'msg': f'创建失败: {str(e)}',
            'data': None
        })


@role_bp.route('/<int:role_id>', methods=['PUT'])
@require_admin()
def update_role(role_id):
    """
    更新角色信息

    Request Body:
        {
            "role_name": "业务经理",
            "role_code": "business_manager",
            "description": "业务部门经理角色（更新）",
            "parent_role_id": null,
            "status": 1
        }

    Returns:
        {
            "code": 200,
            "msg": "更新成功",
            "data": null
        }
    """
    try:
        data = request.get_json() or {}

        role_name = data.get('role_name')
        role_code = data.get('role_code')
        description = data.get('description')
        parent_role_id = data.get('parent_role_id')
        status = data.get('status')

        if status is not None:
            status = int(status)

        success, msg = RoleManagementService.update_role(
            role_id=role_id,
            role_name=role_name,  # pyright: ignore[reportArgumentType]
            role_code=role_code,  # pyright: ignore[reportArgumentType]
            description=description,  # pyright: ignore[reportArgumentType]
            parent_role_id=parent_role_id,  # pyright: ignore[reportArgumentType]
            status=status  # pyright: ignore[reportArgumentType]
        )

        if success:
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
            'msg': f'更新失败: {str(e)}',
            'data': None
        })


@role_bp.route('/<int:role_id>', methods=['DELETE'])
@require_admin()
def delete_role(role_id):
    """
    删除角色

    Args:
        role_id: 角色ID

    Returns:
        {
            "code": 200,
            "msg": "删除成功",
            "data": null
        }
    """
    try:
        success, msg = RoleManagementService.delete_role(role_id)
        if success:
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
            'msg': f'删除失败: {str(e)}',
            'data': None
        })


@role_bp.route('/<int:role_id>/permissions', methods=['GET'])
@require_admin()
def get_role_permissions(role_id):
    """
    获取角色的权限列表（含权限 ID 列表）

    Args:
        role_id: 角色ID

    Returns:
        {
            "code": 200,
            "msg": "success",
            "data": [
                {"id": 1, "permission_name": "删除购物车", "permission_code": "cart:delete", ...},
                ...
            ]
        }
    """
    try:
        permissions = RoleManagementService.get_role_permissions(role_id)
        return jsonify({
            'code': 200,
            'msg': 'success',
            'data': permissions
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'查询失败: {str(e)}',
            'data': None
        })


@role_bp.route('/<int:role_id>/permissions', methods=['PUT'])
@require_admin()
def assign_permissions(role_id):
    """
    为角色分配权限（覆盖式）

    Request Body:
        {
            "permission_ids": [1, 2, 3, 10, 11, 12]
        }

    Returns:
        {
            "code": 200,
            "msg": "权限分配成功",
            "data": null
        }
    """
    try:
        data = request.get_json() or {}
        permission_ids = data.get('permission_ids', []) or []

        # 转换为整数列表（容错：处理字符串/空值）
        permission_ids = [
            int(pid) for pid in permission_ids
            if pid is not None and str(pid).strip() != ''
        ]

        success, msg = RoleManagementService.assign_permissions_to_role(
            role_id, permission_ids
        )
        if success:
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
