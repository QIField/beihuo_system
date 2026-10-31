-- ------------------------------------------------------------
-- 客访管理 - 拜访费用明细表（visit_expense）
-- 设计文档: doc/客访管理/09-费用分析.md
-- 说明:
--   1. 一条记录 = 一次具体消费（如 "2026-10-29 样品费 ¥320"）；
--   2. 关联锚点: source_type 区分关联来源（1-拜访记录 visit_record / 2-跟进记录 visit_follow_record /
--      3-订单关联 crm_sales_order / 4-手动输入），source_id 为对应记录主键；
--      一条费用只能关联其中一个；source_type=4（手动输入）时 source_id 为空；
--   3. amap_customer_id 冗余存储高德客户 POI 编码，按客户/时间维度直接索引，
--      避免费用分析页每次跨表 JOIN；CRM 关联通过 visit_customer_relation 桥接查询，
--      本表不冗余 partner_id；
--   4. expense_type 为自由填写文本（VARCHAR(50)），不做枚举/字典表约束，
--      让业务自行约定分类口径；
--   5. 软作废（status=0），作废后不计入统计；无业务唯一键（费用是事实数据，不做自动去重）。
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS visit_expense (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键，自增',
    source_type TINYINT NOT NULL COMMENT '关联来源类型: 1-拜访记录(visit_record) 2-跟进记录(visit_follow_record) 3-订单(crm_sales_order.orders_id) 4-手动输入',
    source_id BIGINT DEFAULT NULL COMMENT '关联记录ID(记录主键或crm_sales_order.orders_id); source_type=4时为空',
    amap_customer_id VARCHAR(128) NOT NULL COMMENT '高德客户POI编码(冗余,visit_amap_customer.amap_poi_id)',
    expense_date DATE NOT NULL COMMENT '费用发生日期',
    expense_type VARCHAR(50) NOT NULL COMMENT '费用类型(自由填写文本,不做枚举校验)',
    amount DECIMAL(12, 2) NOT NULL COMMENT '金额(元),>0',
    description VARCHAR(500) DEFAULT NULL COMMENT '费用说明/备注',
    recorder_id INT NOT NULL COMMENT '录入人ID(crmapp_users.id)',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '1-正常 0-作废',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    INDEX idx_source (source_type, source_id),
    INDEX idx_amap_customer_date (amap_customer_id, expense_date),
    INDEX idx_expense_type (expense_type),
    INDEX idx_recorder (recorder_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='客访-拜访费用明细表';

-- ------------------------------------------------------------
-- 存量表迁移（已有 visit_expense 的库执行；新库直接用上面的建表语句）
-- 注意: amap_customer_id 若存在 NULL 行需先补齐再执行 NOT NULL 迁移
-- ------------------------------------------------------------
-- UPDATE visit_expense SET source_type = 4 WHERE source_type IS NULL;
-- ALTER TABLE visit_expense
--     MODIFY COLUMN source_type TINYINT NOT NULL COMMENT '关联来源类型: 1-拜访记录(visit_record) 2-跟进记录(visit_follow_record) 3-订单(crm_sales_order.orders_id) 4-手动输入',
--     MODIFY COLUMN source_id BIGINT DEFAULT NULL COMMENT '关联记录ID(记录主键或crm_sales_order.orders_id); source_type=4时为空',
--     MODIFY COLUMN amap_customer_id VARCHAR(128) NOT NULL COMMENT '高德客户POI编码(冗余,visit_amap_customer.amap_poi_id)';
