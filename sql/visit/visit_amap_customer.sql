-- 客访-高德端客户表
-- 表名: visit_amap_customer
-- 设计文档: doc/客访管理/01-主设计文档.md 4.1

CREATE TABLE IF NOT EXISTS visit_amap_customer (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '物理主键，自增',
    amap_poi_id VARCHAR(128) NOT NULL COMMENT '业务主键（唯一键），高德位置编码；手工新建客户由后端生成伪编码（MANUAL_ 前缀）',
    customer_name VARCHAR(255) NOT NULL COMMENT '客户名称（高德端）',
    address VARCHAR(500) COMMENT '地址',
    longitude DECIMAL(10, 6) COMMENT '经度',
    latitude DECIMAL(10, 6) COMMENT '纬度',
    color VARCHAR(100) COMMENT '颜色编码，如#FF7F81',
    tag VARCHAR(100) COMMENT '标签，如规划路线标记客户、未合作客户',
    description TEXT COMMENT '描述',
    folder VARCHAR(100) COMMENT '文件夹',
    business_circle VARCHAR(100) COMMENT '所属商圈，冗余字段',
    created_by VARCHAR(100) COMMENT '创建人',
    photo_url TEXT COMMENT '照片地址',
    contact_person VARCHAR(100) COMMENT '采购负责人',
    main_repair_brands VARCHAR(255) COMMENT '主修车型/品牌（多值，顿号分隔）',
    customer_type VARCHAR(50) COMMENT '客户类型（综合修理厂/杂修店/快保快修店/轮胎专项店/新能源专修）',
    staff_count VARCHAR(50) COMMENT '员工数量（区间文案，如"8人以上"）',
    station_count VARCHAR(50) COMMENT '工位数量（区间文案，如"6工位以上"）',
    purchase_channels VARCHAR(255) COMMENT '拿货方式（多值，| 分隔）',
    goods_habit VARCHAR(255) COMMENT '用货习惯（多值，| 分隔）',
    coop_merchants VARCHAR(500) COMMENT '常合作商家',
    focus_points VARCHAR(255) COMMENT '客户侧重点（多值，| 分隔）',
    remark TEXT COMMENT '客户信息补充',
    visit_time DATETIME COMMENT '拜访时间，冗余字段（高德端采集原文，只读展示）',
    status TINYINT NOT NULL DEFAULT 0 COMMENT '0-未关联CRM 1-已关联CRM 2-无效',
    last_visit_time DATETIME COMMENT '最近拜访时间（冗余，同步/拜访时更新）',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间，默认当前时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间，默认当前时间并随更新自动变更',
    PRIMARY KEY (id),
    UNIQUE KEY uk_amap_poi_id (amap_poi_id),
    INDEX idx_name (customer_name),
    INDEX idx_last_visit (last_visit_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='客访-高德端客户表';
