/**
 * 表单重置组件
 */

// 通用表单重置功能
function handleFormReset(formSelector, tableId) {
    layui.use(['table', 'jquery'], function() {
        var table = layui.table;
        var $ = layui.jquery;

        // 重置按钮点击事件
        $(formSelector + ' #resetBtn').on('click', function() {
            $(formSelector + ' input').val('');

            // 显示加载提示
            var loadIndex = layer.load(1, {shade: [0.1, '#fff']});

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
                },
                done: function(res, curr, count) {
                    // 关闭加载提示
                    layer.close(loadIndex);
                    
                    // 表格数据加载完成后，重新初始化Excel风格单元格选择功能
                    setTimeout(function() {
                        initExcelCellSelection(tableId, table, layer, {
                            enableCopy: true,
                            enableAddToCart: false
                        });
                    }, 100);
                }
            });
        });
    });
}
