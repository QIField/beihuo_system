/**
 * 搜索表单通用模块
 * 整合日期选择、表单搜索、表单重置功能
 * 依赖：Layui (table, form, laydate, layer)
 * 
 * 使用方法：
 * 1. 引入CSS: <link rel="stylesheet" href="{{ url_for('static', filename='css/search-form-common.css') }}">
 * 2. 引入JS: <script src="{{ url_for('static', filename='js/search-form-common.js') }}"></script>
 * 3. HTML结构：
 *    <div class="search-form-container">
 *        <form class="layui-form" id="searchForm">
 *            <div class="search-row">
 *                <div class="search-item">
 *                    <input type="text" name="keyword" placeholder="关键词" class="layui-input">
 *                </div>
 *                <div class="search-item date-range-item">
 *                    <input type="text" name="date_range" id="dateRange" placeholder="日期范围" class="layui-input" readonly>
 *                </div>
 *            </div>
 *            <div class="search-buttons">
 *                <button type="submit" class="layui-btn layui-btn-normal">搜索</button>
 *                <button type="button" class="layui-btn layui-btn-primary" id="resetBtn">重置</button>
 *            </div>
 *        </form>
 *    </div>
 * 4. JS初始化：
 *    initSearchForm({
 *        formSelector: '#searchForm',
 *        tableId: 'dataTable',
 *        apiUrl: '/api/xxx',
 *        dateRangeSelector: '#dateRange'  // 可选，不需要日期选择则不传
 *    });
 */

/**
 * 初始化搜索表单
 * @param {Object} options 配置选项
 * @param {string} options.formSelector 表单选择器，如 '#searchForm'
 * @param {string} options.tableId 表格ID，如 'dataTable'
 * @param {string} options.apiUrl 数据接口URL
 * @param {string} [options.dateRangeSelector] 日期范围选择器，如 '#dateRange'，不传则不初始化日期选择
 * @param {Function} [options.beforeSearch] 搜索前回调，可用于修改搜索参数
 * @param {Function} [options.afterReset] 重置后回调
 */
function initSearchForm(options) {
    const {
        formSelector,
        tableId,
        apiUrl,
        dateRangeSelector,
        beforeSearch,
        afterReset
    } = options;

    // 初始化日期范围选择器（如果提供了选择器）
    if (dateRangeSelector) {
        initDateRangePicker(dateRangeSelector.replace('#', ''));
    }

    // 绑定表单提交事件（搜索）
    bindSearchSubmit(formSelector, tableId, apiUrl, beforeSearch);

    // 绑定重置按钮事件
    bindResetButton(formSelector, tableId, apiUrl, afterReset);
}

/**
 * 初始化日期范围选择器
 * @param {string} elementId 元素ID（不带#）
 * @param {Object} [options] laydate配置选项
 */
function initDateRangePicker(elementId, options) {
    layui.use(['laydate'], function() {
        const laydate = layui.laydate;
        
        const defaultOptions = {
            elem: '#' + elementId,
            range: true,  // 开启范围选择
            format: 'yyyy-MM-dd',
            placeholder: '请选择日期范围',
            ...options
        };
        
        laydate.render(defaultOptions);
    });
}

/**
 * 绑定搜索表单提交事件
 * @param {string} formSelector 表单选择器
 * @param {string} tableId 表格ID
 * @param {string} apiUrl 数据接口URL
 * @param {Function} [beforeSearch] 搜索前回调
 */
function bindSearchSubmit(formSelector, tableId, apiUrl, beforeSearch) {
    layui.use(['form', 'table', 'layer'], function() {
        const form = layui.form;
        const table = layui.table;
        const layer = layui.layer;
        const $ = layui.$;

        // 使用Layui的表单提交事件
        form.on('submit(search)', function(data) {
            // 显示加载层
            const loadIndex = layer.load(1, { shade: [0.1, '#fff'] });

            // 收集表单数据
            let searchParams = { ...data.field };

            // 处理日期范围字段
            if (searchParams.date_range) {
                const dates = searchParams.date_range.split(' - ');
                if (dates.length === 2) {
                    searchParams.start_date = dates[0];
                    searchParams.end_date = dates[1];
                }
                delete searchParams.date_range;
            }

            // 搜索前回调（可用于修改参数）
            if (typeof beforeSearch === 'function') {
                searchParams = beforeSearch(searchParams) || searchParams;
            }

            // 重新加载表格数据
            table.reload(tableId, {
                where: searchParams,
                page: { curr: 1 },  // 重置到第一页
                done: function() {
                    layer.close(loadIndex);
                }
            });

            return false; // 阻止表单默认提交
        });

        // 兼容普通表单提交（没有lay-filter="search"的情况）
        $(formSelector).on('submit', function(e) {
            if (!$(this).attr('lay-filter')) {
                e.preventDefault();
                // 触发自定义搜索
                const formData = {};
                $(this).serializeArray().forEach(function(item) {
                    formData[item.name] = item.value;
                });

                const loadIndex = layer.load(1, { shade: [0.1, '#fff'] });

                let searchParams = { ...formData };

                // 处理日期范围
                if (searchParams.date_range) {
                    const dates = searchParams.date_range.split(' - ');
                    if (dates.length === 2) {
                        searchParams.start_date = dates[0];
                        searchParams.end_date = dates[1];
                    }
                    delete searchParams.date_range;
                }

                if (typeof beforeSearch === 'function') {
                    searchParams = beforeSearch(searchParams) || searchParams;
                }

                table.reload(tableId, {
                    where: searchParams,
                    page: { curr: 1 },
                    done: function() {
                        layer.close(loadIndex);
                    }
                });
            }
        });
    });
}

/**
 * 绑定重置按钮事件
 * @param {string} formSelector 表单选择器
 * @param {string} tableId 表格ID
 * @param {string} apiUrl 数据接口URL
 * @param {Function} [afterReset] 重置后回调
 */
function bindResetButton(formSelector, tableId, apiUrl, afterReset) {
    layui.use(['table', 'layer', 'form'], function() {
        const table = layui.table;
        const layer = layui.layer;
        const form = layui.form;
        const $ = layui.$;

        // 查找重置按钮（支持id或class）
        const $form = $(formSelector);
        const $resetBtn = $form.find('#resetBtn, .reset-btn, [type="reset"]').first();

        if ($resetBtn.length === 0) {
            console.warn('未找到重置按钮，请确保表单内有id="resetBtn"或class="reset-btn"的按钮');
            return;
        }

        $resetBtn.on('click', function(e) {
            e.preventDefault();

            // 显示加载层
            const loadIndex = layer.load(1, { shade: [0.1, '#fff'] });

            // 重置表单
            $form[0].reset();

            // 重新渲染layui表单（如果有）
            if (typeof form.render === 'function') {
                form.render(null, $form.attr('lay-filter') || null);
            }

            // 重新加载表格（不带搜索条件）
            table.reload(tableId, {
                where: {},
                page: { curr: 1 },
                done: function() {
                    layer.close(loadIndex);
                    
                    // 重置后回调
                    if (typeof afterReset === 'function') {
                        afterReset();
                    }
                }
            });
        });
    });
}

/**
 * 快速初始化搜索表单（简化版）
 * 适用于标准结构的页面
 * 
 * @param {string} tableId 表格ID
 * @param {string} apiUrl 数据接口URL
 * @param {boolean} [hasDateRange=true] 是否有日期范围选择器
 */
function quickInitSearchForm(tableId, apiUrl, hasDateRange = true) {
    const options = {
        formSelector: '#searchForm',
        tableId: tableId,
        apiUrl: apiUrl
    };

    if (hasDateRange) {
        options.dateRangeSelector = '#dateRange';
    }

    initSearchForm(options);
}

// 导出模块函数（如果支持模块化）
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        initSearchForm,
        initDateRangePicker,
        bindSearchSubmit,
        bindResetButton,
        quickInitSearchForm
    };
}
