# -*- coding:utf-8 -*-
# @Time    : 2026/6/12
# @Author  : xingkongtub
# @Project : beihuo_system
# @File    : bmw_crawler.py
# @Software : PyCharm
# ============================================================
# 华晨宝马（BMW Brilliance）零件信息查询服务层
#
# 【职责】
#   编排 "参数校验 → 发起爬虫请求 → 解析/清洗 HTML → 中文属性 → DB 字段映射"
#   的完整流程，并通过自定义异常向调用方分层抛出错误。
#
# 【两条核心调用链】
#   1. query_part_stock  → spider.get_stock_check     → clean_stock_html     → map_stock_cn_to_db
#   2. query_part_detail → spider.get_material_details → clean_material_html  → map_detail_key_clean / map_detail_data_clean
#
# 【设计原则】
#   - 异常直接抛出（使用 app.exceptions 中的自定义异常），不做内部二次包装。
#     调用方根据异常层级（ParameterError → CrawlerError → DataError → BeihuoBaseException）
#     决定如何处理异常。
#   - 爬虫实例可由外部传入（参数 crawler），便于批量查询时复用连接。
#   - 所有对外接口均提供 as_db_fields 参数，按需将"中文属性 key"映射为"数据库字段 key"。
# ============================================================

# TODO: 当前文件未使用 json 模块，若后续无需使用建议移除以避免 linter 告警
import json

from app.exceptions.crawler_exceptions import CrawlerError
from app.exceptions.data_exceptions import DataError
from app.scripts.spiders.spider_entities.bmw_brilliance import BMWBrillianceSpider
from app.scripts.spiders.pipeline_clean.bmw_brilliance_clear import (
    clean_stock_html,
    clean_material_html,
    map_detail_data_clean,
    map_detail_key_clean,
)
from app.exceptions import (
    BeihuoBaseException,
    ParameterError,
    CrawlerRequestError,
    CrawlerResponseEmptyError,
    DataNotFoundError,
    DataParseError,
    DataPersistenceError,
)
from app.utils.orm.session import orm_session
from app.models.orm_models.car_parts_library_bmw import CarPartsLibraryBmw
from app.models.orm_models.car_parts_library_bmw_stock import CarPartsLibraryBmwStock
from config.config_list_manager.config_cache import get_config_value
from sqlalchemy.dialects.mysql import insert



def _ensure_crawler(cookie, crawler):
    """
    【内部工具】确保存在一个可用的 BMWBrillianceSpider 实例。

    设计意图：支持"批量查询时复用同一 spider 实例"的优化场景。
    - 若调用方已通过 crawler 参数传入实例，则直接复用；
    - 否则使用当前的 cookie 与 timeout 临时创建一个新实例。

    :param cookie:  BMW Brilliance 登录态 Cookie
    :param crawler: 可选，外部传入的 BMWBrillianceSpider 实例
    :return:        BMWBrillianceSpider 实例（复用或新建）
    """
    if crawler is not None:
        return crawler
    return BMWBrillianceSpider(cookie=cookie)


def _clean_oe(oe):
    """
    【内部工具】校验并清洗零件号（OE Number）。

    - 将 oe 转为字符串并去除首尾空白；
    - 若清洗后为空字符串，抛出 ParameterError，调用方可据此判定非法输入。

    :param oe: 零件号（字符串或可被 str() 转换的类型）
    :return: 清洗后的零件号字符串
    :raises ParameterError: 零件号清洗后为空
    """
    oe_clean = str(oe).strip()
    if not oe_clean:
        raise ParameterError("零件号（oe）不能为空")
    return oe_clean


def _extract_and_clean(response, oe_clean, clean_func):
    """
    【内部工具】从 HTTP response 中提取 HTML，交由清洗函数解析。

    该函数是 "爬虫 → 数据清洗" 的通用粘合层，被 query_part_stock 与
    query_part_detail 同时调用。它只做最通用的两层合法性检查，具体
    的 HTML 结构解析交给 clean_func 负责。

    :param response:   spider 请求返回的响应对象（需具备 .text 属性，可能为 None）
    :param oe_clean:   已清洗的零件号，将透传给 clean_func
    :param clean_func: 解析函数，签名为 clean_func(html_text: str, oe: str) -> dict
    :return:           clean_func 返回的结构化字典
    :raises CrawlerRequestError:      response 为 None（通常是 curl_cffi 未安装 / 网络错误）
    :raises CrawlerResponseEmptyError: response.text 为空字符串（通常是 Cookie 已失效）
    :raises Exception:                clean_func 内部抛出的异常（如 DataParseError、DataNotFoundError）直接上抛
    """
    if response is None:
        raise CrawlerRequestError("请求失败（response 为 None，可能是 curl_cffi 未安装或网络错误）")

    html_text = getattr(response, "text", "")
    if not html_text:
        raise CrawlerResponseEmptyError("响应为空（可能 Cookie 已失效）")

    return clean_func(html_text, oe_clean)


# ====================================================
# 中文属性 → 数据库字段 映射
# ====================================================

# -------- 1. 库存查询映射表 --------
_STOCK_CN_TO_DB = {
    # 基础信息
    "oe": "part_number",
    "零件": "part_name",
    "折扣代码": "discount_code",
    "零售价": "retail_price",
    "销售单位": "sales_unit",
    # 仓库 - 北京
    "库房-北京": "warehouse_beijing",
    "在途-北京": "in_transit_beijing",
    "再定购点-北京": "reorder_point_beijing",
    "主仓-北京": "main_warehouse_beijing",
    # 仓库 - 上海
    "库房-上海": "warehouse_shanghai",
    "在途-上海": "in_transit_shanghai",
    "再定购点-上海": "reorder_point_shanghai",
    "主仓-上海": "main_warehouse_shanghai",
    # 仓库 - 佛山
    "库房-佛山": "warehouse_foshan",
    "在途-佛山": "in_transit_foshan",
    "再定购点-佛山": "reorder_point_foshan",
    "主仓-佛山": "main_warehouse_foshan",
    # 仓库 - 成都
    "库房-成都": "warehouse_chengdu",
    "在途-成都": "in_transit_chengdu",
    "再定购点-成都": "reorder_point_chengdu",
    "主仓-成都": "main_warehouse_chengdu",
    # 仓库 - 沈阳
    "库房-沈阳": "warehouse_shenyang",
    "在途-沈阳": "in_transit_shenyang",
    "再定购点-沈阳": "reorder_point_shenyang",
    "主仓-沈阳": "main_warehouse_shenyang",
    # 仓库 - 合肥
    "库房-合肥": "warehouse_hefei",
    "在途-合肥": "in_transit_hefei",
    "再定购点-合肥": "reorder_point_hefei",
    "主仓-合肥": "main_warehouse_hefei",
    # 仓库 - 宁波
    "库房-宁波": "warehouse_ningbo",
    "在途-宁波": "in_transit_ningbo",
    "再定购点-宁波": "reorder_point_ningbo",
    "主仓-宁波": "main_warehouse_ningbo",
    # 时间
    "采集时间": "data_collect_time",
}


def map_stock_cn_to_db(data_cn):
    """
    【库存查询】将中文属性的 dict 转换为数据库字段的 dict

    :param data_cn: clean_stock_html 返回的中文 key 的 dict
    :return: 转换后的 dict（key 为数据库字段名）
    """
    if not data_cn or not isinstance(data_cn, dict):
        return {}

    result = {}
    for cn_key, db_key in _STOCK_CN_TO_DB.items():
        if cn_key in data_cn:
            result[db_key] = data_cn[cn_key]
    return result


# -------- 2. 详情查询映射表 --------
_DETAIL_CN_TO_DB = {
    # 基础信息
    "oe": "part_number",
    "零件名": "part_name",
    "基本单元": "sales_unit",
    "族组": "material_group",

    # 重量/体积
    "毛重": "gross_weight",
    "净重": "net_weight",
    "体积": "volume",

    # 价格信息（数据库保留原始值）
    "零售价": "retail_price",
    "经销商折扣(Stock)": "discount_stock",
    "经销商折扣(Rush)": "discount_rush",  
    "经销商净值(Stock)": "dealer_net_stock",  
    "经销商净值(Rush)": "dealer_net_rush",

    # 库存
    "可用库存": "available_stock",

    # 时间
    "采集时间": "data_collect_time",
}


def map_detail_cn_to_db(data_cn):
    """
    【详情查询】将中文属性的 dict 转换为数据库字段的 dict

    :param data_cn: clean_material_html 返回的中文 key 的 dict
    :return: 转换后的 dict（key 为数据库字段名）
    """
    if not data_cn or not isinstance(data_cn, dict):
        return {}

    result = {}
    for cn_key, db_key in _DETAIL_CN_TO_DB.items():
        if cn_key in data_cn:
            result[db_key] = data_cn[cn_key]
    return result


# ====================================================
# 接口一：查询零件库存信息
# ====================================================

def query_part_stock(oe, cookie, crawler=None):
    """
    【接口一】查询零件库存信息。

    流程：校验零件号 → 调用 spider.get_stock_check 请求库存页面 →
          clean_stock_html 解析 HTML → （可选）按 _STOCK_CN_TO_DB 映射为数据库字段 →
          删除对下游无意义的 remark / 选择 / 锁止 字段后返回。

    注：函数签名中未直接暴露 timeout，内部使用 timeout=10 的固定默认值。

    :param oe:           零件号，如 "11137600482"
    :param cookie:       BMW Brilliance 的有效登录 Cookie
    :param crawler:      可选，外部传入的 BMWBrillianceSpider 实例（批量查询时可复用）
    :return:             清洗后的 dict。典型字段：
                         - 中文 key 模式：零件、折扣代码、零售价、销售单位、
                           库房-<城市>、在途-<城市>、再定购点-<城市>、主仓-<城市>、采集时间
                         - DB key 模式：part_name、discount_code、retail_price、sales_unit、
                           warehouse_<city>、in_transit_<city>、reorder_point_<city>、
                           main_warehouse_<city>、data_collect_time
    :raises ParameterError:            零件号为空或全空白
    :raises CrawlerRequestError:       请求失败（response 为 None）
    :raises CrawlerResponseEmptyError: 响应为空（Cookie 可能已失效）
    :raises DataParseError:            HTML 解析失败（table 结构异常等）
    :raises DataNotFoundError:         零件不存在或未激活
    :raises Exception:                 爬虫 / 清洗 过程中抛出的其他异常
    """
    oe_clean = _clean_oe(oe)
    spider = _ensure_crawler(cookie, crawler=crawler)

    response = spider.get_stock_check(oe_clean)
    data = _extract_and_clean(response, oe_clean, clean_stock_html)

    

    # 剔除对下游无意义的页面交互字段 / 状态字段：
    #   - remark：页面注释 / 操作备注，不携带业务库存信息；
    #   - "选择"、"锁止"：SAP 页面的交互控件字段，无需随业务数据返回。
    if 'remark' in data:
        del data['remark']  # pyright: ignore[reportIndexIssue]
    if '选择' in data:
        del data['选择']  # pyright: ignore[reportIndexIssue]
    if '锁止' in data:
        del data['锁止']  # pyright: ignore[reportIndexIssue]

    return data


# ====================================================
# 接口二：查询零件详细信息
# ====================================================

def query_part_detail(oe, cookie, crawler=None,is_unit=True):
    """
    【接口二】查询零件详细信息。

    流程：校验零件号 → 调用 spider.get_material_details 请求详情页面 →
          clean_material_html 解析 HTML → （可选）按 _DETAIL_CN_TO_DB 映射为数据库字段 →
          map_detail_key_clean 统一 key 命名 → 根据 is_unit 决定是否做数值/单位清洗后返回。

    :param oe:           零件号，如 "11137600482"
    :param cookie:       BMW Brilliance 的有效登录 Cookie
    :param crawler:      可选，外部传入的 BMWBrillianceSpider 实例（批量查询时可复用）
    :param is_unit:      数值 / 单位处理开关：
                         - True（默认调用方传入的常见值）：保留原始值，不做 map_detail_data_clean 的单位拆分；
                         - False：对价格、重量、体积等字段做 value + unit 的结构化清洗。
    :return:             清洗后的 dict。典型字段：part_number、零件名、基本单元、族组、
                         毛重、净重、体积、零售价、经销商折扣(Stock/Rush)、
                         经销商净值(Stock/Rush)、可用库存、采集时间（中文或 DB key 取决于 as_db_fields）。
    :raises ParameterError:            零件号为空或全空白
    :raises CrawlerRequestError:       请求失败（response 为 None）
    :raises CrawlerResponseEmptyError: 响应为空（Cookie 可能已失效）
    :raises DataParseError:            HTML 解析失败（table 结构异常等）
    :raises Exception:                 爬虫 / 清洗 过程中抛出的其他异常
    """
    oe_clean = _clean_oe(oe)
    spider = _ensure_crawler(cookie, crawler=crawler)
    
    response = spider.get_material_details(oe_clean)
    data = _extract_and_clean(response, oe_clean, clean_material_html)

    
    
    data = map_detail_key_clean(data)
    

    if not is_unit :
        data = map_detail_data_clean(data)


    return data


# ====================================================
# 接口三：批量爬取零件完整信息（仅返回数据，不做持久化）
#
# 【注意】本模块不负责"入库"。上方注释中的"upsert/入库"指的是调用方拿到
#        返回结果后，可在更上层的服务中执行 upsert（存在则更新、不存在则插入）。
# ====================================================


def data_crawler(oe, cookie=None, is_unit=True):
    """
    【接口三】一次性抓取零件的"库存信息 + 详细信息"，并返回合并后的字典。

    该函数是 query_part_stock 与 query_part_detail 的简单组合，调用方可以通过
    一次调用获得一个零件的完整快照。不执行任何数据库写入 / upsert 操作。

    :param oe:           零件号，如 "51749879093"
    :param cookie:       BMW Brilliance 的有效登录 Cookie（可选，不传或为空时从配置 bmw_car_parts_libray 中获取）
    :param as_db_fields: 是否将中文 key 转换为数据库字段 key（透传给两个子接口）
    :param is_unit:      数值 / 单位处理开关（透传给 query_part_detail）
    :return:             {'stock': stock_dict, 'detail': detail_dict}
    :raises ParameterError: cookie 为空且配置中也没有设置时抛出
    :raises:              子接口可能抛出的所有异常（ParameterError / CrawlerError / DataError 等）
    """

    if not cookie or not str(cookie).strip():
        config = get_config_value('bmw_car_parts_libray')
        if config and isinstance(config, dict):
            cookie = config.get('cookie', '')
    if not cookie or not str(cookie).strip():
        raise ParameterError('未配置 BMW Brilliance 登录 Cookie，请在请求中传入 cookie 或在配置中设置')

    stock = query_part_stock(oe, cookie)
    detail = query_part_detail(oe, cookie, is_unit=is_unit)




    return {
        'stock': stock,
        'detail': detail,
    }


#进行入库操作
def data_upsert(oe, cookie):
    """
    一次性抓取零件的"库存信息 + 详细信息"，并执行 upsert 操作。

    该函数是 data_crawler 的完整落地版本：
    1. 调用 data_crawler 获取原始数据（异常直接上抛，不做二次包装）
    2. 通过 map_detail_cn_to_db / map_stock_cn_to_db 转换为数据库字段
    3. 对两个表（详情表 + 库存表）分别执行 upsert

    【异常策略】
    - 爬取/清洗阶段的异常直接向上抛出（ParameterError / CrawlerError / DataError 等）；
    - 数据库执行期间异常抛出 DataPersistenceError。

    :param oe:           零件号，如 "51749879093"
    :param cookie:       BMW Brilliance 的有效登录 Cookie
    :return:             字典 {'status': bool, 'msg': str, 'detail_updated': bool, 'stock_updated': bool}
    :raises DataPersistenceError: 数据库 upsert 操作失败
    """

    # 1. 爬取数据（异常直接上抛）
    data = data_crawler(oe, cookie, is_unit=False)

    # 2. 中文 key → 数据库字段 key 的映射
    detail = map_detail_cn_to_db(data['detail'])
    stock = map_stock_cn_to_db(data['stock'])



    detail_updated = False
    stock_updated = False

    # 3. 数据库 upsert 操作（固定使用主键 part_number）
    with orm_session() as session:
        try:
            # ========= 3.1 upsert 详情表（CarPartsLibraryBmw） =========
            if detail and isinstance(detail, dict) and detail.get('part_number'):
                detail_stmt = insert(CarPartsLibraryBmw).values(**detail)
                detail_update = {c.name: c for c in detail_stmt.inserted if c.name not in ['part_number', 'created_at', 'updated_at']}
                detail_stmt = detail_stmt.on_duplicate_key_update(**detail_update)
                session.execute(detail_stmt)
                detail_updated = True
                print(f"[BMW] 详情表 upsert 成功: part_number = {detail['part_number']}")

            # ========= 3.2 upsert 库存表（CarPartsLibraryBmwStock） =========
            if stock and isinstance(stock, dict) and stock.get('part_number'):
                stock_stmt = insert(CarPartsLibraryBmwStock).values(**stock)
                stock_update = {c.name: c for c in stock_stmt.inserted if c.name not in ['part_number', 'created_at', 'updated_at']}
                stock_stmt = stock_stmt.on_duplicate_key_update(**stock_update)
                session.execute(stock_stmt)
                stock_updated = True
                print(f"[BMW] 库存表 upsert 成功: part_number = {stock['part_number']}")

            # 4. 提交事务
            # session.commit()  # pyright: ignore[reportAttributeAccessIssue]

            return {
                'status': True,
                'msg': f'零件 {oe} 入库成功（详情: {"是" if detail_updated else "否"}, 库存: {"是" if stock_updated else "否"}）',
                'detail_updated': detail_updated,
                'stock_updated': stock_updated,
            }

        except Exception as e:
            # 数据库操作异常时回滚
            # session.rollback()  # pyright: ignore[reportAttributeAccessIssue]
            msg = f"零件 {oe} 入库失败: {str(e)}"
            print(msg)
            raise DataPersistenceError(msg) from e







# def test_external_data_interface():
#     """
#     【手动测试入口】演示如何正确调用库存 / 详情接口并按异常层级捕获错误。

#     使用步骤：
#       1. 将下方 test_cookie 替换为你在 BMW Brilliance 页面登录后获取的有效 Cookie；
#       2. 修改 test_oe 为你要查询的零件号；
#       3. 在 if __name__ == "__main__" 中调用 test_external_data_interface() 即可。

#     异常捕获顺序（从具体到宽泛，体现自定义异常的分层设计）：
#       ParameterError → CrawlerError → DataError → BeihuoBaseException → Exception
#     """
#     from app.exceptions import (
#         BeihuoBaseException,
#         ParameterError,
#         CrawlerError,
#         DataError,
#     )

#     test_cookie = "sap-contextid=SID%3aANON%3apcqpdi44_CQP_44%3aeeFVhYt4p37HAi_RqtF54_BkajnLxx2Z3qXugJ85-NEW; TS0190948c=014e90d2cd8c14c99180a6381ae029d07034d6e40f7fd7e0ecf1a9d4136e9de34d4de428c36f8003e919ec19d5050c015dfa6f760da563872adc657e3cf7959d0a9f6ce3765fa41d94f1b6f7714c9ed9a96a49061541e52105b181aec8cd35378525022fef96f1c3b5bbdf1fcc4fe068539093c387f042980af7e1a3b3209c4c9ed687f64a5c3f0374dd66febaac75d07231fe0af94cfc54372e9af5cce678c2fccc9bcfe8696f8f257efbbd05e0a24f377a338b96ed23d87f4a3bc779d761737544d63d2160ab2a8b4cd2cefd2a06697960a015b5121dd5567d3f2164b7147720ef4241f52b87348f95a86ea04d705bbd31c1b22d; sap-appcontext=c2FwLXNlc3Npb25pZD1TSUQlM2FBTk9OJTNhcGNxcGRpNDRfQ1FQXzQ0JTNhZWVGVi1hZ05UTXRkeUdzRWJxVllpQ1Z4Q2dQTHh4M29ncVZSbmlYQS1BVFQ%3d; TS01d0dca4=014e90d2cd4f5fe3b242d5ccf0d53b5537096b8ae060a44c8d4b5112479d92896a503525318c52c420edd4e78303d5a356515101b4482c3b9ac6470e14dbebc12f423c67d757c1702bcdd8043e61dba4bfe30d62d6b4d6765cdfbc7d0d932572dc8963cdbbe3d408891689c1664fb19fc2527182ce62831ed3070fcb11aacf66b37c78cad2675508826b86b3158529bb8da8834197ff64713e7fe8343393dec182a604f94c; SelectedMaterials=; Order_Selected_materials=; _qimei_uuid42=1991c0f1f091000dd09c5505067aa9f81ee3184806; _qimei_i_3=5cf845d4925301d89593fd395e8d75e6a5eaa5a416525585e1897a5f72c7216b67613e943989e283d4aa; _qimei_h38=c79cc6f2d09c5505067aa9f80200000f21991c; _qimei_fingerprint=54550af90219e3b56fc9224203a3db6d; sap-usercontext=sap-client=100; BIGipServercqpcn.bmwbrill.cn_pool_8443=2345587466.64288.0000; MYSAPSSO2=AjQxMDMBABhDAE0AMAA3ADcAOQAwACAAIAAgACAAIAACAAYxADAAMAADABBDAFEAUAAgACAAIAAgACAABAAYMgAwADIANgAwADYAMQA1ADAAMgA1ADIABQAEAAAACAkAAjEA%2fwFWMIIBUgYJKoZIhvcNAQcCoIIBQzCCAT8CAQExCzAJBgUrDgMCGgUAMAsGCSqGSIb3DQEHATGCAR4wggEaAgEBMG8wZDELMAkGA1UEBhMCREUxHDAaBgNVBAoTE1NBUCBUcnVzdCBDb21tdW5pdHkxEzARBgNVBAsTClNBUCBXZWIgQVMxFDASBgNVBAsTC0kwMDIwNDc0MjYxMQwwCgYDVQQDEwNDUVACByAVCQIJU1kwCQYFKw4DAhoFAKBdMBgGCSqGSIb3DQEJAzELBgkqhkiG9w0BBwEwHAYJKoZIhvcNAQkFMQ8XDTI2MDYxNTAyNTIxOVowIwYJKoZIhvcNAQkEMRYEFBYPHqv71Do%2fgW%21gypci%21vt2mhW9MAkGByqGSM44BAMELzAtAhQooXculaMAcYfANvFSQJOzsgqAyAIVAJPoWZMDRhzTtOqCFWKbVa8VNBS1; _qimei_i_1=76cc66d192530388c7c1fc645b8d20e5f2eea1f1145c52d3bdd920582493206c616361973980ebdd85acf9fa; lf_actionspage=spp05_order_create.htm%3foninputprocessing(update); ordtype_create=; date_create=; po_create=; sppbasket=; back_page=SPP05_ORDER_CREATE_FRAME.htm; SAP_SESSIONID_CQP_100=hmN7dr1qFEaFmMnICJ1B3IcWuYRofRHxtB7VHinbDGY%3d; TS016675fd=014e90d2cd00c6ec941c6207d5302ea9d1b9baa71c915d511c62fc5ca689427a1ff74a15ffa74237785b1ddc2c6850ccdd7eecaf068b26f4c83b158e3ce241d2ebe4958a5549c1acbd04a185d3f5ea6e9ba8b0015349e60d55f656f27c9615b2f84b66567e48c38b878f4e7908dc2e201fa3d37a24861b0894118535f42454e53a899eba4b74b9c50fa747da5a133ab38d3884659b9ba7294c247564a14b44fef4e2e8ff60cb222d8cf7d9a7c5b18314a85f63a18a43f048e29d15eaebb91ff04fe6cc857882ea01d6333cb3eb51b1f7d523b017c2c8ebc12eea75e4cd6cc77d9e11f585578373c160cc0ececa369212b25fde37730d82296859bc0ab65b0514a6440c279d"



#     test_oe = "51749879093"

#     print("=== 测试：库存查询 ===")
#     try:
#         stock = query_part_stock(test_oe, test_cookie)
#         print(stock)
#         for key, value in stock.items():
#             print(f"{key}: {value}")
#     except ParameterError as e:
#         print(f"参数错误: {e}")
#     except CrawlerError as e:
#         print(f"爬虫异常: {e}")
#     except DataError as e:
#         print(f"数据异常: {e}")
#     except BeihuoBaseException as e:
#         print(f"业务异常: {e}")
#     except Exception as e:
#         print(f"未知异常: {e}")

#     print()
#     print("=== 测试：详情查询 ===")
#     try:
#         detail = query_part_detail(test_oe, test_cookie)
#         print(detail)
#     except ParameterError as e:
#         print(f"参数错误: {e}")
#     except CrawlerError as e:
#         print(f"爬虫异常: {e}")
#     except DataError as e:
#         print(f"数据异常: {e}")
#     except BeihuoBaseException as e:
#         print(f"业务异常: {e}")
#     except Exception as e:
#         print(f"未知异常: {e}")







# ====================================================
# 脚本主入口（交互式地打印 data_crawler 的返回结果）
# ====================================================
# if __name__ == "__main__":

#     # 如需走"带异常分层捕获"的测试流程，可改为调用：
#     # test_external_data_interface()

#     test_oe = "11137600482"
#     test_cookie = "sap-contextid=SID%3aANON%3apcqpdi45_CQP_45%3a_Kg1E8l4lLNOmcctW8NR0HozJhC-TFMmOuAkjvmx-NEW; TS0190948c=014e90d2cd21cbb8a51ffc28beda15c054243d04cab8ffaea2d614ff93d05c3001ea7df0e55b7238dcb8037bb5eeb49504e9cac767891059d24aecfc75f0f7854373c3ba26d5ff65560a2de2c7c2b9f7053e8a131db950e841a92af8baf703644f713418c7ef5ea607f4ecf3b1d7e443ba1c70d6dc5a310cf11af843f51dea1aab934f5156920337b769a4abd0ae1f931d6dbae53096a031ede7786fcfe6a98bfb450a184b5e79e8852e8153412705648aace485235138f0ba4956b4866e3c61f84fc24a93d7c11d190acdadd6835e54737064afec781270b6bf62f78b8213d97212335e18; sap-appcontext=c2FwLXNlc3Npb25pZD1TSUQlM2FBTk9OJTNhcGNxcGRpNDVfQ1FQXzQ1JTNhX0tnMVpZS3hNRmsyN2hoRkVSTnJ5Y2RKRzZTX1RGTlhPdUR4bnpkZC1BVFQ%3d; TS01d0dca4=014e90d2cd386108b5935fd9f9ba081f9349634aa0b8ffaea2d614ff93d05c3001ea7df0e55b7238dcb8037bb5eeb49504e9cac767891059d24aecfc75f0f7854373c3ba26d5ff65560a2de2c7c2b9f7053e8a131db950e841a92af8baf703644f713418c7ef5ea607f4ecf3b1d7e443ba1c70d6dc8269fb6c504b678909570c50a2cdc036cb65990e9f07f6889479f88de9ca8195; SelectedMaterials=; Order_Selected_materials=; _qimei_uuid42=1991c0f1f091000dd09c5505067aa9f81ee3184806; _qimei_i_3=5cf845d4925301d89593fd395e8d75e6a5eaa5a416525585e1897a5f72c7216b67613e943989e283d4aa; _qimei_h38=c79cc6f2d09c5505067aa9f80200000f21991c; _qimei_fingerprint=54550af90219e3b56fc9224203a3db6d; BIGipServercqpcn.bmwbrill.cn_pool_8443=2362364682.64288.0000; sap-usercontext=sap-client=100; MYSAPSSO2=AjQxMDMBABhDAE0AMAA3ADcAOQAwACAAIAAgACAAIAACAAYxADAAMAADABBDAFEAUAAgACAAIAAgACAABAAYMgAwADIANgAwADYAMQA3ADAAMgA0ADcABQAEAAAACAkAAjEA%2fwFXMIIBUwYJKoZIhvcNAQcCoIIBRDCCAUACAQExCzAJBgUrDgMCGgUAMAsGCSqGSIb3DQEHATGCAR8wggEbAgEBMG8wZDELMAkGA1UEBhMCREUxHDAaBgNVBAoTE1NBUCBUcnVzdCBDb21tdW5pdHkxEzARBgNVBAsTClNBUCBXZWIgQVMxFDASBgNVBAsTC0kwMDIwNDc0MjYxMQwwCgYDVQQDEwNDUVACByAVCQIJU1kwCQYFKw4DAhoFAKBdMBgGCSqGSIb3DQEJAzELBgkqhkiG9w0BBwEwHAYJKoZIhvcNAQkFMQ8XDTI2MDYxNzAyNDc1MFowIwYJKoZIhvcNAQkEMRYEFM%2fYZ2QjqPW5KrEgjO8TXsCwzO68MAkGByqGSM44BAMEMDAuAhUAwlEhJs9iMBvuN%2fSTkaVheuEmhOkCFQCyJmEMo5mUVYodt9tw30UceFmCTA%3d%3d; SAP_SESSIONID_CQP_100=i3GLOSqq61RKnxoczv3_rO5WTI9p9hHxhn9zrUlrRiU%3d; lf_actionspage=spp05_order_create.htm%3foninputprocessing(update); ordtype_create=; date_create=; po_create=; sppbasket=; back_page=SPP05_ORDER_CREATE_FRAME.htm; TS016675fd=014e90d2cd8ba86a8949baba6af8dc176dc4e1baa5b8ffaea2d614ff93d05c3001ea7df0e55b7238dcb8037bb5eeb49504e9cac767891059d24aecfc75f0f7854373c3ba26d5ff65560a2de2c7c2b9f7053e8a131db950e841a92af8baf703644f713418c7ef5ea607f4ecf3b1d7e443ba1c70d6dc5a310cf11af843f51dea1aab934f5156920337b769a4abd0ae1f931d6dbae53096a031ede7786fcfe6a98bfb450a184b5e79e8852e8153412705648aace485235138f0ba4956b4866e3c61f84fc24a9310eca868ca23cf7862781fbb15de11956b459f4d2d2361fd3d8865bc01aa9e4b4aa40a088ba5fb48e0d6448c26c18d45; _qimei_i_1=73dd7fd192530388c7c1fc645b8d20e5f2eea1f1145c52d3bdd920582493206c616361973980ebdd8597c5e6"
  
#     #test_cookie = "sap-contextid=SID%3aANON%3ap"

#     try:
#         data = data_crawler(test_oe, test_cookie)

#         print(f"[BMW] 零件 {test_oe} 库存信息:")
#         for key, value in data['stock'].items():
#             print(f"  {key}: {value}")

#         print("="*50)

#         print(f"[BMW] 零件 {test_oe} 详情信息:")
#         for key, value in data['detail'].items():
#             print(f"  {key}: {value}")

#     except ParameterError as e:
#         print(f"[BMW][参数错误] {e}")
#     except DataNotFoundError as e:
#         print(f"[BMW][数据未查询到] {e}")
#     except DataParseError as e:
#         print(f"[BMW][数据解析失败] {e}")
#     except CrawlerError as e:
#         print(f"[BMW][爬虫请求失败] {e}")
#     except DataError as e:
#         print(f"[BMW][数据异常] {e}")
#     except BeihuoBaseException as e:
#         print(f"[BMW][业务异常] {e}")
#     except Exception as e:
#         print(f"[BMW][未知异常] {e}")

    
    # result = data_upsert(test_oe, test_cookie)
    # print(f"\n[BMW] 入库结果: {result}")
   
    
    