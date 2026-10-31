-- 客访-高德客户负责人关联表
-- 表名: visit_customer_owner
-- 设计文档: doc/客访管理/07-负责人绑定.md
-- 说明: 负责人（crmapp_users 系统用户）与高德客户（visit_amap_customer）多对多绑定；
--       只存当前有效关系，解绑即物理删除该行、不留历史；
--       同一对（客户+负责人）由 uk_customer_user 唯一键保证不重复绑定

CREATE TABLE IF NOT EXISTS visit_customer_owner (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '主键，自增',
    visit_amap_customer_id INT NOT NULL COMMENT 'visit_amap_customer.id',
    user_id INT NOT NULL COMMENT '负责人ID → crmapp_users.id',
    operator INT NOT NULL COMMENT '操作用户id',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间，默认当前时间（即绑定时间）',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间，默认当前时间并随更新自动变更',
    UNIQUE KEY uk_customer_user (visit_amap_customer_id, user_id),
    KEY idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='客访-高德客户与负责人关联表';
