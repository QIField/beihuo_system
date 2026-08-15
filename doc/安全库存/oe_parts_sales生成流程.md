# oe_parts_sales 销量表生成流程与实施方案

> 本文档设计 `oe_parts_sales` 销量表的生成程序流程与实施方案。
> 表结构定义见 [表设计/02_销量表_oe_parts_sales.md](表设计/02_销量表_oe_parts_sales.md)。
> 销量计算逻辑见 [表设计/01_设计概述与销量计算.md](表设计/01_设计概述与销量计算.md)。
>
> **核心约束**：
> - `oe_parts_sales` 表采用**每日更新**机制，每次更新前**彻底清空**表中所有数据
> - `stock_safe` 安全库存表同样遵循每日更新并清空数据的规则
> - `sales_order_history` 表约 20 万条数据，需采用**分步处理策略**

---

## 一、概述与目标

### 1.1 程序目标

每日定时从 `sales_order_history`（无退货常规订单）与 `stock_safe_refund_ref`（type=21/22 部分退货净额）抽取数据，按 (oe, brand_name) 聚合计算净销量统计，清空并重写 `oe_parts_sales` 表。

### 1.2 设计原则

| 原则 | 说明 |
|------|------|
| 全量重写 | 每日清空后全量写入，保证数据一致性，避免增量同步的复杂性 |
| 分批处理 | 20 万条源数据分批读取，控制内存占用与单次事务规模 |
| 安全清空 | 清空前备份，事务保护，失败可回滚 |
| 断点续传 | 通过检查点表记录处理进度，异常中断后可从断点恢复 |
| 幂等可重跑 | 全量重写模式下可随时重跑，无副作用 |

### 1.3 调度方式

使用项目现有的 `LightweightTaskManager`（基于 APScheduler）注册定时任务：

```python
# app/core/task_manager.py 中已有调度框架
# job_defaults: max_instances=1（防并发）、coalesce=True（防积压）
task_manager.schedule(
    func=oe_parts_sales_daily_refresh,
    trigger='cron',
    job_id='oe_parts_sales_daily_refresh',
    hour=3, minute=0,          # 每日凌晨 3:00 执行
    replace_existing=True
)
```

> **调度时间选择**：凌晨 3:00，避开 22:00 的每日爬取任务与 23:00 的卓之星同步任务，且需在退货匹配任务（step1/2/3）完成后执行，确保 `stock_safe_refund_ref` 数据完整。

---

## 二、数据来源分析

### 2.1 数据源总览

| 数据源 | 表名 | 角色 | 数据量级 | 关键字段 |
|--------|------|------|---------|---------|
| 源表1 | `sales_order_history` | 无退货常规订单的原始销量 | ~20万条 | orders_items_id, order_type_id, number(OE), brand_name, pdname, frey_no, quantity, create_date(秒级时间戳) |
| 源表2 | `stock_safe_refund_ref` | type=21/22 部分退货订单的净销量 | 数千~数万条 | normal_order_items_id, oe, brand_name, product_name, barcode, processed_quantity, type, match_count |
| 目标表 | `oe_parts_sales` | 按 (oe, brand_name) 聚合的净销量统计 | 数万条 | oe, brand_name, product_name, barcode, avg_daily_sales_1y, avg_monthly_sales_1y, annual_sales_1y, sales_this_year, sales_last_year, sales_std_dev_1y, monthly_sales_json |

### 2.2 数据抽取范围

#### 第一部分 — 来自 sales_order_history（无退货常规订单）

```sql
-- 抽取条件
WHERE order_type_id = 1                              -- 常规订单
  AND number IS NOT NULL AND number != ''            -- OE号非空
  AND brand_name IS NOT NULL AND brand_name != ''    -- 品牌非空（唯一键组成部分）
  AND NOT EXISTS (                                   -- 排除有退货记录的常规订单
      SELECT 1 FROM stock_safe_refund_ref r
      WHERE r.normal_order_items_id = sales_order_history.orders_items_id
  )
```

- **取值**：`quantity` 字段作为净销量
- **时间维度**：`create_date`（秒级时间戳），用于按日/月/年聚合
- **字段映射**：number→oe, brand_name→brand_name, pdname→product_name, frey_no→barcode

#### 第二部分 — 来自 stock_safe_refund_ref（type=21/22 部分退货净额）

```sql
-- 抽取条件（与现有 DAO get_type21_22_records 逻辑一致）
WHERE type IN (21, 22)                               -- 部分退货（有剩余）
  AND match_count = (                                -- 取同一常规订单最新记录
      SELECT MAX(match_count) FROM stock_safe_refund_ref r2
      WHERE r2.normal_order_items_id = r.normal_order_items_id
  )
```

- **取值**：`processed_quantity` 字段作为净销量（退货后剩余数量）
- **时间维度**：需 LEFT JOIN `sales_order_history` 取常规订单的 `create_date`（通过 `normal_order_items_id` 关联 `orders_items_id`）
- **字段映射**：oe→oe, brand_name→brand_name, product_name→product_name, barcode→barcode

> **依赖说明**：第二部分依赖退货匹配任务（step1/2/3）已完成，`stock_safe_refund_ref` 数据必须完整。调度顺序：退货匹配任务 → 销量表刷新任务。

### 2.3 数据质量过滤

| 过滤规则 | 原因 |
|---------|------|
| `number IS NOT NULL AND number != ''` | OE号是唯一键组成部分，不可为空 |
| `brand_name IS NOT NULL AND brand_name != ''` | 品牌名是唯一键组成部分，不可为空 |
| `quantity > 0`（第一部分） | 过滤异常零数量订单 |
| `processed_quantity > 0`（第二部分） | type=21/22 理论上 processed_quantity > 0，兜底过滤 |

---

## 三、数据抽取逻辑（分批读取）

### 3.1 分批读取机制 — Keyset Pagination（主键游标分页）

> **不使用 LIMIT/OFFSET**：20 万条数据下 OFFSET 性能急剧下降（需扫描并丢弃前 N 行）。
> **采用 Keyset Pagination**：基于 `orders_items_id` 主键游标分页，每批 WHERE `orders_items_id > last_id`，性能恒定。

#### 第一部分分批读取伪SQL

```sql
-- 每批读取（第 N 批）
SELECT
    s.orders_items_id,
    s.number AS oe,
    s.brand_name,
    s.pdname AS product_name,
    s.frey_no AS barcode,
    s.quantity AS net_quantity,
    s.create_date
FROM sales_order_history s
WHERE s.order_type_id = 1
  AND s.number IS NOT NULL AND s.number != ''
  AND s.brand_name IS NOT NULL AND s.brand_name != ''
  AND s.orders_items_id > :last_processed_id      -- 游标：上一批最大 orders_items_id
  AND NOT EXISTS (
      SELECT 1 FROM stock_safe_refund_ref r
      WHERE r.normal_order_items_id = s.orders_items_id
  )
ORDER BY s.orders_items_id ASC                     -- 按主键升序，保证游标单调
LIMIT :batch_size                                   -- 每批 5000 条
```

#### 第二部分抽取（一次性读取）

```sql
-- type=21/22 记录数量较少（数千~数万条），可一次性读取
SELECT
    r.normal_order_items_id,
    r.oe,
    r.brand_name,
    r.product_name,
    r.barcode,
    r.processed_quantity AS net_quantity,
    s.create_date                                  -- JOIN 取常规订单创建时间
FROM stock_safe_refund_ref r
LEFT JOIN sales_order_history s ON s.orders_items_id = r.normal_order_items_id
WHERE r.type IN (21, 22)
  AND r.match_count = (
      SELECT MAX(match_count) FROM stock_safe_refund_ref r2
      WHERE r2.normal_order_items_id = r.normal_order_items_id
  )
  AND r.oe IS NOT NULL AND r.oe != ''
  AND r.brand_name IS NOT NULL AND r.brand_name != ''
```

> **说明**：第一部分（sales_order_history）采用分批读取；第二部分（stock_safe_refund_ref type=21/22）数据量小，一次性读取后在内存中与第一部分合并聚合。

### 3.2 每批次数据量设定

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| `BATCH_SIZE` | **5000** 条/批 | 平衡内存占用与数据库交互次数。20万条 ÷ 5000 = 40 批 |
| 内存预估 | ~5MB/批 | 每条约 1KB，5000 条约 5MB，远低于内存上限 |
| 数据库交互 | 40 次查询 | Keyset Pagination 每次查询走主键索引，耗时 < 100ms |

> **批次大小调优**：若 `NOT EXISTS` 子查询导致单批耗时过长（>5秒），可降至 2000 条/批；若性能充裕可提升至 10000 条/批。通过配置项 `BATCH_SIZE` 控制，无需改代码。

---

## 四、数据转换规则

### 4.1 净销量计算

每个常规订单的净销量计算（见 [表设计/01_设计概述与销量计算.md](表设计/01_设计概述与销量计算.md)）：

```
净销量(net_quantity) =
    quantity                -- 第一部分：无退货常规订单
    processed_quantity      -- 第二部分：type=21/22 部分退货（已有剩余）
    -- 完全退货(type=11/12/13) 已在抽取阶段排除，净销量为 0 不计入
```

### 4.2 时间维度转换

`create_date` 为秒级时间戳（Integer），需转换为日期维度：

```python
from datetime import datetime

ts = row['create_date']                          # 秒级时间戳
dt = datetime.fromtimestamp(ts)                  # 转为 datetime
sale_date = dt.strftime('%Y-%m-%d')              # 日期键（按日聚合）
year_month = dt.strftime('%Y-%m')                # 月份键（按月聚合）
year = dt.year                                   # 年份键（按年聚合）
```

### 4.3 按 (oe, brand_name) 聚合

在内存中使用字典按 `(oe, brand_name)` 聚合，每个组合维护：

```python
# 聚合结构
aggregate = {
    (oe, brand_name): {
        'oe': oe,
        'brand_name': brand_name,
        'product_name': product_name,            # 取最新一条
        'barcode': barcode,                       # 取最新一条
        'daily_sales': defaultdict(int),          # {'YYYY-MM-DD': 净销量}
        'monthly_sales': defaultdict(int),        # {'YYYY-MM': 净销量}
        'all_records': []                         # 全部记录（用于标准差计算）
    }
}
```

### 4.4 销量统计字段计算

| 目标字段 | 计算公式 | 时间范围 |
|---------|---------|---------|
| `annual_sales_1y` | Σ 净销量 | 近一年（过去 365 天） |
| `avg_daily_sales_1y` | annual_sales_1y / 365 | 近一年 |
| `avg_monthly_sales_1y` | annual_sales_1y / 12 | 近一年 |
| `sales_this_year` | Σ 净销量 | 当前自然年（1月1日至今日） |
| `sales_last_year` | Σ 净销量 | 上一完整自然年 |
| `sales_std_dev_1y` | 基于近 12 个月各月净销量的标准差 | 近 12 个月 |
| `monthly_sales_json` | `{"YYYY-MM": 净销量, ...}` | 近 12 个月 |

#### 标准差计算（总体标准差）

```python
import statistics

# 近12个月各月净销量列表
monthly_values = list(monthly_sales_1y.values())
sales_std_dev_1y = statistics.pstdev(monthly_values) if len(monthly_values) > 1 else 0
```

#### monthly_sales_json 格式

```json
{
    "2025-09": 120,
    "2025-10": 135,
    "2025-11": 98,
    "2025-12": 156,
    "2026-01": 142,
    "2026-02": 110,
    "2026-03": 128,
    "2026-04": 145,
    "2026-05": 160,
    "2026-06": 132,
    "2026-07": 148,
    "2026-08": 105
}
```

> **季节系数计算**由安全库存计算任务完成（读取 `monthly_sales_json` 取当月销量 / `avg_monthly_sales_1y`），本表仅提供原始数据。

---

## 五、数据加载策略

### 5.1 全量重写模式

```
每日流程：
  1. 备份当前 oe_parts_sales 表（安全机制，见第六节）
  2. 清空 oe_parts_sales 表（TRUNCATE 或 DELETE）
  3. 分批读取源数据 → 内存聚合 → 批量插入 oe_parts_sales
  4. 校验数据完整性（行数、关键聚合值）
  5. 清理备份（可选，保留 N 天）
```

### 5.2 清空方式选择

| 方式 | 优点 | 缺点 | 适用场景 |
|------|------|------|---------|
| `TRUNCATE TABLE` | 极快，重置自增ID，不产生大量binlog | 隐式提交，无法在事务中回滚 | ✅ 推荐用于每日全量重写 |
| `DELETE FROM` | 可在事务中回滚 | 慢，产生大量binlog，不重置自增ID | 仅在需要事务保护时使用 |

**推荐方案**：`TRUNCATE TABLE` + 备份表兜底。由于 TRUNCATE 无法回滚，通过先备份后清空的方式保证数据安全（见第六节）。

### 5.3 批量插入

参考现有 `batch_upsert_sales_order_history` 的批量插入模式（[sales_order_history_crawler.py:134-168](file:///e:/Barbori/complete_project/beihuo_system/app/scripts/spiders/spiders_services/sales_order_history_crawler.py#L134-168)），使用 SQLAlchemy `insert().values()` 批量插入：

```python
from sqlalchemy import insert
from app.models.orm_models.stock_safe_models.oe_parts_sales import OePartsSales
from app.utils.orm.session import orm_session

def batch_insert_oe_parts_sales(records: list) -> int:
    """批量插入销量统计记录"""
    if not records:
        return 0
    with orm_session() as session:
        stmt = insert(OePartsSales.__table__).values(records)
        result = session.execute(stmt)
        return result.rowcount
```

**插入批次大小**：聚合后的 (oe, brand_name) 组合约数万条，可一次性插入；若超过 1 万条，分批 2000 条/批插入，避免单条 SQL 过长。

---

## 六、清空表数据的安全机制

### 6.1 安全清空流程

```
┌─────────────────────────────────────────────────────┐
│  Step 1: 创建备份表（按日期命名）                       │
│  CREATE TABLE oe_parts_sales_backup_YYYYMMDD         │
│  AS SELECT * FROM oe_parts_sales;                    │
├─────────────────────────────────────────────────────┤
│  Step 2: 校验备份成功                                  │
│  对比备份表与原表行数，确保一致                          │
├─────────────────────────────────────────────────────┤
│  Step 3: 清空原表                                     │
│  TRUNCATE TABLE oe_parts_sales;                      │
├─────────────────────────────────────────────────────┤
│  Step 4: 写入新数据                                   │
│  分批读取源数据 → 聚合 → 批量插入                       │
├─────────────────────────────────────────────────────┤
│  Step 5: 校验新数据                                   │
│  对比新数据行数与源数据去重 (oe, brand_name) 数          │
├─────────────────────────────────────────────────────┤
│  Step 6: 清理旧备份（保留最近 3 天）                    │
│  DROP TABLE oe_parts_sales_backup_YYYYMMDD (3天前)   │
└─────────────────────────────────────────────────────┘
```

### 6.2 备份表管理

```sql
-- 创建备份（每日执行前）
CREATE TABLE IF NOT EXISTS oe_parts_sales_backup_YYYYMMDD
    AS SELECT * FROM oe_parts_sales;

-- 清理 3 天前的备份（每日执行后）
DROP TABLE IF EXISTS oe_parts_sales_backup_YYYYMMDD_minus3;
```

> **保留 3 天备份**：足够应对回滚需求，同时避免备份表占用过多存储。

### 6.3 失败回滚策略

由于 `TRUNCATE` 无法事务回滚，采用**备份恢复**方式：

| 失败时机 | 回滚方式 |
|---------|---------|
| 备份阶段失败 | 不影响原表，记录日志，跳过本次刷新 |
| 清空后、写入前失败 | 从备份表恢复：`INSERT INTO oe_parts_sales SELECT * FROM oe_parts_sales_backup_YYYYMMDD` |
| 写入阶段失败（部分写入） | 从备份表恢复（重新全量写入） |
| 校验失败 | 从备份表恢复，记录异常日志 |

### 6.4 stock_safe 表的清空

`stock_safe` 安全库存表同样每日清空重写，安全机制与 `oe_parts_sales` 一致。但需注意：

- **执行顺序**：先刷新 `oe_parts_sales`（销量表），再刷新 `stock_safe`（安全库存表），因为后者依赖前者的 `avg_daily_sales`、`sales_std_dev_1y`、`monthly_sales_json`、`avg_monthly_sales_1y`
- **独立备份**：`stock_safe` 表独立备份，备份表命名为 `stock_safe_backup_YYYYMMDD`

---

## 七、分批处理策略（针对 sales_order_history ~20万条）

### 7.1 分批读取机制设计

采用 **Keyset Pagination（主键游标分页）**，详见第三节。核心机制：

```python
def read_sales_order_history_batch(last_id: int, batch_size: int) -> tuple:
    """
    分批读取无退货常规订单
    返回: (本批记录列表, 本批最大 orders_items_id)
    """
    with orm_session() as session:
        sql = text("""
            SELECT s.orders_items_id, s.number AS oe, s.brand_name,
                   s.pdname AS product_name, s.frey_no AS barcode,
                   s.quantity AS net_quantity, s.create_date
            FROM sales_order_history s
            WHERE s.order_type_id = 1
              AND s.number IS NOT NULL AND s.number != ''
              AND s.brand_name IS NOT NULL AND s.brand_name != ''
              AND s.orders_items_id > :last_id
              AND NOT EXISTS (
                  SELECT 1 FROM stock_safe_refund_ref r
                  WHERE r.normal_order_items_id = s.orders_items_id
              )
            ORDER BY s.orders_items_id ASC
            LIMIT :batch_size
        """)
        result = session.execute(sql, {
            "last_id": last_id,
            "batch_size": batch_size
        }).mappings().all()

        records = [dict(row) for row in result]
        max_id = records[-1]['orders_items_id'] if records else last_id
        return records, max_id
```

### 7.2 每批次数据量设定

| 配置项 | 值 | 调整依据 |
|--------|-----|---------|
| `BATCH_SIZE` | 5000 | 20万条 → 40批；每批内存 ~5MB；单批查询 < 1秒 |
| 最大批数 | 无限制 | 以"本批返回空"为终止条件，不预设批数 |
| 超时阈值 | 30 秒/批 | 单批超过 30 秒告警，可能需调小 BATCH_SIZE |

### 7.3 批次处理的事务管理

**关键原则**：聚合阶段（读取+转换）与加载阶段（清空+插入）分离，各自独立事务。

```
阶段1：抽取与聚合（只读，多批）
  ├── 批1读取 (只读事务) → 内存聚合
  ├── 批2读取 (只读事务) → 内存聚合
  └── ... 直到本批返回空
  → 得到完整的 {(oe, brand_name): 聚合结果} 字典

阶段2：加载（写事务）
  ├── 备份表 (独立事务)
  ├── TRUNCATE 原表 (DDL，隐式提交)
  ├── 批量插入新数据 (写事务，可分批)
  └── 校验 (只读)
```

> **事务粒度**：抽取阶段每批读取使用独立的只读 `orm_session()`，无锁竞争；加载阶段 TRUNCATE 后批量插入，插入部分若数据量大可分批提交（每 2000 条一个事务），但需在 TRUNCATE 之后。

### 7.4 处理进度监控与日志记录

#### 进度检查点表

```sql
CREATE TABLE IF NOT EXISTS `oe_parts_sales_sync_checkpoint` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `task_name` VARCHAR(100) NOT NULL COMMENT '任务名称',
    `last_processed_id` BIGINT NOT NULL DEFAULT 0 COMMENT '最后处理的 orders_items_id',
    `last_batch_time` DATETIME COMMENT '最后批次处理时间',
    `total_processed` BIGINT NOT NULL DEFAULT 0 COMMENT '累计处理记录数',
    `batch_count` INT NOT NULL DEFAULT 0 COMMENT '已处理批次数',
    `status` VARCHAR(20) NOT NULL DEFAULT 'running' COMMENT 'running/completed/failed',
    `started_at` DATETIME COMMENT '任务开始时间',
    `completed_at` DATETIME COMMENT '任务完成时间',
    `error_message` TEXT COMMENT '错误信息（失败时）',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_task_name` (`task_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='销量表同步检查点（断点续传）';
```

#### 日志记录规范

使用项目现有 `logging` 模块（参考 [task_manager.py:15](file:///e:/Barbori/complete_project/beihuo_system/app/core/task_manager.py#L15)）：

```python
import logging
logger = logging.getLogger('oe_parts_sales_refresh')

# 每批记录日志
logger.info(
    f"[批次 {batch_count}] 处理 {len(records)} 条 | "
    f"累计 {total_processed} 条 | "
    f"游标 orders_items_id={max_id} | "
    f"耗时 {elapsed:.2f}s"
)

# 阶段日志
logger.info(f"[阶段1] 开始抽取 sales_order_history，last_id={last_id}")
logger.info(f"[阶段1] 抽取完成，共 {total_processed} 条，聚合为 {len(aggregate)} 个 (oe, brand_name) 组合")
logger.info(f"[阶段2] 开始加载：备份 → 清空 → 插入 → 校验")
logger.info(f"[完成] oe_parts_sales 刷新完成，共写入 {inserted} 行，耗时 {total_elapsed:.1f}s")
```

#### 进度输出示例

```
[2026-08-05 03:00:01] [INFO] [开始] oe_parts_sales 每日刷新任务启动
[2026-08-05 03:00:02] [INFO] [阶段1] 开始抽取 sales_order_history（分批读取）
[2026-08-05 03:00:03] [INFO] [批次 1] 处理 5000 条 | 累计 5000 条 | 游标 id=12345 | 耗时 0.8s
[2026-08-05 03:00:04] [INFO] [批次 2] 处理 5000 条 | 累计 10000 条 | 游标 id=24680 | 耗时 0.7s
...
[2026-08-05 03:00:35] [INFO] [批次 40] 处理 3210 条 | 累计 198210 条 | 游标 id=999999 | 耗时 0.6s
[2026-08-05 03:00:36] [INFO] [阶段1] 抽取完成，共 198210 条，聚合为 15234 个 (oe, brand_name) 组合
[2026-08-05 03:00:37] [INFO] [阶段2-1] 备份完成：oe_parts_sales_backup_20260805（15200 行）
[2026-08-05 03:00:38] [INFO] [阶段2-2] 清空完成：TRUNCATE oe_parts_sales
[2026-08-05 03:00:42] [INFO] [阶段2-3] 插入完成：15234 行（分 8 批，每批 2000 条）
[2026-08-05 03:00:43] [INFO] [阶段2-4] 校验通过：源去重 15234 = 目标 15234
[2026-08-05 03:00:44] [INFO] [完成] oe_parts_sales 刷新完成，耗时 43.0s
```

### 7.5 断点续传方案

#### 断点记录机制

每批处理完成后，更新检查点表的 `last_processed_id`：

```python
def update_checkpoint(task_name: str, last_id: int, total: int, batch_count: int, status: str):
    """更新检查点"""
    with orm_session() as session:
        sql = text("""
            INSERT INTO oe_parts_sales_sync_checkpoint
                (task_name, last_processed_id, total_processed, batch_count, status, last_batch_time)
            VALUES (:task_name, :last_id, :total, :batch_count, :status, NOW())
            ON DUPLICATE KEY UPDATE
                last_processed_id = VALUES(last_processed_id),
                total_processed = VALUES(total_processed),
                batch_count = VALUES(batch_count),
                status = VALUES(status),
                last_batch_time = NOW()
        """)
        session.execute(sql, {
            "task_name": task_name, "last_id": last_id,
            "total": total, "batch_count": batch_count, "status": status
        })
```

#### 断点恢复流程

```
任务启动时：
  1. 查询检查点表，获取上次 last_processed_id
  2. 若 status='running' 且 last_batch_time 距今 < 1小时 → 判定为异常中断，从 last_processed_id 续传
  3. 若 status='completed' 或无记录 → 全新开始，last_processed_id = 0
  4. 若 status='failed' → 根据错误信息决定是否续传或重新开始
```

```python
def get_checkpoint(task_name: str) -> dict:
    """获取检查点"""
    with orm_session() as session:
        sql = text("""
            SELECT last_processed_id, total_processed, batch_count, status, last_batch_time
            FROM oe_parts_sales_sync_checkpoint
            WHERE task_name = :task_name
        """)
        row = session.execute(sql, {"task_name": task_name}).mappings().first()
        return dict(row) if row else None
```

#### 续传场景说明

| 场景 | 处理方式 |
|------|---------|
| 阶段1（抽取）中断 | 从 `last_processed_id` 续传读取，已聚合的内存数据保留（若进程存活）；若进程重启则重新聚合（因内存数据丢失） |
| 阶段2（加载）中断 | 由于 TRUNCATE 已执行，需从备份表恢复后重新进入阶段2 |
| 进程崩溃重启 | 检查点 status='running' 且超时 → 判定为崩溃，从 last_processed_id 续传阶段1 |

> **注意**：断点续传主要保护**阶段1（抽取）**。阶段2（加载）由于涉及 TRUNCATE，失败后通过备份表恢复并重做整个阶段2。全量重写模式下，最坏情况是从头重跑，耗时约 1 分钟，影响可控。

---

## 八、异常处理流程

### 8.1 异常分类与处理

| 异常类型 | 触发场景 | 处理策略 |
|---------|---------|---------|
| 数据库连接异常 | orm_session 获取连接失败 | 重试 3 次（间隔 5 秒），仍失败则记录日志并终止任务 |
| 查询超时 | 分批查询超过 30 秒 | 记录日志，将 BATCH_SIZE 减半后重试本批；连续 3 次失败则终止 |
| 数据异常 | quantity 为负、create_date 为空等 | 跳过异常记录，记录警告日志，不影响整体流程 |
| 备份失败 | CREATE TABLE 备份失败 | 终止任务（不清空原表），记录错误日志 |
| 清空失败 | TRUNCATE 失败 | 终止任务，从备份恢复（若已备份） |
| 插入失败 | 批量插入违反唯一键等 | 回滚本批插入，记录错误日志；若为唯一键冲突，跳过冲突记录后重试 |
| 校验失败 | 新数据行数与源去重数不一致 | 从备份恢复，记录错误日志，发送告警 |

### 8.2 异常处理代码框架

```python
def oe_parts_sales_daily_refresh():
    """每日刷新主入口"""
    task_name = 'oe_parts_sales_daily_refresh'
    logger = logging.getLogger('oe_parts_sales_refresh')

    try:
        logger.info(f"[开始] {task_name} 任务启动")

        # 阶段1：抽取与聚合（支持断点续传）
        aggregate = extract_and_aggregate(task_name)

        # 阶段2：加载（备份→清空→插入→校验）
        load_with_safety(aggregate)

        # 更新检查点为完成
        update_checkpoint(task_name, last_id=0, total=len(aggregate),
                          batch_count=0, status='completed')
        logger.info(f"[完成] {task_name} 完成，共 {len(aggregate)} 个 (oe, brand_name) 组合")

    except Exception as e:
        logger.error(f"[失败] {task_name} 异常: {e}", exc_info=True)
        update_checkpoint(task_name, last_id=0, total=0,
                          batch_count=0, status='failed',
                          error_message=str(e))
        # 发送告警（可接入企业微信/邮件）
        send_alert(f"oe_parts_sales 刷新失败: {e}")


def extract_and_aggregate(task_name: str) -> dict:
    """阶段1：分批抽取并聚合（支持断点续传）"""
    checkpoint = get_checkpoint(task_name)
    last_id = checkpoint['last_processed_id'] if checkpoint and should_resume(checkpoint) else 0
    batch_count = checkpoint['batch_count'] if checkpoint and should_resume(checkpoint) else 0
    total_processed = checkpoint['total_processed'] if checkpoint and should_resume(checkpoint) else 0

    aggregate = {}  # {(oe, brand_name): 聚合结果}
    batch_size = BATCH_SIZE  # 5000

    while True:
        records, max_id = read_sales_order_history_batch(last_id, batch_size)
        if not records:
            break  # 全部读取完成

        # 内存聚合
        for row in records:
            key = (row['oe'], row['brand_name'])
            if key not in aggregate:
                aggregate[key] = init_aggregate(row)
            merge_record(aggregate[key], row)

        # 更新游标与检查点
        last_id = max_id
        batch_count += 1
        total_processed += len(records)
        update_checkpoint(task_name, last_id, total_processed, batch_count, 'running')

        logger.info(f"[批次 {batch_count}] 处理 {len(records)} 条 | 累计 {total_processed} 条 | 游标 id={max_id}")

    # 合并第二部分（type=21/22，一次性读取）
    type21_22_records = read_type21_22_records()
    for row in type21_22_records:
        key = (row['oe'], row['brand_name'])
        if key not in aggregate:
            aggregate[key] = init_aggregate(row)
        merge_record(aggregate[key], row)

    logger.info(f"[阶段1] 抽取完成，共 {total_processed} 条 + {len(type21_22_records)} 条(type21/22)，"
                f"聚合为 {len(aggregate)} 个 (oe, brand_name) 组合")
    return aggregate


def load_with_safety(aggregate: dict):
    """阶段2：安全加载（备份→清空→插入→校验）"""
    backup_table = f"oe_parts_sales_backup_{datetime.now().strftime('%Y%m%d')}"

    # Step1: 备份
    create_backup(backup_table)
    logger.info(f"[阶段2-1] 备份完成: {backup_table}")

    # Step2: 清空
    try:
        truncate_oe_parts_sales()
        logger.info("[阶段2-2] 清空完成: TRUNCATE oe_parts_sales")
    except Exception as e:
        # 清空失败，尝试从备份恢复
        restore_from_backup(backup_table)
        raise

    # Step3: 批量插入
    try:
        records = build_insert_records(aggregate)
        inserted = batch_insert_in_chunks(records, chunk_size=2000)
        logger.info(f"[阶段2-3] 插入完成: {inserted} 行")
    except Exception as e:
        # 插入失败，从备份恢复
        restore_from_backup(backup_table)
        raise

    # Step4: 校验
    if not validate_row_count(len(aggregate)):
        restore_from_backup(backup_table)
        raise ValueError("校验失败: 行数不一致")

    logger.info("[阶段2-4] 校验通过")
```

### 8.3 告警机制

异常发生时，通过现有通知机制发送告警（参考 [task_manager.py](file:///e:/Barbori/complete_project/beihuo_system/app/core/task_manager.py) 中 `notification_manager` 的用法）：

```python
def send_alert(message: str):
    """发送告警通知"""
    try:
        from app.sockets import notification_manager
        notification_manager.send_notification(
            notification_type='error',
            message=f'oe_parts_sales 刷新异常: {message}',
            data={}
        )
    except Exception:
        pass  # 告警失败不影响主流程
```

---

## 九、程序流程图

### 9.1 整体流程

```
┌─────────────────────────────────────────────────────────────┐
│  定时触发（每日 03:00，LightweightTaskManager cron）          │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  初始化：读取检查点，判断是否断点续传                           │
│  ┌─ status=running 且超时 → 续传（last_processed_id）        │
│  └─ status=completed/failed/无记录 → 全新开始（last_id=0）   │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  阶段1：抽取与聚合                                            │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  1a. 分批读取 sales_order_history（Keyset Pagination） │  │
│  │      WHILE 本批返回非空:                               │  │
│  │        读取 5000 条 (orders_items_id > last_id)        │  │
│  │        内存聚合到 {(oe, brand_name): stats}            │  │
│  │        更新检查点 (last_processed_id, batch_count)     │  │
│  │        记录进度日志                                    │  │
│  │        IF 异常 → 更新检查点 status=failed, 记录日志    │  │
│  └───────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  1b. 一次性读取 stock_safe_refund_ref type=21/22       │  │
│  │      合并到内存聚合字典                                 │  │
│  └───────────────────────────────────────────────────────┘  │
│  输出: aggregate 字典 {数千~数万个 (oe, brand_name) 组合}    │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  阶段2：安全加载                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  2a. 备份: CREATE TABLE backup_YYYYMMDD AS SELECT *   │  │
│  │  2b. 校验备份行数 = 原表行数                            │  │
│  │  2c. 清空: TRUNCATE TABLE oe_parts_sales              │  │
│  │  2d. 批量插入: 每 2000 条/批，INSERT INTO oe_parts_sales│ │
│  │  2e. 校验: 新表行数 = len(aggregate)                   │  │
│  │  2f. 清理旧备份: DROP TABLE backup_3天前               │  │
│  └───────────────────────────────────────────────────────┘  │
│  任一子步骤失败 → 从备份恢复 → 记录错误 → 发送告警           │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  更新检查点 status=completed，记录完成日志                     │
└──────────────────────────────┬──────────────────────────────┘
                               ▼
                    后续: stock_safe 表刷新
                  （依赖 oe_parts_sales 完成）
```

### 9.2 与 stock_safe 表的协同

```
每日刷新序列（凌晨）:
  03:00  oe_parts_sales 刷新（本流程）
           │
           ▼  依赖 avg_daily_sales_1y, sales_std_dev_1y,
              monthly_sales_json, avg_monthly_sales_1y
  03:45  stock_safe 刷新（独立流程，结构类似）
           │
           ▼  依赖 abc_classification, available_stock(外部)
  04:00  完成，前端可查询最新库存状态
```

---

## 十、待确认事项

> 以下事项需业务方/开发方确认后方可进入代码实现阶段。

1. **执行时间**：凌晨 3:00 是否合适？需确认退货匹配任务（step1/2/3）的完成时间，确保 `stock_safe_refund_ref` 数据完整。

2. **BATCH_SIZE 调优**：5000 条/批是否合适？需在实际数据量下测试 `NOT EXISTS` 子查询的性能。若性能不佳，可考虑先将 `stock_safe_refund_ref.normal_order_items_id` 预加载为集合，在 Python 中过滤。

3. **备份保留天数**：3 天是否足够？是否需要更长的恢复窗口？

4. **告警通道**：异常告警通过 `notification_manager`（WebSocket 推送）是否足够？是否需补充企业微信/邮件通知？

5. **stock_safe 表刷新流程**：本文档仅涉及 `oe_parts_sales`，`stock_safe` 的刷新流程（读取销量表 + 外部库存 + ABC分类 + 计算公式）是否需单独设计文档？

6. **断点续传的必要性**：全量重写模式下，整体耗时约 1 分钟（20万条抽取 + 数万条插入）。断点续传主要应对极端情况（如数据库故障导致抽取中断）。是否值得引入检查点表的额外复杂度？若判断不必要，可简化为"失败即重跑"。

7. **available_stock 数据来源**：`stock_safe` 表的 `available_stock` 字段数据来源待确认（见 [表设计/06_待确认事项与公式自检.md](表设计/06_待确认事项与公式自检.md)），影响 `stock_safe` 刷新流程设计。

---

## 关联文档

- [表设计/README.md](表设计/README.md) — 表结构设计索引
- [表设计/01_设计概述与销量计算.md](表设计/01_设计概述与销量计算.md) — 净销量计算逻辑
- [表设计/02_销量表_oe_parts_sales.md](表设计/02_销量表_oe_parts_sales.md) — 销量表字段定义
- [表设计/04_数据关系与同步流程.md](表设计/04_数据关系与同步流程.md) — 数据流向图
- [表设计/05_设计说明与风险.md](表设计/05_设计说明与风险.md) — 设计说明与潜在风险

---

**文档版本**：v1.0
**创建日期**：2026-08-05
