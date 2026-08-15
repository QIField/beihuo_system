# -*- coding:utf-8 -*-
# @Time    : 2026/07/25
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : stock_safe_refund_ref_service.py
# @Software: trae-cn

# 导入时间模块，用于计算执行耗时
import time

# 导入日志工具，记录每次查询的参数与结果，便于排查匹配问题
from app.scripts.spiders.spiders_services.log import get_stock_safe_logger
# 导入DAO层的所有方法
from app.dao.stock_safe_dao.stock_safe_refund_ref_dao import (
    insert_unmatched_refund_orders,      # Step 1: 批量插入未匹配退货订单
    get_pending_refund_orders,           # 获取待匹配的退货订单列表
    find_matching_normal_orders,         # Step 2: 为退货订单查找匹配的常规订单
    insert_matched_refund,               # 批量插入匹配记录（一次性插入）
    batch_insert_matched_refund,         # 批量插入匹配记录
    delete_pending_by_refund_ids,        # 删除已匹配退货单的type=50占位行
    delete_type40_by_refund_ids,         # 删除step3已匹配退货单的type=40记录
    batch_update_unmatched_to_type40,    # 批量更新未匹配记录为type=40
    batch_update_unmatched_to_type41,    # step3结束后将仍未匹配的type=40更新为type=41
    get_type_summary,                    # 获取各类型分布统计
    get_pending_count,                   # 获取待处理订单数量
    get_type21_22_records,            # 获取常规订单有剩余的记录
    find_matching_refund_order_type3,    # Step 3: 为常规订单查找匹配的退货订单
    get_type3_count,
    update_type_to_by_normal_order,
    update_type_to_by_refund_order                      # 获取数量未完全抵消的退货订单数量
)

# 日志实例：success日志记录每次查询的参数与匹配结果，error日志记录未匹配等异常情况
logger = get_stock_safe_logger()




def _calculate_type(processed_quantity: int, mode: int) -> int:
    """
    根据处理数量和匹配模式计算type值
    
    type字段两位数编码规则：
    - 十位（第一位）：匹配状态分类
      1=完全退货（processed_quantity=0）
      2=部分退货（processed_quantity>0）
      3=退货数量超出（processed_quantity<0）
    - 个位（第二位）：匹配模式
      1=一对一匹配
      2=一对多-常规订单视角（一条常规订单被多条退货订单分摊）
      3=一对多-退货订单视角（一条退货订单分摊到多条常规订单）
    
    Args:
        processed_quantity: 处理数量（常规订单quantity + 退货订单quantity）
        mode: 匹配模式（1=一对一，2=一对多-常规订单，3=一对多-退货订单）
        
    Returns:
        两位数的type值（如11, 12, 13, 21, 22, 23, 31, 32, 33）
    """
    # 根据processed_quantity判断匹配状态（十位）
    if processed_quantity == 0:
        status = 1
    elif processed_quantity > 0:
        status = 2
    else:
        status = 3
    # 组合成两位数的type值
    return status * 10 + mode


def _find_combination_match(quantities: list, target: int) -> list:
    """
    查找数量列表中是否存在子集和等于目标值的组合（子集和问题）

    使用回溯算法查找第一个和为 target 的组合（按索引升序，即优先靠前的元素）。
    由于实际场景中常规订单数量通常较少（<=20），回溯算法性能可接受。

    Args:
        quantities: 数量列表（正数）
        target: 目标值（正数）

    Returns:
        匹配的索引列表（按升序），无匹配则返回空列表
    """
    # 快速剪枝：如果所有数量之和小于 target，不可能有解，直接返回空
    if sum(quantities) < target:
        return []

    def backtrack(start: int, current_sum: int, selected: list) -> list:
        """
        回溯搜索：从 start 索引开始，尝试将 quantities[i] 加入当前组合。
        - current_sum == target：找到解，返回已选索引列表
        - current_sum > target：超出目标值，剪枝回退（因数量均为正数，继续加只会更大）
        - start >= len：已遍历完所有元素，无解
        每次递归从 i+1 开始，确保每个元素只选一次（组合而非排列），且索引升序。
        """
        if current_sum == target:
            return selected
        if current_sum > target or start >= len(quantities):
            return []
        for i in range(start, len(quantities)):
            # 递归：将 quantities[i] 加入组合，从 i+1 继续搜索
            result = backtrack(i + 1, current_sum + quantities[i], selected + [i])
            if result:
                return result  # 找到第一个解即返回（不找全部解）
        return []

    return backtrack(0, 0, [])


def _sort_normal_orders(matched_normal_orders: list, refund_quantity_qty: int) -> None:
    """
    对匹配到的常规订单列表进行排序，优先匹配数量相同或组合匹配的订单

    排序策略（三级降级）：
    1. 有直接匹配（数量相等 → abs(refund)）：匹配项排最前，其余按数量降序
    2. 有组合匹配（子集和等于 abs(refund)）：组合成员排前面（按数量降序），其余按数量降序
    3. 无任何匹配：全部按数量降序（大→小）

    Args:
        matched_normal_orders: 匹配到的常规订单列表（原地排序）
        refund_quantity_qty: 退货数量（负数）
    """
    target = abs(refund_quantity_qty)
    quantities = [o["quantity"] for o in matched_normal_orders]

    # 策略1. 直接匹配：存在数量恰好等于退货数量(abs)的常规订单
    if target in quantities:
        # sort key: (quantity != target, -quantity)
        #   第一键: False(0)排前 → 数量等于target的订单排最前
        #   第二键: -quantity → 其余按数量降序（大→小）
        matched_normal_orders.sort(key=lambda x: (x["quantity"] != target, -x["quantity"]))
        return

    # 策略2. 组合匹配：存在多个常规订单数量之和等于退货数量(abs)
    combo_indices = _find_combination_match(quantities, target)
    if not combo_indices:
        # 策略3. 无任何匹配：全部按数量降序（大→小），优先消耗大额常规订单
        matched_normal_orders.sort(key=lambda x: -x["quantity"])
        return

    # 组合匹配排序：组合成员排前面，非组合成员排后面，各自内部按数量降序
    combo_set = set(combo_indices)
    indexed = list(enumerate(matched_normal_orders))
    # sort key: (是否组合成员, -quantity)
    #   第一键: 0(组合成员)排前, 1(非成员)排后
    #   第二键: -quantity → 各组内部按数量降序
    indexed.sort(key=lambda x: (
        0 if x[0] in combo_set else 1,
        -x[1]["quantity"] if x[0] in combo_set else -x[1]["quantity"]
    ))
    matched_normal_orders[:] = [item for _, item in indexed]


def run_step1(batch_size: int = 1000) -> dict:
    """
    Step 1: 批量新增未匹配的退货订单到关联表（type=50）
    
    使用while循环持续调用DAO方法，直到没有更多数据可插入，确保所有未匹配退货订单都被处理。
    新插入的退货订单标记为type=50（未进行匹配），等待Step 2处理。
    
    Args:
        batch_size: 每批插入数量，默认1000
        
    Returns:
        处理结果统计，包含总插入记录数
    """
    # 记录开始时间
    start_time = time.time()
    # 初始化总插入数量
    total_inserted = 0
    logger.info("[step1] 开始批量插入未匹配退货订单(type=50), batch_size=%d", batch_size)

    # 循环插入，直到没有更多数据
    while True:
        # 调用DAO方法批量插入未匹配的退货订单
        inserted = insert_unmatched_refund_orders(batch_size=batch_size)
        # 累加插入数量
        total_inserted += inserted
        # 如果插入数量小于批次大小，说明没有更多数据，跳出循环
        if inserted < batch_size:
            break

    # 计算耗时
    elapsed_time = time.time() - start_time
    logger.info("[step1] 完成: 共插入 %d 条, 耗时 %.2fs", total_inserted, elapsed_time)

    # 返回处理结果统计
    return {
        "step": "step1",
        "action": "insert_unmatched_refund_orders",
        "inserted_count": total_inserted,
        "batch_size": batch_size,
        "elapsed_time": round(elapsed_time, 2),
        "timestamp": int(time.time())
    }


def run_step2(batch_size: int = 100) -> dict:
    """
    Step 2: 按时间顺序处理退货订单，匹配对应的常规订单（一对多匹配）
    
    核心算法逻辑：
    1. 批量获取待匹配的退货订单（type=50），按时间升序排列
    2. 对每条退货订单执行一次查询，获取0-10条匹配的常规订单
    3. 遍历返回的常规订单列表，将退货数量分摊到常规订单，直到退货数量用完或遍历完
    4. 根据processed_quantity和匹配模式（mode）计算type值：
       - mode=1（一对一）：只有一条常规订单匹配
       - mode=3（一对多-退货订单视角）：一条退货订单分摊到多条常规订单
    5. 匹配失败的退货订单标记为type=40（未匹配）

    跨批次去重依赖DAO层 find_matching_normal_orders 的 NOT EXISTS 子查询
    （排除 type IN (11,12,13,21,22,23,31,32,33) 的已匹配常规订单），
    无需Redis缓存；同批次内未提交的匹配通过 batch_excluded_ids 内存去重。

    Args:
        batch_size: 每批处理数量，默认100
        
    Returns:
        处理结果统计，包含匹配成功/失败数量、总处理数量等
    """
    # 初始化统计变量
    matched_count = 0       # 匹配成功的退货订单数量
    unmatched_count = 0     # 匹配失败的退货订单数量
    total_processed = 0     # 总处理的退货订单数量
    total_matched_pairs = 0 # 总匹配对数（一条退货订单可能匹配多条常规订单）
    # 记录开始时间
    start_time = time.time()
    logger.info("[step2] 开始匹配退货订单与常规订单, batch_size=%d", batch_size)

    # 循环处理，直到没有待匹配的退货订单
    while True:
        # 获取待匹配的退货订单列表（type=50），按时间升序
        pending_orders = get_pending_refund_orders(batch_size=batch_size)
        # 如果没有待匹配订单，跳出循环
        if not pending_orders:
            break
        # 初始化本批次的变量
        matched_list = []           # 本批次匹配成功的记录列表
        unmatched_ids = []          # 本批次匹配失败的退货订单ID列表
        batch_excluded_ids = []     # 本批次已匹配的常规订单ID列表（防止同批次重复匹配；跨批次去重由DAO层NOT EXISTS负责）

        # 遍历本批次的每条退货订单
        for refund_order in pending_orders:
            # 获取退货订单ID
            refund_id = refund_order["refund_order_items_id"]
            # 初始化剩余退货数量（退货订单的quantity字段，负数）
            refund_quantity_qty = refund_order["refund_quantity"]
            # 初始化当前匹配次数
            current_match_index = 0

            # 本次查询排除的常规订单ID（仅同批次已匹配；跨批次去重由DAO层NOT EXISTS负责）
            cur_excluded_ids = batch_excluded_ids


            # 查找匹配的常规订单列表
            matched_normal_orders = find_matching_normal_orders(
                customer_id=refund_order["customer_id"],
                customer_name=refund_order.get("customer_name"),
                number=refund_order["number"],
                brand_name=refund_order["brand_name"],
                pdname=refund_order["pdname"],
                frey_no=refund_order["frey_no"],
                refund_create_date=refund_order["refund_create_date"],
                # 排除本批次内已匹配但尚未提交的常规订单（防止同批次重复匹配）
                excluded_normal_ids=cur_excluded_ids
            )

            # 排序常规订单：优先直接匹配 → 组合匹配 → 数量降序（大→小）
            _sort_normal_orders(matched_normal_orders, refund_quantity_qty)

            # 如果没有匹配到常规订单
            if not matched_normal_orders:
               
                # 记录到未匹配列表
                unmatched_ids.append(refund_id)
                # 累加未匹配数量
                unmatched_count += 1
                # 累加总处理数量
                total_processed += 1
                # 跳过当前退货订单，处理下一条
                continue

            # 匹配成功，累加匹配成功数量
            matched_count += 1

            # 遍历匹配到的常规订单列表，将退货数量分摊到各常规订单
            # refund_quantity_qty 为负数（退货），每匹配一条常规订单后向 0 靠拢
            for normal_order in matched_normal_orders:
                # 退货数量已用完（>=0 表示常规订单有剩余或恰好抵消），跳出循环
                if refund_quantity_qty >= 0:
                    break

                # 累加匹配次数（标识本条记录是第几次匹配产生的）
                current_match_index += 1
                # 获取常规订单数量（正数）
                normal_qty = normal_order["quantity"]

                # 核心分摊公式：处理数量 = 常规订单数量(正) + 剩余退货数量(负)
                # - processed_qty > 0：常规订单有剩余（退货少于常规），type=21/22/23
                # - processed_qty = 0：恰好抵消（完全退货），type=11/12/13
                # - processed_qty < 0：退货超出常规（退货多于常规），type=31/32/33
                processed_qty = normal_qty + refund_quantity_qty

                # 判断匹配模式：第一次匹配为一对一(mode=1)，后续为一对多-退货订单视角(mode=3)
                mode = 1 if current_match_index == 1 else 3

                # 根据处理数量和匹配模式计算type值（两位数编码：十位=状态，个位=模式）
                new_type = _calculate_type(processed_qty, mode)

                # 将匹配记录添加到列表，等待批量插入
                # match_count = current_match_index，标识本条记录是第几次匹配产生的
                matched_list.append({
                    "refund_order_items_id": refund_id, #退货订单明细ID
                    "normal_order_items_id": normal_order["orders_items_id"], #常规订单明细ID
                    "number": refund_order["number"], #OE号
                    "brand_name": refund_order["brand_name"], #品牌名
                    "pdname": refund_order["pdname"], #产品名称
                    "frey_no": refund_order["frey_no"], #条码
                    "customer_id": refund_order["customer_id"], #客户ID
                    "normal_quantity": normal_qty, #常规订单数量
                    "processed_quantity": processed_qty, #处理后的数量
                    "refund_quantity":refund_quantity_qty, #退货订单数量
                    "type": new_type, #类型
                    "match_count": current_match_index  # 第几次匹配产生的记录
                })

                # 更新剩余退货数量：用本次处理结果作为下一条常规订单的输入
                # 若 processed_qty < 0：退货未用完，继续匹配下一条常规订单
                # 若 processed_qty > 0：常规订单有剩余，退货已用完，下方 break 跳出
                refund_quantity_qty = processed_qty

                # 记录已匹配的常规订单ID，避免同批次内重复匹配（跨批次去重由DAO层NOT EXISTS负责）
                batch_excluded_ids.append(normal_order["orders_items_id"])

                # 常规订单有剩余（processed_qty > 0）表示退货数量已完全分摊，跳出循环
                if refund_quantity_qty > 0:
                    break

            # 累加总处理数量
            total_processed += 1
            # 累加总匹配对数
            total_matched_pairs += current_match_index

        # 如果本批次有匹配成功的记录
        if matched_list:
            # 批量插入匹配记录到数据库，match_count已在matched_list的每个元素中
            batch_insert_matched_refund(matched_list)

            # 删除已匹配退货单的 type=50 占位行，防止被 get_pending_refund_orders 重复捞回
            # （否则同一退货单会被反复匹配、消耗多个常规单，并最终被误标为 type=40）
            matched_refund_ids = list({m["refund_order_items_id"] for m in matched_list})
            delete_pending_by_refund_ids(matched_refund_ids)
            

        # 如果本批次有匹配失败的退货订单
        if unmatched_ids:
            # 批量更新为type=40（未匹配）
            logger.warning("[step2] 批量更新未匹配退货单 %d 条 -> type=40: %s", len(unmatched_ids), unmatched_ids)
            batch_update_unmatched_to_type40(unmatched_ids)

    update_type_to_by_refund_order()
    # 计算耗时
    elapsed_time = time.time() - start_time
    logger.info(
        "[step2] 完成: 处理 %d 条, 匹配成功 %d 条, 未匹配 %d 条, 匹配对数 %d, 耗时 %.2fs",
        total_processed, matched_count, unmatched_count, total_matched_pairs, elapsed_time
    )

    # 返回处理结果统计
    return {
        "step": "step2",
        "action": "match_refund_orders_batch",
        "total_processed": total_processed,
        "matched_count": matched_count,
        "unmatched_count": unmatched_count,
        "total_matched_pairs": total_matched_pairs,
        "batch_size": batch_size,
        "elapsed_time": round(elapsed_time, 2),
        "timestamp": int(time.time())
    }


def run_step3(batch_size: int = 100) -> dict:
    """
    Step 3: 处理常规订单剩余数量匹配退货订单（一对多-常规订单视角）

    核心算法逻辑：
    1. 分页获取type=21/22的记录（常规订单有剩余数量，processed_quantity > 0），
       对同一常规订单，只取match_count最大的最新记录（跨所有type），且该最新记录仍为type=21/22
    2. 为每条记录查找匹配的type=40退货订单（step2第一次匹配未命中的退货订单），
       时间约束：退货create_date > 常规订单create_date（退货在常规订单之后）
    3. 遍历匹配到的退货订单，将常规订单剩余数量分摊到各条退货订单，直到剩余用完或遍历完
    4. 新记录 processed_quantity = 常规剩余数量(取自type=21/22的processed_quantity) + 退货数量(取自type=40的refund_quantity)
       根据新的processed_quantity计算type值（mode=2，一对多-常规订单视角）：
       - processed_quantity = 0 → type=12（完全退货）
       - processed_quantity > 0 → type=22（部分退货）
       - processed_quantity < 0 → type=32（退货数量超出）
    5. 匹配成功时预构造记录字典加入本批次列表，本批次全部匹配完后一次性批量插入，match_count = 当前match_count + 1

    清理机制（与step2对称）：
    - step2: type=50(待匹配) → 匹配成功删占位行(delete_pending_by_refund_ids) / 失败→type=40
    - step3: type=40(待匹配) → 匹配成功删type=40行(delete_type40_by_refund_ids) / 失败→type=41
    匹配成功后删除type=40记录，防止step3结束时被batch_update_unmatched_to_type41误标为type=41

    分页策略（页码自增，防止死循环）：
    - 本页有匹配 → 被匹配记录因新插入更高match_count记录而从结果集移除，保持页码重新扫描
    - 本页无匹配 → 记录未消耗，递增页码跳过无法匹配的记录
    - 某页返回空 → 已遍历完，跳出循环

    注意：完全匹配时processed_quantity应为0

    Args:
        batch_size: 每批处理数量，默认100

    Returns:
        处理结果统计，包含匹配成功/失败数量、总处理数量、总匹配对数等
    """
    # 记录开始时间
    start_time = time.time()

    # 初始化统计变量
    matched_count = 0       # 匹配成功的记录数量
    unmatched_count = 0     # 匹配失败的记录数量
    total_processed = 0     # 总处理的记录数量
    total_matched_pairs = 0  # 总匹配对数（一条常规订单可能匹配多条退货订单）
    logger.info("[step3] 开始处理常规订单剩余数量匹配退货订单, batch_size=%d", batch_size)

    # 分页处理type=21/22的记录，页码从1开始
    # 页码自增策略：
    #   - 本页有匹配成功 → 被匹配的记录因新插入的更高match_count记录而从结果集移除，
    #     剩余记录前移，保持当前页码不变以重新扫描前移进入的新记录
    #   - 本页无匹配 → 记录未被消耗，递增页码跳过这些无法匹配的记录
    #   - 某页返回空 → 已遍历完所有记录，跳出循环
    # 这样即使一直没有匹配到也不会死循环，最终会翻完所有页后退出
    page = 1
    while True:
        # 获取常规订单有剩余的记录（type=21/22），只取match_count最大的，分页获取
        type21_records = get_type21_22_records(batch_size=batch_size, page=page)
        # 如果没有记录，跳出循环
        if not type21_records:
            break
        # 初始化本批次已排除的退货订单ID列表（防止同批次重复匹配）
        batch_excluded_refund_ids = []
        # 初始化本批次匹配成功的记录列表（待全部匹配完后一次性批量插入）
        matched_list = []

        # 遍历每条type=21/22的记录
        for record in type21_records:
            # 初始化常规订单剩余数量（正数，表示还有多少可以继续匹配）
            normal_remaining_qty = record["processed_quantity"]
            # 如果常规订单没有剩余数量，跳过
            if normal_remaining_qty <= 0:
                continue

            # 初始化匹配次数（基于当前记录的match_count）
            current_match_count = record.get("match_count", 1)

            

            # 查找多条匹配的退货订单（type=40，step2未匹配的退货订单）
            matched_refund_orders = find_matching_refund_order_type3(
                customer_id=record["customer_id"],
                number=record["number"],
                brand_name=record["brand_name"],
                pdname=record["pdname"],
                frey_no=record["frey_no"],
                normal_order_create_date=record["normal_order_create_date"],
                excluded_refund_ids=batch_excluded_refund_ids
            )

            # 如果没有匹配到退货订单
            if not matched_refund_orders:
                # 累加未匹配数量
                unmatched_count += 1
                # 累加总处理数量
                total_processed += 1
                # 跳过当前记录，处理下一条
                continue

            # 匹配成功，累加匹配成功数量（按匹配对数计算）
            matched_count += len(matched_refund_orders)

            # 遍历匹配到的退货订单，将常规订单剩余数量分摊到各退货订单
            # 与step2方向相反：step2是退货数量分摊到常规订单，step3是常规剩余分摊到退货订单
            # normal_remaining_qty 为正数（剩余），每匹配一条退货订单后向 0 靠拢
            for matched_refund in matched_refund_orders:
                # 常规订单剩余数量已用完（<=0），跳出循环
                if normal_remaining_qty <= 0:
                    break

                # 匹配次数自增（基于type=21/22记录的match_count继续累加）
                current_match_count += 1

                # 获取退货订单的退货数量（负数，取自type=40记录的refund_quantity）
                refund_remaining_qty = matched_refund["refund_quantity"]

                # 核心分摊公式：新处理数量 = 常规剩余数量(正) + 退货数量(负)
                # - new_processed_qty > 0：常规仍有剩余，type=22
                # - new_processed_qty = 0：恰好抵消，type=12
                # - new_processed_qty < 0：退货超出常规剩余，type=32
                new_processed_qty = normal_remaining_qty + refund_remaining_qty

                # mode=2（一对多-常规订单视角）：一条常规订单被多条退货订单分摊
                new_type = _calculate_type(new_processed_qty, 2)

                # 预构造匹配记录字典，加入本批次列表，待全部匹配完后一次性批量插入
                matched_list.append({
                    "refund_order_items_id": matched_refund["refund_order_items_id"],  # 退货订单明细ID
                    "normal_order_items_id": record["normal_order_items_id"],  # 常规订单明细ID
                    "number": record["number"],  # OE号
                    "brand_name": record["brand_name"],  # 品牌名
                    "pdname": record["pdname"],  # 产品名称
                    "frey_no": record["frey_no"],  # 条码
                    "customer_id": record["customer_id"],  # 客户ID
                    "normal_quantity": record["normal_quantity"],  # 常规订单数量
                    "refund_quantity": refund_remaining_qty,  # 退货订单数量
                    "processed_quantity": new_processed_qty,  # 新处理数量
                    "type": new_type,  # 新type值
                    "match_count": current_match_count  # 匹配次数
                })

                # 更新常规订单剩余数量：用本次处理结果作为下一条退货订单的输入
                # 若 new_processed_qty > 0：常规仍有剩余，继续匹配下一条退货订单
                # 若 new_processed_qty <= 0：常规已用完，下方 break 跳出
                normal_remaining_qty = new_processed_qty

                # 记录已匹配的退货订单ID，避免同批次内重复匹配
                batch_excluded_refund_ids.append(matched_refund["refund_order_items_id"])

            # 累加总处理数量
            total_processed += 1
            # 累加总匹配对数
            total_matched_pairs += len(matched_refund_orders)

        # 本批次全部匹配完成，一次性批量插入所有匹配记录
        if matched_list:
            insert_matched_refund(matched_list)
            # 删除本页已匹配退货单的 type=40 记录（第一次匹配失败的占位行），
            # 防止 step3 结束时被 batch_update_unmatched_to_type41 误标为 type=41。
            # 对 type=31/32 退货单（无 type=40 记录）为空操作。
            if batch_excluded_refund_ids:
                delete_type40_by_refund_ids(batch_excluded_refund_ids)
            # 有匹配成功：被匹配记录因新插入的更高match_count记录而从结果集移除，
            # 剩余记录前移，保持当前页码不变以重新扫描前移进入的新记录
        else:
            # 本页无匹配：记录未被消耗，递增页码跳过这些无法匹配的记录，避免死循环
            page += 1

    # 所有分页处理完成，将两次匹配都未命中的 type=40 记录更新为 type=41（第二次匹配失败）
    updated41 = batch_update_unmatched_to_type41()
    if updated41:
        logger.info("[step3] 将 %d 条仍未匹配的 type=40 记录更新为 type=41", updated41)

    update_type_to_by_normal_order()

    # 计算耗时
    elapsed_time = time.time() - start_time
    logger.info(
        "[step3] 完成: 处理 %d 条, 匹配成功 %d 条, 未匹配 %d 条, 匹配对数 %d, 耗时 %.2fs",
        total_processed, matched_count, unmatched_count, total_matched_pairs, elapsed_time
    )

    # 返回处理结果统计
    return {
        "step": "step3",
        "action": "match_type21_with_type3",
        "total_processed": total_processed,
        "matched_count": matched_count,
        "unmatched_count": unmatched_count,
        "total_matched_pairs": total_matched_pairs,
        "batch_size": batch_size,
        "elapsed_time": round(elapsed_time, 2),
        "timestamp": int(time.time())
    }


def get_summary() -> dict:
    """
    获取处理结果统计摘要
    
    返回各类型分布统计、待处理订单数量和数量未完全抵消的退货订单数量。
    
    Returns:
        统计摘要字典，包含type_distribution、pending_count、type3_count
    """
    # 获取各类型分布统计
    type_summary = get_type_summary()
    # 构建摘要字典
    summary = {
        "type_distribution": type_summary,
        "pending_count": get_pending_count(),    # 待处理订单数量（type=50）
        "type3_count": get_type3_count(),        # 数量未完全抵消的退货订单数量（type=31/32/33）
        "timestamp": int(time.time())
    }
    return summary


def run_full_process(batch_size_step1: int = 1000, batch_size_step2: int = 100, batch_size_step3: int = 100) -> dict:
    """
    执行完整的退货订单匹配流程（三步）
    
    流程概述：
    Step 1: 批量插入未匹配的退货订单到关联表（type=50）
    Step 2: 按时间顺序处理退货订单，一对多匹配常规订单
    Step 3: 处理常规订单剩余数量匹配退货订单
    
    Args:
        batch_size_step1: Step 1每批插入数量，默认1000
        batch_size_step2: Step 2每批处理数量，默认100
        batch_size_step3: Step 3每批处理数量，默认100
        
    Returns:
        完整处理结果，包含各步骤的处理统计和类型分布摘要
    """
    # 记录开始时间
    start_time = time.time()

    # 依次执行三步处理
    step1_result = run_step1(batch_size=batch_size_step1)
    step2_result = run_step2(batch_size=batch_size_step2)
    step3_result = run_step3(batch_size=batch_size_step3)

    # 获取处理结果摘要
    summary = get_summary()

    # 计算总耗时
    total_elapsed_time = time.time() - start_time
    # 输出整体摘要日志：各步耗时 + 类型分布 + 待处理/未抵消数量
    logger.info(
        "[full] 全流程完成: 总耗时 %.2fs | step1插入 %d | step2 处理 %d/匹配 %d/未匹配 %d | step3 处理 %d/匹配 %d/未匹配 %d | 待处理(type=50) %d | 未完全抵消(type31/32/33) %d",
        total_elapsed_time,
        step1_result["inserted_count"],
        step2_result["total_processed"], step2_result["matched_count"], step2_result["unmatched_count"],
        step3_result["total_processed"], step3_result["matched_count"], step3_result["unmatched_count"],
        summary["pending_count"], summary["type3_count"]
    )
    logger.info("[full] 类型分布: %s", summary["type_distribution"])

    # 返回完整处理结果
    return {
        "total_elapsed_time": round(total_elapsed_time, 2),
        "step1": step1_result,
        "step2": step2_result,
        "step3": step3_result,
        "summary": summary,
        "timestamp": int(time.time())
    }


