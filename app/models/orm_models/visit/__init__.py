# -*- coding:utf-8 -*-
# 客访管理 ORM 模型

from .visit_amap_customer import VisitAmapCustomer, gen_manual_poi_id
from .visit_customer_relation import VisitCustomerRelation
from .visit_record import VisitRecord
from .visit_follow_record import VisitFollowRecord
from .visit_order_ref import VisitOrderRef

__all__ = ["VisitAmapCustomer", "gen_manual_poi_id", "VisitCustomerRelation", "VisitRecord", "VisitFollowRecord", "VisitOrderRef"]
