-- 采购入库单表
-- 表名: wms_return_items

CREATE TABLE IF NOT EXISTS wms_return_items (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    brand_code VARCHAR(255) COMMENT '品牌代码',
    brand_name_en VARCHAR(255) COMMENT '品牌英文名称',
    suffix VARCHAR(255) COMMENT '后缀',
    return_qty VARCHAR(255) COMMENT '采购入库数量',
    frey_no VARCHAR(255) COMMENT '货运单号',
    number VARCHAR(255) COMMENT '编号',
    qty VARCHAR(255) COMMENT '数量',
    kw_no VARCHAR(255) COMMENT '库位号',
    warehouse_name VARCHAR(255) COMMENT '仓库名称',
    kc VARCHAR(255) COMMENT '库存',
    needqty INT COMMENT '需求数量',
    brandname VARCHAR(255) COMMENT '品牌名称',
    l_name_zh VARCHAR(255) COMMENT '中文名称',
    product_remark VARCHAR(255) COMMENT '产品备注',
    pono VARCHAR(255) COMMENT '拣货单号',
    orders_no VARCHAR(255) COMMENT '订单编号',
    orders_id VARCHAR(255) COMMENT '订单ID',
    status INT COMMENT '状态',
    type_param INT COMMENT '类型',
    fullname VARCHAR(255) COMMENT '供应商名称',
    has_pushed_ks INT DEFAULT 0 COMMENT '是否已推送至快手（0:未推送，1:已推送）',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_orders_no (orders_no),
    INDEX idx_pono (pono),
    INDEX idx_orders_id (orders_id),
    INDEX idx_frey_no (frey_no),
    UNIQUE INDEX idx_orders_no_number (orders_no, number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci COMMENT='采购入库单表';
