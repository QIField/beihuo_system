"""
卡思商城页面/接口解析

解析逻辑与字段清洗规则与原脚本（修理厂询价单.py）逐字段一致：
- 大部分字段：去中括号/引号/制表符/换行/空格
- 询单日期(crte)、报价备注(remark)、卖点标签(selling_point_tag)、品质(quality_name)：保留原文
"""

import json
import re

from lxml import etree

# 品质枚举 -> 平台中文名（与分层树 qualityName 一一对应）
QUALITY_MAP = {
    'ORIGINAL_CURRENCY': '原厂(非国内4S)',
    'ORIGINAL_INLAND_4S': '原厂(国内4S)',
    'EXTERNAL_BRAND': '国际品牌',
    'INTERNAL_BRAND': '其他品牌',
    'OTHER_BRAND': '其他',
    'SECOND_HAND': '拆车件',
}

_TOTAL_PAGES_RE = re.compile(r'var totalPages = parseInt\((\d+)\);')
_CRTE_RE = re.compile(r'(\d{4}-\d{2}-\d{2}\s*\d{2}:\d{2})')

# 行记录字段（中文名与原脚本 DataFrame 列一致）
ROW_FIELDS = (
    '询单ID', '数量', 'vin', '车型', '描述', '日期', '译码', '商家替换号', '4S参考价',
    '零件名称', '品牌名称', '品质', '供应商名称', '卖家价格', '报价备注', '卖点标签',
    '发货地区', '替换', '报价行ID',
)


def _clean(text):
    """去中括号/引号/制表符/换行/空格（xpath list repr 清洗链，与原脚本一致）"""
    return (str(text).replace('[', '').replace(']', '').replace("'", '')
            .replace(r'\t', '').replace(r'\n', '').replace(' ', ''))


def _clean_keep_space(text):
    """仅去中括号/引号/制表符/换行（保留空格，与原脚本一致）"""
    return (str(text).replace('[', '').replace(']', '').replace("'", '')
            .replace(r'\t', '').replace(r'\n', ''))


def parse_list_page(html_text):
    """
    解析列表页

    :return: {'rows': [{'inquiryid':..,'num':..,'vin':..,'cx':..,'ms':..,'crte':..}], 'total_pages': int}
    """
    html = etree.HTML(html_text)
    trs = html.xpath('//tr[contains(@class,"inquiry-tbody-tr") and @inquiryid]')
    pm = _TOTAL_PAGES_RE.search(html_text)
    total_pages = int(pm.group(1)) if pm else 0

    rows = []
    for v in trs:
        inquiryid = _clean(v.xpath('./@inquiryid'))
        num = _clean(v.xpath('td[4]/text()'))
        vin = _clean(v.xpath('td[5]/text()'))
        cx = _clean(v.xpath('td[6]/text()'))
        ms = _clean(v.xpath('td[7]/text()'))
        crte_tmp = ''.join(v.xpath('td[8]//text()'))
        cm = _CRTE_RE.search(crte_tmp)
        # 列表页日期去掉空格（与原脚本 liebiao 一致）
        crte = cm.group(1).replace(' ', '') if cm else _clean(crte_tmp)
        rows.append({'inquiryid': inquiryid, 'num': num, 'vin': vin,
                     'cx': cx, 'ms': ms, 'crte': crte})
    return {'rows': rows, 'total_pages': total_pages}


def parse_purchase_guide(json_text):
    """采购指导响应 -> {报价行ID: 卖点标签}"""
    re_js = json.loads(json_text) if isinstance(json_text, str) else json_text
    if re_js.get('code') != 200:
        return {}
    return {str(item['quotationProductId']): item['sellingPoint']['sellingPointTag']
            for item in re_js.get('data', [])}


def parse_detail(payload, row, guide_map):
    """
    解析询单明细（inquiryWeb/detail，code==200 场景）-> 行记录列表

    :param payload: 明细 JSON
    :param row: 列表页行（含 num/vin/cx/ms/crte）
    :param guide_map: 采购指导映射
    """
    items = payload['data']['inquiryBodyResults']
    records = []
    for i in items:
        try:
            competitive_price = i['competitivePrice']  # 4S参考价（询单级兜底值）
        except Exception:
            competitive_price = ''
        for w in i['inquiryBodyDecodeResultList']:
            try:
                competitive_price = w['competitivePrice']  # 译码行级覆盖
            except Exception:
                if len(str(competitive_price)) == 0:
                    competitive_price = ''
            for k in w['inquiryBodyQuoteResultList']:
                records.append(_build_row(
                    inquiryid=w['inquiryId'], num=row['num'], vin=row['vin'],
                    cx=row['cx'], ms=row['ms'], crte=row['crte'],
                    parts_num=w['partsNum'], competitive_price=competitive_price,
                    parts_name=w['partsName'], guide_map=guide_map,
                    quote=k,
                ))
    return records


def parse_archive_detail(payload, row, guide_map, inquiryid):
    """
    解析归档询单明细（archiveinquiry，data.status==SUCCESS 场景）-> 行记录列表

    :param inquiryid: 归档明细的询单ID作为行询单ID（与原脚本 mx2 一致）
    """
    items = payload['data']['inquiryItems']
    records = []
    for i in items:
        try:
            resolve_results = i['resolveResults']
        except Exception:
            continue
        for k in resolve_results:
            try:
                competitive_price = k['competitivePrice']
            except Exception:
                competitive_price = ''
            try:
                quoted_results = k['quotedPriceResults']
            except Exception:
                continue
            for oo in quoted_results:
                records.append(_build_row(
                    inquiryid=inquiryid, num=row['num'], vin=row['vin'],
                    cx=row['cx'], ms=row['ms'], crte=row['crte'],
                    parts_num=k['partsNum'], competitive_price=competitive_price,
                    parts_name=k['partsName'], guide_map=guide_map,
                    quote=oo, archive=True,
                ))
    return records


def _build_row(inquiryid, num, vin, cx, ms, crte, parts_num, competitive_price,
               parts_name, guide_map, quote, archive=False):
    """
    构建单条报价行记录（明细与归档两个入口共用，字段兜底与清洗规则与原脚本一致）

    - 明细场景（archive=False）：替换/商家替换号/报价备注/卖点标签/报价行ID 缺失时置 ''
    - 归档场景（archive=True）：替换 固定空串；卖点标签与报价行ID 依次兜底 quotationProductId
    """
    brand_name = _guard(quote, 'brandName')
    store_name = _guard(quote, 'storeName')
    seller_price = _guard(quote, 'sellerBtPrice')
    location_name = _guard(quote, 'locationName')
    merchant_parts_num = _guard(quote, 'partsNum')
    remark = _guard(quote, 'remark')

    if archive:
        replacement = ''  # 归档明细无替换字段
        # 卖点标签/报价行ID：userNeedsItemId 缺失时兜底 quotationProductId（与原脚本 try 链一致）
        try:
            selling_point_tag = guide_map[str(quote['userNeedsItemId'])]
        except Exception:
            try:
                selling_point_tag = guide_map[str(quote['quotationProductId'])]
            except Exception:
                selling_point_tag = ''
        try:
            quote_id = quote['userNeedsItemId']
        except Exception:
            try:
                quote_id = quote['quotationProductId']
            except Exception:
                quote_id = ''
    else:
        replacement = _guard(quote, 'replacement')
        try:
            selling_point_tag = guide_map[str(quote['userNeedsItemId'])]
        except Exception:
            selling_point_tag = ''
        try:
            quote_id = quote['userNeedsItemId']
        except Exception:
            quote_id = ''

    quality_name = QUALITY_MAP.get(str(_guard(quote, 'partsBrandQuality')), '')

    # （清洗组）去空格：询单ID/数量/vin/车型/描述/译码/4S参考价/零件名称/品牌/供应商/卖家价格/发货地区/替换/商家替换号/报价行ID
    # （原文组）保留原文：日期/报价备注/卖点标签/品质
    return {
        '询单ID': _clean(inquiryid),
        '数量': _clean(num),
        'vin': _clean(vin),
        '车型': _clean(cx),
        '描述': _clean(ms),
        '日期': _clean_keep_space(crte),
        '译码': _clean(parts_num),
        '商家替换号': _clean(merchant_parts_num),
        '4S参考价': _clean(competitive_price),
        '零件名称': _clean(parts_name),
        '品牌名称': _clean(brand_name),
        '品质': str(quality_name),
        '供应商名称': _clean(store_name),
        '卖家价格': _clean(seller_price),
        '报价备注': str(remark),
        '卖点标签': str(selling_point_tag),
        '发货地区': _clean(location_name),
        '替换': _clean(replacement),
        '报价行ID': _clean(quote_id),
    }


def _guard(mapping, key):
    """取值兜底：缺失/异常返回 ''（与原脚本 try/except 一致）"""
    try:
        return mapping[key]
    except Exception:
        return ''
