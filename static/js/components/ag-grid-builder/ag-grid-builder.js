/**
 * AgGridBuilder
 * 配置化 AG Grid 初始化构建器
 *
 * 作用：将 new agGrid.Grid、GridColumnMenu、ColumnPreference、CustomPagination、
 *      AgGridLoader、拖拽选择、双击复制、快捷键等组件的手动接线收敛到一个配置对象中。
 *
 * 依赖（页面需提前引入）：
 *   - ag-grid 库
 *   - /static/js/components/grid-column-menu/grid-column-menu.js
 *   - /static/js/components/column-preference/column-preference.js
 *   - /static/js/components/custom-pagination/custom-pagination.js
 *   - /static/js/components/ag-grid-loader/ag-grid-loader.js
 *   - /static/ag-grid/ag-grid-utils.js
 *
 * 使用示例：
 *   var builder = AgGridBuilder.create('#myGrid', {
 *       columnDefs: columnDefs,
 *       rowData: [],
 *       components: {
 *           columnMenu: true,                                 // 启用表头列菜单
 *           columnPreference: { pageKey: 'page1', gridKey: 'main' }, // 启用列状态持久化
 *           pagination: true,                                 // 启用自定义分页
 *           loader: true,                                     // 启用 AgGridLoader
 *           dragSelection: true,                              // 启用拖拽选择
 *           doubleClickCopy: true,                            // 启用双击复制
 *           shortcuts: true                                   // 启用快捷键
 *       },
 *       onSort: function(colId, sortDir) { ... },
 *       onFilter: function(filterState) { ... },
 *       onPageChange: function(page, pageSize) { ... },
 *       onGridReady: function(api, columnApi, builder) { ... }
 *   });
 *
 *   // 加载数据
 *   builder.loader.load('/api/data', { page: 1 }, function(result) {
 *       builder.api.setRowData(result.list);
 *       builder.pagination.update(result.total, 1, result.pageSize);
 *   });
 */

var AgGridBuilder = (function() {
    'use strict';

    /**
     * 合并对象（浅合并）
     */
    function assign(target) {
        for (var i = 1; i < arguments.length; i++) {
            var source = arguments[i];
            if (!source) continue;
            for (var key in source) {
                if (source.hasOwnProperty(key)) {
                    target[key] = source[key];
                }
            }
        }
        return target;
    }

    /**
     * 判断某个组件开关是否启用
     * @param {Object} components - components 配置
     * @param {string} key - 组件 key
     */
    function isEnabled(components, key) {
        if (!components) return false;
        var val = components[key];
        return val === true || (typeof val === 'object' && val !== null);
    }

    /**
     * 获取组件配置对象
     */
    function getComponentConfig(components, key) {
        if (!components) return null;
        var val = components[key];
        if (val === true) return {};
        if (typeof val === 'object' && val !== null) return val;
        return null;
    }

    /**
     * 创建 AG Grid 并自动接线组件
     * @param {string} selector - 网格容器 CSS 选择器
     * @param {Object} config - 构建配置
     * @returns {Object|null} builder 实例
     */
    function create(selector, config) {
        config = config || {};

        var gridDiv = document.querySelector(selector);
        if (!gridDiv) {
            console.error('[AgGridBuilder] 找不到网格容器:', selector);
            return null;
        }

        var userGridOptions = config.gridOptions || {};
        var gridOptions = assign({}, userGridOptions);

        // 列定义与数据
        gridOptions.columnDefs = config.columnDefs || userGridOptions.columnDefs || [];
        gridOptions.rowData = config.rowData !== undefined ? config.rowData : (userGridOptions.rowData || []);

        // 默认列定义：关闭原生排序和菜单，统一由 GridColumnMenu 接管
        var needsColumnMenu = isEnabled(config.components, 'columnMenu') ||
                              isEnabled(config.components, 'columnPreference');
        var defaultColDef = assign({
            sortable: !needsColumnMenu,
            filter: true,
            resizable: true,
            suppressMenu: needsColumnMenu
        }, userGridOptions.defaultColDef || {}, config.defaultColDef || {});

        if (needsColumnMenu) {
            defaultColDef.sortable = false;
            defaultColDef.suppressMenu = true;
        }
        gridOptions.defaultColDef = defaultColDef;

        // 布局
        if (config.rowHeight !== undefined) gridOptions.rowHeight = config.rowHeight;
        if (config.headerHeight !== undefined) gridOptions.headerHeight = config.headerHeight;
        if (config.pagination !== undefined) gridOptions.pagination = config.pagination;

        var builder = {
            selector: selector,
            config: config,
            gridOptions: gridOptions,
            api: null,
            columnApi: null,
            loader: null,
            pagination: null,
            columnMenu: null,
            destroyed: false
        };

        var userOnGridReady = gridOptions.onGridReady;
        var configOnGridReady = config.onGridReady;

        gridOptions.onGridReady = function(event) {
            builder.api = event.api;
            builder.columnApi = event.columnApi;

            wireComponents(builder);

            if (typeof userOnGridReady === 'function') {
                userOnGridReady(event, builder);
            }
            if (typeof configOnGridReady === 'function') {
                configOnGridReady(event.api, event.columnApi, builder);
            }
        };

        // 创建网格
        new agGrid.Grid(gridDiv, gridOptions);

        // 兼容旧版 AG Grid：api 可能直接挂在 gridOptions 上
        if (!builder.api && gridOptions.api) {
            builder.api = gridOptions.api;
            builder.columnApi = gridOptions.columnApi;
            wireComponents(builder);
        }

        return builder;
    }

    /**
     * 根据配置自动接线各组件
     */
    function wireComponents(builder) {
        if (builder.destroyed) return;

        var config = builder.config;
        var components = config.components || {};
        var api = builder.api;
        var columnApi = builder.columnApi;
        var selector = builder.selector;

        if (!api) {
            console.warn('[AgGridBuilder] 网格 API 尚未就绪，跳过组件接线');
            return;
        }

        // 1. AgGridLoader
        if (isEnabled(components, 'loader') && typeof AgGridLoader !== 'undefined') {
            builder.loader = new AgGridLoader(api);
        }

        // 2. GridColumnMenu + ColumnPreference
        var cmConfig = getComponentConfig(components, 'columnMenu');
        var cpConfig = getComponentConfig(components, 'columnPreference');
        if (cmConfig || cpConfig || isEnabled(components, 'columnMenu') || isEnabled(components, 'columnPreference')) {
            if (typeof GridColumnMenu === 'undefined') {
                console.warn('[AgGridBuilder] GridColumnMenu 未加载，列菜单功能不可用');
            } else {
                var menuOptions = assign({
                    columnApi: columnApi,
                    gridOptions: builder.gridOptions
                }, cmConfig || {}, cpConfig || {});

                // 只要配置了 columnPreference，默认开启持久化
                if (cpConfig) {
                    menuOptions.persist = true;
                }

                // 优先使用 builder 级别的回调
                if (typeof config.onSort === 'function') {
                    menuOptions.onSort = config.onSort;
                }
                if (typeof config.onDataRefresh === 'function') {
                    menuOptions.onDataRefresh = config.onDataRefresh;
                } else if (typeof config.onFilter === 'function') {
                    menuOptions.onDataRefresh = config.onFilter;
                }
                if (typeof config.getFilterValues === 'function') {
                    menuOptions.getFilterValues = config.getFilterValues;
                }
                if (typeof config.onColumnVisibilityChange === 'function') {
                    menuOptions.onColumnVisibilityChange = config.onColumnVisibilityChange;
                }

                GridColumnMenu.init(api, selector, config.columnDefs || [], menuOptions);
                builder.columnMenu = GridColumnMenu;
            }
        }

        // 3. CustomPagination
        if (isEnabled(components, 'pagination')) {
            if (typeof CustomPagination === 'undefined') {
                console.warn('[AgGridBuilder] CustomPagination 未加载，分页功能不可用');
            } else {
                var pgConfig = getComponentConfig(components, 'pagination') || {};
                var pgOptions = assign({
                    gridSelector: selector,
                    onPageChange: config.onPageChange,
                    onPageSizeChange: config.onPageSizeChange
                }, pgConfig);
                builder.pagination = CustomPagination.init(pgOptions);
            }
        }

        // 4. 工具函数：拖拽选择、双击复制、快捷键
        if (isEnabled(components, 'dragSelection') && typeof initDragSelection === 'function') {
            initDragSelection(api, columnApi);
        }
        if (isEnabled(components, 'doubleClickCopy') && typeof initDoubleClickCopy === 'function') {
            initDoubleClickCopy(api, columnApi);
        }
        if (isEnabled(components, 'shortcuts') && typeof initShortcuts === 'function') {
            initShortcuts(api, config.copyCallback);
        }

        // 5. 自适应列宽（可选）
        if (components.sizeColumnsToFit !== false && typeof api.sizeColumnsToFit === 'function') {
            try {
                api.sizeColumnsToFit();
            } catch (e) {}
        }
    }

    /**
     * 销毁 builder 及其创建的组件
     */
    function destroy(builder) {
        if (!builder || builder.destroyed) return;

        if (builder.pagination && typeof builder.pagination.destroy === 'function') {
            builder.pagination.destroy();
            builder.pagination = null;
        }

        if (builder.api && typeof builder.api.destroy === 'function') {
            try {
                builder.api.destroy();
            } catch (e) {}
        }

        builder.loader = null;
        builder.columnMenu = null;
        builder.api = null;
        builder.columnApi = null;
        builder.destroyed = true;
    }

    // 公共 API
    return {
        create: create,
        destroy: destroy
    };
})();
