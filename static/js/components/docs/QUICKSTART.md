# 快速开始

## 5 分钟上手 DataGrid

### 第 1 步：引入依赖

```html
<!DOCTYPE html>
<html>
<head>
    <!-- Handsontable 样式 -->
    <link rel="stylesheet" href="/static/js/handsontable/handsontable.full.min.css">
    
    <!-- 自定义样式（可选） -->
    <style>
        #my-table {
            height: 500px;
            width: 100%;
        }
    </style>
</head>
<body>
    <!-- 表格容器 -->
    <div id="my-table"></div>
    
    <!-- 引入 Handsontable -->
    <script src="/static/js/handsontable/handsontable.full.min.js"></script>
    
    <!-- 引入 DataGrid 组件 -->
    <script src="/static/js/components/index.js"></script>
</body>
</html>
```

### 第 2 步：初始化表格

```javascript
// 基础表格
const grid = new DataGrid('#my-table', {
    // 数据源配置
    dataSource: {
        type: 'server',           // 服务端分页
        url: '/api/data',         // API地址
        method: 'POST'
    },
    
    // 列定义
    columns: [
        { data: 'id', title: 'ID', width: 80 },
        { data: 'name', title: '名称', sortable: true },
        { data: 'price', title: '价格', width: 100, sortable: true }
    ],
    
    // 启用功能
    pagination: true,
    sorting: true,
    filtering: true
});
```

### 第 3 步：后端 API

```python
# Flask 示例
@app.route('/api/data', methods=['POST'])
def get_data():
    data = request.get_json()
    
    page = data.get('page', 1)
    page_size = data.get('pageSize', 100)
    
    # 查询数据
    query = Model.query
    total = query.count()
    
    # 分页
    items = query.offset((page-1)*page_size).limit(page_size).all()
    
    return jsonify({
        'code': 0,
        'data': [item.to_dict() for item in items],
        'total': total
    })
```

## 常用配置

### 客户端分页（小数据量）

```javascript
const grid = new DataGrid('#table', {
    dataSource: {
        type: 'client',      // 一次性加载，前端分页
        url: '/api/all-data'
    },
    columns: [...],
    pagination: true,
    pageSize: 50
});
```

### 固定列

```javascript
const grid = new DataGrid('#table', {
    dataSource: { ... },
    columns: [...],
    fixedColumns: {
        left: 3,    // 左侧固定3列
        right: 1    // 右侧固定1列
    }
});
```

### 虚拟滚动（大数据量）

```javascript
const grid = new DataGrid('#table', {
    dataSource: { ... },
    columns: [...],
    virtualScroll: true,
    rowHeight: 40,        // 固定行高
    bufferSize: 10        // 缓冲行数
});
```

## 下一步

- 查看 [API.md](./API.md) 了解完整配置
- 查看 [EXAMPLES.md](./EXAMPLES.md) 学习更多示例
