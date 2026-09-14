-- 应收单列表数据表
-- 表名: account_receivable_list

CREATE TABLE IF NOT EXISTS account_receivable_list (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    receipt_no VARCHAR(255) UNIQUE COMMENT '单据编号',
    receipt_status VARCHAR(50) COMMENT '单据状态',
    customer_name VARCHAR(255) COMMENT '客户',
    tax_total_amount DECIMAL(10, 2) COMMENT '价税合计',
    total_amount DECIMAL(10, 2) COMMENT '总金额',
    received_amount DECIMAL(10, 2) COMMENT '已收款金额',
    customer_code VARCHAR(255) COMMENT '客户编码',
    partner_id INT COMMENT '合作伙伴ID（数据回填专用）',
    business_date VARCHAR(50) COMMENT '业务日期',
    due_date VARCHAR(50) COMMENT '到期日',
    payment_terms VARCHAR(255) COMMENT '收款条件',
    payment_org VARCHAR(255) COMMENT '收款组织',
    salesperson VARCHAR(255) COMMENT '销售员',
    remark TEXT COMMENT '备注',
    customer_group VARCHAR(255) COMMENT '客户分组',
    creator VARCHAR(255) COMMENT '创建人',
    create_date VARCHAR(50) COMMENT '创建日期',
    payment_type VARCHAR(255) COMMENT '支付类型',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '数据创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '数据更新时间',
    INDEX idx_receipt_no (receipt_no),
    INDEX idx_customer_name (customer_name),
    INDEX idx_customer_code (customer_code),
    INDEX idx_partner_id (partner_id),
    INDEX idx_create_date (create_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='应收单列表数据表';
