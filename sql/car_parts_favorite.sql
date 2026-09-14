CREATE TABLE `car_parts_favorite` (
  `id` int(11) NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `user_id` int(11) NOT NULL COMMENT '用户ID',
  `part_number` varchar(510) COLLATE utf8mb4_general_ci NOT NULL COMMENT '配件编号',
  `category` varchar(100) COLLATE utf8mb4_general_ci NOT NULL DEFAULT '主收藏' COMMENT '分类',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_user_part_category` (`user_id`,`part_number`,`category`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_part_number` (`part_number`),
  KEY `idx_category` (`category`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='配件收藏夹表';
