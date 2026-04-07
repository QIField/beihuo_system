/**
 * 购物车 API 模块
 * 封装所有与购物车相关的后端请求
 */
var CartAPI = (function() {
    'use strict';

    return {
        /**
         * 删除单个商品
         * @param {string} itemOe - 商品OE号
         * @param {string} itemBarcode - 商品条码
         * @returns {Promise} - 返回 Promise 对象
         */
        removeItem: function(itemOe, itemBarcode) {
            return fetch('/api/cart/remove', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    item_oe: itemOe, 
                    item_barcode: itemBarcode 
                })
            }).then(response => response.json());
        },

        /**
         * 批量删除商品
         * @param {Array} itemDetails - 要删除的商品列表 [{item_oe, item_barcode}, ...]
         * @returns {Promise} - 返回 Promise 对象
         */
        removeMultiple: function(itemDetails) {
            return fetch('/api/cart/remove_multiple', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ item_details: itemDetails })
            }).then(response => response.json());
        },

        /**
         * 获取购物车数据
         * @param {string} dimension - 维度（product/supplier）
         * @returns {Promise} - 返回 Promise 对象
         */
        getCartData: function(dimension) {
            return fetch('/api/cart?dimension=' + (dimension || 'product'))
                .then(response => response.json());
        }
    };
})();
