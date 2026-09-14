-- 微信日报报价详情表
-- 表名: wechat_daily_quote_detail

CREATE TABLE IF NOT EXISTS wechat_daily_quote_detail (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    weixin_decoding_result_id INT COMMENT '微信解码结果表ID',
    quote_number INT COMMENT '报价序号',
    create_date VARCHAR(50) COMMENT '创建日期',
    group_name VARCHAR(255) COMMENT '群名称',
    user_name VARCHAR(255) COMMENT '用户',
    inquiry_customer_id INT COMMENT '询价客户ID',
    inquiry_customer VARCHAR(255) COMMENT '询价客户',
    inquiry TEXT COMMENT '询价',
    part_name VARCHAR(255) COMMENT '配件名称',
    oe_code VARCHAR(255) COMMENT 'OE码',
    brand_price TEXT COMMENT '品牌价格',
    original_quote TEXT COMMENT '原始报价',
    is_out_of_stock BOOLEAN COMMENT '缺货（true/false）',
    draft_link TEXT COMMENT '草稿链接',
    deal_customer_id INT COMMENT '成交客户ID',
    deal_customer VARCHAR(255) COMMENT '成交客户',
    deal_brand VARCHAR(255) COMMENT '成交品牌',
    crm_price DECIMAL(10, 2) COMMENT 'crm里面的开思价格',
    deal_amount DECIMAL(10, 2) COMMENT '成交金额',
    deal_status INT DEFAULT 0 COMMENT '成交状态：0-未知，1-成交，2-未成交',
    inquiry_type INT DEFAULT 3 COMMENT '询价类型：1-车架号询价，2-OE号询价，3-未知',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '数据创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '数据更新时间',
    INDEX idx_weixin_decoding_result_id (weixin_decoding_result_id),
    INDEX idx_create_date (create_date),
    INDEX idx_group_name (group_name),
    INDEX idx_oe_code (oe_code),
    UNIQUE INDEX uk_quote_result (quote_number, weixin_decoding_result_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='微信日报报价详情表';
