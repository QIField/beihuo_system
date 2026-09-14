-- 安全库存表（stock_safe）
-- 存储安全库存计算结果与库存状态，供前端展示
-- 采用预计算存储模式（定时任务刷新），每日全量重写
-- 以number+brand_name+frey_no为业务唯一键，与销量表（oe_parts_sales）关联
-- available_stock 从 crmapp_beihuo 表实时获取（每日快照），使用 number、brand_name、frey_no 三字段匹配
CREATE TABLE IF NOT EXISTS `stock_safe` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `number` VARCHAR(255) NOT NULL COMMENT 'OE号，关联销量表',
    `brand_name` VARCHAR(255) NOT NULL COMMENT '品牌名，与number共同唯一',
    `frey_no` VARCHAR(255) NOT NULL COMMENT '条码，与number、brand_name共同唯一',
    `pdname` VARCHAR(255) DEFAULT NULL COMMENT '产品名称（冗余）',
    `abc_classification` CHAR(1) DEFAULT NULL COMMENT 'ABC分类（A/B/C），决定Z系数与覆盖天数',
    `avg_daily_sales` DECIMAL(12, 3) DEFAULT 0.000 COMMENT '平均日销量（从销量表同步）',
    `base_safety_stock` DECIMAL(12, 3) DEFAULT 0.000 COMMENT '基础安全库存：Z系数 × 销量标准差 × 补货周期',
    `season_coefficient` DECIMAL(4, 3) DEFAULT 1.000 COMMENT '季节系数（范围0.7~1.3）',
    `safety_stock` DECIMAL(12, 3) DEFAULT 0.000 COMMENT '调整后安全库存：基础安全库存 × 季节系数',
    `stock_lower_limit` DECIMAL(12, 3) DEFAULT 0.000 COMMENT '库存下限：平均日销量 × 补货周期 + 安全库存',
    `stock_upper_limit` DECIMAL(12, 3) DEFAULT 0.000 COMMENT '库存上限：平均日销量 × (补货周期 + 覆盖天数) + 安全库存',
    `available_stock` INT DEFAULT 0 COMMENT '可用库存：每日快照从crmapp_beihuo表获取，使用number+brand_name+frey_no匹配',
    `transit_quantity` INT DEFAULT 0 COMMENT '在途数量：从crmapp_beihuo表同步',
    `sellable_days` DECIMAL(12, 3) DEFAULT 0.000 COMMENT '可卖天数：可用库存 / 平均日销量',
    `stock_status` VARCHAR(20) DEFAULT NULL COMMENT '库存状态：呆滞清库/慢动销去库/库存积压/需补货/紧急补货/库存正常',
    `sales_status` VARCHAR(20) DEFAULT NULL COMMENT '销售状态：无销售/销量低/销量正常',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '数据创建时间',
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '数据更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_number_brand_frey` (`number`, `brand_name`, `frey_no`),
    KEY `idx_abc_classification` (`abc_classification`),
    KEY `idx_stock_status` (`stock_status`),
    KEY `idx_brand_name` (`brand_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='安全库存表：存储安全库存计算结果与库存状态，供前端展示；available_stock从crmapp_beihuo每日快照获取';