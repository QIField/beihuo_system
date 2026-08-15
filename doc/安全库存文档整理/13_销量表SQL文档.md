# 销量表同步 SQL 文档（oe_parts_sales）

> 提供销量表同步任务可直接执行的 SQL 速查。
> 建表 DDL 见 [04_销量表结构](04_销量表结构.md)。

## 一、聚合抽取 SQL（fetch_aggregated_sales）

单次 SQL 完成"合并 + 分组 + 条件聚合"。月份/周度列由程序动态拼装参数。

```sql
SELECT
    t.number, t.brand_name,
    MAX(t.pdname) AS pdname, MAX(t.frey_no) AS frey_no,
    SUM(CASE WHEN t.create_date BETWEEN :one_year_ago_ts AND :stat_date_ts
             THEN t.net_qty ELSE 0 END) AS annual_sales_1y,
    SUM(CASE WHEN YEAR(FROM_UNIXTIME(t.create_date)) = :stat_year
             THEN t.net_qty ELSE 0 END) AS sales_this_year,
    SUM(CASE WHEN YEAR(FROM_UNIXTIME(t.create_date)) = :stat_year - 1
             THEN t.net_qty ELSE 0 END) AS sales_last_year,
    -- 12个月度列: month_1~month_12（动态拼装）
    SUM(CASE WHEN DATE_FORMAT(FROM_UNIXTIME(t.create_date), '%Y-%m') = :m1
             THEN t.net_qty ELSE 0 END) AS month_1,
    -- ... month_2~month_12 同构 ...
    -- 52周度列: week_1~week_52（动态拼装）
    SUM(CASE WHEN t.create_date BETWEEN :ws1 AND :we1
             THEN t.net_qty ELSE 0 END) AS week_1,
    -- ... week_2~week_52 同构 ...
FROM (
    -- 第一部分：无退货常规订单
    SELECT s.number, s.brand_name, s.pdname, s.frey_no,
           s.quantity AS net_qty, s.create_date
    FROM sales_order_history s
    WHERE s.order_type_id = 1
      AND s.number IS NOT NULL AND s.number != ''
      AND s.brand_name IS NOT NULL AND s.brand_name != ''
      AND s.quantity > 0
      AND s.create_date BETWEEN :one_year_ago_ts AND :stat_date_ts
      AND NOT EXISTS (
          SELECT 1 FROM stock_safe_refund_ref r
          WHERE r.normal_order_items_id = s.orders_items_id
            AND r.type IN :exclude_types
      )
    UNION ALL
    -- 第二部分：部分退货净额
    SELECT r.number, r.brand_name, r.pdname, r.frey_no,
           r.processed_quantity AS net_qty, h.create_date
    FROM stock_safe_refund_ref r
    JOIN sales_order_history h ON h.orders_items_id = r.normal_order_items_id
    WHERE r.type IN :residual_types
      AND r.processed_quantity > 0
      AND r.number IS NOT NULL AND r.number != ''
      AND r.brand_name IS NOT NULL AND r.brand_name != ''
      AND h.create_date BETWEEN :one_year_ago_ts AND :stat_date_ts
      AND r.match_count = (
          SELECT MAX(match_count) FROM stock_safe_refund_ref r2
          WHERE r2.normal_order_items_id = r.normal_order_items_id
      )
) t
GROUP BY t.number, t.brand_name
```

**参数**：`:stat_date_ts`（统计日结束时间戳）、`:stat_year`（统计年）、`:one_year_ago_ts`（12个月前第一天0点）、`:exclude_types`（11~33）、`:residual_types`（21,22）、`:m1~:m12`（12个月键）、`:ws1~:ws52`/`:we1~:we52`（52周起止时间戳）。

[← 返回索引](README.md) | [→ 下一页：加载与状态SQL](14_销量表加载与状态SQL.md)