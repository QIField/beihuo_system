-- 合并订单数据表
-- 表名: merge_order_list

CREATE TABLE IF NOT EXISTS merge_order_list (
    orders_id INT PRIMARY KEY COMMENT '主键ID',
    customer_id INT COMMENT '客户ID',
    level_id INT COMMENT '客户等级',
    is_wms INT COMMENT '是否WMS',
    sap_no VARCHAR(255) COMMENT '订单号',
    d_sap_no VARCHAR(255) COMMENT '金蝶单号',
    fullname VARCHAR(255) COMMENT '客户名称',
    customer_phone VARCHAR(50) COMMENT '电话',
    sku_num INT COMMENT 'SKU数',
    total_quantity INT COMMENT '产品件数',
    realqty INT COMMENT '实发件数',
    total_price DECIMAL(10,2) COMMENT '订单金额',
    sfje DECIMAL(10,2) COMMENT '实发金额',
    no_receive_amount DECIMAL(10,2) COMMENT '未结算金额',
    status INT COMMENT '订单状态',
    order_type_id INT COMMENT '订单类型',
    order_source_name INT COMMENT '业务类型',
    handler VARCHAR(255) COMMENT '经手人',
    create_date INT COMMENT '创建时间（秒级时间戳）',
    user_id VARCHAR(255) COMMENT '创建人',
    remark TEXT COMMENT '备注',
    street VARCHAR(500) COMMENT '街道地址',
    warehouse VARCHAR(255) COMMENT '仓库',
    order_error TEXT COMMENT '订单错误信息',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '数据创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '数据更新时间',
    INDEX idx_orders_id (orders_id),
    INDEX idx_d_sap_no (d_sap_no),
    INDEX idx_customer_id (customer_id),
    INDEX idx_status (status),
    INDEX idx_create_date (create_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='合并订单数据表';

