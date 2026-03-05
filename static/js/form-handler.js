/**
 * 表单处理组件
 */

// 全局变量管理加载状态
var isLoading = false;

// 通用表单提交事件处理函数
function handleFormSubmit(formSelector, tableId, apiUrl) {
    layui.use(['table', 'jquery', 'form', 'layer'], function() {
        var table = layui.table;
        var $ = layui.jquery;
        var form = layui.form;
        var layer = layui.layer;

        // 表单提交事件
        form.on('submit(search)', function(data) {
            // 如果正在加载，阻止重复提交
            if (isLoading) {
                return false;
            }
            
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

            // 设置加载状态
            isLoading = true;
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
                done: function(res, curr, count) {
                    // 关闭加载提示
                    layer.close(loadIndex);
                    // 重置加载状态
                    isLoading = false;
                    
                    // 表格数据加载完成后，重新初始化Excel风格单元格选择功能
                    setTimeout(function() {
                        initExcelCellSelection(tableId, table, layer, {
                            enableCopy: true,
                            enableAddToCart: false
                        });
                    }, 100);
                }
            });

            return false; // 阻止表单默认提交
        });
    });
}