/**
 * 购物车数量编辑模块
 */
var CartEdit = (function() {
    'use strict';

    /**
     * 根据行数据更新数量
     * @param {object} rowData 行数据
     * @param {number} quantity 新数量
     */
    function updateQuantityByData(rowData, quantity) {
        if (!rowData || !rowData.oe) {
            layui.layer.msg('无法获取商品OE', { icon: 2 });
            return;
        }

        var oe = rowData.oe;
        var num = parseInt(quantity, 10);

        if (isNaN(num) || num <= 0) {
            layui.layer.msg('请输入有效数量', { icon: 2 });
            return;
        }

        console.log('更新购物车数量:', { oe: oe, quantity: num });

        fetch('/api/cart/update_quantity', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                item_oe: oe,
                quantity: num
            })
        })
        .then(function(response) { return response.json(); })
        .then(function(result) {
            if (result.code === 0) {
                layui.layer.msg('数量更新成功', { icon: 1 });
                updateCartCount();
                // 不刷新表格，保留当前滚动位置和上下文
            } else {
                console.log('更新失败:', result.msg);
                layui.layer.msg(result.msg, { icon: 2 });
                // 失败时刷新恢复原始值
                CartPanel.refresh();
            }
        })
        .catch(function(error) {
            console.log('请求错误:', error);
            layui.layer.msg('更新失败: ' + error.message, { icon: 2 });
            // 失败时刷新恢复原始值
            CartPanel.refresh();
        });
    }

    return {
        updateQuantityByData: updateQuantityByData
    };
})();
