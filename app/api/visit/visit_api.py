# -*- coding:utf-8 -*-
# @Time    : 2026/10/12 10:00
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : visit_api.py
# @Software: PyCharm
# 客访管理数据接口（设计文档 doc/客访管理/01-主设计文档.md 第七节）
# 本期实现：高德客户Excel导入、M1 客户列表、M8 客户绑定（03 文档）、
#           拜访记录Excel导入与 M2 拜访历史（4.3）；
#           客户详情聚合（头部+档案）拆分至同目录 visit_detail_api.py。

from flask import jsonify, request, session

from . import visit_bp
# 权限控制：客访模块所有接口统一要求「汽配客访管理」权限（visit:view）
from app.core.permission.decorators import require_permission
from app.services.visit_service import amap_customer_import_service
from app.services.visit_service import amap_customer_service
from app.services.visit_service import customer_owner_service
from app.services.visit_service import customer_relation_service
from app.services.visit_service import order_visit_ref_service
from app.services.visit_service import visit_record_service


@visit_bp.route("/amap-customers/import_excel", methods=["POST"])
@require_permission('visit:view')
def import_amap_excel():
    """高德导出Excel导入（一个文件两个sheet）

    "标记位置"sheet → 客户档案：按位置编码（amap_poi_id）upsert 写入 visit_amap_customer，
    已存在则更新档案字段，不存在则新增；
    "记录"sheet → 拜访记录：按复合唯一键（位置编码+记录时间）upsert 写入 visit_record，
    已存在则更新照片/记录人，不存在则插入；客户档案以"记录所属内容"upsert（仅更新名称）。
    """
    try:
        if "file" not in request.files:
            return jsonify({"code": 400, "msg": "没有上传文件", "data": None})

        file = request.files["file"]
        if not file.filename:
            return jsonify({"code": 400, "msg": "没有选择文件", "data": None})

        result = amap_customer_import_service.import_amap_excel(file, file.filename)
        marker = result["marker"]
        record = result["record"]

        msg = (f'客户档案：新增 {marker["insert_count"]} 条，更新 {marker["update_count"]} 条，'
               f'跳过空行 {marker["empty_rows"]} 行；'
               f'拜访记录：导入 {record["import_count"]} 条（重复的按键自动更新），'
               f'写入客户 {record["customer_count"]} 家')
        extra = []
        if marker["error_rows"]:
            extra.append(f'客户档案异常 {len(marker["error_rows"])} 行')
        if record["error_rows"]:
            extra.append(f'拜访记录异常 {len(record["error_rows"])} 行')
        if extra:
            msg += '（' + '，'.join(extra) + '）'

        return jsonify({"code": 200, "msg": msg, "data": result})
    except ValueError as e:
        return jsonify({"code": 400, "msg": str(e), "data": None})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"导入失败: {e}", "data": None})


@visit_bp.route("/customers", methods=["GET"])
@require_permission('visit:view')
def get_visit_customers():
    """M1 客户列表（分页 + 客户类型/拿货渠道筛选 + 客户名称/地址关键词搜索
    + 拜访时间筛选 + 累计拿货额筛选 + 省市区镇地址筛选，08-客户筛选功能.md）

    查询参数：
        page / limit:      分页参数
        customer_type:     客户类型筛选，选填（多值字段按整词包含匹配；
                           __empty__ 表示筛选"无"）
        purchase_channels: 拿货渠道筛选，选填（同上）
        keyword:           搜索关键词，选填（客户名称/地址模糊匹配，任一命中即返回）
        visit_days:        拜访时间筛选，选填；仅返回"超过 visit_days 天未拜访"的客户，
                           传 "0" 表示筛选"从未拜访过"的客户
        min_amount:        累计拿货额下限（≥），选填
        max_amount:        累计拿货额上限（≤），选填
        province:          省份筛选，选填（地址 LIKE '%广东省%' 模糊匹配）
        city:              城市筛选，选填（地址 LIKE '%佛山市%'）
        district:          区县筛选，选填（地址 LIKE '%禅城区%'）
        town:              镇街筛选，选填（地址 LIKE '%张槎街道%'）
    """
    try:
        result = amap_customer_service.get_customer_list(
            page=request.args.get("page", 1),  # pyright: ignore[reportArgumentType]
            limit=request.args.get("limit", 20),  # pyright: ignore[reportArgumentType]
            customer_type=(request.args.get("customer_type") or "").strip() or None,
            purchase_channels=(request.args.get("purchase_channels") or "").strip() or None,
            keyword=(request.args.get("keyword") or "").strip() or None,
            visit_days=(request.args.get("visit_days") or "").strip() or None,
            min_amount=(request.args.get("min_amount") or "").strip() or None,
            max_amount=(request.args.get("max_amount") or "").strip() or None,
            province=(request.args.get("province") or "").strip() or None,
            city=(request.args.get("city") or "").strip() or None,
            district=(request.args.get("district") or "").strip() or None,
            town=(request.args.get("town") or "").strip() or None,
        )
        return jsonify({"code": 200, "msg": "success", "data": result})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"查询失败: {e}", "data": None})


@visit_bp.route("/filter-options", methods=["GET"])
@require_permission('visit:view')
def get_visit_filter_options():
    """列表筛选下拉选项（来源：visit_amap_customer 实际数据，| 多值拆分去重排序）

    返回 customer_types / purchase_channels 两组选项；"无"选项（筛空值）
    由前端固定添加，值 __empty__。
    """
    try:
        result = amap_customer_service.get_filter_options()
        return jsonify({"code": 200, "msg": "success", "data": result})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"查询失败: {e}", "data": None})


@visit_bp.route("/region-options", methods=["GET"])
@require_permission('visit:view')
def get_visit_region_options():
    """省市区镇级联下拉选项（客户列表地址筛选用）

    来源：visit_amap_customer.address 原文逐级前缀解析（"省+市+区县+镇街+详址"），
    只返回有客户的区域，随导入动态变化；筛选时按所选各级对 address 做 LIKE 模糊匹配。
    返回 {'provinces': [{'name': 省, 'cities': [{'name': 市,
            'districts': [{'name': 区县, 'towns': [镇街...]}]}]}]}
    """
    try:
        result = amap_customer_service.get_region_options()
        return jsonify({"code": 200, "msg": "success", "data": result})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"查询失败: {e}", "data": None})


@visit_bp.route("/partners/search", methods=["GET"])
@require_permission('visit:view')
def search_crm_partners():
    """绑定表单的 CRM 客户搜索（partner_list，名称/简称/记忆代码模糊匹配，排除已绑定与禁用）

    查询参数：
        keyword: 搜索关键词，必填
        limit:   返回条数上限，默认 20
    """
    try:
        result = customer_relation_service.search_crm_partners(
            keyword=request.args.get("keyword", ""),  # pyright: ignore[reportArgumentType]
            limit=request.args.get("limit", 20),  # pyright: ignore[reportArgumentType]
        )
        return jsonify({"code": 200, "msg": "success", "data": result})
    except ValueError as e:
        return jsonify({"code": 400, "msg": str(e), "data": None})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"查询失败: {e}", "data": None})


@visit_bp.route("/relations", methods=["POST"])
@require_permission('visit:view')
def bind_customer_relation():
    """M8 客户绑定（03 文档 3.2）：高德客户 1:N 绑定 CRM客户（追加式，CRM侧仍 1:1）

    请求体 JSON：
        amap_customer_id: 高德客户POI编码，必填
        partner_id:       CRM客户ID，必填
        bind_remark:      绑定备注（名称差异说明），选填
    同一事务写入绑定行（同一对幂等更新、新对插入）并回写 visit_amap_customer.status=1；
    响应 appended=true 表示该高德客户已有其他绑定，本次为追加关联。
    """
    try:
        payload = request.get_json(silent=True) or {}
        result = customer_relation_service.bind_customer(
            amap_customer_id=payload.get("amap_customer_id", ""),
            partner_id=payload.get("partner_id"),
            bind_remark=payload.get("bind_remark", ""),
            operator=session.get("username", ""),
        )
        return jsonify({"code": 200, "msg": "关联成功", "data": result})
    except ValueError as e:
        return jsonify({"code": 400, "msg": str(e), "data": None})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"关联失败: {e}", "data": None})


@visit_bp.route("/relations", methods=["GET"])
@require_permission('visit:view')
def list_customer_relations():
    """M8 查询高德客户当前全部绑定（1:N，绑定弹窗展示已绑定列表 + 解绑操作用）

    查询参数：
        amap_customer_id: 高德客户POI编码，必填
    绑定客户已被 partner_list 周刷新删除的行跳过（口径同详情聚合 crm_list）。
    """
    try:
        result = customer_relation_service.list_relations(
            amap_customer_id=request.args.get("amap_customer_id", ""),  # pyright: ignore[reportArgumentType]
        )
        return jsonify({"code": 200, "msg": "success", "data": result})
    except ValueError as e:
        return jsonify({"code": 400, "msg": str(e), "data": None})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"查询失败: {e}", "data": None})


@visit_bp.route("/relations", methods=["DELETE"])
@require_permission('visit:view')
def unbind_customer_relation():
    """M8 客户解绑：物理删除指定绑定行（误删恢复 = 在客户列表重新关联一次）

    请求体 JSON：
        amap_customer_id: 高德客户POI编码，必填
        partner_id:       CRM客户ID，必填
    同一事务删除绑定行并重算 visit_amap_customer.status（全部解绑后回落 0）；
    响应 remaining 为解绑后剩余绑定数。
    """
    try:
        payload = request.get_json(silent=True) or {}
        result = customer_relation_service.unbind_customer(
            amap_customer_id=payload.get("amap_customer_id", ""),
            partner_id=payload.get("partner_id"),
        )
        return jsonify({"code": 200, "msg": "已解绑", "data": result})
    except ValueError as e:
        return jsonify({"code": 400, "msg": str(e), "data": None})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"解绑失败: {e}", "data": None})


@visit_bp.route("/customer-owners", methods=["GET"])
@require_permission('visit:view')
def list_customer_owners():
    """查询某客户的负责人列表（详情页"负责人"区域展示）

    查询参数：
        visit_amap_customer_id: visit_amap_customer.id（物理主键，与详情页 ?id= 口径一致），必填
    """
    try:
        result = customer_owner_service.list_owners(
            visit_amap_customer_id=request.args.get("visit_amap_customer_id"),  # pyright: ignore[reportArgumentType]
        )
        return jsonify({"code": 200, "msg": "success", "data": result})
    except ValueError as e:
        return jsonify({"code": 400, "msg": str(e), "data": None})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"查询失败: {e}", "data": None})


@visit_bp.route("/owner-candidates", methods=["GET"])
@require_permission('visit:view')
def search_owner_candidates():
    """负责人候选搜索（绑定弹层选用户，来源 crmapp_users，用户名/部门模糊匹配）

    查询参数：
        keyword: 搜索关键词，选填（空 = 返回前 limit 个用户）
        limit:   返回条数上限，默认 50
    """
    try:
        result = customer_owner_service.search_owner_candidates(
            keyword=request.args.get("keyword", ""),
            limit=request.args.get("limit", 50),  # pyright: ignore[reportArgumentType]
        )
        return jsonify({"code": 200, "msg": "success", "data": result})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"查询失败: {e}", "data": None})


@visit_bp.route("/customer-owners", methods=["POST"])
@require_permission('visit:view')
def bind_customer_owner():
    """绑定负责人（07-负责人绑定.md 绑定流程）：客户多对多绑定负责人（系统用户）

    请求体 JSON：
        visit_amap_customer_id: visit_amap_customer.id（物理主键），必填
        user_id:                负责人ID（crmapp_users.id），必填
    校验：客户存在且 status != 2、负责人存在；同对已绑定幂等返回成功（不重复建行）；
    operator 取当前登录用户 id（session.user_id），不从请求参数传入。
    """
    try:
        payload = request.get_json(silent=True) or {}
        result = customer_owner_service.bind_owner(
            visit_amap_customer_id=payload.get("visit_amap_customer_id"),
            user_id=payload.get("user_id"),
            operator=session.get("user_id"),
        )
        return jsonify({"code": 200, "msg": "绑定成功", "data": result})
    except ValueError as e:
        return jsonify({"code": 400, "msg": str(e), "data": None})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"绑定失败: {e}", "data": None})


@visit_bp.route("/customer-owners", methods=["DELETE"])
@require_permission('visit:view')
def unbind_customer_owner():
    """解绑负责人 = 物理删除该行（uk_customer_user 定位唯一行，解绑后可随时重新绑定）

    请求体 JSON：
        visit_amap_customer_id: visit_amap_customer.id（物理主键），必填
        user_id:                负责人ID（crmapp_users.id），必填
    """
    try:
        payload = request.get_json(silent=True) or {}
        result = customer_owner_service.unbind_owner(
            visit_amap_customer_id=payload.get("visit_amap_customer_id"),
            user_id=payload.get("user_id"),
        )
        return jsonify({"code": 200, "msg": "已解绑", "data": result})
    except ValueError as e:
        return jsonify({"code": 400, "msg": str(e), "data": None})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"解绑失败: {e}", "data": None})


@visit_bp.route("/records", methods=["GET"])
@require_permission('visit:view')
def get_visit_records():
    """M2 拜访历史记录（分页，按记录时间倒序）

    查询参数：
        page / limit:     分页参数
        amap_customer_id: 按客户筛选，选填
    """
    try:
        result = visit_record_service.get_record_list(
            page=request.args.get("page", 1),  # pyright: ignore[reportArgumentType]
            limit=request.args.get("limit", 20),  # pyright: ignore[reportArgumentType]
            amap_customer_id=request.args.get("amap_customer_id"),
        )
        return jsonify({"code": 200, "msg": "success", "data": result})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"查询失败: {e}", "data": None})


@visit_bp.route("/order-refs", methods=["PUT"])
@require_permission('visit:view')
def bind_order_ref():
    """订单-拜访人工关联：指定 / 改绑（05-订单拜访关联模块设计.md 第三节）

    请求体 JSON：
        orders_id: 发货金蝶号（sales_order_history.deliverysapno），必填
        record_id: 拜访记录ID（visit_record.id），必填
        remarks:   关联备注，选填
    校验：订单存在、拜访存在且未作废、订单客户 ∈ 拜访客户当前绑定集合（防跨客户错挂）；
    无关联行则插入，已有行（改绑）则覆盖 record_id / matched_by / remarks。
    """
    try:
        payload = request.get_json(silent=True) or {}
        result = order_visit_ref_service.bind_order_visit(
            orders_id=payload.get("orders_id", ""),
            record_id=payload.get("record_id"),
            remarks=payload.get("remarks", ""),
            operator=session.get("username", ""),
        )
        return jsonify({"code": 200, "msg": "关联成功", "data": result})
    except ValueError as e:
        return jsonify({"code": 400, "msg": str(e), "data": None})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"关联失败: {e}", "data": None})


@visit_bp.route("/order-refs", methods=["DELETE"])
@require_permission('visit:view')
def unbind_order_ref():
    """订单-拜访取消关联 = 物理删除该行（业务确认 2026-10-24，误删恢复=重新指定一次）

    请求体 JSON：
        orders_id: 发货金蝶号，必填
    """
    try:
        payload = request.get_json(silent=True) or {}
        order_visit_ref_service.unbind_order(payload.get("orders_id", ""))
        return jsonify({"code": 200, "msg": "已取消关联", "data": None})
    except ValueError as e:
        return jsonify({"code": 400, "msg": str(e), "data": None})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"取消关联失败: {e}", "data": None})
