-- 用户-角色关联表（RBAC 用户角色关联层）
-- 用于建立用户与角色之间的多对多关系
CREATE TABLE `crmapp_user_roles` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `user_id` int(11) NOT NULL COMMENT '用户ID，关联 crmapp_users.id',
  `role_id` int(11) NOT NULL COMMENT '角色ID，关联 crmapp_roles.id',
  `start_time` datetime DEFAULT NULL COMMENT '角色生效时间，null表示立即生效',
  `end_time` datetime DEFAULT NULL COMMENT '角色失效时间，null表示永久有效',
  `status` tinyint(1) DEFAULT '1' COMMENT '分配状态 0-已禁用 1-生效中',
  `created_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_time` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_role_unique` (`user_id`, `role_id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_role_id` (`role_id`),
  KEY `idx_status` (`status`),
  KEY `idx_time_range` (`start_time`, `end_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户-角色关联表';

