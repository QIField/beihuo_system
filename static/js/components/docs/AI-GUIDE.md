# DataGrid 组件 - AI 使用指南

> 本文档专为 AI 助手设计，帮助快速理解和使用该组件库

## 一句话描述

`DataGrid` 是一个企业级表格组件，基于 Handsontable 封装，支持服务端分页、排序、过滤、虚拟滚动等功能。

---

## 快速定位

| 你想做什么 | 查看文档 |
|-----------|---------|
| 了解组件功能 | [README.md](./README.md) |
| 查看所有 API | [API.md](./API.md) |
| 看代码示例 | [EXAMPLES.md](./EXAMPLES.md) |
| 5分钟上手 | [QUICKSTART.md](./QUICKSTART.md) |
| 修复问题/调试 | 本文档下方 "常见问题" |

---

## 核心架构（必须了解）

```
DataGrid (主组件)
    ├── DataSource (数据源)
    │       ├── type: 'client' | 'server'
    │       ├── url: API地址
    │       └── cache: 是否启用缓存
    ├── Pagination (分页)
    ├── Sorting (排序)
    ├── Filtering (过滤)
    ├── Selection (选择)
    └── Skeleton (骨架屏)
```

---

## 最常用的 3 个场景

### 场景 1：服务端分页表格
```javascript
const grid = new DataGrid('#container', {
    dataSource: {
        type: 'server',
        url: '/api/data',
        method: 'POST'
    },
    columns: [
        { data: 'id', title: 'ID' },
        { data: 'name', title: '名称', sortable: true }
    ],
    pagination: true,
    serverSide: true
});
```

### 场景 2：带搜索的表格
```javascript
const grid = new DataGrid('#container', {
    dataSource: { type: 'server', url: '/api/data' },
    columns: [...],
    filtering: true,  // 启用搜索栏
    filterFields: ['name', 'code']  // 可搜索字段
});
```

### 场景 3：固定列 + 虚拟滚动
```javascript
const grid = new DataGrid('#container', {
    dataSource: { type: 'server', url: '/api/data' },
    columns: [...],
    fixedColumns: { left: 3, right: 1 },
    virtualScroll: true,
    rowHeight: 40
});
```

---

## 关键配置项速查表

### DataSource 配置
| 参数 | 类型 | 必填 | 说明 |
|-----|------|-----|------|
| type | string | 是 | 'client' 或 'server' |
| url | string | 是 | API 地址 |
| method | string | 否 | 请求方法，默认 'GET' |
| cache | boolean | 否 | 是否缓存，默认 false |
| cacheTime | number | 否 | 缓存时间(ms)，默认 5分钟 |

### 功能开关
| 参数 | 类型 | 默认 | 说明 |
|-----|------|-----|------|
| pagination | boolean | true | 启用分页 |
| serverSide | boolean | false | 服务端分页 |
| sorting | boolean | true | 启用排序 |
| filtering | boolean | true | 启用过滤 |
| selection | string | 'multiple' | 选择模式：'none'/'single'/'multiple' |
| virtualScroll | boolean | true | 虚拟滚动 |

### 列配置
| 参数 | 类型 | 必填 | 说明 |
|-----|------|-----|------|
| data | string | 是 | 数据字段名 |
| title | string | 是 | 显示标题 |
| width | number | 否 | 列宽 |
| sortable | boolean | 否 | 可排序 |
| type | string | 否 | 'text'/'checkbox'/'number' |

---

## API 快速参考

### 实例方法
```javascript
// 刷新数据
grid.refresh()

// 获取选中行
grid.getSelected()

// 跳转到指定页
grid.goToPage(5)

// 设置每页条数
grid.setPageSize(200)

// 销毁组件
grid.destroy()
```

### 事件回调
```javascript
new DataGrid('#container', {
    onRowClick: (rowData, rowIndex) => { },
    onSelectionChange: (selectedRows) => { },
    onPageChange: (page, pageSize) => { },
    onSort: (field, order) => { },
    onFilter: (filterData) => { }
});
```

---

## 常见问题（调试指南）

### 问题 1：表格不显示
**检查清单：**
1. 容器元素是否存在？`document.querySelector('#container')`
2. 容器是否有高度？检查 CSS height
3. 数据源 URL 是否正确？检查网络请求

### 问题 2：分页不工作
**可能原因：**
- `serverSide: true` 但后端未返回正确格式
- 后端应返回：`{ data: [], total: 100 }`

### 问题 3：滚动卡顿
**优化建议：**
```javascript
{
    virtualScroll: true,
    rowHeight: 40,        // 固定行高
    bufferSize: 5,        // 减少缓冲行数
    renderAllRows: false  // 只渲染可视区域
}
```

### 问题 4：固定列错位
**解决方案：**
```javascript
{
    fixedColumns: { left: 3, right: 0 },  // 减少固定列数量
    autoRowSize: false,                    // 禁用自动行高
    rowHeights: 40                         // 固定行高
}
```

---

## 后端 API 规范

### 请求格式
```javascript
{
    page: 1,           // 当前页
    pageSize: 100,     // 每页条数
    sort: {
        field: 'name', // 排序字段
        order: 'asc'   // 'asc' 或 'desc'
    },
    filter: {
        name: '关键字', // 搜索关键字
        // ... 其他过滤条件
    }
}
```

### 响应格式
```javascript
{
    code: 0,           // 0 表示成功
    data: [],          // 数据列表
    total: 1000,       // 总条数（分页用）
    message: 'success' // 可选
}
```

---

## 文件位置

```
组件入口：static/js/components/index.js
核心组件：static/js/components/core/DataGrid.js
数据源：  static/js/components/core/DataSource.js
功能模块：static/js/components/features/
工具函数：static/js/components/utils/
```

---

## 依赖关系

```
DataGrid
    ├── Handsontable (外部依赖，已加载)
    ├── DataSource
    │       └── LRUCache
    ├── Pagination
    ├── Sorting
    ├── Filtering
    ├── Selection
    └── Skeleton
```

---

## 扩展开发

如需添加新功能，继承基类：

```javascript
class MyFeature extends BaseFeature {
    constructor(grid) {
        super(grid);
    }
    
    init() {
        // 初始化逻辑
    }
    
    destroy() {
        // 清理逻辑
    }
}

// 注册到 DataGrid
DataGrid.registerFeature('myFeature', MyFeature);
```

---

**最后更新：** 2024-03-23  
**版本：** v1.0.0  
**维护者：** 前端架构组
