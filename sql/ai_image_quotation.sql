-- AI图片报价识别记录表
-- 表名: ai_image_quotation
-- 说明: 存储 image_processor.py 从微信群聊天截图识别出的"询价-报价"记录。
--       同一条询价 + 同一报价人合并为一条记录；
--       quote_json_data 为 JSON 字符串，存放该条记录下的"报价信息"数组
--       （元素为 {"报价OE","品质","价格"}）。

CREATE TABLE IF NOT EXISTS ai_image_quotation (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    image_name VARCHAR(255) COMMENT '来源图片名称（关联 wx_chat_image.图片名称）',
    seq_no INT COMMENT '序号（图片内记录顺序编号，从1开始递增）',
    inquiry_person VARCHAR(255) COMMENT '询价人',
    inquiry_oe VARCHAR(255) COMMENT '询价OE',
    quote_person VARCHAR(255) COMMENT '报价人',
    quote_json_data TEXT COMMENT 'JSON 格式的报价信息数组，如 [{"报价OE":"1648804305","品质":"原厂件","价格":0}]',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '数据创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '数据更新时间',
    INDEX idx_image_name (image_name),
    INDEX idx_inquiry_oe (inquiry_oe),
    INDEX idx_quote_person (quote_person)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='AI图片报价识别记录表';