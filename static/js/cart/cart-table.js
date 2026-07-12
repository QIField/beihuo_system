/**
 * 购物车表格操作模块
 * 兼容 LayUI table 与 Handsontable 两种表格
 */
var CartTable = (function() {
    'use strict';

    var TABLE_ID = 'cartTable';

    /**
     * 获取 LayUI 表格主体容器
     * @returns {Element} - 表格主体 DOM 元素
     */
    function getTableBody() {
        return document.querySelector('#' + TABLE_ID + ' + .layui-table-view .layui-table-body');
    }

    /**
     * 获取 LayUI 表格视图容器
     * @returns {Element} - 表格视图 DOM 元素
     */
    function getTableView() {
        return document.querySelector('#' + TABLE_ID + ' + .layui-table-view');
    }

    /**
     * 删除 LayUI 表格指定索引的行（包括固定列和未固定列）
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
     * 更新 LayUI 表格所有行的 data-index 属性
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

    /**
     * 获取 Handsontable 主滚动容器
     * @returns {Element|null}
     */
    function getHandsontableScrollContainer() {
        return document.querySelector('#cartHot .ht_master .wtHolder');
    }

    /**
     * 保存 Handsontable 滚动位置
     * @returns {number}
     */
    function saveScrollPosition() {
        var container = getHandsontableScrollContainer();
        return container ? container.scrollTop : 0;
    }

    /**
     * 恢复 Handsontable 滚动位置
     * @param {number} scrollTop
     */
    function restoreScrollPosition(scrollTop) {
        setTimeout(function() {
            var container = getHandsontableScrollContainer();
            if (container) {
                container.scrollTop = scrollTop;
            }
        }, 0);
    }

    /**
     * 从 Handsontable 数据源中删除指定行
     * @param {string} itemOe - 商品OE号
     * @param {string} itemBarcode - 商品条码
     * @returns {boolean} - 是否删除成功
     */
    function removeRowFromHandsontable(itemOe, itemBarcode) {
        var hot = (typeof CartPanel !== 'undefined' && CartPanel.getHot) ? CartPanel.getHot() : null;
        if (!hot) return false;

        var sourceData = hot.getSourceData();
        if (!sourceData) return false;

        var deleteIndex = -1;
        for (var i = 0; i < sourceData.length; i++) {
            var row = sourceData[i];
            var barcodeMatch = (row.barcode === itemBarcode) ||
                               (!row.barcode && !itemBarcode);
            if (row.oe === itemOe && barcodeMatch) {
                deleteIndex = i;
                break;
            }
        }

        if (deleteIndex > -1) {
            var savedScrollTop = saveScrollPosition();
            // 使用 Handsontable 原生 API 删除行，确保表格正确刷新
            hot.alter('remove_row', deleteIndex);
            restoreScrollPosition(savedScrollTop);
            return true;
        }
        return false;
    }

    /**
     * 从 Handsontable 数据源中批量删除指定行
     * @param {Array} itemDetails - 要删除的商品列表 [{item_oe, item_barcode}, ...]
     * @returns {number} - 成功删除的行数
     */
    function removeRowsFromHandsontable(itemDetails) {
        var hot = (typeof CartPanel !== 'undefined' && CartPanel.getHot) ? CartPanel.getHot() : null;
        if (!hot || !itemDetails || itemDetails.length === 0) return 0;

        var sourceData = hot.getSourceData();
        if (!sourceData) return 0;

        var indices = [];
        for (var i = 0; i < itemDetails.length; i++) {
            var item = itemDetails[i];
            var itemOe = item.item_oe;
            var itemBarcode = item.item_barcode || '';
            for (var j = 0; j < sourceData.length; j++) {
                var row = sourceData[j];
                var barcodeMatch = (row.barcode === itemBarcode) ||
                                   (!row.barcode && !itemBarcode);
                if (row.oe === itemOe && barcodeMatch) {
                    indices.push(j);
                    break;
                }
            }
        }

        // 去重并按降序排列，避免删除后索引错位
        indices = indices.filter(function(value, index, self) {
            return self.indexOf(value) === index;
        }).sort(function(a, b) {
            return b - a;
        });

        if (indices.length > 0) {
            var savedScrollTop = saveScrollPosition();
            for (var k = 0; k < indices.length; k++) {
                hot.alter('remove_row', indices[k]);
            }
            restoreScrollPosition(savedScrollTop);
        }

        return indices.length;
    }

    /**
     * 判断当前是否使用 Handsontable
     * @returns {boolean}
     */
    function isHandsontableMode() {
        return !!(typeof CartPanel !== 'undefined' && CartPanel.getHot && CartPanel.getHot());
    }

    return {
        /**
         * 从表格中删除指定行（前端本地删除，无刷新）
         * @param {string} itemOe - 商品OE号
         * @param {string} itemBarcode - 商品条码
         * @returns {boolean} - 是否删除成功
         */
        removeRowLocal: function(itemOe, itemBarcode) {
            // 优先使用 Handsontable
            if (isHandsontableMode()) {
                return removeRowFromHandsontable(itemOe, itemBarcode);
            }

            // 兼容旧版 LayUI table
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
                tableData.splice(deleteIndex, 1);
                deleteRowByIndex(deleteIndex);
                updateRowIndexes();

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
         * 从表格中批量删除指定行（前端本地删除，无刷新）
         * @param {Array} itemDetails - 要删除的商品列表 [{item_oe, item_barcode}, ...]
         * @returns {number} - 成功删除的行数
         */
        removeRowsLocal: function(itemDetails) {
            if (isHandsontableMode()) {
                return removeRowsFromHandsontable(itemDetails);
            }

            // 兼容旧版 LayUI table
            var self = this;
            var removedCount = 0;
            itemDetails.forEach(function(item) {
                if (self.removeRowLocal(item.item_oe, item.item_barcode)) {
                    removedCount++;
                }
            });
            return removedCount;
        },

        /**
         * 刷新表格（从后端重新加载）
         * @param {string} dimension - 维度
         */
        refresh: function(dimension) {
            // 优先使用 Handsontable
            if (typeof CartPanel !== 'undefined' && CartPanel.refresh) {
                CartPanel.refresh(dimension || 'product');
                return;
            }

            // 兼容旧版 LayUI table
            layui.table.reload(TABLE_ID, {
                url: '/api/cart?dimension=' + (dimension || 'product')
            });
        }
    };
})();
