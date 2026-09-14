-- 配件别名关联表
DROP TABLE IF EXISTS `car_parts_alias`;
CREATE TABLE `car_parts_alias` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `part_number` VARCHAR(510) NOT NULL COMMENT '配件编号',
  `part_number_alias` VARCHAR(510) NOT NULL COMMENT '配件别名',
  `remark` TEXT DEFAULT NULL COMMENT '备注',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_part_number_alias` (`part_number_alias`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='配件别名关联表';
