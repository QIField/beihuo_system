# CRM 批量产品添加工具 - 使用说明

## 📋 功能概述

本工具用于批量从 Excel 文件读取数据，并自动添加产品到 CRM 系统。

### ✨ 特性
- ✅ **三列模式**：支持 oe、brand、brand_code 三列识别
- ✅ **并发处理**：多线程并发发送请求，提高处理速度
- ✅ **统一 Session 管理**：主文件一次性获取 cookie，所有请求共享 session
- ✅ **详细日志**：记录每条数据的请求参数和响应结果
- ✅ **失败记录**：单独保存失败记录便于排查

## 🚀 使用步骤

### 1. 准备 Excel 文件

Excel 文件需要包含以下列（列名可以大小写混合）：
- **oe 列**：`oe`, `OE`, `barcode` 之一
- **brand 列**：`brand`, `品牌` 之一  
- **brand_code 列**：`brand_code`, `条码`, `物料条码` 之一

### 2. 配置文件路径

在 `test_batch_process.py` 中修改 Excel 文件路径：

```python
excel_file_path = r"E:\work download\工作文件\盖茨副水壶管.xlsx"
```

### 3. 运行程序

```bash
cd app/utils/crm_product/crm_productAdd
python test_batch_process.py
```

## 📊 输出结果

### 日志文件
程序会生成两个日志文件：

1. **主日志文件**：`crm_batch_process_YYYYMMDD_HHMMSS.log`
   - 包含所有处理过程的详细日志
   - 每条数据的请求参数和响应结果
   - 处理进度和统计信息

2. **失败记录文件**：`crm_batch_process_YYYYMMDD_HHMMSS_failed.txt`（如果有失败）
   - 仅记录失败的数据
   - 包含失败原因

### 日志格式示例

```
2026-03-03 07:18:04 - INFO - 正在获取 CRM Cookie...
2026-03-03 07:18:05 - INFO - Cookie 获取成功，Session 已创建
2026-03-03 07:18:06 - INFO - [Sheet1] OE: ABC123, 品牌：盖茨，brand_id: 123
2026-03-03 07:18:07 - INFO -   → 获取 OE 信息：ABC123
2026-03-03 07:18:08 - INFO -   → OE 信息：product_name=水泵，vehicle_name=E300, brand_name=奔驰
2026-03-03 07:18:09 - INFO -   → 添加产品到 CRM
2026-03-03 07:18:10 - INFO -   ✓ 添加成功：{'status': 200, 'msg': 'success'}
```

## ⚙️ 配置选项

### 并发线程数
在 `main()` 函数中调整：

```python
max_workers = min(20, len(items))  # 默认最多 20 个线程
```

### 日志级别
在 `setup_logging()` 函数中调整：

```python
logging.basicConfig(
    level=logging.INFO,  # 可改为 DEBUG 获取更详细信息
    ...
)
```

## 🔧 技术细节

### 架构设计

```
┌─────────────────────────────────────┐
│     test_batch_process.py (主文件)    │
│  - 调用 get_crm_cookies() 获取 cookie │
│  - 创建统一的 Session 对象            │
│  - 将 Session 传递给各个模块          │
└──────────────┬──────────────────────┘
               │ Session (带 cookie)
       ┌───────┼───────────┐
       │       │           │
       ▼       ▼           ▼
  crm_brand  crm_get   crm_Product
    _id.py   oe_link.py   _Add.py
   (使用    (使用        (使用
   Session)  Session)     Session)
```

### API 调用流程

```
1. main() 调用 get_crm_cookies() → 获取认证 cookie
   ↓
2. 创建 requests.Session() 并注入 cookie
   ↓
3. 使用 session 获取品牌字典 {brand_id: l_name_zh}
   ↓
4. 反转字典 → {l_name_zh: brand_id}
   ↓
5. 对每条数据（并发处理，共享同一个 session）:
   - get_oe_link(oe_number, session) → 获取 OE 信息
   - create_product_entry(..., session) → 添加产品到 CRM
   ↓
6. 记录日志（请求参数 + 响应结果）
```

### 请求参数

添加到 CRM 的产品数据结构：

```python
{
    "number": oe_number,           # OE 编号
    "brand_id": brand_id,          # 品牌 ID
    "l_name_zh": product_name,     # 产品名称
    "l_name_zh_store": product_name,
    "cass_oebrand_name": brand_name,  # OE 品牌名称
    "l_model_zh": vehicle_name     # 车型
}
```

## ❗ 注意事项

1. **文件格式**：确保 Excel 文件格式正确，列名匹配
2. **网络环境**：需要能访问 `https://crm.gzbbr.com` 和 `http://113.45.176.129:8001`
3. **Cookie 有效性**：程序会自动获取 cookie，但如果频繁失败可能需要检查网络
4. **并发限制**：如果服务器压力大，可减少并发线程数
5. **数据备份**：建议先小批量测试，确认无误后再大批量处理

## 🐛 故障排除

### 常见问题

**Q: 提示"未找到品牌对应的 brand_id"**
A: 检查 Excel 中的品牌名称是否与 CRM 系统中的完全一致

**Q: 提示"获取 OE 信息失败"**
A: 检查 OE 编号是否正确，或网络连接是否正常

**Q: 大量请求失败**
A: 可能是并发太高，减少 `max_workers` 的值

**Q: Cookie 获取失败**
A: 检查是否能访问 `http://113.45.176.129:8001/get_crm_cookies`

**Q: Session 相关错误**
A: 检查 cookie 是否过期，重新运行程序会自动获取新的 cookie

## 📝 模块说明

### 主文件
- `test_batch_process.py`: 主程序入口，负责协调所有模块

### 功能模块
- `crm_brand_id.py`: 获取品牌列表，提供品牌 ID 映射
- `crm_get_oe_link.py`: 根据 OE 编号获取产品信息
- `crm_Product_Add.py`: 添加产品到 CRM 系统
- `crm_excel.py`: Excel 文件读取和列识别

### 配置模块
- `config/crm_config.py`: 获取 CRM cookie（由主文件调用）

## 💡 优势

### 统一 Session 管理的优点
1. **代码简洁**：不需要在每个模块中都获取 cookie
2. **性能更好**：只调用一次 cookie 接口，减少请求次数
3. **易于维护**：cookie 逻辑集中在主文件，修改方便
4. **资源复用**：所有请求共享同一个 session，连接池复用

## 📝 修改历史

- 2026-03-03: 
  - 初始版本，支持三列模式、并发处理
  - 采用统一 Session 管理，所有请求共享 cookie
