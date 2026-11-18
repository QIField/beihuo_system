#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
汽配龙自动报价重构 · 新 package

职责：取代 app/utils/qpl_auto_bill/ 旧任务（旧任务冻结后只读保留），
按新页面 API（PAGE_QUOTE 灰度全量）重新实现"一单一单串行处理"的自动报价，
三层表落库支持全链路追溯。
"""
