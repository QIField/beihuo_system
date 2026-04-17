# AG Grid 工具函数库

## 文件说明

| 文件 | 类型 | 说明 |
|:---|:---:|:---|
| `ag-grid-community.min.js` | AG Grid 自带 | AG Grid 核心库（官方） |
| `ag-grid.css` | AG Grid 自带 | AG Grid 基础样式（官方） |
| `ag-theme-alpine.css` | AG Grid 自带 | Alpine 主题样式（官方） |
| `ag-custom-checkbox.css` | 手动编写 | 自定义复选框样式 |
| `ag-grid-utils.js` | **手动编写** | **AG Grid 增强工具函数** |

---

## ag-grid-utils.js 功能列表

### 1. initDragSelection(gridApi, gridColumnApi)
**拖拽选择功能**
- 按住鼠标拖拽批量选择单元格
- 选中的单元格会高亮显示
- 支持跨行跨列选择

```javascript
const gridApi = new agGrid.Grid(gridDiv, gridOptions).api;
const gridColumnApi = gridOptions.columnApi;
initDragSelection(gridApi, gridColumnApi);
```

---

### 2. initDoubleClickCopy(gridApi, gridColumnApi)
**双击复制功能**
- 双击单元格复制内容到剪贴板
- 显示复制成功提示
- 自动处理兼容性

```javascript
initDoubleClickCopy(gridApi, gridColumnApi);
```

---

### 3. initShortcuts(gridApi, copyCallback)
**快捷键功能**
- `Ctrl+C`: 复制选中单元格
- `Ctrl+A`: 全选所有行
- `Esc`: 取消选择

```javascript
initShortcuts(gridApi, function() {
    // 自定义复制逻辑
});
```

---

### 4. initPageSizeSelector(gridApi, sizes)
**分页大小选择器**
- 在分页栏添加下拉选择框
- 可自定义分页大小选项
- 默认选项：[10, 20, 50, 100]

```javascript
// 使用默认选项
initPageSizeSelector(gridApi);

// 自定义选项
initPageSizeSelector(gridApi, [20, 50, 100, 200]);
```

---

### 5. sizeColumnsToFit(gridApi)
**自适应列宽**
- 自动调整所有列宽以适应容器
- AG Grid 自带 API 的封装

```javascript
// 初始化后调用
sizeColumnsToFit(gridApi);

// 窗口大小改变时调用
window.addEventListener('resize', function() {
    sizeColumnsToFit(gridApi);
});
```

---

### 6. exportToCsv(gridApi, filename)
**导出 CSV**
- 将表格数据导出为 CSV 文件
- 支持自定义文件名

```javascript
exportToCsv(gridApi, '数据导出');
```

---

### 7. copyToClipboard(text)
**复制文本到剪贴板**
- 兼容性复制（支持现代浏览器和旧浏览器）
- 显示复制成功提示

```javascript
copyToClipboard('要复制的文本');
```

---

## 完整使用示例

```html
<!DOCTYPE html>
<html>
<head>
    <!-- AG Grid 样式 -->
    <link rel="stylesheet" href="/static/ag-grid/ag-grid.css">
    <link rel="stylesheet" href="/static/ag-grid/ag-theme-alpine.css">
</head>
<body>
    <div id="myGrid" class="ag-theme-alpine" style="height: 400px;"></div>
    
    <!-- AG Grid 核心库 -->
    <script src="/static/ag-grid/ag-grid-community.min.js"></script>
    <!-- AG Grid 工具函数 -->
    <script src="/static/ag-grid/ag-grid-utils.js"></script>
    
    <script>
        // 定义列
        const columnDefs = [
            { headerName: '姓名', field: 'name', sortable: true, filter: true, resizable: true },
            { headerName: '年龄', field: 'age', sortable: true, filter: true, resizable: true },
            { headerName: '城市', field: 'city', sortable: true, filter: true, resizable: true }
        ];
        
        // 定义数据
        const rowData = [
            { name: '张三', age: 25, city: '北京' },
            { name: '李四', age: 30, city: '上海' },
            { name: '王五', age: 28, city: '广州' }
        ];
        
        // Grid 配置
        const gridOptions = {
            columnDefs: columnDefs,
            rowData: rowData,
            pagination: true,
            paginationPageSize: 10,
            rowSelection: 'multiple',
            onGridReady: function(params) {
                // 获取 API
                const gridApi = params.api;
                const gridColumnApi = params.columnApi;
                
                // 启用工具函数功能
                initDragSelection(gridApi, gridColumnApi);
                initDoubleClickCopy(gridApi, gridColumnApi);
                initShortcuts(gridApi);
                initPageSizeSelector(gridApi, [10, 20, 50]);
                sizeColumnsToFit(gridApi);
            }
        };
        
        // 创建 Grid
        const gridDiv = document.querySelector('#myGrid');
        new agGrid.Grid(gridDiv, gridOptions);
    </script>
</body>
</html>
```

---

## 依赖说明

- **必须依赖**：`ag-grid-community.min.js`（AG Grid 核心库）
- **可选依赖**：`layui.js`（用于显示提示信息，没有时会使用 console.log）

---

## 浏览器兼容性

- Chrome 60+
- Firefox 55+
- Safari 12+
- Edge 79+

---

## 更新日志

### 2026-04-15
- 初始版本发布
- 包含功能：拖拽选择、双击复制、快捷键、分页选择器、自适应列宽、CSV导出
