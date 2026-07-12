/**
 * 购物车筛选模块
 */
var CartFilters = (function() {
    'use strict';

    /**
     * 初始化购物车搜索和筛选按钮
     */
    function initCartFilterButtons() {
        // 搜索按钮
        FilterPanel.initSearch({
            container: '#cartFilterButtons',
            fields: [
                { label: 'OE号', inputId: 'cartSearchOe' },
                { label: '物料条码', inputId: 'cartSearchBarcode' },
                { label: '物料名称', inputId: 'cartSearchMaterialName' },
                { label: '品牌', inputId: 'cartSearchBrand' },
                { label: '车型品牌', inputId: 'cartSearchCarBrand' },
                { label: '标签', inputId: 'cartSearchTag' },
                { label: '车型', inputId: 'cartSearchCarModel' }
            ],
            onApply: function(field, value) {
                applyCartFilters();
            }
        });

        // 添加分隔符
        var container = document.getElementById('cartFilterButtons');
        if (container) {
            var separator = document.createElement('span');
            separator.textContent = '|';
            separator.style.margin = '0 5px';
            separator.style.color = '#999';
            container.appendChild(separator);
        }

        // 筛选按钮
        FilterPanel.init({
            container: '#cartFilterButtons',
            fields: [
                { field: 'brand', label: '品牌' },
                { field: 'car_brand', label: '车型品牌' },
                { field: 'tag', label: '标签' }
            ],
            data: [],
            onApply: function(filters) {
                applyCartFilters();
            }
        });

        // 添加分隔符和重置按钮
        if (container) {
            var separator2 = document.createElement('span');
            separator2.textContent = '|';
            separator2.style.margin = '0 5px';
            separator2.style.color = '#999';
            container.appendChild(separator2);

            var resetBtn = document.createElement('button');
            resetBtn.className = 'filter-btn';
            resetBtn.id = 'cartResetBtn';
            resetBtn.textContent = '重置';
            // 重置按钮的具体点击逻辑由 cart-panel.js 统一绑定
            container.appendChild(resetBtn);
        }
    }

    /**
     * 应用购物车筛选条件
     */
    function applyCartFilters() {
        // 刷新表格，具体参数由 CartPanel.paramsBuilder 统一组装
        CartPanel.refresh(1);
    }

    return {
        initCartFilterButtons: initCartFilterButtons,
        applyCartFilters: applyCartFilters
    };
})();
