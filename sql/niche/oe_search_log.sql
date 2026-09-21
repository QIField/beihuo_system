-- OE搜索日志表（oe_search_log）
-- 存储 CRM 系统中 Product.Product/oeSearchLog 接口返回的 OE 码搜索记录
-- 用于分析 OE 搜索热度、用户搜索行为等
-- 以 source_biz_id（源记录 ID）为唯一键，支持幂等写入
CREATE TABLE IF NOT EXISTS `oe_search_log` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `source_biz_id` VARCHAR(128) NOT NULL COMMENT '源业务记录ID（CRM日志id）',
    `brand_name` VARCHAR(255) DEFAULT NULL COMMENT '品牌名称',
    `product_name` VARCHAR(255) DEFAULT NULL COMMENT '产品名称',
    `oe_number` VARCHAR(255) DEFAULT NULL COMMENT 'OE号',
    `num` INT DEFAULT 0 COMMENT '返回的数据条数（搜索结果数量）这个字段暂时无用，但是保留',
    `search_time` DATETIME DEFAULT NULL COMMENT '搜索发生时间（CRM返回）',
    `search_date` VARCHAR(20) DEFAULT NULL COMMENT '搜索日期（YYYY-MM-DD，冗余方便按天统计）',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '数据创建时间',
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '数据更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_source_biz_id` (`source_biz_id`),
    KEY `idx_search_date` (`search_date`),
    KEY `idx_oe_number` (`oe_number`),
    KEY `idx_search_time` (`search_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='OE搜索日志表：CRM OE搜索记录，用于搜索热度分析';
