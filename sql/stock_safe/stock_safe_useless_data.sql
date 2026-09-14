-- 安全库存无效数据记录表（stock_safe_useless_data）
-- 用于记录在安全库存计算/处理流程中判定为无效、需要排除的零件数据
-- 典型场景：数据缺失、格式异常、长期无销售且库存异常等被人工或算法标记的记录
-- 以 (number, brand_name, pdname) 为业务唯一键，防止重复插入同一条无效记录
CREATE TABLE IF NOT EXISTS `stock_safe_useless_data` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `number` VARCHAR(255) NOT NULL COMMENT 'OE号，零件唯一标识',
    `brand_name` VARCHAR(255) NOT NULL COMMENT '品牌名，与number、pdname共同唯一',
    `frey_no` VARCHAR(255) NOT NULL COMMENT '条码，与number、brand_name共同唯一',
    `pdname` VARCHAR(255) DEFAULT NULL COMMENT '产品名称，与number、brand_name共同唯一',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '数据创建时间',
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '数据更新时间',
    PRIMARY KEY (`id`),
    -- 联合唯一索引：number + brand_name + pdname 三字段共同唯一，避免重复插入同一条无效记录
    UNIQUE KEY `uk_number_brand_pdname` (`number`, `brand_name`, `pdname`),
    -- 唯一索引：条码单独唯一
    UNIQUE KEY `uk_frey_no` (`frey_no`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='安全库存无效数据记录表：存储被判定为无效/需排除的零件数据，以number+brand_name+pdname为联合唯一键，frey_no单独唯一';
