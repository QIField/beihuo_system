
CREATE TABLE IF NOT EXISTS `stock_safe_sync_queue` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
    `number` VARCHAR(255) NOT NULL COMMENT 'OE号（CRM匹配键）',
    `brand_name` VARCHAR(255) NOT NULL COMMENT '品牌名（CRM匹配键）',
    `frey_no` VARCHAR(255) DEFAULT NULL COMMENT '条码（取自stock_safe第一条，仅供参考）',
    `pdname` VARCHAR(255) DEFAULT NULL COMMENT '产品名称（冗余展示）',
    `sync_enabled` TINYINT NOT NULL DEFAULT 1 COMMENT '是否开启同步：1=开启，0=关闭',
    `synced_at` DATETIME DEFAULT NULL COMMENT '最后一次成功同步时间',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_number_brand` (`number`, `brand_name`),
    KEY `idx_number_brand` (`number`, `brand_name`),
    KEY `idx_synced_at` (`synced_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='安全库存同步CRM队列表';
