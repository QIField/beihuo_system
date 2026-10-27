-- ------------------------------------------------------------
-- 客访管理 - 跟进记录表（visit_follow_record）
-- 设计文档: doc/客访管理/04-跟进记录模块设计.md 第二节
-- 说明:
--   1. 客户维度的全渠道沟通流水，纯手动写入（唯一渠道为后台表单）；
--   2. 与拜访记录 visit_record 完全独立：无字段关联、无自动联动、互不引用；
--   3. channel 为固定枚举（微信/电话/线上平台/上门/其他），
--      channel_desc 为时间轴标题（后端按 channel 映射默认值，前端可覆盖）；
--   4. 作废走 status=0 软删，不做物理删除；纯手动写入无幂等诉求，无唯一键。
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS visit_follow_record (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT '主键，自增',
    amap_customer_id VARCHAR(128) NOT NULL COMMENT '高德客户POI编码 -> visit_amap_customer.amap_poi_id',
    channel VARCHAR(50) NOT NULL COMMENT '跟进渠道:微信/电话/线上平台/上门/其他',
    channel_desc VARCHAR(100) DEFAULT NULL COMMENT '时间轴标题,后端按channel映射默认值,前端可覆盖',
    content TEXT NOT NULL COMMENT '跟进内容',
    follow_time DATETIME NOT NULL COMMENT '跟进时间,缺省当前时间,允许补录过去时间',
    creator_id INT DEFAULT NULL COMMENT '记录人ID -> crmapp_users.id(会话无用户ID时为空)',
    creator_name VARCHAR(50) NOT NULL COMMENT '记录人(登录用户名 session.username)',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '1-正常 0-作废',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id),
    INDEX idx_amap_customer_time (amap_customer_id, follow_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='客访-跟进记录表';
