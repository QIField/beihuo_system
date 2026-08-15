# 02 销量表 `oe_parts_sales` 结构定义

**定位**：安全库存计算的数据来源，存储按 (OE号, 品牌) 汇总的净销量统计。

## 2.1 字段说明

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| id | BIGINT UNSIGNED, PK, AUTO_INCREMENT | - | 主键ID |
| oe | VARCHAR(255), NOT NULL | - | OE号：零件唯一标识（来源 sales_order_history.number / stock_safe_refund_ref.oe） |
| brand_name | VARCHAR(255), NOT NULL | - | 品牌名（来源 sales_order_history.brand_name / stock_safe_refund_ref.brand_name）。同一 OE 号可有多个品牌，与 oe 共同构成唯一键 |
| product_name | VARCHAR(255) | NULL | 产品名称（来源 sales_order_history.pdname / stock_safe_refund_ref.product_name） |
| barcode | VARCHAR(255) | NULL | 条码（来源 sales_order_history.frey_no / stock_safe_refund_ref.barcode） |
| avg_daily_sales_1y | DECIMAL(12,2) | 0.00 | 日销量（近一年数据）：近一年平均日净销量 = 近一年总净销量 / 365，单位：个 |
| avg_monthly_sales_1y | DECIMAL(12,2) | 0.00 | 月销量（近一年数据）：近一年平均月净销量 = 近一年总净销量 / 12，单位：个 |
| annual_sales_1y | INT | 0 | 年销量（近一年数据）：近一年（过去365天）总净销量，单位：个 |
| sales_this_year | INT | 0 | 今年销量：当前自然年（1月1日至统计日）总净销量，单位：个 |
| sales_last_year | INT | 0 | 上一年销量：上一个完整自然年总净销量，单位：个 |
| sales_std_dev_1y | DECIMAL(12,2) | 0.00 | 近一年销量标准差：基于近12个月各月净销量计算，用于基础安全库存公式（Z系数 × 标准差 × 补货周期） |
| monthly_sales_json | JSON | NULL | 近12个月各月净销量JSON：格式 `{"YYYY-MM": 数量, ...}`，用于计算季节系数（当月销量/全年平均月销量），范围限制 0.7~1.3 |
| created_at | DATETIME | CURRENT_TIMESTAMP | 数据创建时间 |
| updated_at | DATETIME | CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | 数据更新时间 |

> **净销量说明**：以上销量统计字段均基于[净销量计算逻辑](01_设计概述与销量计算.md#14-销量数据来源与计算逻辑)：先按 (oe, brand_name) 计算每个常规订单的净销量（无退货取 quantity，部分退货取 processed_quantity，完全退货为 0），再按日/月/年聚合。

## 2.2 相比原表的变更

| 变更项 | 说明 |
|--------|------|
| 移除 `abc_classification` | 迁移至安全库存表（属库存管控参数，非销量属性） |
| 移除 `stat_date` | 数据时效由 `updated_at` 体现，无需统计日期 |
| 唯一键由 `uk_oe` 改为 `uk_oe_brand (oe, brand_name)` | 同一 OE 号有多个品牌，需 (oe, brand_name) 共同唯一 |
| `brand_name` 改为 NOT NULL | 作为唯一键组成部分，不可为空 |

## 2.3 索引设计

| 索引名 | 类型 | 字段 | 用途 |
|--------|------|------|------|
| PRIMARY | 主键 | id | 主键 |
| uk_oe_brand | 唯一 | oe, brand_name | (OE号, 品牌) 联合唯一，防重复；兼作与安全库存表的关联键 |
| idx_brand_name | 普通 | brand_name | 按品牌筛选 |
| idx_barcode | 普通 | barcode | 按条码筛选 |

## 2.4 建表语句（草案）

```sql
CREATE TABLE IF NOT EXISTS `oe_parts_sales` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `oe` VARCHAR(255) NOT NULL COMMENT 'OE号：零件唯一标识（来源 sales_order_history.number / stock_safe_refund_ref.oe）',
    `brand_name` VARCHAR(255) NOT NULL COMMENT '品牌名（来源 sales_order_history.brand_name / stock_safe_refund_ref.brand_name），同一OE号可有多个品牌，与oe共同构成唯一键',
    `product_name` VARCHAR(255) DEFAULT NULL COMMENT '产品名称（来源 sales_order_history.pdname / stock_safe_refund_ref.product_name）',
    `barcode` VARCHAR(255) DEFAULT NULL COMMENT '条码（来源 sales_order_history.frey_no / stock_safe_refund_ref.barcode）',
    `avg_daily_sales_1y` DECIMAL(12, 2) DEFAULT 0.00 COMMENT '日销量（近一年数据）：近一年平均日净销量 = 近一年总净销量 / 365，单位：个',
    `avg_monthly_sales_1y` DECIMAL(12, 2) DEFAULT 0.00 COMMENT '月销量（近一年数据）：近一年平均月净销量 = 近一年总净销量 / 12，单位：个',
    `annual_sales_1y` INT DEFAULT 0 COMMENT '年销量（近一年数据）：近一年（过去365天）总净销量，单位：个',
    `sales_this_year` INT DEFAULT 0 COMMENT '今年销量：当前自然年（1月1日至统计日）总净销量，单位：个',
    `sales_last_year` INT DEFAULT 0 COMMENT '上一年销量：上一个完整自然年总净销量，单位：个',
    `sales_std_dev_1y` DECIMAL(12, 2) DEFAULT 0.00 COMMENT '近一年销量标准差：基于近12个月各月净销量计算，用于基础安全库存公式（Z系数 × 标准差 × 补货周期）',
    `monthly_sales_json` JSON DEFAULT NULL COMMENT '近12个月各月净销量JSON：格式{"YYYY-MM": 数量, ...}，用于计算季节系数（当月销量/全年平均月销量），范围限制0.7~1.3',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '数据创建时间',
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '数据更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_oe_brand` (`oe`, `brand_name`),
    KEY `idx_brand_name` (`brand_name`),
    KEY `idx_barcode` (`barcode`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='OE零件销量统计表：按(OE号,品牌)汇总的日/月/年净销量数据，为安全库存计算提供基础数据支撑。净销量来源于sales_order_history（无退货常规订单）与stock_safe_refund_ref（type=21/22部分退货净额），支持季节系数计算';
```

## 2.5 销量计算逻辑（说明性，非落地代码）

> 以下伪SQL仅用于说明净销量聚合逻辑，实际实现见 [oe_parts_sales生成流程](../oe_parts_sales生成流程.md)。

**步骤1：计算每个常规订单的净销量**

```sql
-- 第一部分：无退货的常规订单，净销量 = quantity
SELECT
    s.number AS oe, s.brand_name, s.pdname AS product_name, s.frey_no AS barcode,
    s.quantity AS net_quantity, s.create_date, s.orders_items_id
FROM sales_order_history s
WHERE s.order_type_id = 1
  AND NOT EXISTS (
      SELECT 1 FROM stock_safe_refund_ref r
      WHERE r.normal_order_items_id = s.orders_items_id
  )

UNION ALL

-- 第二部分：部分退货的常规订单（type=21/22 最新记录），净销量 = processed_quantity
SELECT
    r.oe, r.brand_name, r.product_name, r.barcode,
    r.processed_quantity AS net_quantity,
    NULL AS create_date,   -- 需JOIN sales_order_history 取常规订单 create_date
    r.normal_order_items_id
FROM stock_safe_refund_ref r
WHERE r.type IN (21, 22)
  AND r.match_count = (
      SELECT MAX(match_count) FROM stock_safe_refund_ref r2
      WHERE r2.normal_order_items_id = r.normal_order_items_id
  )
```

**步骤2：按 (oe, brand_name) 与时间维度聚合**，计算 avg_daily_sales_1y、avg_monthly_sales_1y、annual_sales_1y、sales_this_year、sales_last_year、sales_std_dev_1y、monthly_sales_json，upsert 入 oe_parts_sales。

---

[← 返回索引](README.md) | [下一页：安全库存表 →](03_安全库存表_stock_safe.md)
