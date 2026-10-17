# -*- coding:utf-8 -*-
# @Time    : 2026/10/16
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : push_data.py
# @Software: trae-cn

"""
安全库存数据推送 CRM 服务

职责：
  将 stock_safe 表中的安全库存数据推送到 CRM 系统。
  推送前通过 OE 号调用 CRM Product.Product/list 接口，
  匹配获取对应商品的 product_id，再调用 Product.Product/saveSafeStock 推送。

核心函数：
  - push_stock_safe_data: 单条 OE 推送安全库存
  - batch_push_stock_safe_data: 批量推送安全库存
"""

from app.scripts.spiders.spider_entities.crm_gzbbr import CrmGzbbrSpider
from app.scripts.spiders.spiders_services.log import get_stock_safe_logger
from app.utils.orm.session import orm_session
from app.dao.stock_safe_dao.replenish_dao import fetch_replenish_data

# 统一日志记录器，复用 stock_safe 模块的日志配置
logger = get_stock_safe_logger()


def _extract_product_ids(product_list, number, brand_name=None):
    """
    从 Product.Product/list 接口返回数据中提取匹配的 product_id。

    接口返回结构：
        {
          "data": {
            "data": [
              {
                "child": [
                  {"product_id": 123, "number": "OE001", "brand_name": "品牌A", "stock": 10, "price": 99.9, "name": "..."}
                ]
              }
            ]
          }
        }

    匹配规则：
      1. OE 号（number）必须精确匹配
      2. 若传入 brand_name，则品牌名也必须精确匹配；否则不过滤品牌

    :param product_list: 接口返回的原始 JSON 数据（已解析为字典）
    :param number: OE 号，用于精确匹配
    :param brand_name: 品牌名称（可选），有值时需精确匹配
    :return: 匹配到的 product_id 列表（int 类型）
    """
    # 参数校验
    if not product_list or not isinstance(product_list, dict):
        return []

    # 提取 data.data 层级
    data_obj = product_list.get('data', {})
    if not data_obj or not isinstance(data_obj, dict):
        return []

    data_list = data_obj.get('data', [])
    if not data_list or not isinstance(data_list, list):
        return []

    # 展平所有 child 列表中的产品
    all_products = []
    for item in data_list:
        child_list = item.get('child', [])
        if child_list and isinstance(child_list, list):
            all_products.extend(child_list)

    if not all_products:
        return []

    # 标准化输入 OE 号
    target_number = str(number).strip()

    matched = []
    for product in all_products:
        # 精确匹配 OE 号
        if str(product.get('number', '')).strip() != target_number:
            continue
        # 品牌名精确匹配（仅当传入 brand_name 时过滤）
        if brand_name:
            if str(product.get('brand_name', '')).strip() != str(brand_name).strip():
                continue

        pid = product.get('product_id')
        if pid is not None and pid != '':
            # 转换为 int（接口可能返回字符串类型的数字）
            try:
                matched.append(int(pid))
            except (TypeError, ValueError):
                matched.append(pid)

    return matched


def push_stock_safe_data(number, brand_name, safety_stock=0, max_stock=0,
                         season_coefficient=1, warehouse_id=1, isnotstock="0",
                         spider=None):
    """
    通过 OE 号获取 product_id 后，推送安全库存数据到 CRM。

    执行流程：
      1. 调用 Product.Product/list 接口按 OE 号查询，精确匹配获取 product_id
      2. 组装安全库存参数，调用 Product.Product/saveSafeStock 接口推送

    :param number: OE 号（对应 stock_safe.number 字段），必填
    :param brand_name: 品牌名称（对应 stock_safe.brand_name 字段），必填，用于精确匹配 product_id
    :param safety_stock: 安全库存数量（对应 stock_safe.safety_stock 字段）
    :param max_stock: 最大库存数量（对应 stock_safe.stock_upper_limit 字段）
    :param season_coefficient: 季节系数（对应 stock_safe.season_coefficient 字段），默认 1
    :param warehouse_id: 仓库 ID，默认 1
    :param isnotstock: 是否无库存（"0"=否, "1"=是），默认 "0"
    :param spider: 外部传入的 CrmGzbbrSpider 实例。
                   批量调用时建议复用同一实例以减少连接开销；
                   未传入时自动创建并在结束时关闭。
    :return: dict，包含推送结果：
             - success: 是否成功
             - product_ids: 匹配到的 product_id 列表
             - pushed_count: 成功推送的数量
             - message: 结果说明
    """
    if not number:
        return {"success": False, "product_ids": [], "pushed_count": 0, "message": "OE号为空"}

    number = str(number).strip()
    if not number:
        return {"success": False, "product_ids": [], "pushed_count": 0, "message": "OE号为空"}

    if not brand_name:
        return {"success": False, "product_ids": [], "pushed_count": 0, "message": "品牌名称为空"}

    brand_name = str(brand_name).strip()
    if not brand_name:
        return {"success": False, "product_ids": [], "pushed_count": 0, "message": "品牌名称为空"}

    # 判断是否需要自行管理爬虫生命周期
    own_spider = spider is None
    if own_spider:
        spider = CrmGzbbrSpider()

    try:
        # 步骤1：调用 CRM 接口按 OE 号查询产品列表，获取 product_id
        response = spider.get_product_product_list(number=number)
        product_list = response.json() if response else None
        product_ids = _extract_product_ids(product_list, number, brand_name)

        if not product_ids:
            logger.warning(f"[推送安全库存] OE={number} 品牌={brand_name} 未匹配到 product_id，跳过推送")
            return {"success": False, "product_ids": [], "pushed_count": 0, "message": "未匹配到product_id"}

        logger.info(f"[推送安全库存] OE={number} 品牌={brand_name} 匹配 {len(product_ids)} 个 product_id: {product_ids}")

        # 步骤2：组装 saveSafeStock 接口参数并推送
        items = []
        for pid in product_ids:
            items.append({
                "product_id": str(pid),
                "warehouse_id": warehouse_id,
                "safety_stock": safety_stock,
                "max_stock": max_stock,
                "isnotstock": isnotstock,
                "seasonal_coefficient": season_coefficient,
            })

        push_resp = spider.save_safe_stock(items)
        push_result = push_resp.json() if push_resp else {}

        pushed_count = len(product_ids)
        success = push_result.get("status") == 200

        if success:
            logger.info(
                f"[推送安全库存成功] OE={number} 推送 {pushed_count} 条 "
                f"(safety_stock={safety_stock}, max_stock={max_stock})"
            )
        else:
            logger.error(
                f"[推送安全库存失败] OE={number} 响应: {push_result}"
            )

        return {
            "success": success,
            "product_ids": product_ids,
            "pushed_count": pushed_count if success else 0,
            "message": push_result.get("msg", ""),
        }

    except Exception as e:
        logger.error(
            f"[推送安全库存异常] OE={number} 品牌={brand_name} 异常: {e}",
            exc_info=True,
        )
        return {"success": False, "product_ids": [], "pushed_count": 0, "message": str(e)}

    finally:
        # 仅关闭自行创建的爬虫实例，外部传入的由调用方负责关闭
        if own_spider:
            spider.close()






# if __name__ == '__main__':
#     result = push_stock_safe_data(
#         number="31108854989",
#         brand_name="原厂国内4s件",
#         safety_stock=20,
#         max_stock=30,
#         season_coefficient=1,
#     )
#     print(result)
    



def batch_push_stock_safe_data(records):
    """
    批量推送安全库存数据到 CRM。

    对每条记录按 OE 号 + 品牌循环调用 push_stock_safe_data，
    复用同一个 CrmGzbbrSpider 实例以减少连接开销。

    :param records: 字典列表，每个字典包含：
                    - number: OE 号（必填）
                    - brand_name: 品牌名称（必填）
                    - safety_stock: 安全库存数量
                    - max_stock: 最大库存数量
                    - season_coefficient: 季节系数（可选，默认 1）
                    - warehouse_id: 仓库 ID（可选，默认 1）
                    - isnotstock: 是否无库存（可选，默认 "0"）
    :return: dict，包含批量推送统计：
             - total: 总记录数
             - success_count: 成功推送数
             - fail_count: 失败数
             - details: 每条记录的推送结果列表
    """
    if not records:
        return {"total": 0, "success_count": 0, "fail_count": 0, "details": []}

    spider = CrmGzbbrSpider()
    details = []
    success_count = 0
    fail_count = 0
    processed_keys = set()  # 用于跳过重复的 (number, brand_name) 组合

    try:
        total = len(records)
        for idx, record in enumerate(records, start=1):
            number = record.get('number')
            brand_name = record.get('brand_name')

            if not number:
                details.append({"number": number, "brand_name": brand_name,
                                "success": False, "message": "OE号为空"})
                fail_count += 1
                continue

            if not brand_name:
                details.append({"number": number, "brand_name": brand_name,
                                "success": False, "message": "品牌名称为空"})
                fail_count += 1
                continue

            # 跳过已处理过的相同 (number, brand_name) 组合，避免重复推送
            key = f"{number}|{brand_name}"
            if key in processed_keys:
                continue
            processed_keys.add(key)

            # 调用单条推送
            result = push_stock_safe_data(
                number=number,
                brand_name=brand_name,
                safety_stock=record.get('safety_stock', 0),
                max_stock=record.get('max_stock', 0),
                season_coefficient=record.get('season_coefficient', 1),
                warehouse_id=record.get('warehouse_id', 1),
                isnotstock=record.get('isnotstock', '0'),
                spider=spider,
            )

            result["number"] = number
            result["brand_name"] = brand_name
            details.append(result)

            if result.get("success"):
                success_count += 1
            else:
                fail_count += 1

            # 每处理 50 条输出一次进度日志
            if idx % 50 == 0:
                logger.info(
                    f"[批量推送安全库存进度] {idx}/{total} "
                    f"(成功={success_count}, 失败={fail_count})"
                )
    finally:
        spider.close()

    logger.info(
        f"[批量推送安全库存完成] 总数={len(records)} "
        f"成功={success_count} 失败={fail_count}"
    )

    return {
        "total": len(records),
        "success_count": success_count,
        "fail_count": fail_count,
        "details": details,
    }


def fetch_replenish_records() -> list:
    """
    从 stock_safe 表查询符合补货条件的记录。

    筛选条件与补货清单 Excel（replenish.py）完全一致：
      - 销售状态（sales_status）：销量低、销量正常
      - 库存状态（stock_status）：需补货|可卖天数较少、需补货、紧急补货

    排序：库存状态按紧急程度（紧急补货 > 需补货|可卖天数较少 > 需补货），
          再按可用库存升序。

    :return: 符合补货条件的记录列表（每项为字典，包含 stock_safe 全字段）
    """
    with orm_session() as session:
        records = fetch_replenish_data(session)
    logger.info(f"[推送安全库存] 查询到 {len(records)} 条需补货记录")
    return records


def push_replenish_data_to_crm() -> dict:
    """
    查询需补货的安全库存数据并推送到 CRM。

    执行流程：
      1. 从 stock_safe 表查询符合补货条件的记录（与补货 Excel 筛选条件一致）
      2. 转换为推送所需格式：
         - number: OE 号
         - brand_name: 品牌名
         - safety_stock: 调整后安全库存（stock_safe.safety_stock）
         - max_stock: 库存上限（stock_safe.stock_upper_limit）
         - season_coefficient: 季节系数（stock_safe.season_coefficient）
      3. 调用 batch_push_stock_safe_data 批量推送到 CRM

    :return: dict，包含推送统计：
             - total: 总记录数
             - success_count: 成功推送数
             - fail_count: 失败数
             - details: 每条记录的推送结果列表
    """
    logger.info("[推送安全库存] ====== 开始执行 ======")

    # 步骤1：查询符合补货条件的安全库存数据
    records = fetch_replenish_records()
    if not records:
        logger.info("[推送安全库存] 无需补货的记录，跳过推送")
        return {"total": 0, "success_count": 0, "fail_count": 0, "details": []}

    # 步骤2：转换为推送所需格式
    push_records = []
    for rec in records:
        push_records.append({
            "number": rec.get("number"),
            "brand_name": rec.get("brand_name"),
            "safety_stock": rec.get("safety_stock", 0),
            "max_stock": rec.get("stock_upper_limit", 0),
            "season_coefficient": rec.get("season_coefficient", 1),
        })

    logger.info(f"[推送安全库存] 待推送 {len(push_records)} 条")

    # 步骤3：批量推送到 CRM
    result = batch_push_stock_safe_data(push_records)

    logger.info(
        f"[推送安全库存] ====== 完成 总数={result['total']} "
        f"成功={result['success_count']} 失败={result['fail_count']} ======"
    )

    return result

# if __name__ == '__main__':
#     result = push_replenish_data_to_crm()
#     print(result)