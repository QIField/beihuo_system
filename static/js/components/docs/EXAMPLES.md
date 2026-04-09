# 使用示例

## 示例 1：日期查询表格（完整版）

```javascript
const grid = new DataGrid('#date-query-table', {
    dataSource: {
        type: 'server',
        url: '/api/date_ordercount',
        method: 'POST',
        cache: true,
        cacheTime: 300000  // 5分钟缓存
    },
    
    columns: [
        { data: 'selected', type: 'checkbox', width: 40 },
        { data: 'rowNumber', title: '行号', width: 60, readOnly: true },
        { data: 'oe', title: 'OE', width: 100, sortable: true },
        { data: '物料名称', title: '物料名称', width: 120 },
        { data: '品牌', title: '品牌', width: 80, sortable: true },
        { data: '物料条码', title: '物料条码', width: 120 },
        { data: '库存数量', title: '库存数量', width: 88, sortable: true },
        { data: '销量', title: '销量', width: 60, sortable: true },
        { data: '供应商', title: '供应商', width: 120 }
    ],
    
    // 功能配置
    pagination: true,
    serverSide: true,
    sorting: true,
    filtering: true,
    selection: 'multiple',
    
    // 固定列
    fixedColumns: { left: 15, right: 0 },
    
    // 虚拟滚动
    virtualScroll: true,
    rowHeight: 40,
    
    // 事件回调
    onSelectionChange: (selectedRows) => {
        console.log('选中行:', selectedRows);
    },
    
    onRowClick: (rowData, rowIndex) => {
        console.log('点击行:', rowData);
    }
});
```

## 示例 2：询比价模块

```javascript
const compareGrid = new DataGrid('#compare-table', {
    dataSource: {
        type: 'server',
        url: '/api/purchase_plan/compare'
    },
    
    columns: [
        { data: 'oe', title: 'OE号', width: 120, sortable: true },
        { data: 'brand', title: '品牌', width: 80 },
        { data: 'supplier1_price', title: '供应商1价格', width: 100 },
        { data: 'supplier2_price', title: '供应商2价格', width: 100 },
        { data: 'supplier3_price', title: '供应商3价格', width: 100 },
        { data: 'min_price', title: '最低价', width: 80, sortable: true },
        { data: 'action', title: '操作', width: 100, type: 'action' }
    ],
    
    pagination: true,
    serverSide: true,
    sorting: true,
    fixedColumns: { left: 2, right: 1 }
});
```

## 示例 3：库存管理（客户端分页）

```javascript
const stockGrid = new DataGrid('#stock-table', {
    dataSource: {
        type: 'client',      // 一次性加载所有数据
        url: '/api/stock/all'
    },
    
    columns: [
        { data: 'code', title: '商品编码', sortable: true },
        { data: 'name', title: '商品名称' },
        { data: 'stock', title: '库存数量', sortable: true },
        { data: 'warning', title: '预警状态' }
    ],
    
    pagination: true,
    pageSize: 50,        // 每页50条
    sorting: true,
    filtering: true
});
```

## 示例 4：带工具栏的表格

```javascript
const grid = new DataGrid('#table', {
    dataSource: { ... },
    columns: [...],
    
    // 工具栏配置
    toolbar: {
        items: [
            { type: 'button', text: '新增', icon: 'plus', onClick: () => { } },
            { type: 'button', text: '导出', icon: 'export', onClick: () => { } },
            { type: 'separator' },
            { type: 'search', placeholder: '搜索...' }
        ]
    },
    
    pagination: true
});
```

## 示例 5：自定义单元格渲染

```javascript
const grid = new DataGrid('#table', {
    dataSource: { ... },
    
    columns: [
        { data: 'id', title: 'ID' },
        { 
            data: 'status', 
            title: '状态',
            renderer: (value) => {
                const colors = {
                    '正常': 'green',
                    '预警': 'orange',
                    '缺货': 'red'
                };
                return `<span style="color: ${colors[value]}">${value}</span>`;
            }
        },
        { 
            data: 'progress', 
            title: '进度',
            renderer: (value) => {
                return `
                    <div style="width: 100%; background: #f0f0f0;">
                        <div style="width: ${value}%; background: #1890ff; height: 20px;"></div>
                    </div>
                `;
            }
        }
    ]
});
```

## 示例 6：树形表格

```javascript
const treeGrid = new DataGrid('#tree-table', {
    dataSource: { ... },
    columns: [
        { data: 'name', title: '名称', treeColumn: true },
        { data: 'size', title: '大小' },
        { data: 'date', title: '修改日期' }
    ],
    
    treeConfig: {
        idField: 'id',
        parentIdField: 'parentId',
        expandAll: false
    }
});
```

## 示例 7：可编辑表格

```javascript
const editGrid = new DataGrid('#edit-table', {
    dataSource: { ... },
    
    columns: [
        { data: 'id', title: 'ID', readOnly: true },
        { data: 'name', title: '名称', editor: 'text' },
        { data: 'price', title: '价格', editor: 'numeric' },
        { data: 'category', title: '分类', editor: 'dropdown', options: ['A', 'B', 'C'] }
    ],
    
    editable: true,
    
    onCellChange: (rowIndex, colIndex, oldValue, newValue) => {
        console.log('单元格修改:', rowIndex, colIndex, oldValue, newValue);
    }
});
```

## 示例 8：大数据量表格（10万行）

```javascript
const bigDataGrid = new DataGrid('#big-table', {
    dataSource: {
        type: 'server',
        url: '/api/bigdata'
    },
    
    columns: [...],
    
    // 虚拟滚动配置
    virtualScroll: true,
    rowHeight: 40,
    bufferSize: 20,       // 增大缓冲区
    overscan: 10,         // 预渲染行数
    
    // 禁用不必要功能提升性能
    columnResize: false,
    manualColumnMove: false,
    
    pagination: true,
    serverSide: true,
    pageSize: 200         // 每页200条
});
```

## 方法调用示例

```javascript
// 刷新数据
grid.refresh();

// 获取选中行
const selected = grid.getSelected();
console.log(selected);

// 跳转到第5页
grid.goToPage(5);

// 设置每页100条
grid.setPageSize(100);

// 添加过滤条件
grid.setFilter({ status: 'active' });

// 清空选择
grid.clearSelection();

// 销毁组件
grid.destroy();
```
