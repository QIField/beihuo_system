-- =====================================================================
-- 汽车配件收藏表数据迁移 SQL（MySQL 5.7）
-- 功能：1. 所有收藏的 part_number 去重，统一归入"奔驰主收藏"分类
--       2. 删除其他分类的收藏记录
--       3. 更新唯一索引（由用户维度改为全局维度）
-- 说明：数据量少，直接跑即可；执行前请自行备份
-- =====================================================================

-- 1. 删除旧的唯一约束（按用户维度）
ALTER TABLE car_parts_favorite DROP INDEX uq_user_part_category;

-- 2. 将所有收藏的 part_number 去重后插入到"奔驰主收藏"分类
INSERT IGNORE INTO car_parts_favorite (part_number, category, user_id, created_at)
SELECT DISTINCT part_number, '奔驰主收藏', NULL, NOW() FROM car_parts_favorite;

-- 3. 删除其他分类的所有记录，只保留"奔驰主收藏"
DELETE FROM car_parts_favorite WHERE category != '奔驰主收藏';

-- 4. 添加新的全局唯一约束（按配件编号+分类，同一分类下同一配件只能有一条）
ALTER TABLE car_parts_favorite ADD UNIQUE KEY uq_part_category (part_number, category);
