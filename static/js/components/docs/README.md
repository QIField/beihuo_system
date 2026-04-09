# DataGrid 组件库

> 企业级表格组件，基于 Handsontable 封装

## 特性

- ✅ 服务端/客户端分页
- ✅ 服务端/客户端排序
- ✅ 多条件过滤搜索
- ✅ 固定列（左/右）
- ✅ 虚拟滚动（大数据量）
- ✅ 骨架屏加载
- ✅ 行选择（单选/多选）
- ✅ 数据缓存
- ✅ 模块化架构

## 安装

```html
<!-- 1. 引入 Handsontable -->
<link rel="stylesheet" href="/static/js/handsontable/handsontable.full.min.css">
<script src="/static/js/handsontable/handsontable.full.min.js"></script>

<!-- 2. 引入 DataGrid 组件 -->
<script src="/static/js/components/index.js"></script>
```

## 快速开始

```javascript
const grid = new DataGrid('#container', {
    dataSource: {
        type: 'server',
        url: '/api/data'
    },
    columns: [
        { data: 'id', title: 'ID', width: 80 },
        { data: 'name', title: '名称', sortable: true },
        { data: 'price', title: '价格', width: 100 }
    ]
});
```

## 文档导航

| 文档 | 说明 |
|-----|------|
| [AI-GUIDE.md](./AI-GUIDE.md) | **AI助手专用指南** |
| [API.md](./API.md) | 完整API参考 |
| [EXAMPLES.md](./EXAMPLES.md) | 使用示例 |
| [QUICKSTART.md](./QUICKSTART.md) | 5分钟快速上手 |

## 浏览器支持

- Chrome 80+
- Firefox 75+
- Safari 13+
- Edge 80+

## 许可证

MIT
