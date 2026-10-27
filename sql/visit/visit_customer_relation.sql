-- 客访-高德客户与CRM客户关联表
-- 表名: visit_customer_relation
-- 设计文档: doc/客访管理/01-主设计文档.md 4.2
-- 说明: 只存当前有效绑定（1:N，一条高德客户可绑定多条CRM客户；反方向仍为1:1，
--       一条CRM客户仅归属一个高德客户），解绑即物理删除该行、不留历史；
--       绑定成功回写 visit_amap_customer.status=1

CREATE TABLE IF NOT EXISTS visit_customer_relation (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '主键，自增',
    amap_customer_id VARCHAR(128) NOT NULL COMMENT '高德客户POI编码 → visit_amap_customer.amap_poi_id',
    partner_id INT NOT NULL COMMENT 'CRM客户ID → partner_list.partner_id',
    last_operator VARCHAR(50) NOT NULL COMMENT '最后操作人（绑定人）',
    bind_remark VARCHAR(255) COMMENT '绑定备注（名称差异说明）',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间，即绑定时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间，默认当前时间并随更新自动变更',
    KEY idx_amap_customer_id (amap_customer_id),
    UNIQUE KEY uk_partner_id (partner_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='客访-高德客户与CRM客户关联表';

-- ============================================================
-- 存量库迁移语句（1:1 → 1:N，bbr_test 已建旧版表时手动执行）：
-- ALTER TABLE visit_customer_relation
--     DROP KEY uk_amap_customer_id,
--     ADD KEY idx_amap_customer_id (amap_customer_id);
-- ============================================================
