/**
 * 日期范围选择器组件
 */

// 日期范围选择器初始化函数
function initDateRangePicker(elementId, options = {}) {
    layui.use(['laydate'], function() {
        var laydate = layui.laydate;

        // 默认配置
        var defaultOptions = {
            elem: '#' + elementId,
            trigger: 'click',
            format: 'yyyy-MM-dd',
            range: true,
            max: 0 // 限制最大日期不能超过今天
        };

        // 合并用户配置
        var finalOptions = Object.assign(defaultOptions, options);

        // 初始化日期范围选择器
        laydate.render(finalOptions);
    });
}

// 通用表单提交事件处理函数
function handleFormSubmit(formSelector, tableId, apiUrl) {
    layui.use(['table', 'jquery', 'form'], function() {
        var table = layui.table;
        var $ = layui.jquery;
        var form = layui.form;

        // 表单提交事件
        form.on('submit(search)', function(data) {
            var formData = {};
            // 获取所有表单字段的值
            $(formSelector + ' input').each(function() {
                var fieldName = $(this).attr('name');
                if (fieldName) {
                    formData[fieldName] = $(this).val();
                }
            });

            var dateRangeValue = formData['date_range'];
            var startDate = '';
            var endDate = '';

            // 如果选择了日期范围，则分割值获取开始和结束日期
            if (dateRangeValue) {
                var dates = dateRangeValue.split(' - ');
                if (dates.length === 2) {
                    startDate = dates[0].trim();
                    endDate = dates[1].trim();
                }
            }

            // 显示加载提示
            var loadIndex = layer.load(1, {shade: [0.1, '#fff']});

            // 重新加载表格并传递搜索参数
            table.reload(tableId, {
                where: {
                    ks_order_id: formData['ks_order_id'],
                    crm_order_id: formData['crm_order_id'],
                    start_date: startDate,
                    end_date: endDate
                },
                page: {
                    curr: 1 // 从第一页开始
                },
                done: function() {
                    // 搜索完成后关闭加载提示
                    layer.close(loadIndex);
                }
            });

            return false; // 阻止表单默认提交
        });

        // 重置按钮点击事件
        $(formSelector + ' #resetBtn').on('click', function() {
            $(formSelector + ' input').val('');

            // 显示操作提示
            layer.msg('已重置', {time: 1000});

            // 重载表格，不带搜索参数
            table.reload(tableId, {
                where: {
                    ks_order_id: '',
                    crm_order_id: '',
                    start_date: '',
                    end_date: ''
                },
                page: {
                    curr: 1
                }
            });
        });
    });
}