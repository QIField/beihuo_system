"""
通用权限控制服务
提供组织权限控制的装饰器和函数，可以方便地限制特定功能只能由特定组织访问
"""

from functools import wraps
from flask import session, jsonify


def check_org_permission(allowed_orgs):
    """
    检查用户组织权限
    :param allowed_orgs: 允许访问的组织列表
    :return: True if user has permission, otherwise False
    """
    if 'logged_in' not in session:
        return False
    
    # 获取用户当前组织
    current_org = session.get('current_org', session.get('store', ''))
    
    # 检查用户组织是否在允许列表中
    return current_org in allowed_orgs


def org_required(allowed_orgs):
    """
    组织权限验证装饰器
    :param allowed_orgs: 允许访问的组织列表
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'logged_in' not in session:
                return jsonify({'code': 1, 'msg': '请先登录'}), 401
            
            # 获取用户当前组织
            current_org = session.get('current_org', session.get('store', ''))
            
            # 检查用户组织是否在允许列表中
            if current_org not in allowed_orgs:
                return jsonify({'code': 1, 'msg': f'您没有权限访问此功能，仅限 {",".join(allowed_orgs)} 组织访问'}), 403
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def get_current_org():
    """
    获取当前用户的组织
    :return: 当前组织代码
    """
    return session.get('current_org', session.get('store', ''))


def check_specific_permission(permission_name):
    """
    检查用户特定权限
    :param permission_name: 权限名称，如 'can_process_orders', 'can_delete_cart' 等
    :return: True if user has permission, otherwise False
    """
    if 'logged_in' not in session:
        return False
    
    # 从session中获取特定权限
    return session.get(permission_name, False)


def specific_permission_required(permission_name):
    """
    特定权限验证装饰器
    :param permission_name: 权限名称
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'logged_in' not in session:
                return jsonify({'code': 1, 'msg': '请先登录'}), 401
            
            # 检查用户是否具有特定权限
            if not session.get(permission_name, False):
                return jsonify({'code': 1, 'msg': f'您没有 {permission_name} 权限'}), 403
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# 前端JavaScript代码示例 (需要在HTML模板中使用)
FRONTEND_JS_CODE = """
/**
 * 检查当前用户是否有权限访问特定功能
 * @param {Array} allowedOrgs - 允许访问的组织列表
 * @returns {boolean} - 是否有权限
 */
function checkUserOrgPermission(allowedOrgs) {
    // 这里需要确保window.currentUserPermissions对象已经从后端获取
    // window.currentUserPermissions = { username, is_admin, can_delete_cart, can_process_orders, store, current_org }
    if (!window.currentUserPermissions) {
        console.error('用户权限信息未加载');
        return false;
    }
    
    const currentOrg = window.currentUserPermissions.current_org || window.currentUserPermissions.store;
    return allowedOrgs.includes(currentOrg);
}

/**
 * 根据组织权限显示或隐藏页面元素
 * @param {Array} allowedOrgs - 允许访问的组织列表
 * @param {string} elementSelector - 元素选择器
 */
function toggleElementByOrgPermission(allowedOrgs, elementSelector) {
    const element = document.querySelector(elementSelector);
    if (!element) {
        console.error(`未找到选择器为 ${elementSelector} 的元素`);
        return;
    }
    
    if (checkUserOrgPermission(allowedOrgs)) {
        element.style.display = 'block';
    } else {
        element.style.display = 'none';
    }
}

/**
 * 检查当前用户是否有特定权限
 * @param {string} permissionName - 权限名称
 * @returns {boolean} - 是否有权限
 */
function checkSpecificPermission(permissionName) {
    if (!window.currentUserPermissions) {
        console.error('用户权限信息未加载');
        return false;
    }
    
    return !!window.currentUserPermissions[permissionName];
}

/**
 * 根据特定权限显示或隐藏页面元素
 * @param {string} permissionName - 权限名称
 * @param {string} elementSelector - 元素选择器
 */
function toggleElementBySpecificPermission(permissionName, elementSelector) {
    const element = document.querySelector(elementSelector);
    if (!element) {
        console.error(`未找到选择器为 ${elementSelector} 的元素`);
        return;
    }
    
    if (checkSpecificPermission(permissionName)) {
        element.style.display = 'block';
    } else {
        element.style.display = 'none';
    }
}
"""


"""
使用说明：

1. 在后端路由中使用组织权限控制：
   from app.services.permission_service import org_required
   
   @app.route('/your_page')
   @org_required(['fsbbr'])  # 只允许fsbbr组织访问
   def your_page():
       return render_template('your_page.html')

2. 在后端路由中使用特定权限控制：
   from app.services.permission_service import specific_permission_required
   
   @app.route('/delete_cart')
   @specific_permission_required('can_delete_cart')  # 需要有删除购物车权限
   def delete_cart():
       # 删除购物车逻辑
       return jsonify({'code': 0, 'msg': '删除成功'})

3. 在函数中检查权限：
   from app.services.permission_service import check_org_permission
   
   def some_function():
       if check_org_permission(['fsbbr', 'zsbbr']):  # 检查是否为fsbbr或zsbbr组织
           # 执行特定组织的功能
           pass
       else:
           # 返回权限不足的错误
           return jsonify({'code': 1, 'msg': '权限不足'})

4. 在前端JavaScript中控制元素显示：
   // 确保在页面加载完成后执行
   document.addEventListener('DOMContentLoaded', function() {
       // 只有fsbbr组织才显示特定按钮
       toggleElementByOrgPermission(['fsbbr'], '#special-button');
       
       // 只有有处理订单权限的用户才显示特定菜单项
       toggleElementBySpecificPermission('can_process_orders', '#process-orders-menu-item');
   });
"""