-- 合作伙伴数据表
-- 表名: partner_list

CREATE TABLE IF NOT EXISTS partner_list (
    partner_id INT PRIMARY KEY COMMENT '合作伙伴ID',
    contacts VARCHAR(255) COMMENT '联系人',
    contacts_phone INT COMMENT '联系电话',
    country VARCHAR(255) COMMENT '国家',
    create_time INT COMMENT '创建时间（秒级时间戳）',
    currency_name VARCHAR(255) COMMENT '货币名称',
    fullname VARCHAR(255) COMMENT '全名',
    is_disabled INT COMMENT '是否禁用',
    language_types VARCHAR(255) COMMENT '语言类型',
    level_id INT COMMENT '客户等级',
    orderTimes INT COMMENT '订单统计（份）',
    payment_description VARCHAR(255) COMMENT '付款说明',
    payment_method VARCHAR(255) COMMENT '付款方式',
    real_name VARCHAR(255) COMMENT '所属业务员',
    region VARCHAR(255) COMMENT '区域',
    remenber_code VARCHAR(255) COMMENT '记忆代码',
    sap_no VARCHAR(255) COMMENT 'SAP编号',
    short_name VARCHAR(255) COMMENT '简称',
    street VARCHAR(500) COMMENT '街道',
    upload_sap VARCHAR(255) COMMENT '上传SAP',
    user_name VARCHAR(255) COMMENT '创建人',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '数据创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '数据更新时间',
    INDEX idx_fullname (fullname),
    INDEX idx_sap_no (sap_no),
    INDEX idx_level_id (level_id),
    INDEX idx_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='合作伙伴数据表';
