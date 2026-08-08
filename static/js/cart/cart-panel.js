/**
 * 购物车面板主模块（Handsontable）
 */
var CartPanel = (function() {
    'use strict';

    /**
     * 复制文本到剪贴板
     */
    function copyTextToClipboard(text, onSuccess, onError) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(function() {
                if (typeof onSuccess === 'function') onSuccess();
            }, function(err) {
                if (typeof onError === 'function') onError(err);
            });
        } else {
            var textarea = document.createElement('textarea');
            textarea.value = text;
            textarea.style.position = 'fixed';
            textarea.style.left = '-9999px';
            document.body.appendChild(textarea);
            textarea.select();
            try {
                document.execCommand('copy');
                if (typeof onSuccess === 'function') onSuccess();
            } catch (err) {
                if (typeof onError === 'function') onError(err);
            }
            document.body.removeChild(textarea);
        }
    }

    // 私有变量
    var builder = null;
    var hot = null;
    var currentDimension = 'product';
    var layero = null;
    var activeColumnFilters = {}; // 表头下拉菜单筛选条件

    // 面板 HTML 模板
    var cartPanelContent = `
        <style>
            #cartHot .handsontable .htCore input[type="checkbox"] {
                width: 20px;
                height: 20px;
                cursor: pointer;
                vertical-align: middle;
            }
            #cartHot .handsontable .htCore tbody tr {
                height: 48px !important;
                max-height: 48px !important;
            }
            #cartHot .handsontable .htCore td {
                height: 48px !important;
                max-height: 48px !important;
                overflow: hidden !important;
                vertical-align: middle !important;
            }
            #cartHot .supplier-cell {
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                display: block;
                max-width: 100%;
            }
            #cartHot .sales-cell-content {
                display: -webkit-box;
                -webkit-line-clamp: 2;
                -webkit-box-orient: vertical;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: normal;
                line-height: 1.3;
                max-height: 2.6em;
            }
        </style>
        <div id="cartPanelMain" style="padding:15px; height: calc(100vh - 120px); display: flex; flex-direction: column; overflow: hidden;">
            <div style="margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center; flex-shrink: 0;">
                <div>
                    <button class="layui-btn layui-btn-sm layui-btn-normal" id="productDimensionBtn">产品维度</button>
                    <button class="layui-btn layui-btn-sm layui-btn-primary" id="supplierDimensionBtn">供应商维度</button>
                </div>
                <div class="layui-btn-group toolbar" style="display: flex; align-items: center; flex-wrap: wrap; gap: 8px;">
                    <button class="layui-btn layui-btn-sm btn-secondary" id="importCartBtn">
                        <i class="layui-icon layui-icon-add-1"></i>
                        <span>导入产品</span>
                    </button>
                    <button class="layui-btn layui-btn-sm btn-secondary" id="selectAllBtn">
                        <i class="layui-icon layui-icon-ok-circle"></i>
                        <span>全选本页</span>
                    </button>
                    <button class="layui-btn layui-btn-sm btn-secondary" id="deleteSelectedBtn">
                        <i class="layui-icon layui-icon-delete"></i>
                        <span>删除选中</span>
                    </button>
                    <button class="layui-btn layui-btn-sm btn-secondary" id="clearCartBtn">
                        <i class="layui-icon layui-icon-fonts-clear"></i>
                        <span>清空购物车</span>
                    </button>
                    <button class="layui-btn layui-btn-sm btn-secondary" id="exportCartBtn">
                        <i class="layui-icon layui-icon-export"></i>
                        <span>导出数据</span>
                    </button>
                </div>
            </div>
            <div id="cartFilterButtons" style="margin-bottom: 15px; flex-shrink: 0; display: flex; flex-wrap: wrap; gap: 10px; align-items: center;"></div>
            <!-- 隐藏的输入框用于存储搜索值 -->
            <input type="hidden" id="cartSearchOe">
            <input type="hidden" id="cartSearchBarcode">
            <input type="hidden" id="cartSearchMaterialName">
            <input type="hidden" id="cartSearchBrand">
            <input type="hidden" id="cartSearchCarBrand">
            <input type="hidden" id="cartSearchTag">
            <input type="hidden" id="cartSearchCarModel">
            <div id="cartTableContainer" style="flex: 1; min-height: 0; overflow: hidden; height: auto;">
                <div id="cartHot" style="width: 100%; height: 100%;"></div>
            </div>
            <div id="cartPaginationBar" style="flex-shrink: 0;"></div>
        </div>
    `;

    /**
     * 读取隐藏搜索框的值
     */
    function getSearchParams() {
        var params = {};
        var oe = document.getElementById('cartSearchOe');
        var barcode = document.getElementById('cartSearchBarcode');
        var materialName = document.getElementById('cartSearchMaterialName');
        var brand = document.getElementById('cartSearchBrand');
        var carBrand = document.getElementById('cartSearchCarBrand');
        var tag = document.getElementById('cartSearchTag');
        var carModel = document.getElementById('cartSearchCarModel');

        if (oe && oe.value) params.cart_oe = oe.value;
        if (barcode && barcode.value) params.cart_barcode = barcode.value;
        if (materialName && materialName.value) params.cart_material_name = materialName.value;
        if (brand && brand.value) params.cart_brand = brand.value;
        if (carBrand && carBrand.value) params.cart_car_brand = carBrand.value;
        if (tag && tag.value) params.cart_tag = tag.value;
        if (carModel && carModel.value) params.cart_car_model = carModel.value;

        return params;
    }

    /**
     * 读取 FilterPanel 和表头下拉菜单筛选条件
     */
    function getFilterParams() {
        var params = {};

        // FilterPanel 按钮筛选
        if (typeof FilterPanel !== 'undefined' && typeof FilterPanel.getActiveFilters === 'function') {
            var activeFilters = FilterPanel.getActiveFilters();
            if (activeFilters.brand && activeFilters.brand.length > 0) {
                params.filter_brand = activeFilters.brand.join(',');
            }
            if (activeFilters.car_brand && activeFilters.car_brand.length > 0) {
                params.filter_car_brand = activeFilters.car_brand.join(',');
            }
            if (activeFilters.tag && activeFilters.tag.length > 0) {
                params.filter_tag = activeFilters.tag.join(',');
            }
        }

        // 表头下拉菜单筛选（优先级高于 FilterPanel）
        for (var field in activeColumnFilters) {
            if (activeColumnFilters[field] && activeColumnFilters[field].length > 0) {
                params['filter_' + field] = activeColumnFilters[field].join(',');
            }
        }

        return params;
    }

    /**
     * 切换当前页所有行的选中状态
     */
    function toggleSelectAll(checked) {
        var currentHot = getCurrentHot();
        if (!currentHot) return;

        var count = currentHot.countRows();
        var changes = [];
        for (var i = 0; i < count; i++) {
            changes.push([i, 0, checked]);
        }
        currentHot.setDataAtCell(changes);
    }

    /**
     * 构建 HandsontableBuilder 配置
     * @param {string} dimension - 当前维度
     */
    function buildBuilderConfig(dimension) {
        var isProduct = dimension === 'product';
        var columns = isProduct ? CartColumns.getProductColumns() : CartColumns.getSupplierColumns();
        var fixedLeft = isProduct ? CartColumns.fixedColumnsLeft.product : CartColumns.fixedColumnsLeft.supplier;

        return {
            containerSelector: '#cartHot',
            dataUrl: '/api/cart',
            gridKey: 'cart_grid',
            pageKey: 'cart',
            rowHeight: 48,
            dataTransform: function(data) {
                // 初始化复选状态，确保 Handsontable checkbox 列能正确读写
                if (Array.isArray(data)) {
                    data.forEach(function(item) {
                        item._selected = false;

                        // 合成销量字段，供复制、筛选、排序使用
                        if (item.sales_data === undefined || item.sales_data === null) {
                            var today = item.today_sales || 0;
                            var yesterday = item.sales_yesterday || 0;
                            var sales7d = item.sales_7d || 0;
                            var salesMonth = item.sales_month || 0;
                            var sales6m = item.avg_sales_6m || 0;
                            var sales12m = item.avg_sales_12m || 0;
                            item.sales_data = '今/昨/近7天: ' + today + '/' + yesterday + '/' + sales7d + '\n' +
                                '近1/6/12月: ' + salesMonth + '/' + sales6m + '/' + sales12m;
                        }
                    });
                }
                return data;
            },
            paramsBuilder: function() {
                var params = { dimension: currentDimension };
                var searchParams = getSearchParams();
                var filterParams = getFilterParams();

                for (var key in searchParams) {
                    params[key] = searchParams[key];
                }
                for (var key in filterParams) {
                    params[key] = filterParams[key];
                }

                return params;
            },
            beforeLoad: function(params) {
                // 把排序参数改名为后端需要的 field/order
                if (params.sort_column) {
                    params.field = params.sort_column;
                    delete params.sort_column;
                }
                if (params.sort_dir) {
                    params.order = params.sort_dir;
                    delete params.sort_dir;
                }

                return params;
            },
            columns: columns,
            components: {
                pagination: {
                    container: '#cartPaginationBar',
                    pageSizeOptions: [50, 75, 100, 200],
                    defaultPageSize: 50
                },
                columnMenu: {
                    persist: true
                },
                doubleClickCopy: false,
                contextMenu: false,
                shortcuts: true,
                virtualScroll: true
            },
            handsontableOptions: {
                fixedColumnsLeft: fixedLeft,
                fixedColumnsRight: 1,
                rowHeaders: true,
                height: '100%',
                stretchH: 'none',
                rowHeight: 48,
                headerHeight: 36,
                afterChange: function(changes, source) {
                    if (!changes || source === 'loadData') return;

                    for (var i = 0; i < changes.length; i++) {
                        var change = changes[i];
                        var row = change[0];
                        var prop = change[1];
                        var newValue = change[3];

                        if (prop === 'quantity') {
                            var rowData = this.getSourceDataAtRow(row);
                            if (rowData && typeof CartEdit !== 'undefined' && typeof CartEdit.updateQuantityByData === 'function') {
                                CartEdit.updateQuantityByData(rowData, newValue);
                            }
                        }
                    }
                },
            },
            afterLoad: function(result) {
                // 更新筛选面板数据
                var list = [];
                if (result.data && Array.isArray(result.data.list)) {
                    list = result.data.list;
                } else if (Array.isArray(result.data)) {
                    list = result.data;
                }

                if (typeof FilterPanel !== 'undefined' && typeof FilterPanel.updateData === 'function') {
                    FilterPanel.updateData(list);
                }

                // 导入后若后端返回清理结果，给出提示
                if (result.cleanup_result && result.cleanup_result.deleted_count > 0) {
                    layui.layer.msg('库存大于20的商品已自动删除 ' + result.cleanup_result.deleted_count + ' 个', {
                        icon: 1,
                        time: 3000
                    });
                }
            },
            onDataRefresh: function(filterState) {
                // 保存表头下拉菜单筛选条件，确保翻页/排序后仍然生效
                activeColumnFilters = filterState.filters || {};

                // 清除 HandsontableBuilder 内部 filter 状态，避免生成冗余的 filter_column/filter_values 参数
                if (builder) {
                    builder.filterColumn = null;
                    builder.filterValues = null;
                }
            },
            onColumnVisibilityChange: function(visibleColumns) {
                // 列显隐变化时，重新计算固定列数量
                var fixedLeftCount = 0;
                var fixedRightCount = 0;
                for (var i = 0; i < visibleColumns.length; i++) {
                    if (visibleColumns[i].originallyFixed === 'left') {
                        fixedLeftCount++;
                    } else if (visibleColumns[i].originallyFixed === 'right') {
                        fixedRightCount++;
                    }
                }

                var currentHot = getCurrentHot();
                if (currentHot) {
                    currentHot.updateSettings({
                        fixedColumnsLeft: fixedLeftCount,
                        fixedColumnsRight: fixedRightCount
                    });
                }
            },
            getFilterValues: function(colId, callback) {
                // 从后端获取该列全部去重值，和汽配龙页面保持一致
                var params = {
                    dimension: currentDimension,
                    column: colId
                };

                // 带上当前搜索条件，让筛选值受其他条件约束
                var searchParams = getSearchParams();
                for (var key in searchParams) {
                    params[key] = searchParams[key];
                }

                // 带上当前已生效的其他列筛选条件
                var filterParams = getFilterParams();
                for (var key in filterParams) {
                    if (key !== 'filter_' + colId) {
                        params[key] = filterParams[key];
                    }
                }

                var queryParts = [];
                for (var key in params) {
                    if (params[key] !== undefined && params[key] !== null && params[key] !== '') {
                        queryParts.push(encodeURIComponent(key) + '=' + encodeURIComponent(params[key]));
                    }
                }

                fetch('/api/cart/filter_values?' + queryParts.join('&'), {
                    method: 'GET',
                    credentials: 'same-origin'
                })
                .then(function(response) { return response.json(); })
                .then(function(result) {
                    if (result.code !== 0) {
                        callback([]);
                        return;
                    }
                    var values = (result.data || [])
                        .map(function(v) {
                            return { value: String(v), count: 0 };
                        })
                        .sort(function(a, b) {
                            return a.value.localeCompare(b.value);
                        });
                    callback(values);
                })
                .catch(function(error) {
                    console.error('[CartPanel] 加载筛选值失败:', colId, error);
                    callback([]);
                });
            }
        };
    }

    /**
     * 解析供应商数据（优先JSON格式，兼容旧字符串格式）
     */
    function parseSupplierString(supplierText, jsonRecords) {
        // 优先解析 purchase_records JSON
        if (jsonRecords) {
            try {
                var records = JSON.parse(jsonRecords);
                if (Array.isArray(records) && records.length > 0) {
                    return records.map(function(r) {
                        return {
                            name: r.supplier_name || '',
                            price: r.purchase_price !== undefined ? String(r.purchase_price) : '',
                            date: r.purchase_date || ''
                        };
                    });
                }
            } catch (e) {
                // JSON 解析失败，回退到字符串解析
            }
        }
        // 回退：解析旧格式字符串 "供应商A：123.00"
        if (!supplierText) return [];
        var suppliers = [];
        var regex = /(.+?)：(\d+\.?\d*)/g;
        var match;
        while ((match = regex.exec(supplierText)) !== null) {
            var name = match[1].trim();
            var price = match[2].trim();
            if (name) {
                suppliers.push({ name: name, price: price, date: '' });
            }
        }
        return suppliers;
    }

    /**
     * 确保全局供应商 tooltip 元素存在
     */
    function ensureSupplierTooltipLayer() {
        var layer = document.getElementById('cartSupplierTooltip');
        if (!layer) {
            layer = document.createElement('div');
            layer.id = 'cartSupplierTooltip';
            layer.style.cssText = 'position: fixed; display: none; background: #fff; border: 1px solid #e6e6e6; ' +
                'border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); max-width: 400px; ' +
                'min-width: 250px; font-size: 12px; z-index: 99999999; padding: 0;';
            document.body.appendChild(layer);
        }
        return layer;
    }

    /**
     * 显示供应商悬浮窗（全局唯一元素，支持JSON格式展示日期+供应商+单价）
     */
    function showSupplierTooltip(cell) {
        var layer = ensureSupplierTooltipLayer();
        var supplierText = (cell.getAttribute('data-suppliers') || cell.innerText || '').trim();
        var jsonRecords = cell.getAttribute('data-purchase-records') || '';
        var suppliers = parseSupplierString(supplierText, jsonRecords);

        var hasDate = suppliers.some(function(s) { return s.date; });
        var tooltipContent = '';
        if (suppliers.length > 0) {
            suppliers.forEach(function(supplier) {
                if (hasDate) {
                    tooltipContent += '<div class="supplier-tooltip-row" style="display: flex; justify-content: space-between; ' +
                        'padding: 8px 16px; border-bottom: 1px solid #f6f6f6;">' +
                        '<span style="flex: 1; padding-right: 8px; color: #333;">' + (supplier.date || '-') + '</span>' +
                        '<span style="flex: 2; padding-right: 16px; color: #333;">' + supplier.name + '</span>' +
                        '<span style="color: #666; white-space: nowrap;">' + supplier.price + '</span>' +
                        '</div>';
                } else {
                    tooltipContent += '<div class="supplier-tooltip-row" style="display: flex; justify-content: space-between; ' +
                        'padding: 8px 16px; border-bottom: 1px solid #f6f6f6;">' +
                        '<span class="supplier-name" style="flex: 1; padding-right: 16px; color: #333;">' + supplier.name + '</span>' +
                        '<span class="supplier-price" style="color: #666; white-space: nowrap;">' + supplier.price + '</span>' +
                        '</div>';
                }
            });
        } else if (supplierText) {
            tooltipContent = '<div class="supplier-tooltip-row" style="display: flex; justify-content: space-between; ' +
                'padding: 8px 16px; border-bottom: 1px solid #f6f6f6;">' +
                '<span class="supplier-name" style="flex: 1; padding-right: 16px; color: #333;">' + supplierText + '</span>' +
                '<span class="supplier-price" style="color: #666; white-space: nowrap;">-</span>' +
                '</div>';
        } else {
            tooltipContent = '<div class="supplier-tooltip-row" style="padding: 8px 16px; color: #999;">暂无供应商信息</div>';
        }

        var headerText = hasDate ? '日期 - 供应商 - 单价' : '供应商 - 单价';
        layer.innerHTML = '<div class="supplier-tooltip-header" style="padding: 12px 16px; background: #f8f9fa; ' +
            'border-bottom: 1px solid #e6e6e6; border-radius: 8px 8px 0 0; font-weight: 500; color: #333; font-size: 14px;">' +
            headerText + '</div>' +
            '<div class="supplier-tooltip-content" style="max-height: 300px; overflow-y: auto;">' + tooltipContent + '</div>';

        var cellRect = cell.getBoundingClientRect();
        var viewportHeight = window.innerHeight;
        var viewportWidth = window.innerWidth;

        layer.style.display = 'block';
        var contentWidth = Math.min(layer.offsetWidth, 400);
        var contentHeight = Math.min(layer.offsetHeight, 300);

        var top = cellRect.top - contentHeight - 5;
        var left = cellRect.left;

        if (left + contentWidth > viewportWidth) {
            left = Math.max(10, viewportWidth - contentWidth - 10);
        }
        if (top < 0 && cellRect.bottom + contentHeight + 5 < viewportHeight) {
            top = cellRect.bottom + 5;
        }

        layer.style.top = top + 'px';
        layer.style.left = left + 'px';
    }

    /**
     * 隐藏供应商悬浮窗
     */
    function hideSupplierTooltip() {
        var layer = document.getElementById('cartSupplierTooltip');
        if (layer) {
            layer.style.display = 'none';
        }
    }

    /**
     * 绑定供应商悬浮窗事件（事件委托，全局唯一 tooltip）
     */
    var supplierTooltipBound = false;
    function bindSupplierTooltipEvents() {
        var container = document.getElementById('cartHot');
        if (!container || supplierTooltipBound) return;
        supplierTooltipBound = true;

        container.addEventListener('mouseenter', function(e) {
            var cell = e.target.closest ? e.target.closest('.supplier-cell') : null;
            if (cell) {
                showSupplierTooltip(cell);
            }
        }, true);

        container.addEventListener('mouseleave', function(e) {
            var cell = e.target.closest ? e.target.closest('.supplier-cell') : null;
            if (cell) {
                hideSupplierTooltip();
            }
        }, true);

        // 滚动时隐藏悬浮窗
        var scrollContainer = container.querySelector('.ht_master .wtHolder');
        if (scrollContainer) {
            scrollContainer.addEventListener('scroll', hideSupplierTooltip, { passive: true });
        }

        // 鼠标离开购物车容器时隐藏
        container.addEventListener('mouseleave', hideSupplierTooltip);
    }

    /**
     * 初始化 HandsontableBuilder
     */
    function initBuilder(dimension) {
        if (builder && typeof builder.destroy === 'function') {
            builder.destroy();
        }

        builder = HandsontableBuilder.create('#cartHot', buildBuilderConfig(dimension));
        if (builder) {
            hot = builder.hot;
            window.cartTableInstance = hot;
            bindDoubleClickCopy();
            bindRemoveButtonEvents();
            bindSupplierTooltipEvents();
        }
    }

    /**
     * 获取当前 Handsontable 实例（每次从 builder 取最新，避免 refresh 后实例失效）
     */
    function getCurrentHot() {
        return builder ? builder.hot : null;
    }

    /**
     * 绑定双击复制事件委托
     */
    var doubleClickCopyBound = false;
    function bindDoubleClickCopy() {
        var container = document.getElementById('cartHot');
        if (!container || doubleClickCopyBound) return;
        doubleClickCopyBound = true;

        container.addEventListener('dblclick', function(e) {
            var td = e.target.closest ? e.target.closest('td') : null;
            if (!td) return;

            var currentHot = getCurrentHot();
            if (!currentHot) return;

            var coords = currentHot.getCoords(td);
            if (!coords || coords.row < 0 || coords.col < 0) return;

            var value = currentHot.getDataAtCell(coords.row, coords.col);
            if (value !== undefined && value !== null && value !== '') {
                copyTextToClipboard(String(value), function() {
                    layui.layer.msg('已复制到剪贴板', { icon: 1, time: 1000 });
                }, function() {
                    layui.layer.msg('复制失败', { icon: 2 });
                });
            }
        });
    }

    /**
     * 绑定移除按钮事件委托
     */
    function bindRemoveButtonEvents() {
        var container = document.getElementById('cartHot');
        if (!container) return;

        // 避免重复绑定导致一次点击触发多次删除
        if (container._cartRemoveClickHandler) {
            container.removeEventListener('click', container._cartRemoveClickHandler);
        }

        container._cartRemoveClickHandler = function(e) {
            // 处理点击到按钮内文本节点的情况
            var target = e.target;
            if (target && target.nodeType === 3 && target.parentNode) {
                target = target.parentNode;
            }
            var btn = target.closest ? target.closest('.cart-remove-btn') : null;
            if (!btn) return;

            var row = parseInt(btn.getAttribute('data-row'), 10);
            var currentHot = getCurrentHot();
            if (isNaN(row) || !currentHot) return;

            var rowData = currentHot.getSourceDataAtRow(row);
            if (rowData) {
                CartActions.removeFromCart(rowData.oe, rowData.barcode);
            }
        };

        container.addEventListener('click', container._cartRemoveClickHandler);
    }

    /**
     * 打开购物车面板
     * @param {object} table 表格对象（保留参数兼容性，未使用）
     */
    function open(table) {
        layui.use(['layer'], function() {
            var layer = layui.layer;

            layer.open({
                type: 1,
                title: '购物车',
                content: cartPanelContent,
                area: ['95%', '95%'],
                maxmin: true,
                end: function() {
                    // 弹窗关闭时销毁 builder
                    if (builder && typeof builder.destroy === 'function') {
                        builder.destroy();
                        builder = null;
                        hot = null;
                    }
                    if (window.cartTableInstance) {
                        delete window.cartTableInstance;
                    }
                    doubleClickCopyBound = false;
                    supplierTooltipBound = false;
                    activeColumnFilters = {};
                },
                success: function(layeroInstance, index) {
                    layero = layeroInstance;
                    window.currentCartLayero = layero;

                    // 初始化搜索和筛选按钮
                    CartFilters.initCartFilterButtons();

                    // 初始化维度
                    currentDimension = 'product';
                    window.currentCartDimension = currentDimension;
                    updateDimensionButtonState();

                    // 初始化 Handsontable（内部已绑定移除按钮事件委托）
                    initBuilder(currentDimension);

                    // 绑定删除选中按钮
                    layero.find('#deleteSelectedBtn').on('click', function() {
                        var currentHot = getCurrentHot();
                        if (!currentHot) return;

                        var sourceData = currentHot.getSourceData();
                        var selectedData = [];
                        for (var i = 0; i < sourceData.length; i++) {
                            if (sourceData[i]._selected) {
                                selectedData.push({
                                    item_oe: sourceData[i].oe,
                                    item_barcode: sourceData[i].barcode || ''
                                });
                            }
                        }

                        if (selectedData.length === 0) {
                            layui.layer.msg('请先选择要删除的商品', { icon: 2 });
                            return;
                        }

                        layui.layer.confirm('确定要删除选中的 ' + selectedData.length + ' 个商品吗？', {
                            btn: ['确定', '取消']
                        }, function(index) {
                            CartManager.removeMultiple(selectedData);
                            layui.layer.close(index);
                        });
                    });

                // 绑定全选本页按钮
                layero.find('#selectAllBtn').on('click', function() {
                    var currentHot = getCurrentHot();
                    if (!currentHot) return;

                    var sourceData = currentHot.getSourceData();
                    var allSelected = true;
                    for (var i = 0; i < sourceData.length; i++) {
                        if (!sourceData[i]._selected) {
                            allSelected = false;
                            break;
                        }
                    }

                    toggleSelectAll(!allSelected);
                    layui.layer.msg(allSelected ? '已取消全选' : '已全选本页', { icon: 1, time: 800 });
                });

                // 绑定维度切换按钮
                    layero.find('#productDimensionBtn').on('click', function() {
                        if (currentDimension === 'product') return;
                        currentDimension = 'product';
                        window.currentCartDimension = currentDimension;
                        updateDimensionButtonState();
                        initBuilder(currentDimension);
                        layui.layer.msg('切换到产品维度', { icon: 1 });
                    });

                    layero.find('#supplierDimensionBtn').on('click', function() {
                        if (currentDimension === 'supplier') return;
                        currentDimension = 'supplier';
                        window.currentCartDimension = currentDimension;
                        updateDimensionButtonState();
                        initBuilder(currentDimension);
                        layui.layer.msg('切换到供应商维度', { icon: 1 });
                    });

                    // 绑定导入产品按钮
                    layero.find('#importCartBtn').on('click', function() {
                        CartActions.importCartData();
                    });

                    // 绑定清空购物车按钮
                    layero.find('#clearCartBtn').on('click', function() {
                        CartActions.clearCart();
                    });

                    // 绑定导出数据按钮
                    layero.find('#exportCartBtn').on('click', function() {
                        CartActions.exportCartData();
                    });

                    // 绑定表格顶部按钮事件
                    layero.find('#cartTableTopBtn').on('click', function() {
                        if (builder && builder.hot && typeof builder.hot.scrollViewportTo === 'function') {
                            builder.hot.scrollViewportTo(0, 0);
                            layui.layer.msg('已滚动到表格顶部', { icon: 1 });
                        } else {
                            layui.layer.msg('未找到表格滚动容器', { icon: 2 });
                        }
                    });
                }
            });
        });
    }

    /**
     * 更新维度按钮样式
     */
    function updateDimensionButtonState() {
        if (!layero) return;
        var productBtn = layero.find('#productDimensionBtn');
        var supplierBtn = layero.find('#supplierDimensionBtn');

        if (currentDimension === 'product') {
            productBtn.removeClass('layui-btn-primary').addClass('layui-btn-normal');
            supplierBtn.removeClass('layui-btn-normal').addClass('layui-btn-primary');
        } else {
            supplierBtn.removeClass('layui-btn-primary').addClass('layui-btn-normal');
            productBtn.removeClass('layui-btn-normal').addClass('layui-btn-primary');
        }
    }

    /**
     * 刷新购物车表格
     * @param {string|number} dimension 维度或页码
     */
    function refresh(dimension) {
        if (typeof dimension === 'string' && (dimension === 'product' || dimension === 'supplier')) {
            currentDimension = dimension;
            window.currentCartDimension = currentDimension;
            updateDimensionButtonState();
            initBuilder(currentDimension);
        } else if (builder && typeof builder.refresh === 'function') {
            if (typeof dimension === 'number') {
                builder.refresh(dimension);
            } else {
                // 不传参数时保持当前页
                builder.refresh();
            }
        }
    }

    /**
     * 获取 HandsontableBuilder 实例
     * @returns {object|null}
     */
    function getBuilder() {
        return builder;
    }

    /**
     * 获取 Handsontable 实例
     * @returns {object|null}
     */
    function getHot() {
        return getCurrentHot();
    }

    /**
     * 获取当前维度
     * @returns {string}
     */
    function getCurrentDimension() {
        return currentDimension;
    }

    /**
     * 获取当前弹层 layero
     * @returns {object|null}
     */
    function getLayero() {
        return layero;
    }

    return {
        open: open,
        getBuilder: getBuilder,
        getHot: getHot,
        getCurrentDimension: getCurrentDimension,
        getLayero: getLayero,
        refresh: refresh
    };
})();
