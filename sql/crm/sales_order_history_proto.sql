-- 销售订单历史原始数据表
-- 表名: sales_order_history_proto

CREATE TABLE IF NOT EXISTS sales_order_history_proto (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    time_batch_id VARCHAR(255) COMMENT '时间批次ID',
    batch_id VARCHAR(255) COMMENT '批次ID',
    sales_order_id VARCHAR(255) COMMENT '销售订单ID',
    orders_items_id VARCHAR(255) COMMENT '订单商品ID',
    json_text TEXT COMMENT '原始JSON文本',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_sales_order_id (sales_order_id),
    INDEX idx_orders_items_id (orders_items_id),
    INDEX idx_time_batch_id (time_batch_id),
    INDEX idx_batch_id (batch_id),
    INDEX idx_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='销售订单历史原始数据表';
