/**
 * 通用权限控制处理器
 * 提供组织权限控制和特定权限控制功能
 */

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
    return Array.isArray(allowedOrgs) ? allowedOrgs.includes(currentOrg) : false;
}

/**
 * 根据组织权限显示或隐藏页面元素
 * @param {Array} allowedOrgs - 允许访问的组织列表
 * @param {string|HTMLElement} elementSelector - 元素选择器或DOM元素
 */
function toggleElementByOrgPermission(allowedOrgs, elementSelector) {
    let element;
    
    if (typeof elementSelector === 'string') {
        element = document.querySelector(elementSelector);
    } else if (elementSelector instanceof HTMLElement) {
        element = elementSelector;
    } else {
        console.error(`无效的元素选择器: ${elementSelector}`);
        return;
    }
    
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
 * @param {string|HTMLElement} elementSelector - 元素选择器或DOM元素
 */
function toggleElementBySpecificPermission(permissionName, elementSelector) {
    let element;
    
    if (typeof elementSelector === 'string') {
        element = document.querySelector(elementSelector);
    } else if (elementSelector instanceof HTMLElement) {
        element = elementSelector;
    } else {
        console.error(`无效的元素选择器: ${elementSelector}`);
        return;
    }
    
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

/**
 * 检查多个权限条件
 * @param {Array} orgPermissions - 组织权限条件，例如 ['fsbbr', 'zsbbr']
 * @param {Array} specificPermissions - 特定权限条件，例如 ['can_process_orders', 'can_delete_cart']
 * @param {string} logic - 逻辑关系 'AND' 或 'OR'
 * @returns {boolean} - 是否满足权限条件
 */
function checkMultiplePermissions(orgPermissions, specificPermissions, logic = 'AND') {
    const hasOrgPermission = orgPermissions && orgPermissions.length > 0 
        ? checkUserOrgPermission(orgPermissions) 
        : true; // 如果没有组织权限要求，则认为满足条件
    
    const hasSpecificPermission = specificPermissions && specificPermissions.length > 0
        ? specificPermissions.some(permission => checkSpecificPermission(permission))
        : true; // 如果没有特定权限要求，则认为满足条件
    
    if (logic.toUpperCase() === 'OR') {
        return hasOrgPermission || hasSpecificPermission;
    } else {
        return hasOrgPermission && hasSpecificPermission;
    }
}

/**
 * 根据多个权限条件显示或隐藏页面元素
 * @param {Array} orgPermissions - 组织权限条件
 * @param {Array} specificPermissions - 特定权限条件
 * @param {string} logic - 逻辑关系 'AND' 或 'OR'
 * @param {string|HTMLElement} elementSelector - 元素选择器或DOM元素
 */
function toggleElementByMultiplePermissions(orgPermissions, specificPermissions, logic, elementSelector) {
    let element;
    
    if (typeof elementSelector === 'string') {
        element = document.querySelector(elementSelector);
    } else if (elementSelector instanceof HTMLElement) {
        element = elementSelector;
    } else {
        console.error(`无效的元素选择器: ${elementSelector}`);
        return;
    }
    
    if (!element) {
        console.error(`未找到选择器为 ${elementSelector} 的元素`);
        return;
    }
    
    if (checkMultiplePermissions(orgPermissions, specificPermissions, logic)) {
        element.style.display = 'block';
    } else {
        element.style.display = 'none';
    }
}

// 页面加载完成后执行权限控制
document.addEventListener('DOMContentLoaded', function() {
    // 确保用户权限信息已加载
    if (window.currentUserPermissions) {
        // 可以在这里添加针对特定元素的权限控制
        // 例如，只有fsbbr组织才显示特定按钮
        // toggleElementByOrgPermission(['fsbbr'], '#special-button');
    } else {
        // 如果权限信息未加载，稍后重试
        setTimeout(function() {
            if (window.currentUserPermissions) {
                // 可以在这里添加针对特定元素的权限控制
                // 例如，只有fsbbr组织才显示特定按钮
                // toggleElementByOrgPermission(['fsbbr'], '#special-button');
            }
        }, 1000);
    }
});

/*
 * 使用说明：
 *
 * 1. 检查组织权限：
 *    if (checkUserOrgPermission(['fsbbr', 'zsbbr'])) {
 *      // 执行特定组织的功能
 *    }
 *
 * 2. 控制元素显示（组织权限）：
 *    toggleElementByOrgPermission(['fsbbr'], '#element-id');
 *
 * 3. 检查特定权限：
 *    if (checkSpecificPermission('can_process_orders')) {
 *      // 执行特定权限的功能
 *    }
 *
 * 4. 控制元素显示（特定权限）：
 *    toggleElementBySpecificPermission('can_delete_cart', '#delete-cart-btn');
 *
 * 5. 检查多重权限：
 *    if (checkMultiplePermissions(['fsbbr'], ['can_process_orders'], 'AND')) {
 *      // 用户是fsbbr组织且有处理订单权限
 *    }
 *
 * 6. 控制元素显示（多重权限）：
 *    toggleElementByMultiplePermissions(['fsbbr'], ['can_process_orders'], 'AND', '#special-feature');
 */