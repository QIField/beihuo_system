-- 删除询价表的 inquiry_date 字段
-- 因为导入时不需要这个字段

-- 先检查字段是否存在
SELECT COLUMN_NAME 
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_SCHEMA = DATABASE() 
AND TABLE_NAME = 'crmapp_price_inquiry' 
AND COLUMN_NAME = 'inquiry_date';

-- 如果存在则删除
ALTER TABLE crmapp_price_inquiry DROP COLUMN inquiry_date;

-- 验证删除结果
DESCRIBE crmapp_price_inquiry;
