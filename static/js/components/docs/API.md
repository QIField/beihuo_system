# API 参考文档

## DataGrid 类

### 构造函数

```javascript
new DataGrid(container, options)
```

| 参数 | 类型 | 必填 | 说明 |
|-----|------|-----|------|
| container | string/Element | 是 | 容器选择器或DOM元素 |
| options | object | 是 | 配置选项 |

### 配置选项

#### dataSource

数据源配置。

```javascript
{
    dataSource: {
        type: 'server',           // 'client' 或 'server'
        url: '/api/data',         // API地址
        method: 'GET',            // 请求方法
        headers: {},              // 自定义请求头
        dataKey: 'data',          // 响应数据字段
        totalKey: 'total',        // 响应总数字段
        cache: false,             // 是否启用缓存
        cacheTime: 300000,        // 缓存时间(ms)
        transform: (data) => data // 数据转换函数
    }
}
```

#### columns

列定义数组。

```javascript
{
    columns: [
        {
            data: 'fieldName',        // 数据字段名
            title: '显示标题',         // 列标题
            width: 100,               // 列宽
            type: 'text',             // 类型: text/checkbox/number
            sortable: false,          // 是否可排序
            filterable: true,         // 是否可过滤
            readOnly: false,          // 是否只读
            editor: 'text',           // 编辑器类型
            renderer: (value) => {},  // 自定义渲染函数
            className: 'custom-cell'  // 自定义CSS类
        }
    ]
}
```

#### 功能开关

```javascript
{
    pagination: true,           // 启用分页
    serverSide: false,          // 服务端分页
    sorting: true,              // 启用排序
    filtering: true,            // 启用过滤
    selection: 'multiple',      // 选择模式: none/single/multiple
    virtualScroll: true,        // 虚拟滚动
    showSkeleton: true,         // 显示骨架屏
    showToolbar: false,         // 显示工具栏
    editable: false             // 可编辑
}
```

#### 固定列

```javascript
{
    fixedColumns: {
        left: 0,    // 左侧固定列数
        right: 0    // 右侧固定列数
    }
}
```

#### 虚拟滚动配置

```javascript
{
    rowHeight: 40,              // 行高
    bufferSize: 5,              // 缓冲区大小
    overscan: 5                 // 预渲染行数
}

```

#### 分页配置

```javascript
{
    pageSize: 100,              // 每页条数
    pageSizes: [50, 100, 200],  // 可选每页条数
    showTotal: true             // 显示总条数
}
```

#### 事件回调

```javascript
{
    onLoad: (data) => {},                    // 数据加载完成
    onError: (error) => {},                  // 加载错误
    onRowClick: (rowData, rowIndex) => {},   // 行点击
    onRowDoubleClick: (rowData) => {},       // 行双击
    onSelectionChange: (selectedRows) => {}, // 选择变化
    onPageChange: (page, pageSize) => {},    // 页码变化
    onSort: (field, order) => {},            // 排序变化
    onFilter: (filterData) => {},            // 过滤变化
    onCellChange: (row, col, oldVal, newVal) => {} // 单元格修改
}
```

### 实例方法

#### 数据操作

| 方法 | 参数 | 返回值 | 说明 |
|-----|------|-------|------|
| `refresh()` | - | Promise | 刷新数据 |
| `reload()` | - | Promise | 重新加载（清除缓存） |
| `getData()` | - | Array | 获取当前页数据 |
| `getAllData()` | - | Array | 获取所有数据（客户端模式） |
| `setData(data)` | data: Array | - | 设置数据 |
| `updateRow(index, data)` | index: number, data: object | - | 更新行 |
| `deleteRow(index)` | index: number | - | 删除行 |
| `insertRow(index, data)` | index: number, data: object | - | 插入行 |

#### 分页操作

| 方法 | 参数 | 返回值 | 说明 |
|-----|------|-------|------|
| `goToPage(page)` | page: number | Promise | 跳转到指定页 |
| `nextPage()` | - | Promise | 下一页 |
| `prevPage()` | - | Promise | 上一页 |
| `getCurrentPage()` | - | number | 获取当前页 |
| `getTotalPages()` | - | number | 获取总页数 |
| `setPageSize(size)` | size: number | Promise | 设置每页条数 |

#### 选择操作

| 方法 | 参数 | 返回值 | 说明 |
|-----|------|-------|------|
| `getSelected()` | - | Array | 获取选中行数据 |
| `getSelectedKeys()` | - | Array | 获取选中行主键 |
| `selectRow(index)` | index: number | - | 选中行 |
| `unselectRow(index)` | index: number | - | 取消选中 |
| `selectAll()` | - | - | 全选 |
| `clearSelection()` | - | - | 清空选择 |
| `selectRows(indexes)` | indexes: Array | - | 选中多行 |

#### 排序和过滤

| 方法 | 参数 | 返回值 | 说明 |
|-----|------|-------|------|
| `sort(field, order)` | field: string, order: 'asc'/'desc' | Promise | 排序 |
| `clearSort()` | - | - | 清除排序 |
| `setFilter(filter)` | filter: object | Promise | 设置过滤条件 |
| `clearFilter()` | - | Promise | 清除过滤 |
| `getFilter()` | - | object | 获取当前过滤条件 |

#### 其他方法

| 方法 | 参数 | 返回值 | 说明 |
|-----|------|-------|------|
| `getInstance()` | - | Handsontable | 获取 Handsontable 实例 |
| `resize()` | - | - | 调整大小 |
| `destroy()` | - | - | 销毁组件 |
| `validate()` | - | boolean | 验证数据（编辑模式） |
| `getChanges()` | - | Array | 获取修改记录（编辑模式） |

### 静态方法

```javascript
// 注册插件
DataGrid.registerPlugin(name, plugin)

// 注册渲染器
DataGrid.registerRenderer(name, renderer)

// 注册编辑器
DataGrid.registerEditor(name, editor)

// 设置全局配置
DataGrid.setDefaults(options)

// 获取版本
DataGrid.getVersion()
```

## 数据格式

### 请求格式

```javascript
{
    page: 1,              // 当前页
    pageSize: 100,        // 每页条数
    sort: {
        field: 'name',    // 排序字段
        order: 'asc'      // 排序方向
    },
    filter: {
        name: '关键字',   // 过滤条件
        status: 'active'
    }
}
```

### 响应格式

```javascript
{
    code: 0,              // 状态码，0表示成功
    data: [],             // 数据列表
    total: 1000,          // 总条数
    message: 'success'    // 消息
}
```

## 类型定义

### Column

```typescript
interface Column {
    data: string;
    title?: string;
    width?: number;
    type?: 'text' | 'checkbox' | 'number' | 'date' | 'dropdown';
    sortable?: boolean;
    filterable?: boolean;
    readOnly?: boolean;
    editor?: string | Editor;
    renderer?: (value: any, rowData: object) => string;
    className?: string;
    style?: object;
}
```

### DataSourceOptions

```typescript
interface DataSourceOptions {
    type: 'client' | 'server';
    url: string;
    method?: string;
    headers?: object;
    dataKey?: string;
    totalKey?: string;
    cache?: boolean;
    cacheTime?: number;
    transform?: (data: any) => any;
}
```

### GridOptions

```typescript
interface GridOptions {
    dataSource: DataSourceOptions;
    columns: Column[];
    pagination?: boolean;
    serverSide?: boolean;
    sorting?: boolean;
    filtering?: boolean;
    selection?: 'none' | 'single' | 'multiple';
    virtualScroll?: boolean;
    fixedColumns?: { left?: number; right?: number };
    rowHeight?: number;
    bufferSize?: number;
    pageSize?: number;
    onLoad?: (data: any[]) => void;
    onError?: (error: Error) => void;
    onRowClick?: (rowData: object, rowIndex: number) => void;
    onSelectionChange?: (selectedRows: object[]) => void;
}
```

## 错误码

| 错误码 | 说明 |
|-------|------|
| 0 | 成功 |
| 1001 | 网络错误 |
| 1002 | 数据解析错误 |
| 1003 | 配置错误 |
| 1004 | 渲染错误 |
| 1005 | 数据源错误 |

## 浏览器兼容性

- Chrome 80+
- Firefox 75+
- Safari 13+
- Edge 80+

## 更新日志

### v1.0.0 (2024-03-23)

- 初始版本发布
- 支持服务端/客户端分页
- 支持排序、过滤、选择
- 支持固定列、虚拟滚动
- 支持骨架屏加载
