-- ------------------------------------------------------------
-- 客访管理 - 拜访记录表（visit_record）
-- 设计文档: doc/客访管理/01-主设计文档.md 4.3
-- 说明:
--   1. 本期唯一写入渠道为 Excel 导入（source=2，后台补录）；
--   2. 幂等去重键: 复合唯一键 uk_visit_dedup (amap_customer_id, visit_time)，
--      同位置 + 同一秒 = 同一次拜访；
--   3. external_record_id 为预留的高德小程序同步幂等键（渠道内防重），
--      与复合唯一键构成两层防线（渠道内防重复推送 / 跨渠道防重复拜访）；
--   4. 2.1 高德同步契约专用字段（签到经纬度/围栏/费用）实现时再补列
--      （内容文本已由 Excel"记录文字"列落地为 content 字段）。
--   5. partner_id / visitor_id / converted 字段已删除：
--      CRM 关联经 visit_customer_relation 桥接查询，拜访记录表不冗余存储；
--      记录人为我方业务人员，Excel"记录人"原样存 recorder 展示；
--      转化标记由订单数据实时统计，不在记录表落库。
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS visit_record (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键，自增',
    amap_customer_id VARCHAR(128) NOT NULL COMMENT '高德客户POI编码(Excel记录内容位置编码) -> visit_amap_customer.amap_poi_id',
    recorder VARCHAR(50) DEFAULT NULL COMMENT '记录人(Excel"记录人"原样,我方业务人员文案,展示用)',
    visit_time DATETIME NOT NULL COMMENT '记录时间(Excel记录时间)',
    content TEXT COMMENT '记录文字(Excel"记录文字"列原样字符串), 直接存入不做结构化',
    images TEXT COMMENT '记录照片, Excel照片列原样字符串(url逗号分隔), 直接存入不做结构化',
    external_record_id VARCHAR(128) DEFAULT NULL COMMENT '预留:小程序端记录唯一ID(同步幂等键)',
    source TINYINT NOT NULL DEFAULT 1 COMMENT '1-高德小程序同步 2-后台补录(Excel导入)',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '1-正常 0-作废',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    UNIQUE KEY uk_visit_dedup (amap_customer_id, visit_time),
    UNIQUE KEY uk_external_record_id (external_record_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='客访-拜访记录表';
