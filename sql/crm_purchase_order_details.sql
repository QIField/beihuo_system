-- 创建采购订单明细表
-- 表名: crm_purchase_order_details
-- 说明: 存储采购订单的明细商品信息

CREATE TABLE IF NOT EXISTS `crm_purchase_order_details` (
    `purchase_order_line_id` BIGINT NOT NULL COMMENT '订单明细ID',
    `purchase_order_id` BIGINT NULL COMMENT '采购订单ID',
    `no` INT NULL COMMENT '明细序号',
    `product_id` BIGINT NULL COMMENT '产品ID',
    `number` VARCHAR(100) NULL COMMENT '产品编号',
    `l_model_zh` TEXT NULL COMMENT '适用车型',
    `brand` VARCHAR(100) NULL COMMENT '品牌名称',
    `l_name_zh` VARCHAR(255) NULL COMMENT '产品名称',
    `brand_code` VARCHAR(100) NULL COMMENT '品牌代码',
    `frey_no` VARCHAR(100) NULL COMMENT 'Frey编号',
    `user_code` VARCHAR(100) NULL COMMENT '用户编码',
    `unit` VARCHAR(20) NULL COMMENT '单位',
    `purchase_quantity` DECIMAL(12, 2) NULL COMMENT '采购数量',
    `price` DECIMAL(12, 2) NULL COMMENT '单价',
    `amount_money` DECIMAL(12, 2) NULL COMMENT '金额小计',
    `unit_cost` DECIMAL(12, 2) NULL COMMENT '单位成本',
    `received_quantity` DECIMAL(12, 2) NULL COMMENT '已收货数量',
    `gift` INT NULL COMMENT '是否赠品',
    `shipping_fee` DECIMAL(10, 2) NULL COMMENT '运费',
    `unit_shipping_fee` DECIMAL(10, 2) NULL COMMENT '单位运费',
    `packing_fee` DECIMAL(10, 2) NULL COMMENT '包装费',
    `unit_packing_fee` DECIMAL(10, 2) NULL COMMENT '单位包装费',
    `delivery_date` VARCHAR(255) NULL COMMENT '交货日期',
    `company_remark` TEXT NULL COMMENT '公司备注',
    `is_unsalable` INT NULL COMMENT '是否滞销',
    `ks_price` VARCHAR(50) NULL COMMENT '开思价',
    `store` VARCHAR(50) NULL COMMENT '门店',
    `created_at` DATETIME NULL DEFAULT CURRENT_TIMESTAMP COMMENT '数据创建时间',
    `updated_at` DATETIME NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '数据更新时间',
    PRIMARY KEY (`purchase_order_line_id`),
    INDEX `idx_purchase_order_id` (`purchase_order_id`),
    INDEX `idx_product_id` (`product_id`),
    INDEX `idx_number` (`number`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='采购订单明细表';
