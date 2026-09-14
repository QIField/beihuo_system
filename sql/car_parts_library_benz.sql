CREATE TABLE `car_parts_library_benz` (
  `part_number` varchar(510) COLLATE utf8mb4_general_ci NOT NULL COMMENT '配件编号',
  `descriptions` varchar(510) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '英文描述',
  `description_cn` varchar(510) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '中文描述',
  `marketing_code` varchar(510) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '营销代码',
  `dealer_discount_group` varchar(510) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '经销商折扣组',
  `msrp` double DEFAULT NULL COMMENT '建议零售价',
  `dealer_fixed_nominal_margin` double DEFAULT NULL COMMENT '经销商固定名义利润',
  `wholesale_price` double DEFAULT NULL COMMENT '批发价格',
  `marketing_code_description` varchar(510) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '营销代码描述',
  `quantity_unit` varchar(510) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '数量单位',
  `sales_pack_size` varchar(510) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '销售包装规格',
  `weight` bigint(20) DEFAULT NULL COMMENT '重量',
  `length` varchar(510) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '长度',
  `width` varchar(510) DEFAULT NULL COMMENT '宽度',
  `height` varchar(510) DEFAULT NULL COMMENT '高度',
  `effective_date` varchar(510) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '生效日期',
 

  -- ======================
  -- 以下是【截图有、原表缺失】新增字段
  -- ======================
  `brand` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '品牌',
  `category` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '分类',
  `ccc_mark` varchar(50) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT 'CCC标识',
  `volume` decimal(10,3) DEFAULT NULL COMMENT '体积',
  `hazmat_code` varchar(50) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '危险货物代码',
  `origin_country` varchar(50) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '原产地',
  `shelf_life` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '存储期限',
  `is_hazmat` varchar(10) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '防盗标识/危险品',
  `purchase_price` decimal(18,2) DEFAULT NULL COMMENT '巴博瑞采购价',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',


  -- 新加的辅助字段

  `data_source` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '数据来源',
  `l_model_zh` text COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '车型中文名',
  `part_nr_info_super_session` longtext COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '零件替代关系信息',


  PRIMARY KEY (`part_number`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;