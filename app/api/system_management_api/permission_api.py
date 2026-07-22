# -*- coding:utf-8 -*-
"""
权限管理 API

提供权限的增删改查接口。

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
from app.services.permission_service import PermissionManagementService


permission_bp = Blueprint('permission_api_bp', __name__, url_prefix='/permissions')


@permission_bp.route('', methods=['GET'])
@require_admin()
def get_permissions():
    """
    获取权限列表（分页 + 搜索 + 筛选）

    Query Parameters:
        page: 页码，默认 1
        limit: 每页数量，默认 10（Layui 表格参数名）
        keyword: 搜索关键词（权限名称或权限编码）
        type: 权限类型筛选（1-模块权限，2-操作权限）
        parent_permission_id: 父权限ID筛选

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
        perm_type = request.args.get('type')
        if perm_type:
            perm_type = int(perm_type)
        parent_perm_id = request.args.get('parent_permission_id')
        if parent_perm_id:
            parent_perm_id = int(parent_perm_id)

        permissions, total = PermissionManagementService.get_permission_list(
            page=page,
            page_size=page_size,
            keyword=keyword,  # pyright: ignore[reportArgumentType]
            perm_type=perm_type,  # pyright: ignore[reportArgumentType]
            parent_permission_id=parent_perm_id  # pyright: ignore[reportArgumentType]
        )

        return jsonify({
            'code': 200,
            'msg': 'success',
            'data': {
                'total': total,
                'data_list': permissions
            }
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'查询失败: {str(e)}',
            'data': None
        })


@permission_bp.route('/all', methods=['GET'])
@require_admin()
def get_all_permissions():
    """
    获取所有权限（按模块分组，用于权限分配选择）。

    调用业务层的 get_permission_tree()，返回带 children 的树结构。

    Returns:
        {
            "code": 200,
            "msg": "success",
            "data": [
                {
                    "id": 1,
                    "permission_name": "购物车模块",
                    "permission_code": "module:cart",
                    "type": 1,
                    "children": [
                        {"id": 9, "permission_name": "查看购物车", "permission_code": "cart:view", ...},
                        ...
                    ]
                },
                ...
            ]
        }
    """
    try:
        permissions = PermissionManagementService.get_permission_tree()
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


@permission_bp.route('/modules', methods=['GET'])
@require_admin()
def get_module_permissions():
    """
    获取所有模块权限（type=1，无限层级树形结构）。

    用于"父权限下拉框"等只需模块作为候选父节点的场景。
    只返回 type=1 的模块权限，支持任意层级的父子嵌套。

    Returns:
        {
            "code": 200,
            "msg": "success",
            "data": [
                {
                    "id": 1,
                    "permission_name": "系统管理",
                    "permission_code": "module:system",
                    ...
                    "children": [
                        {"id": 2, "permission_name": "用户管理", "children": [...]},
                        ...
                    ]
                },
                ...
            ]
        }
    """
    try:
        permissions = PermissionManagementService.get_all_permissions()
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


@permission_bp.route('/<int:permission_id>', methods=['GET'])
@require_admin()
def get_permission_detail(permission_id):
    """
    获取权限详情

    Args:
        permission_id: 权限ID

    Returns:
        {
            "code": 200,
            "msg": "success",
            "data": {...}
        }
    """
    try:
        perm = PermissionManagementService.get_permission_by_id(permission_id)
        if not perm:
            return jsonify({
                'code': 404,
                'msg': '权限不存在',
                'data': None
            })

        return jsonify({
            'code': 200,
            'msg': 'success',
            'data': perm
        })
    except Exception as e:
        return jsonify({
            'code': 500,
            'msg': f'查询失败: {str(e)}',
            'data': None
        })


@permission_bp.route('', methods=['POST'])
@require_admin()
def create_permission():
    """
    创建权限

    Request Body:
        {
            "permission_name": "删除订单",
            "permission_code": "order:delete",
            "description": "删除订单的权限",
            "parent_permission_id": 2,
            "type": 2,
            "status": 1
        }

    Returns:
        {
            "code": 200,
            "msg": "创建成功",
            "data": {"permission_id": 50}
        }
    """
    try:
        data = request.get_json() or {}

        permission_name = data.get('permission_name', '').strip()
        permission_code = data.get('permission_code', '').strip()
        description = data.get('description', '').strip()
        parent_permission_id = data.get('parent_permission_id')
        perm_type = int(data.get('type', 2))
        status = int(data.get('status', 1))

        success, msg, permission_id = PermissionManagementService.create_permission(
            permission_name=permission_name,
            permission_code=permission_code,
            description=description,
            parent_permission_id=parent_permission_id,  # pyright: ignore[reportArgumentType]
            perm_type=perm_type,
            status=status
        )

        if success:
            return jsonify({
                'code': 200,
                'msg': msg,
                'data': {'permission_id': permission_id}
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


@permission_bp.route('/<int:permission_id>', methods=['PUT'])
@require_admin()
def update_permission(permission_id):
    """
    更新权限信息

    Request Body:
        {
            "permission_name": "删除订单",
            "permission_code": "order:delete",
            "description": "删除订单的权限（更新）",
            "parent_permission_id": 2,
            "type": 2,
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

        permission_name = data.get('permission_name')
        permission_code = data.get('permission_code')
        description = data.get('description')
        parent_permission_id = data.get('parent_permission_id')
        perm_type = data.get('type')
        status = data.get('status')

        if perm_type is not None:
            perm_type = int(perm_type)
        if status is not None:
            status = int(status)

        success, msg = PermissionManagementService.update_permission(
            permission_id=permission_id,
            permission_name=permission_name,  # pyright: ignore[reportArgumentType]
            permission_code=permission_code,  # pyright: ignore[reportArgumentType]
            description=description,  # pyright: ignore[reportArgumentType]
            parent_permission_id=parent_permission_id,  # pyright: ignore[reportArgumentType]
            perm_type=perm_type,  # pyright: ignore[reportArgumentType]
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


@permission_bp.route('/<int:permission_id>', methods=['DELETE'])
@require_admin()
def delete_permission(permission_id):
    """
    删除权限

    Args:
        permission_id: 权限ID

    Returns:
        {
            "code": 200,
            "msg": "删除成功",
            "data": null
        }
    """
    try:
        success, msg = PermissionManagementService.delete_permission(permission_id)
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
