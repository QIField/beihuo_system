/**
 * 购物车管理模块
 * 处理购物车的业务逻辑，协调 API 和表格操作
 */
var CartManager = (function() {
    'use strict';

    /**
     * 更新购物车数量显示
     */
    function updateCartCount() {
        if (typeof window.updateCartCount === 'function') {
            window.updateCartCount();
        }
    }

    /**
     * 显示消息提示
     * @param {string} msg - 消息内容
     * @param {number} icon - 图标类型（1=成功，2=失败）
     */
    function showMsg(msg, icon) {
        if (typeof layui !== 'undefined' && layui.layer) {
            layui.layer.msg(msg, { icon: icon });
        }
    }

    return {
        /**
         * 删除单个商品（前端立即删除 + 后台异步同步）
         * @param {string} itemOe - 商品OE号
         * @param {string} itemBarcode - 商品条码
         */
        removeItem: function(itemOe, itemBarcode) {
            // 1. 前端立即删除
            var removed = CartTable.removeRowLocal(itemOe, itemBarcode);
            if (!removed) return;

            // 2. 后台异步删除
            CartAPI.removeItem(itemOe, itemBarcode)
                .then(function(result) {
                    if (result.code === 0) {
                        updateCartCount();
                    } else {
                        showMsg('删除失败，正在刷新数据...', 2);
                        CartTable.refresh();
                    }
                })
                .catch(function(error) {
                    console.error('删除请求失败:', error);
                    showMsg('删除失败，正在刷新数据...', 2);
                    CartTable.refresh();
                });
        },

        /**
         * 批量删除商品（前端立即删除 + 后台异步同步）
         * @param {Array} itemDetails - 要删除的商品列表 [{item_oe, item_barcode}, ...]
         */
        removeMultiple: function(itemDetails) {
            if (!itemDetails || itemDetails.length === 0) return;

            // 1. 前端立即删除（逐个删除）
            var removedCount = 0;
            itemDetails.forEach(function(item) {
                var removed = CartTable.removeRowLocal(item.item_oe, item.item_barcode);
                if (removed) removedCount++;
            });

            if (removedCount > 0) {
                showMsg('已删除 ' + removedCount + ' 个商品', 1);
                updateCartCount();
            }

            // 2. 后台异步删除
            CartAPI.removeMultiple(itemDetails)
                .then(function(result) {
                    if (result.code !== 0) {
                        showMsg('删除失败，正在刷新数据...', 2);
                        CartTable.refresh();
                    }
                })
                .catch(function(error) {
                    console.error('批量删除请求失败:', error);
                    showMsg('删除失败，正在刷新数据...', 2);
                    CartTable.refresh();
                });
        }
    };
})();
