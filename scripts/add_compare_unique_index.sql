-- 为比价表添加唯一索引，确保 oe + brand + company 唯一
-- 这是根本解决方案，数据库层面防止重复数据

-- 步骤1：检查是否有重复数据
SELECT oe, brand, company, COUNT(*) as cnt
FROM crmapp_compare_summary
GROUP BY oe, brand, company
HAVING cnt > 1;

-- 步骤2：如果有重复数据，保留最新的一条，删除其他
-- DELETE t1 FROM crmapp_compare_summary t1
-- INNER JOIN crmapp_compare_summary t2 
-- WHERE t1.id > t2.id 
-- AND t1.oe = t2.oe 
-- AND t1.brand = t2.brand 
-- AND t1.company = t2.company;

-- 步骤3：添加唯一索引
ALTER TABLE crmapp_compare_summary 
ADD UNIQUE INDEX uk_oe_brand_company (oe, brand, company);

-- 步骤4：验证
SHOW INDEX FROM crmapp_compare_summary;
