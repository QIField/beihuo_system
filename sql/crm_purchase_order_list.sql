-- 采购订单数据表
-- 表名: purchase_order_list

CREATE TABLE IF NOT EXISTS crm_purchase_order_list (
    purchase_order_id BIGINT PRIMARY KEY COMMENT '采购订单ID',
    pono VARCHAR(100) COMMENT '采购单号',
    partner_id BIGINT COMMENT '供应商ID',
    fullname VARCHAR(255) COMMENT '供应商名称',
    supplier_phone VARCHAR(50) COMMENT '供应商电话',
    status INT COMMENT '订单状态',
    order_type_id INT COMMENT '订单类型',
    order_source_type INT COMMENT '订单来源类型',
    total INT COMMENT '商品总数量',
    amount_money DECIMAL(12,2) COMMENT '订单总金额',
    received_quantity DECIMAL(12,2) COMMENT '已收货数量',
    received DECIMAL(12,2) COMMENT '已收货金额',
    shipping_fee DECIMAL(10,2) COMMENT '运费',
    packing_fee DECIMAL(10,2) COMMENT '包装费',
    create_date VARCHAR(255) COMMENT '创建时间',
    expected_delivery_date VARCHAR(255) COMMENT '预计交货时间',
    e_date VARCHAR(255) COMMENT '实际完成时间',
    name VARCHAR(255) COMMENT '操作人',
    payment_description VARCHAR(255) COMMENT '支付方式描述',
    is_wms INT COMMENT '是否WMS订单',
    store VARCHAR(50) COMMENT '门店',
    remarks TEXT COMMENT '备注',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '数据创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '数据更新时间',
    INDEX idx_purchase_order_id (purchase_order_id),
    INDEX idx_pono (pono),
    INDEX idx_partner_id (partner_id),
    INDEX idx_status (status),
    INDEX idx_create_date (create_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='采购订单数据表';
