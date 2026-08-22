/**
 * 购物车操作模块
 * 包含移除、清空、导入、导出等操作
 */
var CartActions = (function() {
    'use strict';

    /**
     * 从购物车移除商品
     * @param {string} itemOe 商品OE
     * @param {string} itemBarcode 商品条码
     */
    function removeFromCart(itemOe, itemBarcode) {
        // 使用 CartManager 进行删除（前端立即删除 + 后台异步同步）
        CartManager.removeItem(itemOe, itemBarcode);
    }

    /**
     * 清空购物车
     */
    function clearCart() {
        layui.use(['layer'], function(layer) {
            layer.confirm('确定要清空购物车吗？', function(index) {
                fetch('/api/cart/clear', {
                    method: 'POST'
                })
                .then(function(response) { return response.json(); })
                .then(function(result) {
                    if (result.code === 0) {
                        var dimension = window.currentCartDimension || 'product';
                        CartPanel.refresh(dimension);
                        updateCartCount();
                        layui.layer.msg('购物车已清空', { icon: 1 });
                    } else {
                        layui.layer.msg(result.msg, { icon: 2 });
                    }
                })
                .catch(function(error) {
                    layui.layer.msg('操作失败: ' + error.message, { icon: 2 });
                });
                layer.close(index);
            });
        });
    }

    /**
     * 导入购物车数据
     */
    function importCartData() {
        // 创建文件输入元素
        var fileInput = document.createElement('input');
        fileInput.type = 'file';
        fileInput.accept = '.xlsx,.xls,.csv';

        fileInput.onchange = function(e) {
            var file = e.target.files[0];
            if (!file) return;

            // 显示加载提示
            var loadingIndex = layui.layer.load(2, {
                content: '正在导入数据...',
                shade: [0.3, '#000']
            });

            // 创建FormData对象
            var formData = new FormData();
            formData.append('file', file);

            // 发送请求
            fetch('/api/cart/import', {
                method: 'POST',
                body: formData
            })
            .then(function(response) { return response.json(); })
            .then(function(result) {
                layui.layer.close(loadingIndex);

                if (result.code === 0) {
                    layui.layer.msg('导入成功！' + result.msg, { icon: 1 });

                    // 重新加载表格
                    var currentDimension = window.currentCartDimension || 'product';
                    CartPanel.refresh(currentDimension);

                    updateCartCount(); // 更新购物车计数

                    // 如果有未匹配的数据，提示用户下载
                    if (result.unmatched_count > 0) {
                        layui.layer.confirm('导入完成，有 ' + result.unmatched_count + ' 条数据在系统中不存在，是否下载这些数据的Excel文件？', {
                            btn: ['下载', '取消']
                        }, function(index) {
                            // 下载未匹配的数据
                            var downloadLink = document.createElement('a');
                            downloadLink.href = '/api/cart/download_unmatched';
                            downloadLink.download = '';
                            downloadLink.click();
                            layui.layer.close(index);
                        });
                    }
                } else {
                    layui.layer.msg('导入失败: ' + result.msg, { icon: 2 });
                }
            })
            .catch(function(error) {
                layui.layer.close(loadingIndex);
                layui.layer.msg('导入失败: ' + error.message, { icon: 2 });
            });
        };

        fileInput.click();
    }

    /**
     * 导出购物车数据
     */
    function exportCartData() {
        // 获取当前维度
        var currentDimension = window.currentCartDimension || 'product'; // 默认为产品维度

        // 获取当前搜索条件（从购物车弹层面板中获取）
        var searchParams = new URLSearchParams();
        searchParams.append('dimension', currentDimension);

        // 获取购物车搜索框的值
        var cartSearchOe = document.getElementById('cartSearchOe');
        var cartSearchBarcode = document.getElementById('cartSearchBarcode');
        var cartSearchMaterialName = document.getElementById('cartSearchMaterialName');
        var cartSearchBrand = document.getElementById('cartSearchBrand');
        var cartSearchTag = document.getElementById('cartSearchTag');
        var cartSearchCarModel = document.getElementById('cartSearchCarModel');
        var cartSearchCarBrand = document.getElementById('cartSearchCarBrand');

        if (cartSearchOe) {
            var cartOe = (cartSearchOe.value || '').trim();
            var cartBarcode = (cartSearchBarcode.value || '').trim();
            var cartMaterialName = (cartSearchMaterialName.value || '').trim();
            var cartBrand = (cartSearchBrand.value || '').trim();
            var cartTag = (cartSearchTag.value || '').trim();
            var cartCarModel = (cartSearchCarModel.value || '').trim();
            var cartCarBrand = (cartSearchCarBrand.value || '').trim();

            if (cartOe) searchParams.append('oe', cartOe);
            if (cartBarcode) searchParams.append('barcode', cartBarcode);
            if (cartMaterialName) searchParams.append('material_name', cartMaterialName);
            if (cartBrand) searchParams.append('brand', cartBrand);
            if (cartTag) searchParams.append('tag', cartTag);
            if (cartCarModel) searchParams.append('car_model', cartCarModel);
            if (cartCarBrand) searchParams.append('car_brand', cartCarBrand);
        }

        // 构建URL
        var url = '/api/export/cart?' + searchParams.toString();

        // 显示遮罩加载动画，阻断用户操作
        var loadingIndex = layui.layer.load(2, {
            shade: [0.6, '#000'],
            time: 0
        });

        // 使用fetch获取Excel文件
        fetch(url)
            .then(function(response) {
                if (response.ok) {
                    return response.blob();
                } else {
                    return response.json().then(function(errorData) {
                        throw new Error(errorData.msg || '导出失败');
                    });
                }
            })
            .then(function(blob) {
                layui.layer.close(loadingIndex);
                var link = document.createElement('a');
                link.href = URL.createObjectURL(blob);
                var timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
                link.download = '购物车_' + (currentDimension === 'supplier' ? '供应商维度' : '产品维度') + '_' + timestamp + '.xlsx';
                link.click();
                URL.revokeObjectURL(link.href);
                layui.layer.msg('数据导出成功', { icon: 1 });
            })
            .catch(function(error) {
                layui.layer.close(loadingIndex);
                console.error('导出失败:', error);
                layui.layer.msg('导出失败: ' + error.message, { icon: 2 });
            });
    }

    return {
        removeFromCart: removeFromCart,
        clearCart: clearCart,
        importCartData: importCartData,
        exportCartData: exportCartData
    };
})();
