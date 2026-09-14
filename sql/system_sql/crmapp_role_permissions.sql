-- 角色-权限关联表（RBAC 角色权限关联层）
-- 用于建立角色与权限之间的多对多关系
CREATE TABLE `crmapp_role_permissions` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `role_id` int(11) NOT NULL COMMENT '角色ID，关联 crmapp_roles.id',
  `permission_id` int(11) NOT NULL COMMENT '权限ID，关联 crmapp_permissions.id',
  `status` tinyint(1) DEFAULT '1' COMMENT '权限分配状态 0-已禁用 1-生效中',
  `created_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_time` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `role_permission_unique` (`role_id`, `permission_id`),
  KEY `idx_role_id` (`role_id`),
  KEY `idx_permission_id` (`permission_id`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='角色-权限关联表';

