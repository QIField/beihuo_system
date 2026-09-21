-- 商机表（niche_opportunity）
-- 基于微信询价数据预计算的商机结果，供前端商机看板展示与补货建议参考
-- 采用预计算存储模式（定时任务刷新），每日全量重写
-- 以 oe_code + stat_date 为业务唯一键
-- available_stock / transit_quantity 从 crmapp_beihuo 表实时获取（每日快照），使用 oe 字段匹配
--
-- 已有表升级脚本（MySQL）：
-- ALTER TABLE `niche_opportunity`
--   ADD COLUMN `brand_name` VARCHAR(255) DEFAULT NULL COMMENT '品牌名称（来自最近一条询价记录）' AFTER `part_name`,
--   ADD COLUMN `search_count_30d` INT DEFAULT 0 COMMENT '近30天OE搜索次数' AFTER `replenish_suggestion`,
--   ADD COLUMN `search_count_prev_30d` INT DEFAULT 0 COMMENT '上一个30天OE搜索次数' AFTER `search_count_30d`,
--   ADD COLUMN `search_score` DECIMAL(6,2) DEFAULT 0.00 COMMENT '搜索热度分（0~100）' AFTER `search_count_prev_30d`,
--   ADD COLUMN `inquiry_count_7d` INT DEFAULT 0 COMMENT '近7天询价次数' AFTER `search_score`;
--
-- 2026-09-19 下线搜索转化/搜索缺口分（OE 搜索由业务员发起，不能用于衡量客户需求缺口）
-- ALTER TABLE `niche_opportunity`
--   DROP COLUMN `search_to_inquiry_rate`,
--   DROP COLUMN `search_gap_score`;
CREATE TABLE IF NOT EXISTS `niche_opportunity` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `oe_code` VARCHAR(255) NOT NULL COMMENT 'OE码（产品标识）',
    `part_name` VARCHAR(255) DEFAULT NULL COMMENT '配件名称（冗余，取最近一条询价记录）',
    `brand_name` VARCHAR(255) DEFAULT NULL COMMENT '品牌名称（来自最近一条询价记录）',
    `inquiry_count_30d` INT DEFAULT 0 COMMENT '近30天询价次数',
    `inquiry_count_prev_30d` INT DEFAULT 0 COMMENT '上一个30天询价次数（用于趋势）',
    `inquiry_trend_rate` DECIMAL(6,4) DEFAULT 0.0000 COMMENT '询价趋势增长率',
    `out_of_stock_count_30d` INT DEFAULT 0 COMMENT '近30天缺货次数',
    `out_of_stock_rate_30d` DECIMAL(5,4) DEFAULT 0.0000 COMMENT '近30天缺货率',
    `customer_count_30d` INT DEFAULT 0 COMMENT '近30天询价客户数',
    `inquiry_score` DECIMAL(6,2) DEFAULT 0.00 COMMENT '询价热度分（0~100）',
    `out_of_stock_score` DECIMAL(6,2) DEFAULT 0.00 COMMENT '缺货强度分（0~100）',
    `customer_score` DECIMAL(6,2) DEFAULT 0.00 COMMENT '客户广度分（0~100）',
    `trend_score` DECIMAL(6,2) DEFAULT 0.00 COMMENT '需求趋势分（0~100）',
    `opportunity_score` DECIMAL(6,2) DEFAULT 0.00 COMMENT '综合商机评分（0~100）',
    `opportunity_level` VARCHAR(10) DEFAULT NULL COMMENT '商机等级（S/A/B/C/D）',
    `available_stock` INT DEFAULT 0 COMMENT '当前可用库存（来自 crmapp_beihuo）',
    `transit_quantity` INT DEFAULT 0 COMMENT '在途数量（来自 crmapp_beihuo）',
    `suggested_stock_qty` DECIMAL(10,2) DEFAULT 0.00 COMMENT '建议备货量',
    `replenish_suggestion` INT DEFAULT 0 COMMENT '建议补货数量（0表示无需补货）',
    `search_count_30d` INT DEFAULT 0 COMMENT '近30天OE搜索次数',
    `search_count_prev_30d` INT DEFAULT 0 COMMENT '上一个30天OE搜索次数',
    `search_score` DECIMAL(6,2) DEFAULT 0.00 COMMENT '搜索热度分（0~100）',
    `inquiry_count_7d` INT DEFAULT 0 COMMENT '近7天询价次数',
    `stat_date` VARCHAR(20) DEFAULT NULL COMMENT '统计日期，格式 YYYY-MM-DD',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '数据创建时间',
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '数据更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_oe_code_stat_date` (`oe_code`, `stat_date`),
    KEY `idx_opportunity_level` (`opportunity_level`),
    KEY `idx_out_of_stock_rate` (`out_of_stock_rate_30d`),
    KEY `idx_opportunity_score` (`opportunity_score`),
    KEY `idx_stat_date` (`stat_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='商机表：基于微信询价数据预计算的OE码维度商机结果，每日全量刷新；可用库存从 crmapp_beihuo 每日快照获取';
