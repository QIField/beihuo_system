# 销量表加载与状态 SQL（oe_parts_sales）

> 本文为 [13_销量表SQL文档](13_销量表SQL文档.md) 的续篇，覆盖写入 SQL 与辅助索引。

## 一、写入 SQL（batch_insert）

```sql
INSERT INTO oe_parts_sales (
    number, brand_name, pdname, frey_no,
    avg_daily_sales_1y, avg_monthly_sales_1y, annual_sales_1y,
    sales_this_year, sales_last_year, sales_std_dev_1y,
    monthly_sales_json, weekly_sales_json, stat_date
) VALUES (
    :number, :brand_name, :pdname, :frey_no,
    :avg_daily_sales_1y, :avg_monthly_sales_1y, :annual_sales_1y,
    :sales_this_year, :sales_last_year, :sales_std_dev_1y,
    :monthly_sales_json, :weekly_sales_json, :stat_date
);
```

程序层使用 `executemany` 分批执行（2000条/批）。

## 二、清空 SQL（truncate_table）

```sql
TRUNCATE TABLE oe_parts_sales;
```

清空并重置自增ID。**DDL 操作，隐式提交，不可回滚**。

## 三、辅助索引说明

- `sales_order_history`：idx_normal_cid / idx_normal_name（见 [03_退货关联表结构](03_退货关联表结构.md) 第四节）
- `stock_safe_refund_ref`：idx_normal_match(normal_order_items_id, match_count) 支撑 MAX 子查询与 NOT EXISTS
- `oe_parts_sales`：uk_number_brand 唯一键兼作关联键

[← 返回索引](README.md) | [← 上一页：销量表SQL文档](13_销量表SQL文档.md) | [→ 下一页：虚拟库存概念](15_虚拟库存概念.md)