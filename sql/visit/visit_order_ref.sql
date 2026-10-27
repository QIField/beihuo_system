-- 客访-订单与拜访关联表（05-订单拜访关联模块设计.md 第二节）
-- 一次拜访关联多张订单（1:N），一张订单最多一条关联行（uk_orders_id），纯人工维护，取消=物理删除
CREATE TABLE IF NOT EXISTS visit_order_ref (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键',
    orders_id VARCHAR(255) NOT NULL COMMENT '订单标识=发货金蝶号(sales_order_history.deliverysapno)',
    record_id BIGINT NOT NULL COMMENT '关联拜访记录ID(visit_record.id)',
    matched_by VARCHAR(50) NOT NULL COMMENT '操作人(登录用户名)',
    remarks VARCHAR(255) DEFAULT NULL COMMENT '关联备注',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_orders_id (orders_id),
    INDEX idx_record_id (record_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='客访-订单与拜访关联表(一次拜访关联多张订单,纯人工维护)';
