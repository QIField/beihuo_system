-- 为询价表创建唯一索引，用于导入时自动去重
-- 重复判断条件：oe + brand + supplier + price + company

-- 步骤1：检查是否有重复数据
SELECT oe, brand, supplier, price, company, COUNT(*) as cnt
FROM crmapp_price_inquiry
GROUP BY oe, brand, supplier, price, company
HAVING cnt > 1;

-- 步骤2：如果有重复数据，先清理（保留id最小的一条）
-- DELETE t1 FROM crmapp_price_inquiry t1
-- INNER JOIN crmapp_price_inquiry t2 
-- WHERE t1.id > t2.id 
-- AND t1.oe = t2.oe 
-- AND t1.brand = t2.brand 
-- AND t1.supplier = t2.supplier 
-- AND t1.price = t2.price 
-- AND t1.company = t2.company;

-- 步骤3：创建唯一索引
ALTER TABLE crmapp_price_inquiry 
ADD UNIQUE INDEX uk_oe_brand_supplier_price_company (oe, brand, supplier, price, company);

-- 步骤4：验证索引创建成功
SHOW INDEX FROM crmapp_price_inquiry;
