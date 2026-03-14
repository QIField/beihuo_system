-- 修复索引长度超限问题
-- 方法：缩短字段长度

-- 先删除可能存在的旧索引
DROP INDEX IF EXISTS uk_oe_brand_supplier_price_company ON crmapp_price_inquiry;

-- 修改字段长度
ALTER TABLE crmapp_price_inquiry 
MODIFY oe VARCHAR(100) NOT NULL COMMENT 'OE号',
MODIFY brand VARCHAR(50) COMMENT '品牌',
MODIFY supplier VARCHAR(50) COMMENT '供应商';

-- 创建唯一索引
ALTER TABLE crmapp_price_inquiry 
ADD UNIQUE INDEX uk_oe_brand_supplier_price_company (oe, brand, supplier, price, company);

-- 验证
SHOW INDEX FROM crmapp_price_inquiry;
