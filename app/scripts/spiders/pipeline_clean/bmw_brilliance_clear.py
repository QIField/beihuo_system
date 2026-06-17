# -*- coding:utf-8 -*-
# @Time    : 2026/6/12
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : bmw_brilliance_clear.py
# @Software : PyCharm
# 华晨宝马库存系统 —— 数据清洗通道
# 职责：把爬虫拿到的 HTML 响应解析成结构化的 dict / JSON
# 注意：一个爬虫接口 对应 一个清洗函数，不做跨接口合并
# =======================================================================

import json
from datetime import datetime
from lxml import etree

from app.exceptions import DataParseError, DataNotFoundError


# ===================== 通用工具函数 =====================

def _clean_text(text_list):
    """清洗 xpath 提取到的文本列表：去括号、空格、\xa0"""
    if not text_list:
        return ""
    text = str(text_list).replace('[', '').replace(']', '').replace(' ', '').replace('\\xa0', '').replace("','", '').replace("'", '')
    return text.strip()


def _translate_warehouse(text):
    """SY01/SY02 仓库代号 → 中文城市名"""
    mapping = {
        "SY01": "-北京",
        "SY02": "-上海",
        "SY03": "-佛山",
        "SY06": "-成都",
        "SY07": "-沈阳",
        "SY08": "-合肥",
        "SY09": "-宁波",
    }
    for code, city in mapping.items():
        text = text.replace(code, city)
    return text


def _parse_rmb_price(value_str):
    """解析带 RMB 的价格（自动 ×1.13 换算含税价）"""
    if value_str and isinstance(value_str, str) and 'RMB' in value_str:
        try:
            num = float(str(value_str).replace('RMB', '').replace(',', ''))
            return round(num * 1.13, 2)
        except (ValueError, TypeError):
            pass
    return value_str


def _safe_extract_cell(cell, xpath_expr, index=0):
    """从 lxml cell 中安全提取文本（取不到返回空字符串）"""
    result = cell.xpath(xpath_expr)
    if result and len(result) > index:
        return str(result[index]).replace(' ', '')
    return ''


# ===================== 1. 库存查询清洗（对应 get_stock_check） =====================

def clean_stock_html(html_text, oe):
    """
    清洗【库存查询】接口返回的 HTML —— 对应爬虫 get_stock_check

    :param html_text: 原始 HTML 字符串（response.text）
    :param oe: 零件号
    :return: dict，结构如 {'oe': 'xxx', '主仓': 10, '北京': 3, ...}
    :raises DataParseError: HTML 结构异常、解析失败等
    :raises DataNotFoundError: 零件不存在或未激活
    """
    if not html_text:
        raise DataParseError("[{}] 空响应".format(oe))

    if '不存在或未激活' in html_text:
        raise DataNotFoundError("[{}] 零件不存在或未激活".format(oe))

    # 切出核心表格区域
    try:
        html_parts = str(html_text).split('<!-- Header  -->')
        if len(html_parts) < 2:
            raise DataParseError("[{}] HTML 结构异常（找不到 Header 标记）".format(oe))
        table_part = html_parts[1].split('<table  border="0" cellpadding="0" cellspacing="0">')[0]
    except DataParseError:
        raise
    except Exception as e:
        raise DataParseError("[{}] HTML 切片失败: {}".format(oe, e))

    html_dom = etree.HTML(table_part)
    if html_dom is None:
        raise DataParseError("[{}] HTML 解析失败".format(oe))

    trs = html_dom.xpath('/html/body/table/tr')
    if not trs or len(trs) < 4:
        raise DataParseError("[{}] 解析到的表格行数不足".format(oe))

    # 列索引配置（与原脚本一致）
    STOCK_COL_INDEXES = [0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 12, 13, 14, 16, 17, 18, 20, 21, 22, 24, 25, 26, 28, 29, 30, 32, 33, 34]
    WAREHOUSE_COL_INDEXES = [7, 11, 15, 19, 23, 27, 31]

    # ---- 第 3 行（索引3）：表头 ----
    name_list = []
    titles = trs[3].xpath('td')
    for k1, v1 in enumerate(titles):
        if k1 in STOCK_COL_INDEXES:
            name = _clean_text(v1.xpath('text()'))
        elif k1 in WAREHOUSE_COL_INDEXES:
            name = _clean_text(v1.xpath('b/i/text()'))
        else:
            continue
        name = _translate_warehouse(name)
        name_list.append(name)

    # ---- 第 4 行（索引4）：数据 ----
    value_list = []
    values = trs[4].xpath('td') if len(trs) > 4 else []
    for k1, v1 in enumerate(values):
        if k1 == 0:
            continue  # 第 0 列跳过

        if k1 == 1:
            # 第 1 列：OE 号链接文本 + 普通文本
            value_list.append(_safe_extract_cell(v1, 'a/text()'))
            value_list.append(_safe_extract_cell(v1, 'text()'))
            continue

        if k1 in STOCK_COL_INDEXES:
            cell_val = _safe_extract_cell(v1, 'text()')
        elif k1 in WAREHOUSE_COL_INDEXES:
            # 从 onmouseover 属性中提取可用库存
            attr_str = str(v1.xpath('a/@onmouseover')).replace(' ', '') \
                .replace("doTooltip(event,'可用库存overreorderpoint:", '') \
                .replace("')", '').replace('["', '').replace('"]', '')
            cell_val = attr_str if attr_str and attr_str != '[]' else ''
        else:
            continue

        # 价格处理（RMB × 1.13）
        cell_val = _parse_rmb_price(cell_val)
        value_list.append(cell_val)

    # ---- 第 5 行（索引5）：备注 ----
    remark = ''
    if len(trs) > 5:
        values5 = trs[5].xpath('td')
        for k1, v1 in enumerate(values5):
            if k1 == 2:
                remark = _clean_text(v1.xpath('text()'))

    # 组装结果
    result = {
        "oe": oe,
        "remark": remark,
        "采集时间": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    for name, val in zip(name_list, value_list):
        if name:
            result[name] = val

    return result


# ===================== 2. 零件详情查询清洗（对应 get_material_details） =====================

def clean_material_html(html_text, oe):
    """
    清洗【零件详情】接口返回的 HTML —— 对应爬虫 get_material_details

    :param html_text: 原始 HTML 字符串（response.text）
    :param oe: 零件号
    :return: dict，结构如 {'oe': 'xxx', '4S含税售价': 123.45, '4S含税进价': 100.00, ...}
    :raises DataParseError: HTML 结构异常、解析失败等
    """
    if not html_text:
        raise DataParseError("[{}] 空响应".format(oe))

    html_dom = etree.HTML(html_text)
    if html_dom is None:
        raise DataParseError("[{}] HTML 解析失败".format(oe))

    trs = html_dom.xpath('/html/body/table[1]/tr/td[2]/table/tr')
    if not trs:
        raise DataParseError("[{}] 解析不到详情表格".format(oe))

    # 第一步：逐行提取文本
    row_list = []
    for v in trs:
        cells = v.xpath('td/text()')
        row_text = ''
        for w in cells:
            row_text += str(w).replace(',', '').replace(' ', '').replace('\xa0', '').replace('\r\n', '') + ','
        row_text = row_text[:-1]
        row_list.append(row_text)

    # 第二步：拆成 key-value
    kv_list = []
    has_part_name = False  # 是否已添加"零件名"（用于识别 HTML 中空标签行的零件名称）
    for item in row_list:
        parts = item.replace("'", '').replace('[', '').replace(']', '').split(',')
        if item == '新零件号':
            kv_list.append(['新零件号', ''])
        if len(parts) > 1 and len(parts[0]) > 0:
            kv_list.append(parts)
        # 修复：HTML 中"零件名"一行的标签是 &nbsp;（空标签），导致 parts[0] 为空，被过滤
        # 当 parts[0] 为空但 parts[1] 有值时，将其识别为"零件名"（只处理第一个匹配项）
        elif len(parts) > 1 and len(parts[0]) == 0 and len(parts[1]) > 0 and not has_part_name:
            kv_list.append(['零件名', parts[1]])
            has_part_name = True

    # 第三步：组装字典（价格自动 ×1.13）
    result = {
        "oe": oe,
        "采集时间": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    for item in kv_list:
        key = item[0]
        val = item[1] if len(item) > 1 else ''
        if key in ['零售价', '经销商净值(Stock)', '经销商净值(Rush)']:
            result[key] = _parse_rmb_price(val)
        else:
            result[key] = val

    # 第四步：列名重命名（与原脚本一致）
    if '零售价' in result:
        result['4S含税售价'] = result.pop('零售价')
    if '经销商净值(Stock)' in result:
        result['4S含税进价'] = result.pop('经销商净值(Stock)')

    return result


# ===================== 通用：dict → JSON =====================

def records_to_json(records, indent=2, ensure_ascii=False):
    """
    dict 或 dict 列表 转 JSON 字符串

    :param records: dict 或 list[dict]
    :param indent: 缩进空格数
    :param ensure_ascii: False 时中文正常显示
    """
    if isinstance(records, dict):
        records = [records]
    return json.dumps(records, indent=indent, ensure_ascii=ensure_ascii, default=str)









def map_detail_key_clean(data_fields):
    """
    对传入字典的 key 进行标准化清洗：去除所有空格、去除冒号（:）。

    场景：爬虫解析出来的 key 可能带有首尾空格、"可用库存:" 等
          脏字符，在进入数据库字段映射前，先把 key 统一标准化。

    :param data_fields: dict，如 {" 零件名 ": "xxx", "可用库存:": 10}
    :return: 清洗后的 dict，如 {"零件名": "xxx", "可用库存": 10}
    """
    if not data_fields or not isinstance(data_fields, dict):
        return data_fields

    cleaned = {}
    for key, value in data_fields.items():
        # 仅对字符串类型的 key 做清洗（其它类型如 int 直接原样保留）
        if isinstance(key, str):
            new_key = key.replace(' ', '').replace(':', '').strip()
        else:
            new_key = key

        # 如果清洗后的 key 与原 key 不同，且新 key 已存在，
        # 则保留先出现的那个（避免覆盖已有 key 的风险）
        if new_key in cleaned:
            continue
        cleaned[new_key] = value

    return cleaned


def map_detail_data_clean(data):
    """
    对传入字典的 value 按属性字段分别进行数值化清洗（与 demo/test 规则一致）。

    逐个字段的清洗规则：
      - 毛重：              如 "1.067KG" → 1.067（去除 KG 后缀，转 float）
      - 净重：              如 "1.067KG" → 1.067（去除 KG 后缀，转 float）
      - 体积：              如 "22.040CDM" → 22.040（去除 CDM 后缀，转 float）
      - 零售价：            如 "601.77RMB" → 601.77（去除 RMB 后缀，转 float）
      - 经销商折扣(Stock)： 如 "25%" → 0.25（去除 % 后缀，除以 100）
      - 经销商折扣(Rush)：  如 "25%" → 0.25（去除 % 后缀，除以 100）
      - 经销商净值(Stock)： 如 "451.33RMB" → 451.33（去除 RMB 后缀，转 float）
      - 经销商净值(Rush)：  如 "451.33RMB" → 451.33（去除 RMB 后缀，转 float）
      - 可用库存：          如 "35件" → 35（去除 "件" 字后缀，转 float）
      - 其它字段：          原样保留（如 oe、零件名、基本单元、族组、采集时间等）

    :param data: dict，爬虫解析出的原始字段
    :return: 清洗后的 dict
    """
    if not data or not isinstance(data, dict):
        return data

    cleaned = {}
    for key, value in data.items():
        # 非字符串类型（int/float/None 等）原样保留
        if not isinstance(value, str):
            cleaned[key] = value
            continue

        text = value.strip()

        # —— 1. 毛重：去除 "KG" 单位 ——
        if key == '毛重':
            try:
                num_str = text.replace('KG', '').replace('kg', '').strip()
                cleaned[key] = float(num_str)
                continue
            except (ValueError, TypeError):
                cleaned[key] = value
                continue

        # —— 2. 净重：去除 "KG" 单位 ——
        if key == '净重':
            try:
                num_str = text.replace('KG', '').replace('kg', '').strip()
                cleaned[key] = float(num_str)
                continue
            except (ValueError, TypeError):
                cleaned[key] = value
                continue

        # —— 3. 体积：去除 "CDM" 单位 ——
        if key == '体积':
            try:
                num_str = text.replace('CDM', '').replace('cdm', '').strip()
                cleaned[key] = float(num_str)
                continue
            except (ValueError, TypeError):
                cleaned[key] = value
                continue

        # —— 4. 零售价：去除 "RMB" 单位 ——
        if key == '零售价':
            try:
                num_str = text.replace('RMB', '').replace('rmb', '').strip()
                cleaned[key] = float(num_str)
                continue
            except (ValueError, TypeError):
                cleaned[key] = value
                continue

        # —— 5. 经销商折扣(Stock)：百分比 → 小数 ——
        if key == '经销商折扣(Stock)':
            try:
                num_str = text.replace('%', '').strip()
                cleaned[key] = round(float(num_str) / 100.0, 4)
                continue
            except (ValueError, TypeError):
                cleaned[key] = value
                continue

        # —— 6. 经销商折扣(Rush)：百分比 → 小数 ——
        if key == '经销商折扣(Rush)':
            try:
                num_str = text.replace('%', '').strip()
                cleaned[key] = round(float(num_str) / 100.0, 4)
                continue
            except (ValueError, TypeError):
                cleaned[key] = value
                continue

        # —— 7. 经销商净值(Stock)：去除 "RMB" 单位 ——
        if key == '经销商净值(Stock)':
            try:
                num_str = text.replace('RMB', '').replace('rmb', '').strip()
                cleaned[key] = float(num_str)
                continue
            except (ValueError, TypeError):
                cleaned[key] = value
                continue

        # —— 8. 经销商净值(Rush)：去除 "RMB" 单位 ——
        if key == '经销商净值(Rush)':
            try:
                num_str = text.replace('RMB', '').replace('rmb', '').strip()
                cleaned[key] = float(num_str)
                continue
            except (ValueError, TypeError):
                cleaned[key] = value
                continue

        # —— 9. 可用库存：去除 "件" 字 ——
        if key == '可用库存':
            try:
                num_str = text.replace('件', '').strip()
                cleaned[key] = float(num_str)
                continue
            except (ValueError, TypeError):
                cleaned[key] = value
                continue

        # —— 其它字段：原样保留 ——
        cleaned[key] = value

    return cleaned