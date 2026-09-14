CREATE TABLE IF NOT EXISTS `stock_safe_refund_ref` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `normal_order_items_id` INT DEFAULT NULL COMMENT '常规订单明细ID（sales_order_history表orders_items_id），未匹配时为NULL',
    `refund_order_items_id` INT NOT NULL COMMENT '退货订单明细ID（sales_order_history表orders_items_id）',
    `number` VARCHAR(255) DEFAULT NULL COMMENT 'OE号（即sales_order_history表number字段）',
    `brand_name` VARCHAR(255) DEFAULT NULL COMMENT '品牌名（即sales_order_history表brand_name字段）',
    `pdname` VARCHAR(255) DEFAULT NULL COMMENT '产品名称（即sales_order_history表pdname字段）',
    `frey_no` VARCHAR(255) DEFAULT NULL COMMENT '条码（即sales_order_history表frey_no字段）',
    `customer_id` INT DEFAULT NULL COMMENT '客户ID（即sales_order_history表customer_id字段）',
    `normal_quantity` INT DEFAULT NULL COMMENT '常规订单数量',
    `refund_quantity` INT DEFAULT NULL COMMENT '退货订单数量',
    `refund_create_date` INT DEFAULT NULL COMMENT '退货订单创建时间戳（sales_order_history表create_date字段）',
    `processed_quantity` INT DEFAULT NULL COMMENT '处理数量（常规订单quantity + 退货订单quantity）',
    `match_count` INT DEFAULT 0 COMMENT '匹配次数（标识本条记录是第几次匹配产生的，同一订单多次匹配时递增；查询最新匹配状态时取MAX(match_count)）',
    `type` SMALLINT DEFAULT NULL COMMENT '类型（两位数编码）：十位=匹配状态[1=完全退货(processed_quantity=0)/2=部分退货(>0)/3=退货数量超出(<0)/4=未匹配/5=未进行匹配]，个位=匹配模式[1=一对一/2=一对多-常规订单视角/3=一对多-退货订单视角]。取值：11,12,13,21,22,23,31,32,33,40(第一次匹配step2未命中),41(第二次匹配step3仍未命中),50(未进行匹配)',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '数据创建时间',
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '数据更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_customer_id` (`customer_id`),
    KEY `idx_number` (`number`),
    KEY `idx_type` (`type`),
    KEY `idx_created_at` (`created_at`),
    -- 联合唯一索引：同一(常规订单, 退货订单)匹配组合唯一，支持一对多匹配（不同组合可重复）
    UNIQUE KEY `uk_normal_refund` (`normal_order_items_id`, `refund_order_items_id`),
    KEY `idx_match_count` (`match_count`),
    -- 复合索引：优化子查询 MAX(match_count) WHERE normal_order_items_id = ...
    KEY `idx_normal_match` (`normal_order_items_id`, `match_count`),
    -- 复合索引：优化子查询 MAX(match_count) WHERE refund_order_items_id = ...
   KEY `idx_refund_match` (`refund_order_items_id`, `match_count`),
    -- 匹配查询复合索引（与sales_order_history字段同名同义，前缀长度对齐idx_normal_cid）
   KEY `idx_match_refund` (
    `customer_id`,
    `frey_no`(50),
    `number`(60),
    `brand_name`(50),
    `type`,
    `refund_create_date`
),
    -- 类型+时间复合索引（对应sales_order_history的idx_order_type_date）
    KEY `idx_order_type_date` (`type`, `refund_create_date`),
    -- 复合索引：加速 NOT EXISTS 子查询中 normal_order_items_id + type 过滤
    KEY `idx_normal_type` (`normal_order_items_id`, `type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='安全库存退货关联表（支持一对多匹配，同一订单通过match_count区分多次匹配记录，type使用两位数编码标识匹配状态与模式）';
