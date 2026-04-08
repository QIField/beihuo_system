/**
 * 购物车表格操作模块
 * 处理表格的增删改查等操作
 */
var CartTable = (function() {
    'use strict';

    var TABLE_ID = 'cartTable';

    /**
     * 获取表格主体容器
     * @returns {Element} - 表格主体 DOM 元素
     */
    function getTableBody() {
        return document.querySelector('#' + TABLE_ID + ' + .layui-table-view .layui-table-body');
    }

    /**
     * 获取表格视图容器
     * @returns {Element} - 表格视图 DOM 元素
     */
    function getTableView() {
        return document.querySelector('#' + TABLE_ID + ' + .layui-table-view');
    }

    /**
     * 删除指定索引的行（包括固定列和未固定列）
     * @param {number} index - 行索引
     */
    function deleteRowByIndex(index) {
        var tableView = getTableView();
        if (!tableView) return;

        // 删除主表格中的行
        var mainBody = tableView.querySelector('.layui-table-body.layui-table-main');
        if (mainBody) {
            var mainRow = mainBody.querySelector('tr[data-index="' + index + '"]');
            if (mainRow) {
                mainRow.remove();
            }
        }

        // 删除固定列中的行（左侧固定列）
        var fixedLeftBody = tableView.querySelector('.layui-table-fixed-l .layui-table-body');
        if (fixedLeftBody) {
            var fixedLeftRow = fixedLeftBody.querySelector('tr[data-index="' + index + '"]');
            if (fixedLeftRow) {
                fixedLeftRow.remove();
            }
        }

        // 删除固定列中的行（右侧固定列）
        var fixedRightBody = tableView.querySelector('.layui-table-fixed-r .layui-table-body');
        if (fixedRightBody) {
            var fixedRightRow = fixedRightBody.querySelector('tr[data-index="' + index + '"]');
            if (fixedRightRow) {
                fixedRightRow.remove();
            }
        }
    }

    /**
     * 更新所有行的 data-index 属性
     */
    function updateRowIndexes() {
        var tableView = getTableView();
        if (!tableView) return;

        var bodies = [
            tableView.querySelector('.layui-table-body.layui-table-main'),
            tableView.querySelector('.layui-table-fixed-l .layui-table-body'),
            tableView.querySelector('.layui-table-fixed-r .layui-table-body')
        ];

        bodies.forEach(function(body) {
            if (body) {
                var rows = body.querySelectorAll('tr');
                rows.forEach(function(row, newIndex) {
                    row.setAttribute('data-index', newIndex);
                });
            }
        });
    }

    return {
        /**
         * 从表格中删除指定行（前端本地删除，无刷新）
         * @param {string} itemOe - 商品OE号
         * @param {string} itemBarcode - 商品条码
         * @returns {boolean} - 是否删除成功
         */
        removeRowLocal: function(itemOe, itemBarcode) {
            // 保存当前滚动位置
            var tableBody = getTableBody();
            var savedScrollTop = tableBody ? tableBody.scrollTop : 0;

            var tableData = layui.table.cache[TABLE_ID];
            if (!tableData) return false;

            var deleteIndex = -1;
            for (var i = 0; i < tableData.length; i++) {
                var row = tableData[i];
                var barcodeMatch = (row.barcode === itemBarcode) || 
                                   (!row.barcode && !itemBarcode);
                if (row.oe === itemOe && barcodeMatch) {
                    deleteIndex = i;
                    break;
                }
            }

            if (deleteIndex > -1) {
                // 从缓存数据中删除
                tableData.splice(deleteIndex, 1);

                // 删除 DOM 中的行（包括固定列）
                deleteRowByIndex(deleteIndex);

                // 更新所有行的 data-index
                updateRowIndexes();

                // 恢复滚动位置
                setTimeout(function() {
                    var newTableBody = getTableBody();
                    if (newTableBody && savedScrollTop > 0) {
                        newTableBody.scrollTop = savedScrollTop;
                    }
                }, 0);

                return true;
            }
            return false;
        },

        /**
         * 刷新表格（从后端重新加载）
         * @param {string} dimension - 维度
         */
        refresh: function(dimension) {
            layui.table.reload(TABLE_ID, {
                url: '/api/cart?dimension=' + (dimension || 'product')
            });
        }
    };
})();
