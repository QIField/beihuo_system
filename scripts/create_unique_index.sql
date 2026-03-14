-- 为询价表创建唯一索引，用于导入时自动去重
-- 重复判断条件：oe + brand + supplier + price + company

-- 先检查索引是否已存在
SELECT INDEX_NAME 
FROM INFORMATION_SCHEMA.STATISTICS 
WHERE TABLE_SCHEMA = DATABASE() 
AND TABLE_NAME = 'crmapp_price_inquiry' 
AND INDEX_NAME = 'uk_oe_brand_supplier_price_company';

-- 如果索引不存在，则创建
-- 注意：如果表中已有重复数据，创建索引会失败，需要先清理重复数据
ALTER TABLE crmapp_price_inquiry 
ADD UNIQUE INDEX uk_oe_brand_supplier_price_company (oe, brand, supplier, price, company);

-- 创建后验证
SHOW INDEX FROM crmapp_price_inquiry;
