-- OE零件销量统计表（oe_parts_sales）
-- 按OE号汇总的日/月/年销量数据，为安全库存计算提供基础数据支撑
-- 每日全量刷新，以number+brand_name为业务唯一键
-- 注意：abc_classification字段已移除，归属安全库存表（stock_safe）管理
CREATE TABLE IF NOT EXISTS `oe_parts_sales` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `number` VARCHAR(255) NOT NULL COMMENT 'OE号（即sales_order_history表number字段）：零件唯一标识',
    `brand_name` VARCHAR(255) DEFAULT NULL COMMENT '品牌名（即sales_order_history表brand_name字段）',
    `pdname` VARCHAR(255) DEFAULT NULL COMMENT '产品名称（即sales_order_history表pdname字段）',
    `frey_no` VARCHAR(255) DEFAULT NULL COMMENT '条码（即sales_order_history表frey_no字段）',
    `avg_daily_sales_1y` DECIMAL(12, 3) DEFAULT 0.000 COMMENT '日销量（近一年数据）：近一年平均日销量 = 近一年总销量 / 365，单位：个',
    `avg_monthly_sales_1y` DECIMAL(12, 3) DEFAULT 0.000 COMMENT '月销量（近一年数据）：近一年平均月销量 = 近一年总销量 / 12，单位：个',
    `annual_sales_1y` INT DEFAULT 0 COMMENT '年销量（近一年数据）：近一年（过去365天）总销量，单位：个',
    `sales_this_year` INT DEFAULT 0 COMMENT '今年销量：当前自然年（1月1日至统计日）总销量，单位：个',
    `sales_last_year` INT DEFAULT 0 COMMENT '上一年销量：上一个完整自然年总销量，单位：个',
    `sales_std_dev_1y` DECIMAL(12, 3) DEFAULT 0.000 COMMENT '近一年销量标准差（周标准差 σ_w）：基于近52周各周净销量计算，用于基础安全库存公式 SS = Z × σ_w × √(L/7)，其中 σ_w 为周销量总体标准差（ddof=0）',
    `monthly_sales_json` JSON DEFAULT NULL COMMENT '近12个月各月销量JSON：格式{"YYYY-MM": 数量, ...}，用于计算季节系数（当月销量/全年平均月销量），范围限制0.7~1.3',
    `weekly_sales_json` JSON DEFAULT NULL COMMENT '近52周各周销量JSON：格式{"YYYY-MM-DD": 数量, ...}，键为周起始日期，用于安全库存计算中的周标准差原始数据追溯',
    `stat_date` DATE DEFAULT NULL COMMENT '统计日期：数据统计的时间点，标识这批销量数据的截止日期',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '数据创建时间',
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '数据更新时间',
    PRIMARY KEY (`id`),
    -- 联合唯一键：oe_parts_sales 表以 (number, brand_name) 作为业务唯一键，每日全量刷新时据此去重
    UNIQUE KEY `uk_number_brand` (`number`, `brand_name`),
    -- 单字段索引：与 ORM 模型 __table_args__ 中定义的索引一一对应
    KEY `idx_brand_name` (`brand_name`),
    KEY `idx_frey_no` (`frey_no`),
    KEY `idx_stat_date` (`stat_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='OE零件销量统计表（按OE号汇总的日/月/年销量数据，为安全库存计算提供基础数据支撑；每日全量刷新，以number+brand_name为业务唯一键）';