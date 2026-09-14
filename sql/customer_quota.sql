-- 客户额度表
-- 表名: customer_quota
-- 用于管理客户的交易额度和授信额度

CREATE TABLE IF NOT EXISTS customer_quota (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID，自增，无业务含义',
    partner_id INT NOT NULL COMMENT '合作伙伴ID，唯一键，关联partner_list.partner_id',
    remenber_code VARCHAR(255) COMMENT '客户编码，外键，关联partner_list.remenber_code',
    fullname VARCHAR(255) COMMENT '客户名称',
    max_trade_quota DECIMAL(16, 2) NOT NULL DEFAULT 0.00 COMMENT '客户交易额度（累计交易额上限）',
    credit_quota DECIMAL(16, 2) NOT NULL DEFAULT 0.00 COMMENT '客户授信总额度（最大可欠款额度）',
    quota_status VARCHAR(20) NOT NULL DEFAULT 'normal' COMMENT '额度状态：normal-正常，frozen-冻结，restricted-限制使用，expired-已过期',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
    remark TEXT COMMENT '备注（额度调整说明、风控记录）',
    operator VARCHAR(50) COMMENT '最后操作人（管理员姓名/ID）',
    is_deleted TINYINT NOT NULL DEFAULT 0 COMMENT '软删除标记：0-正常，1-删除',
    UNIQUE KEY uk_partner_id (partner_id),
    INDEX idx_remenber_code (remenber_code),
    INDEX idx_quota_status (quota_status),
    INDEX idx_is_deleted (is_deleted)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='客户额度表';

-- -- 如果表已存在，添加 fullname 字段
-- ALTER TABLE customer_quota 
-- ADD COLUMN IF NOT EXISTS fullname VARCHAR(255) COMMENT '客户名称' 
-- AFTER remenber_code;
