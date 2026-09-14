

CREATE TABLE `car_parts_library_bmw_stock` (
  `part_number` varchar(510) COLLATE utf8mb4_general_ci NOT NULL COMMENT '配件编号(OE号)',
  `part_name` varchar(510) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '零件名称',
  `discount_code` varchar(50) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '折扣代码',
  `retail_price` varchar(50) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '零售价(爬虫返回的原始含税价格)',
  `sales_unit` varchar(50) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '销售单位',

  -- ===================== 仓库 - 北京 =====================
  `warehouse_beijing` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '库房-北京',
  `in_transit_beijing` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '在途-北京',
  `reorder_point_beijing` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '再定购点-北京',
  `main_warehouse_beijing` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '主仓-北京',

  -- ===================== 仓库 - 上海 =====================
  `warehouse_shanghai` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '库房-上海',
  `in_transit_shanghai` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '在途-上海',
  `reorder_point_shanghai` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '再定购点-上海',
  `main_warehouse_shanghai` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '主仓-上海',

  -- ===================== 仓库 - 佛山 =====================
  `warehouse_foshan` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '库房-佛山',
  `in_transit_foshan` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '在途-佛山',
  `reorder_point_foshan` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '再定购点-佛山',
  `main_warehouse_foshan` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '主仓-佛山',

  -- ===================== 仓库 - 成都 =====================
  `warehouse_chengdu` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '库房-成都',
  `in_transit_chengdu` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '在途-成都',
  `reorder_point_chengdu` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '再定购点-成都',
  `main_warehouse_chengdu` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '主仓-成都',

  -- ===================== 仓库 - 沈阳 =====================
  `warehouse_shenyang` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '库房-沈阳',
  `in_transit_shenyang` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '在途-沈阳',
  `reorder_point_shenyang` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '再定购点-沈阳',
  `main_warehouse_shenyang` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '主仓-沈阳',

  -- ===================== 仓库 - 合肥 =====================
  `warehouse_hefei` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '库房-合肥',
  `in_transit_hefei` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '在途-合肥',
  `reorder_point_hefei` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '再定购点-合肥',
  `main_warehouse_hefei` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '主仓-合肥',

  -- ===================== 仓库 - 宁波 =====================
  `warehouse_ningbo` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '库房-宁波',
  `in_transit_ningbo` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '在途-宁波',
  `reorder_point_ningbo` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '再定购点-宁波',
  `main_warehouse_ningbo` varchar(100) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '主仓-宁波',

  -- ===================== 时间字段 =====================
  `data_collect_time` varchar(50) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '采集时间(原始字符串)',
  -- ===================== 数据来源 =====================
  `data_source` varchar(50) COLLATE utf8mb4_general_ci DEFAULT NULL COMMENT '数据来源',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

  PRIMARY KEY (`part_number`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='华晨宝马零件库存表(零件基础信息+多仓库库存)';
