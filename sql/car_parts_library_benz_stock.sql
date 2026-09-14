CREATE TABLE `car_parts_library_benz_stock` (
  `part_number` varchar(510) COLLATE utf8mb4_general_ci NOT NULL COMMENT '配件编号',
  `warehouse` varchar(100) COLLATE utf8mb4_general_ci NOT NULL COMMENT '仓库代码',
  `description` varchar(510) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '零件描述',
  `quantity_available` bigint(20) DEFAULT NULL COMMENT '可用数量',
  `unit` varchar(50) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '单位',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  
  PRIMARY KEY (`part_number`, `warehouse`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='奔驰库存信息表';

