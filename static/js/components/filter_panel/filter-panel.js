/**
 * Filter Panel Component
 * 筛选面板组件（包含搜索面板和筛选面板）
 *
 * Usage:
 * // 初始化筛选面板
 * FilterPanel.init({
 *     container: '#filterContainer',
 *     fields: ['品牌', '车型品牌', '标签'],
 *     data: currentData,
 *     onApply: function(filters) {
 *         console.log('Applied filters:', filters);
 *     }
 * });
 *
 * // 初始化搜索面板
 * FilterPanel.initSearch({
 *     container: '#searchContainer',
 *     fields: [
 *         { label: 'OE号', inputId: 'advSearchOe', btnId: 'searchOeBtn' },
 *         { label: '物料条码', inputId: 'advSearchBarcode', btnId: 'searchBarcodeBtn' }
 *     ],
 *     onApply: function(field, value) {
 *         console.log('Search:', field, value);
 *     }
 * });
 */

var FilterPanel = (function() {
    'use strict';

    // 私有变量
    var filterConfig = {};
    var searchConfig = {};
    var activeFilters = {};
    var currentPanel = null;
    var currentMode = null; // 'filter' or 'search'
    var currentField = null;
    var currentInputId = null;

    // ==================== 筛选面板功能 ====================

    /**
     * 初始化筛选面板
     * @param {Object} options - 配置选项
     */
    function init(options) {
        filterConfig = Object.assign({
            container: null,
            fields: [],
            data: [],
            onApply: null,
            onClear: null
        }, options);

        // 渲染筛选按钮
        renderFilterButtons();
    }

    /**
     * 渲染筛选按钮
     */
    function renderFilterButtons() {
        var container = document.querySelector(filterConfig.container);
        if (!container) {
            console.error('FilterPanel: Filter container not found');
            return;
        }

        // 创建筛选按钮容器
        var filterContainer = document.createElement('div');
        filterContainer.className = 'filter-panel-buttons';
        filterConfig.fields.forEach(function(field, index) {
            // 支持两种格式：字符串 'brand' 或对象 { field: 'brand', label: '品牌' }
            var fieldName = typeof field === 'object' ? field.field : field;
            var fieldLabel = typeof field === 'object' ? field.label : field;
            var btnId = 'filterBtn_' + index + '_' + fieldName.replace(/\s+/g, '_');
            var btn = document.createElement('button');
            btn.className = 'filter-btn';
            btn.id = btnId;
            btn.setAttribute('data-field', fieldName);
            btn.textContent = fieldLabel;
            // 绑定点击事件
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                toggleFilter(fieldName, btn);
            });
            filterContainer.appendChild(btn);
        });
        container.appendChild(filterContainer);
    }

    /**
     * 切换筛选下拉面板
     * @param {string} field - 字段名
     * @param {HTMLElement} btnElement - 按钮元素
     */
    function toggleFilter(field, btnElement) {
        // 如果当前正在显示同一个筛选面板，则关闭它
        if (currentPanel && currentMode === 'filter' && currentField === field) {
            closeAll();
            return;
        }
        // 否则关闭当前面板（如果有），然后打开新的
        closeAll();
        createFilterPanel(field, btnElement);
    }

    /**
     * 创建筛选面板
     * @param {string} field - 字段名
     * @param {HTMLElement} btnElement - 按钮元素
     */
    function createFilterPanel(field, btnElement) {
        currentMode = 'filter';
        currentField = field;

        var panel = document.createElement('div');
        panel.className = 'filter-dropdown-panel show';
        panel.id = 'filter-panel-dropdown';
        panel.style.display = 'block'; // 强制显示

        var values = getUniqueValues(field);
        var currentFilter = activeFilters[field] || [];

        var listHtml = '';
        values.forEach(function(item) {
            var isChecked = currentFilter.includes(item.value) ? 'checked' : '';
            listHtml += '<div class="filter-dropdown-item" onclick="FilterPanel.toggleItemCheckbox(this)">' +
                '<input type="checkbox" value="' + item.value + '" ' + isChecked + ' onclick="event.stopPropagation()">' +
                '<label>' + item.value + ' <span class="count">(' + item.count + ')</span></label>' +
            '</div>';
        });

        panel.innerHTML =
            '<div class="filter-dropdown-header">' + field + '筛选</div>' +
            '<div class="filter-dropdown-search" style="padding: 8px 12px; box-sizing: border-box;">' +
                '<input type="text" placeholder="搜索..." oninput="FilterPanel.filterSearch(this)" style="width: 100%; padding: 5px 8px; border: 1px solid #d9d9d9; border-radius: 4px; font-size: 12px; box-sizing: border-box;">' +
            '</div>' +
            '<div class="filter-dropdown-list">' + listHtml + '</div>' +
            '<div class="filter-dropdown-footer">' +
                '<button onclick="FilterPanel.selectAll()">全选</button>' +
                '<button onclick="FilterPanel.invert()">反选</button>' +
                '<button class="btn-confirm" onclick="FilterPanel.applyFilter()">确定</button>' +
                '<button onclick="FilterPanel.cancel()">取消</button>' +
            '</div>';

        // 定位到按钮下方
        var rect = btnElement.getBoundingClientRect();
        panel.style.position = 'fixed';
        panel.style.left = rect.left + 'px';
        panel.style.top = (rect.bottom + 4) + 'px';
        panel.style.zIndex = '999999999';

        document.body.appendChild(panel);
        currentPanel = panel;

        // 高亮按钮
        btnElement.classList.add('active');
    }

    /**
     * 获取列的唯一值及数量
     * @param {string} field - 字段名
     * @returns {Array} - 包含value和count的数组
     */
    function getUniqueValues(field) {
        var valueCount = {};
        filterConfig.data.forEach(function(row) {
            if (row[field]) {
                var value = String(row[field]);
                valueCount[value] = (valueCount[value] || 0) + 1;
            }
        });

        // 转换为数组并按值排序
        return Object.entries(valueCount)
            .map(function(entry) {
                return { value: entry[0], count: entry[1] };
            })
            .sort(function(a, b) {
                return a.value.localeCompare(b.value);
            });
    }

    // ==================== 搜索面板功能 ====================

    /**
     * 初始化搜索面板
     * @param {Object} options - 配置选项
     */
    function initSearch(options) {
        searchConfig = Object.assign({
            container: null,
            fields: [], // [{ label: 'OE号', inputId: 'advSearchOe', btnId: 'searchOeBtn' }]
            onApply: null
        }, options);

        // 渲染搜索按钮
        renderSearchButtons();
    }

    /**
     * 渲染搜索按钮
     */
    function renderSearchButtons() {
        var container = document.querySelector(searchConfig.container);
        if (!container) {
            return;
        }

        // 为每个字段生成 btnId（如果没有提供）
        searchConfig.fields.forEach(function(field, index) {
            if (!field.btnId) {
                field.btnId = 'searchBtn_' + index + '_' + field.inputId.replace(/[^a-zA-Z0-9]/g, '_');
            }
        });

        // 创建搜索按钮容器
        var searchContainer = document.createElement('div');
        searchContainer.className = 'search-panel-buttons';
        searchConfig.fields.forEach(function(field) {
            var btn = document.createElement('button');
            btn.className = 'filter-btn';
            btn.id = field.btnId;
            btn.setAttribute('data-label', field.label);
            btn.setAttribute('data-input', field.inputId);
            btn.textContent = field.label;
            // 绑定点击事件
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                toggleSearch(field.label, field.inputId, btn);
            });
            searchContainer.appendChild(btn);
        });
        container.appendChild(searchContainer);

        // 初始化按钮状态
        refreshSearchButtonStates();
    }

    /**
     * 切换搜索下拉面板
     * @param {string} label - 标签名
     * @param {string} inputId - 输入框ID
     * @param {HTMLElement} btnElement - 按钮元素
     */
    function toggleSearch(label, inputId, btnElement) {
        // 如果当前正在显示同一个搜索面板，则关闭它
        if (currentPanel && currentMode === 'search' && currentField === label) {
            closeAll();
            return;
        }
        // 否则关闭当前面板（如果有），然后打开新的
        closeAll();
        createSearchPanel(label, inputId, btnElement);
    }

    /**
     * 创建搜索面板
     * @param {string} label - 标签名
     * @param {string} inputId - 输入框ID
     * @param {HTMLElement} btnElement - 按钮元素
     */
    function createSearchPanel(label, inputId, btnElement) {
        currentMode = 'search';
        currentField = label;
        currentInputId = inputId;

        var panel = document.createElement('div');
        panel.className = 'filter-dropdown-panel show';
        panel.id = 'search-panel-dropdown';
        panel.style.display = 'block';

        var input = document.getElementById(inputId);
        var currentValue = input ? input.value : '';

        panel.innerHTML =
            '<div class="filter-dropdown-header">' + label + '</div>' +
            '<div class="filter-dropdown-search" style="padding: 12px; box-sizing: border-box;">' +
                '<textarea id="searchPanelTextarea" placeholder="支持多行输入，每行一个" style="width: 100%; height: 120px; padding: 8px; border: 1px solid #d9d9d9; border-radius: 4px; font-size: 12px; resize: none; line-height: 1.4; box-sizing: border-box;">' + currentValue + '</textarea>' +
            '</div>' +
            '<div class="filter-dropdown-footer">' +
                '<button onclick="FilterPanel.clearSearch()">清空</button>' +
                '<button class="btn-confirm" onclick="FilterPanel.applySearch()">确定</button>' +
                '<button onclick="FilterPanel.cancel()">取消</button>' +
            '</div>';

        var rect = btnElement.getBoundingClientRect();
        panel.style.position = 'fixed';
        panel.style.left = rect.left + 'px';
        panel.style.top = (rect.bottom + 4) + 'px';
        panel.style.zIndex = '999999999'; // 确保面板在最上层（比LayUI弹窗的19891015更高）

        document.body.appendChild(panel);
        currentPanel = panel;
        
        // 打印层级调试信息
        // 高亮按钮
        btnElement.classList.add('active');
    }

    /**
     * 刷新所有搜索按钮状态
     */
    function refreshSearchButtonStates() {
        if (!searchConfig.fields) return;
        searchConfig.fields.forEach(function(field) {
            var input = document.getElementById(field.inputId);
            var btn = document.getElementById(field.btnId);
            if (input && btn) {
                if (input.value && input.value.trim()) {
                    btn.classList.add('active');
                } else {
                    btn.classList.remove('active');
                }
            }
        });
    }

    // ==================== 公共功能 ====================

    /**
     * 切换筛选项复选框
     * @param {HTMLElement} item - 选项元素
     */
    function toggleItemCheckbox(item) {
        var checkbox = item.querySelector('input');
        checkbox.checked = !checkbox.checked;
    }

    /**
     * 下拉框搜索
     * @param {HTMLInputElement} input - 搜索输入框
     */
    function filterSearch(input) {
        var keyword = input.value.toLowerCase();
        var items = currentPanel.querySelectorAll('.filter-dropdown-item');
        items.forEach(function(item) {
            var text = item.textContent.toLowerCase();
            item.style.display = text.includes(keyword) ? 'flex' : 'none';
        });
    }

    /**
     * 全选
     */
    function selectAll() {
        var checkboxes = currentPanel.querySelectorAll('input[type="checkbox"]');
        checkboxes.forEach(function(cb) {
            cb.checked = true;
        });
    }

    /**
     * 反选
     */
    function invert() {
        var checkboxes = currentPanel.querySelectorAll('input[type="checkbox"]');
        checkboxes.forEach(function(cb) {
            cb.checked = !cb.checked;
        });
    }

    /**
     * 应用筛选
     */
    function applyFilter() {
        var checkboxes = currentPanel.querySelectorAll('input[type="checkbox"]:checked');
        var selectedValues = Array.from(checkboxes).map(function(cb) {
            return cb.value;
        });
        var field = currentField;

        if (selectedValues.length === 0) {
            delete activeFilters[field];
        } else {
            activeFilters[field] = selectedValues;
        }

        closeAll();

        // 触发回调
        if (typeof filterConfig.onApply === 'function') {
            filterConfig.onApply(getActiveFilters());
        }
    }

    /**
     * 清空搜索
     */
    function clearSearch() {
        var textarea = document.getElementById('searchPanelTextarea');
        if (textarea) textarea.value = '';
    }

    /**
     * 应用搜索
     */
    function applySearch() {
        var textarea = document.getElementById('searchPanelTextarea');
        var value = textarea ? textarea.value : '';

        // 更新原始输入框
        var originalInput = document.getElementById(currentInputId);
        if (originalInput) originalInput.value = value;

        closeAll();

        // 刷新按钮状态
        refreshSearchButtonStates();

        // 触发回调
        if (typeof searchConfig.onApply === 'function') {
            searchConfig.onApply(currentField, value);
        }
    }

    /**
     * 取消/关闭面板
     */
    function cancel() {
        closeAll();
    }

    /**
     * 关闭所有面板
     */
    function closeAll() {
        if (currentPanel) {
            currentPanel.remove();
            currentPanel = null;
        }

        currentMode = null;
        currentField = null;
        currentInputId = null;

        // 移除所有按钮高亮
        document.querySelectorAll('.filter-btn').forEach(function(btn) {
            btn.classList.remove('active');
        });

        // 刷新搜索按钮状态（恢复有值的按钮高亮）
        refreshSearchButtonStates();

        // 刷新筛选按钮状态
        Object.keys(activeFilters).forEach(function(field) {
            var btn = document.querySelector('.filter-btn[data-field="' + field + '"]');
            if (btn && activeFilters[field] && activeFilters[field].length > 0) {
                btn.classList.add('active');
            }
        });
    }

    /**
     * 获取当前激活的筛选条件
     * @returns {Object} - 筛选条件对象
     */
    function getActiveFilters() {
        return Object.assign({}, activeFilters);
    }

    /**
     * 设置筛选条件
     * @param {Object} filters - 筛选条件
     */
    function setActiveFilters(filters) {
        activeFilters = Object.assign({}, filters);
        // 更新所有按钮状态
        Object.keys(activeFilters).forEach(function(field) {
            var btn = document.querySelector('.filter-btn[data-field="' + field + '"]');
            if (btn && activeFilters[field] && activeFilters[field].length > 0) {
                btn.classList.add('active');
            }
        });
    }

    /**
     * 清除所有筛选
     */
    function clearAll() {
        activeFilters = {};
        document.querySelectorAll('.filter-btn[data-field]').forEach(function(btn) {
            btn.classList.remove('active');
        });

        if (typeof filterConfig.onClear === 'function') {
            filterConfig.onClear();
        }
    }

    /**
     * 更新筛选数据源
     * @param {Array} newData - 新数据
     */
    function updateData(newData) {
        filterConfig.data = newData;
    }

    // ==================== 外部选项筛选面板功能 ====================

    var externalFilterConfig = {
        fields: [],
        onApply: null,
        activeValues: {}
    };

    /**
     * 使用外部选项初始化筛选按钮（适用于非 AG Grid 数据的场景）
     * @param {Object} options - 配置选项
     * @param {string} options.container - 按钮容器选择器
     * @param {Array} options.fields - 字段配置 [{ field: 'brand', label: '品牌', options: [{value, text}] }]
     * @param {Function} options.onApply - 应用筛选的回调函数 function(field, selectedValues)
     * @param {Object} options.initialValues - 初始选中值 { brand: ['宝马'] }
     */
    function initWithOptions(options) {
        externalFilterConfig = Object.assign({
            container: null,
            fields: [],
            onApply: null,
            initialValues: {}
        }, options);

        externalFilterConfig.activeValues = Object.assign({}, options.initialValues || {});

        // 渲染筛选按钮
        renderExternalFilterButtons();
    }

    /**
     * 渲染外部选项筛选按钮
     */
    function renderExternalFilterButtons() {
        var container = document.querySelector(externalFilterConfig.container);
        if (!container) return;

        container.innerHTML = '';

        externalFilterConfig.fields.forEach(function(fieldConfig) {
            var btn = document.createElement('button');
            btn.className = 'filter-btn';
            btn.id = 'externalFilterBtn_' + fieldConfig.field;
            btn.setAttribute('data-field', fieldConfig.field);
            btn.textContent = fieldConfig.label;

            // 初始高亮状态
            var currentValues = externalFilterConfig.activeValues[fieldConfig.field] || [];
            if (currentValues.length > 0) {
                btn.classList.add('active');
            }

            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                togglePanelWithOptions(fieldConfig, btn);
            });

            container.appendChild(btn);
        });
    }

    /**
     * 切换外部选项筛选面板
     * @param {Object} fieldConfig - 字段配置
     * @param {HTMLElement} btnElement - 按钮元素
     */
    function togglePanelWithOptions(fieldConfig, btnElement) {
        if (currentPanel && currentMode === 'external' && currentField === fieldConfig.field) {
            closeAll();
            return;
        }
        closeAll();
        createPanelWithOptions(fieldConfig, btnElement);
    }

    /**
     * 创建外部选项筛选面板（带搜索框）
     * @param {Object} fieldConfig - 字段配置
     * @param {HTMLElement} btnElement - 按钮元素
     */
    function createPanelWithOptions(fieldConfig, btnElement) {
        currentMode = 'external';
        currentField = fieldConfig.field;

        var panel = document.createElement('div');
        panel.className = 'filter-dropdown-panel show';
        panel.id = 'filter-panel-dropdown';
        panel.style.display = 'block';

        var currentFilter = externalFilterConfig.activeValues[fieldConfig.field] || [];

        var listHtml = '';
        fieldConfig.options.forEach(function(opt) {
            var isChecked = currentFilter.includes(opt.value) ? 'checked' : '';
            listHtml += '<div class="filter-dropdown-item" onclick="FilterPanel.toggleItemCheckbox(this)">' +
                '<input type="checkbox" value="' + opt.value + '" ' + isChecked + ' onclick="event.stopPropagation()">' +
                '<label>' + opt.text + '</label>' +
            '</div>';
        });

        panel.innerHTML =
            '<div class="filter-dropdown-header">' + fieldConfig.label + '筛选</div>' +
            '<div class="filter-dropdown-search" style="padding: 8px 12px; box-sizing: border-box;">' +
                '<input type="text" placeholder="搜索..." oninput="FilterPanel.filterSearch(this)" style="width: 100%; padding: 5px 8px; border: 1px solid #d9d9d9; border-radius: 4px; font-size: 12px; box-sizing: border-box;">' +
            '</div>' +
            '<div class="filter-dropdown-list">' + listHtml + '</div>' +
            '<div class="filter-dropdown-footer">' +
                '<button onclick="FilterPanel.selectAll()">全选</button>' +
                '<button onclick="FilterPanel.invert()">反选</button>' +
                '<button class="btn-confirm" onclick="FilterPanel.applyFilterWithOptions()">确定</button>' +
                '<button onclick="FilterPanel.cancel()">取消</button>' +
            '</div>';

        var rect = btnElement.getBoundingClientRect();
        panel.style.position = 'fixed';
        panel.style.left = rect.left + 'px';
        panel.style.top = (rect.bottom + 4) + 'px';
        panel.style.zIndex = '999999999';

        document.body.appendChild(panel);
        currentPanel = panel;

        btnElement.classList.add('active');
    }

    /**
     * 应用外部选项筛选
     */
    function applyFilterWithOptions() {
        if (!currentPanel) return;

        var checkboxes = currentPanel.querySelectorAll('input[type="checkbox"]:checked');
        var selectedValues = Array.from(checkboxes).map(function(cb) { return cb.value; });

        externalFilterConfig.activeValues[currentField] = selectedValues;

        if (typeof externalFilterConfig.onApply === 'function') {
            externalFilterConfig.onApply(currentField, selectedValues);
        }

        closeAll();
    }

    // ==================== AG Grid 列菜单功能（已迁移） ====================
    // 该部分代码已迁移至 grid-column-menu.js 与 column-preference.js

    /**
     * 销毁组件
     */
    function destroy() {
        closeAll();

        // 清空容器
        var filterContainer = document.querySelector(filterConfig.container);
        if (filterContainer) filterContainer.innerHTML = '';

        var searchContainer = document.querySelector(searchConfig.container);
        if (searchContainer) searchContainer.innerHTML = '';

        filterConfig = {};
        searchConfig = {};
        activeFilters = {};
        externalFilterConfig = { fields: [], onApply: null, activeValues: {} };
    }

    /**
     * 处理文档点击事件
     * @param {Event} e - 点击事件
     */
    function handleDocumentClick(e) {
        var isFilterBtn = e.target.closest('.filter-btn');
        var isDropdownPanel = e.target.closest('.filter-dropdown-panel');

        if (!isFilterBtn && !isDropdownPanel) {
            closeAll();
        }
    }

    // 绑定点击外部关闭事件
    document.addEventListener('click', handleDocumentClick);

    // 暴露公共API
    return {
        // 筛选面板
        init: init,
        initWithOptions: initWithOptions,
        applyFilterWithOptions: applyFilterWithOptions,
        updateData: updateData,
        getActiveFilters: getActiveFilters,
        setActiveFilters: setActiveFilters,
        clearAll: clearAll,

        // 搜索面板
        initSearch: initSearch,

        // 公共方法
        toggleItemCheckbox: toggleItemCheckbox,
        filterSearch: filterSearch,
        selectAll: selectAll,
        invert: invert,
        applyFilter: applyFilter,
        clearSearch: clearSearch,
        applySearch: applySearch,
        cancel: cancel,
        closeAll: closeAll,
        destroy: destroy
    };
})();
