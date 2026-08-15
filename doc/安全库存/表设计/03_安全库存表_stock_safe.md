# 03 安全库存表 `stock_safe` 结构定义

**定位**：前端展示用，存储安全库存计算结果与库存状态。采用 **预计算存储** 模式（定时任务刷新计算值），以提升前端查询性能。

## 3.1 字段说明

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| id | BIGINT UNSIGNED, PK, AUTO_INCREMENT | - | 主键ID |
| oe | VARCHAR(255), NOT NULL | - | OE号：关联销量表（与 brand_name 共同唯一） |
| brand_name | VARCHAR(255), NOT NULL | - | 品牌名（冗余，便于前端展示与筛选；与 oe 共同构成唯一键） |
| product_name | VARCHAR(255) | NULL | 产品名称（冗余展示字段） |
| barcode | VARCHAR(255) | NULL | 条码（冗余展示字段） |
| abc_classification | CHAR(1) | NULL | ABC分类（A/B/C），决定Z系数与覆盖天数 |
| avg_daily_sales | DECIMAL(12,2) | 0.00 | 平均日销量（从销量表 avg_daily_sales_1y 同步），用于下限/上限/可卖天数计算 |
| base_safety_stock | DECIMAL(12,2) | 0.00 | 基础安全库存 = Z系数 × 销量标准差 × 补货周期 |
| season_coefficient | DECIMAL(4,2) | 1.00 | 季节系数（范围 0.7~1.3） |
| safety_stock | DECIMAL(12,2) | 0.00 | 调整后安全库存 = 基础安全库存 × 季节系数 |
| stock_lower_limit | DECIMAL(12,2) | 0.00 | 库存下限（再订货点）= 平均日销量 × 补货周期 + 安全库存 |
| stock_upper_limit | DECIMAL(12,2) | 0.00 | 库存上限（目标库存）= 平均日销量 × (补货周期 + 覆盖天数) + 安全库存 |
| available_stock | INT | 0 | 可用库存（⚠️ 数据来源待确认，见[待确认事项](06_待确认事项与公式自检.md)） |
| sellable_days | DECIMAL(12,2) | 0.00 | 可卖天数 = 可用库存 / 平均日销量 |
| stock_status | VARCHAR(20) | '正常' | 库存状态：需补货 / 库存偏低 / 库存积压 / 正常 |
| created_at | DATETIME | CURRENT_TIMESTAMP | 数据创建时间 |
| updated_at | DATETIME | CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | 数据更新时间 |

## 3.2 字段与公式对应关系

| test.md 公式 | 对应字段 | 输入来源 |
|-------------|---------|---------|
| 基础安全库存 = Z系数 × 销量标准差 × 补货周期 | `base_safety_stock` | Z系数（按ABC全局配置）、销量标准差（销量表 `sales_std_dev_1y`）、补货周期（全局配置=1天） |
| 季节系数 = 当月销量 / 全年平均月销量 | `season_coefficient` | 当月销量（销量表 `monthly_sales_json` 取当月）、全年平均月销量（销量表 `avg_monthly_sales_1y`） |
| 调整后安全库存 = 基础安全库存 × 季节系数 | `safety_stock` | `base_safety_stock` × `season_coefficient` |
| 库存下限 = 平均日销量 × 补货周期 + 安全库存 | `stock_lower_limit` | `avg_daily_sales`、补货周期、`safety_stock` |
| 库存上限 = 平均日销量 × (补货周期 + 覆盖天数) + 安全库存 | `stock_upper_limit` | `avg_daily_sales`、补货周期、覆盖天数（按ABC全局配置）、`safety_stock` |
| 可卖天数 = 可用库存 / 平均日销量 | `sellable_days` | `available_stock` / `avg_daily_sales` |
| 库存状态判定 | `stock_status` | `sellable_days`、补货周期、预警天数、`available_stock`、`stock_upper_limit`、积压阈值 |

## 3.3 库存状态判定逻辑（对应 test.md）

```
if 可卖天数 <= 补货周期(1天):
    stock_status = "需补货"      # 立即补货，防止断货
elif 可卖天数 <= 预警天数(3天):
    stock_status = "库存偏低"    # 关注并准备补货
elif 可用库存 > 库存上限 × 积压阈值(1.3):
    stock_status = "库存积压"    # 库存过多，考虑促销
else:
    stock_status = "正常"        # 库存健康
```

## 3.4 索引设计

| 索引名 | 类型 | 字段 | 用途 |
|--------|------|------|------|
| PRIMARY | 主键 | id | 主键 |
| uk_oe_brand | 唯一 | oe, brand_name | (OE号, 品牌) 联合唯一，关联销量表 |
| idx_abc_classification | 普通 | abc_classification | 按 ABC 分类筛选 |
| idx_stock_status | 普通 | stock_status | 按库存状态筛选（预警看板） |
| idx_brand_name | 普通 | brand_name | 按品牌筛选 |

## 3.5 建表语句（草案）

```sql
CREATE TABLE IF NOT EXISTS `stock_safe` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `oe` VARCHAR(255) NOT NULL COMMENT 'OE号：关联销量表oe_parts_sales（与brand_name共同唯一）',
    `brand_name` VARCHAR(255) NOT NULL COMMENT '品牌名（冗余，便于前端展示与筛选；与oe共同构成唯一键）',
    `product_name` VARCHAR(255) DEFAULT NULL COMMENT '产品名称（冗余展示字段）',
    `barcode` VARCHAR(255) DEFAULT NULL COMMENT '条码（冗余展示字段）',
    `abc_classification` CHAR(1) DEFAULT NULL COMMENT 'ABC分类（A/B/C），对应安全库存配置参数：A类Z系数1.5/覆盖10天，B类Z系数1.2/覆盖20天，C类Z系数0.8/覆盖30天',
    `avg_daily_sales` DECIMAL(12, 2) DEFAULT 0.00 COMMENT '平均日销量（从销量表avg_daily_sales_1y同步），用于库存下限/上限/可卖天数计算',
    `base_safety_stock` DECIMAL(12, 2) DEFAULT 0.00 COMMENT '基础安全库存 = Z系数 × 销量标准差 × 补货周期',
    `season_coefficient` DECIMAL(4, 2) DEFAULT 1.00 COMMENT '季节系数 = 当月销量 / 全年平均月销量，范围限制0.7~1.3',
    `safety_stock` DECIMAL(12, 2) DEFAULT 0.00 COMMENT '调整后安全库存 = 基础安全库存 × 季节系数',
    `stock_lower_limit` DECIMAL(12, 2) DEFAULT 0.00 COMMENT '库存下限（再订货点）= 平均日销量 × 补货周期 + 安全库存',
    `stock_upper_limit` DECIMAL(12, 2) DEFAULT 0.00 COMMENT '库存上限（目标库存）= 平均日销量 × (补货周期 + 覆盖天数) + 安全库存',
    `available_stock` INT DEFAULT 0 COMMENT '可用库存（数据来源待确认，见设计文档待确认事项）',
    `sellable_days` DECIMAL(12, 2) DEFAULT 0.00 COMMENT '可卖天数 = 可用库存 / 平均日销量',
    `stock_status` VARCHAR(20) DEFAULT '正常' COMMENT '库存状态：需补货/库存偏低/库存积压/正常',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '数据创建时间',
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '数据更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_oe_brand` (`oe`, `brand_name`),
    KEY `idx_abc_classification` (`abc_classification`),
    KEY `idx_stock_status` (`stock_status`),
    KEY `idx_brand_name` (`brand_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='安全库存表：存储按(OE号,品牌)的安全库存计算结果与库存状态，供前端展示。通过(oe,brand_name)关联销量表oe_parts_sales';
```

---

[← 返回索引](README.md) | [上一页：销量表 ←](02_销量表_oe_parts_sales.md) | [下一页：数据关系 →](04_数据关系与同步流程.md)
