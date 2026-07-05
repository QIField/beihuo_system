# -*- coding:utf-8 -*-
# @Time    : 2026/3/30 11:17
# @Author  : xingkongtub
# @Project : overall_project
# @File    : dashboard_crm_wms.py
# @Software: PyCharm

import pandas as pd
from datetime import datetime

from app.services.dashboard_crm_wms_services import wms_orders
from app.services.dashboard_crm_wms_services.load_config import get_config
from app.utils.spider_utli import simple_spider
from app.models.raw_sql_models.wms_status_orders_raw import WmsStatusOrders


def crm_mergeOrderList_spider(url0, headers, start_date, end_date):
    page = 1  # 第几页
    limit = 200  # 每页返回的数据
    # status = 1  # 状态（1为已调单）
    order_type_id = 1  # 表示1为销售订单
    is_wms = 1

    # 使用pandas进行分析，爬取的数据写入DataFrame
    df = pd.DataFrame()

    # 循环分页爬取
    while True:

        # print("参数",page,limit,status,order_type_id,is_wms)
        url = (url0 + "?page=" + page.__str__() + "&limit=" + limit.__str__()
               + "&order_type_id=" + order_type_id.__str__()
               + "&orderdate[]=" + start_date + "&orderdate[]=" + end_date)

        print("爬取的api为", url)

        json_data = simple_spider(url, headers)
        page += 1

        if not json_data.get("data", {}):
            break

        data = json_data.get("data", {}).get("list", {}).get("data")

        if data:
            # DataFrame数据追加
            df = pd.concat([df, pd.DataFrame(data)], ignore_index=True)
            # print(data)
            # print("数据为", len(data))
            if len(data) < limit:
                break
        else:
            continue

    return df


def wms_get_status_orders_spider(url0, headers, page_num):
    # 使用pandas进行分析，爬取的数据写入DataFrame
    df = pd.DataFrame()
    flag = 1
    type_id = 3
    # status = 1  # 拣货单      0表示未开始，1表示正在拣货，2表示已完成,空表示全部
    page = 1  # 页数空表示第一页
    url = url0

    # 进行循环拣货单状态爬取
    for status in range(0, 2):  # 拣货单      0表示未开始，1表示正在拣货，2表示已完成,空表示全部
        flag = 1

        # 进行循环分页爬取
        while True:
            # url=url0
            if flag == 1:
                page = ""
            else:
                page = "&page=" + flag.__str__()

            # print("合成", url, type_id.__str__(), status, page)
            url = url0 + "?type=" + type_id.__str__() + "&status=" + status.__str__() + page

            print("正在爬取的接口", url)
            json_data = simple_spider(url, headers)

            # print(json_data)
            data = json_data.get("data", {}).get("data", {}).get("data")
            # print(data)

            if data:
                df = pd.concat([df, pd.DataFrame(data)], ignore_index=True)
                # print(data)

            flag += 1

            # print("数据总数：", len(df))
            if len(json_data) < 20:
                break

    # 原有爬虫代码已注释，改为直接从数据库获取数据
    # for i in range(1, page_num + 1):
    #     print()
    #     url = url0 + "?type=3" + "&status=2" + "&page=" + i.__str__()
    #     print("正在爬取的接口", url)
    #     json_data = simple_spider(url, headers)
    #     data = json_data.get("data", {}).get("data", {}).get("data")
    #     if data:
    #         df = pd.concat([df, pd.DataFrame(data)], ignore_index=True)
    
    # 直接从数据库获取当天的所有数据
    today_date = datetime.now().strftime('%Y-%m-%d')
    print(f"正在从数据库获取 {today_date} 的拣货单数据...")
    df_today = WmsStatusOrders.get_by_orderdate_to_df(today_date)
    # df_today=WmsStatusOrders.get_by_orderdate_range_to_df("2026-04-09", "2026-04-10")
    if not df_today.empty:
        df = pd.concat([df, df_today], ignore_index=True)
        print(f"从数据库获取到 {len(df_today)} 条 {today_date} 的拣货单数据")

    return df


def wms_get_status_orders_keywd_spider(url0, headers, keywd_list):
    # ==================== 原代码已注释 ====================
    # # 使用pandas进行分析，爬取的数据写入DataFrame
    # df = pd.DataFrame()
    # type_id = 3
    #
    #
    # # 进行循环拣货单已完成的数据爬取
    # for keywd in keywd_list:
    #
    #     url = url0 + "?type=" + type_id.__str__() + "&keywd=" + keywd
    #     print("爬取接口" + url)
    #     print("爬取中请等待")
    #
    #     json_data = simple_spider(url, headers)
    #
    #     data = json_data.get("data", {}).get("data", {}).get("data")
    #
    #     print("数据为", json_data)
    #
    #     if data:
    #
    #         df = pd.concat([df, pd.DataFrame(data)], ignore_index=True)
    #         # 1. 如果没有 is_data_exists 列，就创建一列，默认值 0
    #         if 'is_data_exists' not in df.columns:
    #             df['is_data_exists'] = 0
    #
    #         # 2. 找到 pono == keywd 的行，把 is_data_exists 设置为 1
    #         df.loc[df['pono'] == keywd, 'is_data_exists'] = 1
    #
    #     else:
    #
    #         # df = pd.concat([df, pd.DataFrame({"pono":keywd,"is_data_exists":2})], ignore_index=True)
    #         df = pd.concat([df, pd.DataFrame({"pono": [keywd], "is_data_exists": [2]})], ignore_index=True)
    # return df
    # ==================== 原代码结束 ====================
    
    # ==================== 新代码开始 ====================
    # 初始化DataFrame
    df = pd.DataFrame()
    type_id = 3
    
    # 1. 先在数据库中搜索 keywd_list 中的数据
    print(f"正在从数据库中查询 {len(keywd_list)} 个订单号...")
    existing_orders = WmsStatusOrders.get_by_ponos(keywd_list)
    
    # 创建一个集合，用于记录已经在数据库中找到的订单号
    found_ponos = set()
    
    # 2. 将数据库中已有的数据添加到df中
    if existing_orders:
        existing_data = [order.to_dict() for order in existing_orders]
        df = pd.concat([df, pd.DataFrame(existing_data)], ignore_index=True)
        found_ponos = {order.pono for order in existing_orders}
        print(f"从数据库找到 {len(found_ponos)} 条已有数据")
    
    # 3. 从 keywd_list 中删除已经找到的订单号，只保留需要爬虫的
    remaining_keywd_list = [keywd for keywd in keywd_list if keywd not in found_ponos]
    print(f"剩余 {len(remaining_keywd_list)} 个订单号需要爬虫")
    
    # 4. 对剩余的订单号进行循环爬取
    for keywd in remaining_keywd_list:
        url = url0 + "?type=" + type_id.__str__() + "&keywd=" + keywd
        print("爬取接口" + url)
        print("爬取中请等待")
        
        json_data = simple_spider(url, headers)
        data = json_data.get("data", {}).get("data", {}).get("data")
        print("数据为", json_data)
        
        if data:
            # 4.1 爬虫有数据的情况
            # 将数据添加到df中
            df = pd.concat([df, pd.DataFrame(data)], ignore_index=True)
            
            # 如果没有 is_data_exists 列，就创建一列
            if 'is_data_exists' not in df.columns:
                df['is_data_exists'] = 0
            
            # 设置 is_data_exists 为 1
            df.loc[df['pono'] == keywd, 'is_data_exists'] = 1
            
            # 准备插入/更新到数据库的数据
            data_list = []
            for item in data:
                item_dict = dict(item)
                item_dict['is_data_exists'] = 1
                data_list.append(item_dict)
            
            # 批量插入/更新到数据库
            if data_list:
                WmsStatusOrders.batch_upsert(data_list)
                print(f"已将 {len(data_list)} 条数据更新到数据库，is_data_exists=1")
        
        else:
            # 4.2 爬虫没有数据的情况
            # 将订单号添加到df中，is_data_exists 设置为 2
            df = pd.concat([df, pd.DataFrame({"pono": [keywd], "is_data_exists": [2]})], ignore_index=True)
            
            # 插入/更新到数据库，is_data_exists 设置为 2
            WmsStatusOrders.batch_upsert([{"pono": keywd, "is_data_exists": 2}])
            print(f"已将订单号 {keywd} 更新到数据库，is_data_exists=2")
    
    return df
    # ==================== 新代码结束 ====================


def crawl_data_crm_wms(start_date, end_date):
    # 业务函数

    # 每次都会拿最新配置
    config = get_config()

    crm_token = config["crm_token"]
    wms_token = config["wms_token"]
    print("token为：", crm_token, wms_token)  # 修改json后，不用重启，直接变

    url_crm = "https://crm.gzbbr.com/api/Crm.Orders/mergeOrderList"
    headers_crm = {
        # 模拟浏览器请求头（必须加，否则很多网站会拦截）
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0",
        "authorization": crm_token}

    url_wms = "https://wms.gzbbr.com/api/Wms.Orders/get_status_orders"
    headers_wms = {
        # 模拟浏览器请求头（必须加，否则很多网站会拦截）
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0",
        "authorization": wms_token
    }

    print("--------------------------------------")
    df1 = crm_mergeOrderList_spider(url_crm, headers_crm, start_date, end_date)
    # 查看数据总条数（总行数）
    print("df1爬取的数据总数：", len(df1))
    # print(df1[["d_sap_no", "fullname", "customer_phone", "handler", "create_date"]].head(100))
    # 步骤1: 清洗df1数据
    # 删除订单号为空的行
    print("df1数据删除空订单号重复订单号")
    df1_clean = df1.dropna(subset=['d_sap_no']).copy()

    # 处理重复订单号 （保留第一条记录）
    df1_clean = df1_clean.drop_duplicates(subset=['d_sap_no'], keep='first')
    print("df1清洗后数据总数：", len(df1_clean))
    # print("df1清洗后前10条的数据",df1_clean[["d_sap_no", "fullname", "customer_phone", "handler", "create_date"]].head(10))
    print("--------------------------------------")

    # 爬取wms的数据
    print("--------------------------------------")
    df2 = wms_get_status_orders_spider(url_wms, headers_wms, len(df1) // 20 + 3)
    print("df2爬取的数据总数：", len(df2))
    # 查看数据总条数（总行数）
    # print("df2数据总数：", len(df2))
    # pono为原单号
    # l_name_zh为货品名称
    # fullname为客户名称
    # real_name为业务员
    # name为拣货员
    # jhdate为拣货日期时间戳

    # 步骤1: 清洗df1数据
    # 删除订单号为空的行
    print("df2数据删除空订单号和重复订单号")
    df2_clean = df2.dropna(subset=['pono']).copy()
    # 处理重复订单号 （保留第一条记录）
    df2_clean = df2_clean.drop_duplicates(subset=['pono'], keep='first')
    print("df2清洗后数据总数：", len(df2_clean))
    print("--------------------------------------")

    # 执行合并
    print("--------------------------------------")
    # 步骤1：为所有字段添加统一后缀
    df1_clean = df1_clean.add_suffix('_crm')
    df2_clean = df2_clean.add_suffix('_wms')

    df1_clean = df1_clean.rename(columns={'d_sap_no_crm': 'pono_new'})
    df2_clean = df2_clean.rename(columns={'pono_wms': 'pono_new'})

    df_merged = pd.merge(
        df1_clean,
        df2_clean,
        on='pono_new',  # 连接字段
        how='left',  # 连接方式 左连接   保留df1所有订单，df2没有的填充NaN
        suffixes=('', '')  # 列名冲突后缀
    )

    # 步骤4：验证结果
    print("df_merged************数据合并后的数据**************数据总数：", len(df_merged))

    # 条件：orders_no_wms 不是空值 且 不是空字符串
    condition = (df_merged['orders_no_wms'].isna()) | (df_merged['orders_no_wms'] == '')
    # 提取符合条件的 pono_new 并转成列表
    pono_new_list = df_merged.loc[condition, 'pono_new'].tolist()

    print("需要查找的有", len(pono_new_list), pono_new_list)
    df3 = wms_get_status_orders_keywd_spider(url_wms, headers_wms, pono_new_list)
    print("--------------------------------------")

    print("--------------------------------------")
    print("df3清洗前数据总数：", len(df3))
    print("df3数据删除空订单号和重复订单号")
    if len(df3) == 0:
        df3[
            ['pono',
            'name',
            'jhdate',
            'status',
            'wait_pick',
            'toqty',
            "orders_no",
            'l_name_zh',
            'already_pick_num',
            'is_data_exists',
             'wait_pick_num',
             'qty'
             ]
        ] = ""

    print(df3.columns.tolist())
    # 删除空订单号
    df3_clean = df3.dropna(subset=['pono']).copy()
    # 处理重复订单号 （保留第一条记录）
    df3_clean = df3_clean.drop_duplicates(subset=['pono'], keep='first')
    print("df3清洗后数据总数：", len(df3_clean))
    print("--------------------------------------")

    # df_merged与df3_clean合并
    # 执行合并
    print("--------------------------------------")

    # 步骤1：为所有字段添加统一后缀
    df3_clean = df3_clean.add_suffix('_wms_keywd')

    df3_clean = df3_clean.rename(columns={'pono_wms_keywd': 'pono_new'})

    df_merged = pd.merge(
        df_merged,
        df3_clean,
        on='pono_new',  # 连接字段
        how='left',  # 连接方式 外连接
        suffixes=('', '')  # 列名冲突后缀
    )

    print("--------------------------------------")

    # ==================== 步骤2: 字段筛选 ====================
    keep_columns = [
        'pono_new',
        'handler_crm',
        'create_date_crm',
        'fullname_crm',
        'customer_phone_crm',
        'is_data_exists_wms_keywd'
    ]

    keep_columns_wms = [
        'name_wms',
        'jhdate_wms',
        'status_wms',
        'wait_pick_num_wms',
        'toqty_wms',
        "orders_no_wms",
        'l_name_zh_wms',
        'already_pick_num_wms',
        'qty_wms'
    ]

    keep_columns_wms_keywd = [
        'name_wms_keywd',
        'jhdate_wms_keywd',
        'status_wms_keywd',
        'wait_pick_num_wms_keywd',
        'toqty_wms_keywd',
        "orders_no_wms_keywd",
        'l_name_zh_wms_keywd',
        'already_pick_num_wms_keywd',
        'qty_wms_keywd'
    ]

    keep_columns.extend(keep_columns_wms)

    if 'orders_no_wms_keywd' in df_merged.columns and len(df3)!=0:
        print("df_merged.columns***************************")
        # 把后缀为df3的字段的数据，复制到后缀为df2
        print(df_merged.columns.tolist())
        df_merged.loc[df_merged['is_data_exists_wms_keywd'] == 1, keep_columns_wms] = df_merged.loc[
            df_merged['is_data_exists_wms_keywd'] == 1, keep_columns_wms_keywd].values

    # 只保留指定字段
    df_merged_new = df_merged[keep_columns]

    target_out_nos = df_merged_new['pono_new'].tolist()

    print("target_out_nos的列表", target_out_nos)

    wms_orders_by_out_nos = wms_orders.get_orders_by_out_nos(target_out_nos)

    df_wms_orders_by_out_nos = pd.DataFrame()

    print("左边表 df_merged_new 列名：", list(df_merged_new.columns))

    # 把数据库返回的数据转成df列表
    df_wms_orders_by_out_nos = pd.DataFrame([vars(order) for order in wms_orders_by_out_nos])
    # print("数据库查到的数据",df_wms_orders_by_out_nos)

    # 要新增的列名
    new_columns = ['out_no', 'shipper', 'ship_date', 'order_id', 'photos', 'total_quantity']
    print("df_wms_orders_by_out_nos列名=",df_wms_orders_by_out_nos.columns)
    if 'out_no' not in df_wms_orders_by_out_nos.columns:
        # df_wms_orders_by_out_nos['out_no'] = ''
        # 添加多个新列，全部赋值为空字符串
        df_wms_orders_by_out_nos[new_columns] = ""

    df_wms_orders_by_out_nos = df_wms_orders_by_out_nos.rename(columns={'out_no': 'pono_new'})

    print("右边表 df_wms_orders_by_out_nos 列名：", list(df_wms_orders_by_out_nos.columns))
    df_merged_new = pd.merge(
        df_merged_new,
        df_wms_orders_by_out_nos,
        on='pono_new',  # 连接字段
        how='left',  # 连接方式 外连接
    )
    new_columns.remove('out_no')
    keep_columns.extend(new_columns)
    # 删除没用字段
    df_merged_new = df_merged_new[keep_columns]

    # 将jhdate_wms转换为Unix时间戳（秒）
    # 先将jhdate_wms转换为日期时间类型
    # Asia/Shanghai 就是北京时间的标准时区名称
    df_merged_new['jhdate_timestamp'] = (
            pd.to_datetime(df_merged_new['jhdate_wms'], errors='coerce')
            .dt.tz_localize('Asia/Shanghai', nonexistent='shift_forward')
            .astype('int64') // 10 ** 9
    )

    # 把小于等于0的时间戳，替换为 pandas 专用空值 pd.NA
    df_merged_new.loc[df_merged_new['jhdate_timestamp'] <= 0, 'jhdate_timestamp'] = pd.NA
    # 把所有 pandas 空值（pd.NA/np.nan）全局替换为 Python 原生空值 None
    df_merged_new = df_merged_new.where(pd.notna(df_merged_new))
    df_merged_new = df_merged_new.astype(object).where(pd.notna(df_merged_new), None)
    # 删除没用字段
    df_merged_new = df_merged_new.drop(['l_name_zh_wms', 'jhdate_wms', 'customer_phone_crm'], axis=1)

    import json
    json_str = json.dumps(
        df_merged_new.to_dict(orient='records'),
        ensure_ascii=False,  # 核心：不把中文转成Unicode
        indent=4
    )

    return json.loads(json_str)

    # # # 生成带时间戳的文件名
    # print("************生成excel")
    # timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    # filename = f'订单合并_{timestamp}.xlsx'
    # df_merged_new.to_excel(
    #     filename,
    #     index=False,
    #     sheet_name='合并订单数据',
    #     engine='openpyxl',
    # )
    # print(f"[成功] 导出成功！\n文件: {filename}\n记录数: {len(df_merged_new)}")
