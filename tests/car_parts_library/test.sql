-- 取最新统计日及派生时间窗口
SET @stat_date := (SELECT MAX(stat_date) FROM oe_parts_sales);
SET @stat_year := YEAR(@stat_date);
SET @one_year_ago := DATE_SUB(@stat_date, INTERVAL 365 DAY);
SET @stat_date_ts := UNIX_TIMESTAMP(DATE_ADD(@stat_date, INTERVAL 1 DAY)) - 1;       -- 统计日23:59:59秒级时间戳
SET @one_year_ago_ts := UNIX_TIMESTAMP(DATE(@one_year_ago));                         -- 一年前0点秒级时间戳
SELECT @stat_date AS stat_date, @stat_year AS stat_year, @one_year_ago AS one_year_ago;

-- 主键无重复
SELECT id, COUNT(*) AS cnt FROM oe_parts_sales GROUP BY id HAVING cnt > 1;

-- (number, brand_name) 联合唯一键无重复
SELECT number, brand_name, COUNT(*) AS cnt
FROM oe_parts_sales
GROUP BY number, brand_name
HAVING cnt > 1;

-- number 为表定义 NOT NULL，brand_name 文档要求 NOT NULL（实际DDL为NULLABLE，需查实际是否有空值）
SELECT
    SUM(number IS NULL OR number = '')               AS number_null_cnt,
    SUM(brand_name IS NULL OR brand_name = '')       AS brand_name_null_cnt,
    SUM(stat_date IS NULL)                            AS stat_date_null_cnt,
    SUM(annual_sales_1y IS NULL)                      AS annual_null_cnt,
    SUM(avg_daily_sales_1y IS NULL)                   AS daily_null_cnt,
    SUM(avg_monthly_sales_1y IS NULL)                 AS monthly_null_cnt
FROM oe_parts_sales;

-- DECIMAL/INT 字段不应为 NULL（有 DEFAULT 0），且销量类字段不应为负数
SELECT
    SUM(annual_sales_1y IS NULL OR annual_sales_1y < 0)     AS annual_invalid,
    SUM(sales_this_year IS NULL OR sales_this_year < 0)     AS this_year_invalid,
    SUM(sales_last_year IS NULL OR sales_last_year < 0)     AS last_year_invalid,
    SUM(avg_daily_sales_1y IS NULL OR avg_daily_sales_1y < 0) AS daily_invalid,
    SUM(avg_monthly_sales_1y IS NULL OR avg_monthly_sales_1y < 0) AS monthly_invalid,
    SUM(sales_std_dev_1y IS NULL OR sales_std_dev_1y < 0)   AS std_dev_invalid
FROM oe_parts_sales;

-- 检查同一次刷新是否出现多个 stat_date（每日全量刷新应只有1个）
SELECT stat_date, COUNT(*) AS cnt
FROM oe_parts_sales
GROUP BY stat_date
ORDER BY stat_date DESC;

-- 校验 JSON 是否合法、键数是否为12、键值类型是否合规
SELECT
    number, brand_name,
    JSON_VALID(monthly_sales_json)                                                AS is_valid_json,
    JSON_LENGTH(monthly_sales_json)                                               AS key_count,
    SUM(CASE WHEN JSON_VALID(monthly_sales_json)
              AND JSON_LENGTH(monthly_sales_json) <> 12 THEN 1 ELSE 0 END)        AS not_12_keys
FROM oe_parts_sales
WHERE monthly_sales_json IS NOT NULL
GROUP BY number, brand_name, monthly_sales_json
HAVING is_valid_json = 0 OR key_count <> 12
LIMIT 50;

-- TRUNCATE 后 id 应连续；若有大空洞说明写入异常或中途有 DELETE
SELECT MIN(id) AS min_id, MAX(id) AS max_id, COUNT(*) AS row_cnt,
       (MAX(id) - MIN(id) + 1 - COUNT(*)) AS id_gap
FROM oe_parts_sales;

-- created_at 应 >= stat_date（数据创建在统计之后），不应早于统计日
SELECT COUNT(*) AS abnormal_created_cnt
FROM oe_parts_sales
WHERE DATE(created_at) < stat_date;

-- avg_daily_sales_1y 应等于 ROUND(annual_sales_1y / 365, 2)
SELECT number, brand_name, annual_sales_1y, avg_daily_sales_1y,
       ROUND(annual_sales_1y / 365, 2) AS expected_daily
FROM oe_parts_sales
WHERE ABS(avg_daily_sales_1y - ROUND(annual_sales_1y / 365, 2)) > 0.01
LIMIT 50;

-- avg_monthly_sales_1y 应等于 ROUND(annual_sales_1y / 12, 2)
SELECT number, brand_name, annual_sales_1y, avg_monthly_sales_1y,
       ROUND(annual_sales_1y / 12, 2) AS expected_monthly
FROM oe_parts_sales
WHERE ABS(avg_monthly_sales_1y - ROUND(annual_sales_1y / 12, 2)) > 0.01
LIMIT 50;

-- 注意：月度按自然月 YYYY-MM 聚合，annual_sales_1y 按 365 天窗口，两者口径不同会有差异
-- 但差异应在合理范围（±当月跨年窗口外的销量）
SELECT number, brand_name, annual_sales_1y,
       (SELECT SUM(jt.qty) FROM JSON_TABLE(monthly_sales_json, '$.*' COLUMNS(qty INT PATH '$')) jt) AS json_sum,
       annual_sales_1y - (SELECT SUM(jt.qty) FROM JSON_TABLE(monthly_sales_json, '$.*' COLUMNS(qty INT PATH '$')) jt) AS diff
FROM oe_parts_sales
HAVING ABS(diff) > 5  -- 差异大于5需排查
LIMIT 50;

-- sales_this_year 应等于 stat_year 年份月份的JSON值之和
SELECT number, brand_name, sales_this_year,
       (SELECT SUM(jt.qty) FROM JSON_TABLE(monthly_sales_json, '$.*' COLUMNS(m_key VARCHAR(7) PATH '$.key', qty INT PATH '$')) jt
        WHERE jt.m_key LIKE CONCAT(@stat_year, '-%')) AS json_this_year_sum
FROM oe_parts_sales
HAVING sales_this_year <> json_this_year_sum
LIMIT 50;

-- sales_last_year 应等于 stat_year-1 年份月份的JSON值之和
SELECT number, brand_name, sales_last_year,
       (SELECT SUM(jt.qty) FROM JSON_TABLE(monthly_sales_json, '$.*' COLUMNS(m_key VARCHAR(7) PATH '$.key', qty INT PATH '$')) jt
        WHERE jt.m_key LIKE CONCAT(@stat_year - 1, '-%')) AS json_last_year_sum
FROM oe_parts_sales
HAVING sales_last_year <> json_last_year_sum
LIMIT 50;

-- 抽查月度 JSON 中是否存在负值或非整数值
SELECT DISTINCT number, brand_name, jt.m_key, jt.qty
FROM oe_parts_sales,
JSON_TABLE(monthly_sales_json, '$.*' COLUMNS(m_key VARCHAR(7) PATH '$.key', qty INT PATH '$')) jt
WHERE jt.qty < 0
LIMIT 50;

-- 由于 annual_sales_1y 是滚动365天，sales_this_year+sales_last_year是两个自然年，两者不严格相等
-- 但若 sales_this_year + sales_last_year = 0 而 annual_sales_1y > 0，说明销量落在 stat_year-2 及更早
-- 或者 annual_sales_1y = 0 而 sales_last_year > 0，说明该SKU去年有销量但近365天无销量（"僵尸SKU"）
SELECT
    SUM(CASE WHEN annual_sales_1y = 0 AND sales_last_year > 0 THEN 1 ELSE 0 END) AS zombie_last_year_active,
    SUM(CASE WHEN annual_sales_1y = 0 AND sales_this_year = 0 AND sales_last_year = 0 THEN 1 ELSE 0 END) AS total_zombie,
    SUM(CASE WHEN annual_sales_1y > 0 AND sales_this_year + sales_last_year = 0 THEN 1 ELSE 0 END) AS sales_outside_2years
FROM oe_parts_sales;

SELECT
    COALESCE(abc_classification, 'NULL') AS abc,
    COUNT(*)                              AS cnt,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM oe_parts_sales), 2) AS pct
FROM oe_parts_sales
GROUP BY abc_classification
ORDER BY abc_classification;

-- 各分位数销量分布，识别销量集中度
SELECT
    COUNT(*)                                                       AS total_sku,
    AVG(annual_sales_1y)                                           AS avg_sales,
    MAX(annual_sales_1y)                                           AS max_sales,
    MIN(annual_sales_1y)                                           AS min_sales,
    SUM(annual_sales_1y)                                           AS total_sales,
    -- 帕累托：前20% SKU 贡献多少销量
    ROUND((SELECT SUM(annual_sales_1y) FROM (
        SELECT annual_sales_1y FROM oe_parts_sales ORDER BY annual_sales_1y DESC LIMIT (SELECT ROUND(COUNT(*)*0.2) FROM oe_parts_sales)
    ) t) * 100.0 / SUM(annual_sales_1y), 2)                       AS top20_pct_contrib
FROM oe_parts_sales;

SELECT
    CASE
        WHEN annual_sales_1y = 0 THEN '0_zero'
        WHEN annual_sales_1y BETWEEN 1 AND 10 THEN '1_very_low'
        WHEN annual_sales_1y BETWEEN 11 AND 100 THEN '2_low'
        WHEN annual_sales_1y BETWEEN 101 AND 1000 THEN '3_medium'
        WHEN annual_sales_1y BETWEEN 1001 AND 10000 THEN '4_high'
        ELSE '5_very_high'
    END AS sales_band,
    COUNT(*) AS cnt,
    SUM(annual_sales_1y) AS total_sales
FROM oe_parts_sales
GROUP BY sales_band
ORDER BY sales_band;

-- Top 20 品牌 SKU 数与销量占比
SELECT brand_name,
       COUNT(*) AS sku_cnt,
       SUM(annual_sales_1y) AS total_sales,
       ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM oe_parts_sales), 2) AS sku_pct
FROM oe_parts_sales
GROUP BY brand_name
ORDER BY total_sales DESC
LIMIT 20;

-- 标准差分位：识别高波动 vs 稳定销量 SKU
SELECT
    COUNT(*) AS cnt,
    ROUND(AVG(sales_std_dev_1y), 2) AS avg_std,
    ROUND(MAX(sales_std_dev_1y), 2) AS max_std,
    SUM(CASE WHEN sales_std_dev_1y = 0 THEN 1 ELSE 0 END) AS zero_std_cnt,
    SUM(CASE WHEN sales_std_dev_1y > 0 AND sales_std_dev_1y <= 5 THEN 1 ELSE 0 END) AS low_std,
    SUM(CASE WHEN sales_std_dev_1y > 5 AND sales_std_dev_1y <= 50 THEN 1 ELSE 0 END) AS mid_std,
    SUM(CASE WHEN sales_std_dev_1y > 50 THEN 1 ELSE 0 END) AS high_std
FROM oe_parts_sales;

-- 全表 12 个月份总销量趋势，识别淡旺季
SELECT jt.m_key AS month, SUM(jt.qty) AS total_qty
FROM oe_parts_sales,
JSON_TABLE(monthly_sales_json, '$.*' COLUMNS(m_key VARCHAR(7) PATH '$.key', qty INT PATH '$')) jt
GROUP BY jt.m_key
ORDER BY jt.m_key;

-- 这是上一轮分析中指出的核心问题：子查询缺时间下界导致大量0值SKU
SELECT
    COUNT(*) AS total_sku,
    SUM(CASE WHEN annual_sales_1y = 0 THEN 1 ELSE 0 END) AS zero_annual_cnt,
    ROUND(SUM(CASE WHEN annual_sales_1y = 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS zero_pct,
    SUM(CASE WHEN avg_monthly_sales_1y = 0 THEN 1 ELSE 0 END) AS zero_monthly_cnt,
    SUM(CASE WHEN sales_last_year = 0 THEN 1 ELSE 0 END) AS zero_last_year_cnt
FROM oe_parts_sales;

-- 销量异常大的 SKU，需人工核对是否数据错误
SELECT number, brand_name, pdname, annual_sales_1y, avg_daily_sales_1y, sales_std_dev_1y
FROM oe_parts_sales
ORDER BY annual_sales_1y DESC
LIMIT 20;

-- avg_daily_sales_1y × 365 应接近 annual_sales_1y（容差 ±2）
SELECT number, brand_name,
       annual_sales_1y,
       avg_daily_sales_1y,
       avg_daily_sales_1y * 365 AS daily_x_365,
       ABS(annual_sales_1y - avg_daily_sales_1y * 365) AS diff
FROM oe_parts_sales
WHERE ABS(annual_sales_1y - avg_daily_sales_1y * 365) > 2
ORDER BY diff DESC
LIMIT 50;

-- sales_this_year（自然年）理论上可以 > annual_sales_1y（365天滚动），但若当年已超去年全年很多需关注
-- 实际若 stat_year=当年，sales_this_year 是当年1月至今，annual_sales_1y 是过去365天
-- 异常：annual_sales_1y < sales_this_year 且差额很大，说明时间窗口计算可能有问题
SELECT number, brand_name, annual_sales_1y, sales_this_year, sales_last_year,
       annual_sales_1y - sales_this_year AS annual_minus_this_year
FROM oe_parts_sales
WHERE sales_this_year > annual_sales_1y * 1.5  -- 今年销量远超近一年总量，异常
LIMIT 50;

-- stat_date 应为历史日期（今天或更早），不应是未来
SELECT stat_date, COUNT(*) AS cnt
FROM oe_parts_sales
WHERE stat_date > CURDATE()
GROUP BY stat_date;

-- monthly_sales_json 的键应全部落在 [@one_year_ago, @stat_date] 范围内
-- 即从 @stat_date 倒推12个月，超出范围的键为异常
SELECT DISTINCT number, brand_name, jt.m_key AS abnormal_month
FROM oe_parts_sales,
JSON_TABLE(monthly_sales_json, '$.*' COLUMNS(m_key VARCHAR(7) PATH '$.key', qty INT PATH '$')) jt
WHERE jt.m_key < DATE_FORMAT(@one_year_ago, '%Y-%m')
   OR jt.m_key > DATE_FORMAT(@stat_date, '%Y-%m')
LIMIT 50;

-- 标准差大于年均月销量×3，说明销量集中在一两个月，其他月份几乎无销量
SELECT number, brand_name, annual_sales_1y, avg_monthly_sales_1y, sales_std_dev_1y,
       ROUND(sales_std_dev_1y / NULLIF(avg_monthly_sales_1y, 0), 2) AS cv_ratio
FROM oe_parts_sales
WHERE avg_monthly_sales_1y > 0
  AND sales_std_dev_1y / avg_monthly_sales_1y > 3
ORDER BY cv_ratio DESC
LIMIT 50;

-- 用 sales_order_history 重新计算近365天净销量，与 oe_parts_sales.annual_sales_1y 对比
-- 净销量 = 无退货常规订单 quantity + 部分退货(type=21/22最新) processed_quantity
SELECT t.number, t.brand_name,
       t.annual_sales_1y                                       AS table_value,
       COALESCE(s.net_qty, 0) + COALESCE(r.net_qty, 0)         AS recompute_value,
       t.annual_sales_1y - (COALESCE(s.net_qty, 0) + COALESCE(r.net_qty, 0)) AS diff
FROM oe_parts_sales t
LEFT JOIN (
    -- 第一部分：无退货常规订单
    SELECT s.number, s.brand_name, SUM(s.quantity) AS net_qty
    FROM sales_order_history s
    WHERE s.order_type_id = 1
      AND s.number IS NOT NULL AND s.number != ''
      AND s.brand_name IS NOT NULL AND s.brand_name != ''
      AND s.quantity > 0
      AND s.create_date BETWEEN @one_year_ago_ts AND @stat_date_ts
      AND NOT EXISTS (
          SELECT 1 FROM stock_safe_refund_ref r
          WHERE r.normal_order_items_id = s.orders_items_id
            AND r.type IN (11,12,13,21,22,23,31,32,33)
      )
    GROUP BY s.number, s.brand_name
) s ON s.number = t.number AND s.brand_name = t.brand_name
LEFT JOIN (
    -- 第二部分：部分退货净额（type=21/22 最新 match_count）
    SELECT r.number, r.brand_name, SUM(r.processed_quantity) AS net_qty
    FROM stock_safe_refund_ref r
    JOIN sales_order_history h ON h.orders_items_id = r.normal_order_items_id
    WHERE r.type IN (21, 22)
      AND r.processed_quantity > 0
      AND h.create_date BETWEEN @one_year_ago_ts AND @stat_date_ts
      AND r.match_count = (SELECT MAX(match_count) FROM stock_safe_refund_ref r2 WHERE r2.normal_order_items_id = r.normal_order_items_id)
    GROUP BY r.number, r.brand_name
) r ON r.number = t.number AND r.brand_name = t.brand_name
HAVING diff <> 0
ORDER BY ABS(diff) DESC
LIMIT 50;

-- oe_parts_sales 与 stock_safe 通过 (number, brand_name) 关联，冗余字段应一致
SELECT t.number, t.brand_name,
       t.pdname AS sales_pdname, s.pdname AS safe_pdname,
       t.frey_no AS sales_frey_no, s.frey_no AS safe_frey_no
FROM oe_parts_sales t
JOIN stock_safe s ON s.number = t.number AND s.brand_name = t.brand_name
WHERE t.pdname <> s.pdname OR t.frey_no <> s.frey_no
LIMIT 50;

-- 安全库存表有但销量表无的 SKU（违反1:1关联）
SELECT s.number, s.brand_name, s.abc_classification, s.available_stock
FROM stock_safe s
LEFT JOIN oe_parts_sales t ON t.number = s.number AND t.brand_name = s.brand_name
WHERE t.number IS NULL
LIMIT 50;

-- 销量表存在该 SKU，但近一年 sales_order_history 已无任何相关订单（数据被清理或时间戳异常）
SELECT t.number, t.brand_name, t.annual_sales_1y
FROM oe_parts_sales t
LEFT JOIN sales_order_history s
       ON s.number = t.number AND s.brand_name = t.brand_name
      AND s.order_type_id = 1
      AND s.create_date BETWEEN @one_year_ago_ts AND @stat_date_ts
WHERE t.annual_sales_1y > 0
  AND s.orders_items_id IS NULL
LIMIT 50;

-- 第二部分数据源依赖 JOIN sales_order_history，若 JOIN 丢失则部分退货净额未被计入
SELECT r.normal_order_items_id, r.refund_order_items_id, r.number, r.brand_name,
       r.processed_quantity, r.type, r.match_count
FROM stock_safe_refund_ref r
LEFT JOIN sales_order_history h ON h.orders_items_id = r.normal_order_items_id
WHERE r.type IN (21, 22)
  AND r.processed_quantity > 0
  AND h.orders_items_id IS NULL
LIMIT 50;

