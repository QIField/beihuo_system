

CREATE TABLE `car_parts_library_bmw` (
  `part_number` varchar(510) COLLATE utf8mb4_general_ci NOT NULL COMMENT '配件编号(OE号)',

  -- ===================== 基础信息 =====================
  `part_name` varchar(510) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '零件名称',
  `sales_unit` varchar(50) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '基本单位/销售单位',
  `material_group` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '族组/物料组',

  -- ===================== 重量/体积信息 =====================
  `gross_weight` varchar(50) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '毛重(含原始单位如1.067KG)',
  `net_weight` varchar(50) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '净重(含原始单位如1.067KG)',
  `volume` varchar(50) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '体积(含原始单位如22.040CDM)',

  -- ===================== 价格信息（数据库存储原始值） =====================
  `retail_price` varchar(50) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '零售价(爬虫返回的原始含税价格)',
  `discount_stock` varchar(50) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '经销商折扣(Stock, 含%如25%)',
  `discount_rush` varchar(50) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '经销商折扣(Rush, 含%如25%)',
  `dealer_net_stock` varchar(50) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '经销商净值(Stock订单，含税)',
  `dealer_net_rush` varchar(50) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '经销商净值(Rush订单，含税)',

  -- ===================== 库存信息 =====================
  `available_stock` varchar(50) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '可用库存(含单位如35件)',

 

  -- ===================== 时间字段 =====================
  `data_collect_time` varchar(50) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '采集时间(原始字符串)',

  -- ===================== 数据来源 =====================
  `data_source` varchar(50) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '数据来源',

  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

  PRIMARY KEY (`part_number`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='宝马零件详情表(零件详细信息+价格信息)';
