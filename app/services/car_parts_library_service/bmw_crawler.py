# -*- coding:utf-8 -*-
# @Time    : 2026/6/12
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : bmw_crawler.py
# @Software : PyCharm
# 华晨宝马爬虫服务层
# 职责：编排 "爬虫请求 + 数据清洗" 的完整流程
# 结构：一个爬虫接口 对应 一个清洗函数 对应 一个 service 函数
#   1. get_stock_check      → clean_stock_html     → query_part_stock
#   2. get_material_details  → clean_material_html  → query_part_detail
# =====================================================================

from datetime import datetime

# ---------- 1. 爬虫（只发请求，不解析） ----------
from app.scripts.spiders.spider_entities.bmw_brilliance import BMWBrillianceSpider

# ---------- 2. 清洗通道（只解析，不发请求） ----------
from app.scripts.spiders.pipeline_clean.bmw_brilliance_clear import (
    clean_stock_html,
    clean_material_html,
    records_to_json,
)


# ====================================================
# 内部工具
# ====================================================

def _wrap_result(oe, data, success, message=""):
    """统一响应包装格式"""
    return {
        "success": success,
        "oe": oe,
        "data": data,
        "message": message,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _ensure_crawler(cookie, timeout, crawler):
    """内部用：如果调用方没传 crawler，就临时创建一个"""
    if crawler is not None:
        return crawler
    return BMWBrillianceSpider(cookie=cookie, timeout=timeout)


# ====================================================
# 接口一：查询零件库存信息
#   爬虫  → BMWBrillianceSpider.get_stock_check(oe)
#   清洗  → clean_stock_html(html, oe)
# ====================================================

def query_part_stock(oe, cookie, timeout=15, crawler=None, return_json=False):
    """
    查询零件库存信息 —— 完整流程（爬虫 + 清洗）

    :param oe: 零件号，如 "36121116326"
    :param cookie: 从浏览器/Hoppscotch 复制的有效 Cookie
    :param timeout: 请求超时时间（秒）
    :param crawler: 可选，外部传入的爬虫实例（便于批量查询时复用）
    :param return_json: True 时返回 JSON 字符串，False 返回 dict
    :return: dict 或 JSON 字符串
    """
    oe_clean = str(oe).strip()
    if not oe_clean:
        result = _wrap_result("", None, False, "零件号（oe）不能为空")
        return records_to_json([result]) if return_json else result

    # 1) 初始化爬虫
    spider = _ensure_crawler(cookie, timeout, crawler)

    # 2) 发请求 —— 拿原始 HTML
    try:
        response = spider.get_stock_check(oe_clean)
    except Exception as e:
        result = _wrap_result(oe_clean, None, False, "爬虫异常: {}".format(e))
        return records_to_json([result]) if return_json else result

    if response is None:
        result = _wrap_result(oe_clean, None, False, "请求失败（可能是 curl_cffi 未安装或网络错误）")
        return records_to_json([result]) if return_json else result

    if not response.text or len(response.text) == 0:
        result = _wrap_result(oe_clean, None, False, "响应为空（可能 Cookie 已失效）")
        return records_to_json([result]) if return_json else result

    # 3) 清洗解析 —— HTML → dict
    try:
        data = clean_stock_html(response.text, oe_clean)
    except Exception as e:
        result = _wrap_result(oe_clean, None, False, "清洗解析失败: {}".format(e))
        return records_to_json([result]) if return_json else result

    # 4) 包装返回
    if data and "error" in data:
        result = _wrap_result(oe_clean, data, False, data["error"])
    elif data and data.get("status") == "未查询到":
        result = _wrap_result(oe_clean, data, True, data.get("remark", "零件不存在或未激活"))
    else:
        result = _wrap_result(oe_clean, data, True, "查询成功")

    return records_to_json([result]) if return_json else result


# ====================================================
# 接口二：查询零件详细信息
#   爬虫  → BMWBrillianceSpider.get_material_details(oe)
#   清洗  → clean_material_html(html, oe)
# ====================================================

def query_part_detail(oe, cookie, timeout=15, crawler=None, return_json=False):
    """
    查询零件详细信息 —— 完整流程（爬虫 + 清洗）

    :param oe: 零件号
    :param cookie: 有效 Cookie
    :param timeout: 请求超时时间（秒）
    :param crawler: 可选，外部传入的爬虫实例（便于批量查询时复用）
    :param return_json: True 时返回 JSON 字符串
    :return: dict 或 JSON 字符串
    """
    oe_clean = str(oe).strip()
    if not oe_clean:
        result = _wrap_result("", None, False, "零件号（oe）不能为空")
        return records_to_json([result]) if return_json else result

    # 1) 初始化爬虫
    spider = _ensure_crawler(cookie, timeout, crawler)

    # 2) 发请求
    try:
        response = spider.get_material_details(oe_clean)
    except Exception as e:
        result = _wrap_result(oe_clean, None, False, "爬虫异常: {}".format(e))
        return records_to_json([result]) if return_json else result

    if response is None:
        result = _wrap_result(oe_clean, None, False, "请求失败（可能是 curl_cffi 未安装或网络错误）")
        return records_to_json([result]) if return_json else result

    if not response.text or len(response.text) == 0:
        result = _wrap_result(oe_clean, None, False, "响应为空（可能 Cookie 已失效）")
        return records_to_json([result]) if return_json else result

    # 3) 清洗解析
    try:
        data = clean_material_html(response.text, oe_clean)
    except Exception as e:
        result = _wrap_result(oe_clean, None, False, "清洗解析失败: {}".format(e))
        return records_to_json([result]) if return_json else result

    # 4) 包装返回
    if data and "error" in data:
        result = _wrap_result(oe_clean, data, False, data["error"])
    else:
        result = _wrap_result(oe_clean, data, True, "查询成功")

    return records_to_json([result]) if return_json else result


if __name__ == "__main__":
    # 简单测试入口（需要替换成有效的 Cookie）
    test_cookie = "sap-contextid=SID%3aANON%3apcqpdi44_CQP_44%3aeeFVG31p0xe5jSWeLAUwHjGly13Lxx3So6XR8ZUJ-NEW; TS0190948c=014e90d2cd280c239bdc9c3e0f6764c394fdb66d93b8bf097ce6ecf5570bbeb013f04e9f86d5e06b3afdb85fbc001b6d79fc53c73638eafe55ef7d60e2f90c868751f85cf7895380bd8a851ce6ccf78cbff5761f5ce3056e90f74e9c9c96cc96b26c6f8af2fa3845a73ef7c3d58be012dc48de78376d48f68411319f498640d16d3be96218c08639c1fa1eb15c6cdd67acb55c26309e8d63ea1eb782f89f1e5a99d770b76c6be64b3ec4c32dd27866e6ac1c9bf539d4ce87660e98a68446ef38bb13426b38db334b10a2257e3797fe78c53032c75bb02ac2ab68668d141eca5d5cac2fa1a774087fd2a3fbbb68cb76a316e01adcb9; sap-appcontext=c2FwLXNlc3Npb25pZD1TSUQlM2FBTk9OJTNhcGNxcGRpNDRfQ1FQXzQ0JTNhZWVGVllSUkZMYkNHV3VudXltQk12WndIcUhmS3h4MnhvNlVFbGd2OS1BVFQ%3d; TS01d0dca4=014e90d2cd61c371f3a2354f3d98b5662872ca4924b8bf097ce6ecf5570bbeb013f04e9f86d5e06b3afdb85fbc001b6d79fc53c73638eafe55ef7d60e2f90c868751f85cf7895380bd8a851ce6ccf78cbff5761f5ce3056e90f74e9c9c96cc96b26c6f8af2fa3845a73ef7c3d58be012dc48de78376d48f68411319f498640d16d3be96218882fef96356b0e74bd9b22ec72d30313391978f0ee0c5cc4dafb6b5cafd50de2; SelectedMaterials=; Order_Selected_materials=; _qimei_uuid42=1991c0f1f091000dd09c5505067aa9f81ee3184806; _qimei_i_3=5cf845d4925301d89593fd395e8d75e6a5eaa5a416525585e1897a5f72c7216b67613e943989e283d4aa; _qimei_h38=c79cc6f2d09c5505067aa9f80200000f21991c; _qimei_fingerprint=54550af90219e3b56fc9224203a3db6d; sap-usercontext=sap-client=100; BIGipServercqpcn.bmwbrill.cn_pool_8443=2345587466.64288.0000; MYSAPSSO2=AjQxMDMBABhDAE0AMAA3ADcAOQAwACAAIAAgACAAIAACAAYxADAAMAADABBDAFEAUAAgACAAIAAgACAABAAYMgAwADIANgAwADYAMQAyADAAMwAwADQABQAEAAAACAkAAjEA%2fwFWMIIBUgYJKoZIhvcNAQcCoIIBQzCCAT8CAQExCzAJBgUrDgMCGgUAMAsGCSqGSIb3DQEHATGCAR4wggEaAgEBMG8wZDELMAkGA1UEBhMCREUxHDAaBgNVBAoTE1NBUCBUcnVzdCBDb21tdW5pdHkxEzARBgNVBAsTClNBUCBXZWIgQVMxFDASBgNVBAsTC0kwMDIwNDc0MjYxMQwwCgYDVQQDEwNDUVACByAVCQIJU1kwCQYFKw4DAhoFAKBdMBgGCSqGSIb3DQEJAzELBgkqhkiG9w0BBwEwHAYJKoZIhvcNAQkFMQ8XDTI2MDYxMjAzMDQwNVowIwYJKoZIhvcNAQkEMRYEFAOHVRIGlhbSImUxxWih54XnduPGMAkGByqGSM44BAMELzAtAhUAyDFZuUlfe%2fseAFh0dxEetv3C1ioCFBuc0on9uJbRjcT9iNk2UiBPOm7f; _qimei_i_1=27c72bd192530388c7c1fc645b8d20e5f2eea1f1145c52d3bdd920582493206c616361973980ebdd8588dce5; lf_actionspage=spp05_order_create.htm%3foninputprocessing(update); ordtype_create=; date_create=; po_create=; sppbasket=; back_page=SPP05_ORDER_CREATE_FRAME.htm; SAP_SESSIONID_CQP_100=i4iNfZI4pEVUlnEQn12URS74HlVmHBHxtBnVHinbDGY%3d; TS016675fd=014e90d2cda0799d420525b9f503f61d34e5f344e56131994b7bbc5e317db714f5d3ae8de1539f1dd1864e41944039910c580229182cb5bf497b108648c5c55ea04cfc4ae0903f7c20424b0496868ccf5511270642b03c14fadf7610988e7acbee16dba3bf18358233aec2246332bd7fea1ad2a14a68eaa4341473989d0b4b985b3c768accf20a866246b7181c1645ecab96a6a74fde3a349ee9c35ba34d9a361839a28d660692f7cf4e0cff978a5392c0defa22c52abec97c92b3605842027ca142fff1eed1494e5257856acc836f02e75bc40be60cb9e8a94c8cd7e2e5551c278e2bc1a8beafe8b9d6f86f98a965a2811e630c53384e1f13557f5965fa54026e2edbdbc0"
    test_oe = "22118835572"

    print("=== 测试：库存查询 ===")
    stock = query_part_stock(test_oe, test_cookie, return_json=True)
    print(stock)
    print()

    print("=== 测试：详情查询 ===")
    detail = query_part_detail(test_oe, test_cookie, return_json=True)
    print(detail)
