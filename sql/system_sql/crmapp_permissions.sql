-- 权限表（RBAC 权限层）
-- 用于定义系统中的操作权限，是最细粒度的控制单元
CREATE TABLE `crmapp_permissions` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `permission_name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '权限名称，如：删除购物车、处理单据',
  `permission_code` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '权限编码，唯一标识，如：cart:delete, order:process',
  `description` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '权限描述',
  `parent_permission_id` int(11) DEFAULT NULL COMMENT '父权限ID，用于构建权限树，null表示顶级权限',
  `type` tinyint(1) DEFAULT '2' COMMENT '权限类型 1-模块权限 2-操作权限',
  `status` tinyint(1) DEFAULT '1' COMMENT '权限状态 0-禁用 1-启用',
  `created_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_time` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `permission_code` (`permission_code`),
  KEY `idx_permission_code` (`permission_code`),
  KEY `idx_parent_permission_id` (`parent_permission_id`),
  KEY `idx_type` (`type`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='权限表';


