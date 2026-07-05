# -*- coding:utf-8 -*-
# @Time    : 2026/3/30 11:17
# @Author  : xingkongtub
# @Project : overall_project
# @File    : dashboard_crm_wms.py
# @Software: PyCharm

import pandas as pd

from app.services.dashboard_crm_wms_services import wms_orders
from app.services.dashboard_crm_wms_services.load_config import get_config
from app.utils.spider_utli import simple_spider


def crm_mergeOrderList_spider(url0,headers,start_date,end_date):


    page = 1  # 第几页
    limit = 200  # 每页返回的数据
    status = 1  # 状态（1为已调单）
    order_type_id = 1  # 表示1为销售订单
    is_wms = 1

    # 使用pandas进行分析，爬取的数据写入DataFrame
    df = pd.DataFrame()

    #循环分页爬取
    while True:

        # print("参数",page,limit,status,order_type_id,is_wms)
        url = (url0+"?page="+page.__str__()+"&limit="+limit.__str__()
               +"&status="+status.__str__()+"&order_type_id="+order_type_id.__str__()+"&is_wms="+is_wms.__str__()
               +"&orderdate[]="+start_date+"&orderdate[]="+end_date)

        print("爬取的api为",url)

        json_data=simple_spider(url, headers)
        page +=1

        if not json_data.get("data",{}):
            break

        data = json_data.get("data", {}).get("list", {}).get("data")

        if  data:
            # DataFrame数据追加
            df = pd.concat([df, pd.DataFrame(data)], ignore_index=True)
            # print(data)
            # print("数据为", len(data))
            if len(data) < limit:
                break
        else:
            continue

        # 查看数据总条数（总行数）
        # print("数据总数：", len(df))
        # print(df.head(10))




    return df





def wms_get_status_orders_spider(url0,headers):




    # 使用pandas进行分析，爬取的数据写入DataFrame
    df = pd.DataFrame()
    flag = 1
    type_id = 3
    # status = 1  # 拣货单      0表示未开始，1表示正在拣货，2表示已完成,空表示全部
    page = 1  # 页数空表示第一页
    url = url0

    # 进行循环拣货单状态爬取
    for status in range(0, 2):    # 拣货单      0表示未开始，1表示正在拣货，2表示已完成,空表示全部
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

            print("正在爬取的接口",url)
            json_data=simple_spider(url, headers)


            # print(json_data)
            data=json_data.get("data", {}).get("data", {}).get("data")
            # print(data)


            if data:
                df = pd.concat([df, pd.DataFrame(data)], ignore_index=True)
                # print(data)

            flag += 1


            # print("数据总数：", len(df))
            if len(json_data) < 20:
                break


    # 查看数据总条数（总行数）
    # print("数据总数：", len(df))
    # print(df.head(10))


    return df





def wms_get_status_orders_keywd_spider(url0,headers,keywd_list):
    # 使用pandas进行分析，爬取的数据写入DataFrame
    df = pd.DataFrame()
    type_id = 3

    # keywd_list.append("CK0201026032910260508")
    # 进行循环拣货单已完成的数据爬取
    for keywd in keywd_list:

        url = url0 + "?type=" + type_id.__str__() + "&keywd="+keywd
        print("爬取接口"+url)
        print("爬取中请等待")
        # time.sleep(1)
        json_data=simple_spider(url, headers)
        # json_data=json_data["data"]
        data = json_data.get("data", {}).get("data", {}).get("data")

        print("数据为",json_data)

        if data:
            df = pd.concat([df, pd.DataFrame(data)], ignore_index=True)
        else:

            # df = pd.concat([df, pd.DataFrame({"pono":keywd,"is_data_exists":2})], ignore_index=True)
            df = pd.concat([df, pd.DataFrame({"pono": [keywd], "is_data_exists": [2]})], ignore_index=True)
    return df








def crawl_data_crm_wms(start_date,end_date):
    # 业务函数

        # 每次都会拿最新配置
    config = get_config()

    crm_token = config["crm_token"]
    wms_token = config["wms_token"]
    print("token为：", crm_token,wms_token)  # 修改json后，不用重启，直接变


    url_crm = "https://crm.gzbbr.com/api/Crm.Orders/mergeOrderList"
    headers_crm = {
        # 模拟浏览器请求头（必须加，否则很多网站会拦截）
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0",
        "authorization":crm_token}


    url_wms = "https://wms.gzbbr.com/api/Wms.Orders/get_status_orders"
    headers_wms = {
        # 模拟浏览器请求头（必须加，否则很多网站会拦截）
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0",
        "authorization": wms_token
    }

    print("--------------------------------------")
    df1 = crm_mergeOrderList_spider(url_crm,headers_crm,start_date,end_date)
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
    df2 = wms_get_status_orders_spider(url_wms,headers_wms)
    print("df2爬取的数据总数：", len(df2))
    # 查看数据总条数（总行数）
    # print("df2数据总数：", len(df2))
    # pono为原单号
    # l_name_zh为货品名称
    # fullname为客户名称
    # real_name为业务员
    # name为拣货员
    # jhdate为拣货日期
    # print(df2[["pono", "l_name_zh", "fullname", "real_name", "name"]].head(100))
    # print("df2 的所有列名：", df2.columns.tolist())
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
    df1_clean = df1_clean.add_suffix('_df1')
    df2_clean = df2_clean.add_suffix('_df2')

    df1_clean = df1_clean.rename(columns={'d_sap_no_df1': 'pono_new'})
    df2_clean = df2_clean.rename(columns={'pono_df2': 'pono_new'})

    df_merged = pd.merge(
        df1_clean,
        df2_clean,
        on='pono_new',  # 连接字段
        how='left',  # 连接方式 左连接   保留df1所有订单，df2没有的填充NaN
        suffixes=('', '')  # 列名冲突后缀
    )

    # 步骤4：验证结果
    # print(f"合并完成！数据形状: {df_merged.shape}")
    # print(df_merged.head())

    print("df_merged************数据合并后的数据**************数据总数：", len(df_merged))
    # print(df_merged.head(100))

    # 生成带时间戳的文件名
    # print("************生成excel")
    # timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    # filename = f'合并前订单合并_{timestamp}.xlsx'
    # df_merged.to_excel(
    #     filename,
    #     index=False,
    #     sheet_name='合并订单数据',
    #     engine='openpyxl',
    # )
    # print(f"[成功] 导出成功！\n文件: {filename}\n记录数: {len(df_merged)}")

    # 条件：orders_no_df2 不是空值 且 不是空字符串
    condition = (df_merged['orders_no_df2'].isna()) | (df_merged['orders_no_df2'] == '')
    # 提取符合条件的 pono_new 并转成列表
    pono_new_list = df_merged.loc[condition, 'pono_new'].tolist()

    print("需要查找的有",len(pono_new_list),pono_new_list)
    df3=wms_get_status_orders_keywd_spider(url_wms,headers_wms,pono_new_list)
    print("--------------------------------------")




    print("--------------------------------------")
    print("df3清洗前数据总数：", len(df3))
    print("df3数据删除空订单号和重复订单号")
    #删除空订单号
    df3_clean = df3.dropna(subset=['pono']).copy()
    # 处理重复订单号 （保留第一条记录）
    df3_clean = df3_clean.drop_duplicates(subset=['pono'], keep='first')
    print("df3清洗后数据总数：", len(df3_clean))
    print("--------------------------------------")



    # df_merged与df3_clean合并
    # 执行合并
    print("--------------------------------------")
    # print(f"合并前！数据形状: {df_merged.shape}")
    # print(df_merged[["pono_new", "orders_no_df2"]].head(100))
    # 步骤1：为所有字段添加统一后缀
    df3_clean = df3_clean.add_suffix('_df3')

    df3_clean = df3_clean.rename(columns={'pono_df3': 'pono_new'})

    df_merged = pd.merge(
        df_merged,
        df3_clean,
        on='pono_new',  # 连接字段
        how='left',  # 连接方式 外连接
        suffixes=('', '')  # 列名冲突后缀
    )

    # 步骤4：验证结果
    # print(f"合并完成！数据形状: {df_merged.shape}")
    # print(df_merged[["pono_new", "orders_no_df2"]].head(100))
    print("--------------------------------------")







    # 生成带时间戳的文件名
    # print("************生成excel")
    # timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    # filename = f'合并后订单合并_{timestamp}.xlsx'
    # df_merged.to_excel(
    #     filename,
    #     index=False,
    #     sheet_name='合并订单数据',
    #     engine='openpyxl',
    # )
    # print(f"导出成功！\n文件: {filename}\n记录数: {len(df_merged)}")

    # ==================== 步骤2: 字段筛选 ====================
    keep_columns = [
        'pono_new',
        'handler_df1',
        'create_date_df1',
        'fullname_df1',
        'customer_phone_df1',
        'is_data_exists_df3'
    ]

    keep_columns_df2=[
        'name_df2',
        'jhdate_df2',
        'status_df2',
        'wait_pick_num_df2',
        'toqty_df2',
        "orders_no_df2",
        'l_name_zh_df2',
        'already_pick_num_df2'
    ]

    keep_columns_df3=[
        'name_df3',
        'jhdate_df3',
        'status_df3',
        'wait_pick_num_df3',
        'toqty_df3',
        "orders_no_df3",
        'l_name_zh_df3',
        'already_pick_num_df3'
    ]

    keep_columns.extend(keep_columns_df2)

    # # # 生成带时间戳的文件名
    # print("************生成excel")
    # timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    # filename = f'订单df_merged_{timestamp}.xlsx'
    # df_merged.to_excel(
    #     filename,
    #     index=False,
    #     sheet_name='合并订单数据',
    #     engine='openpyxl',
    # )
    # print(f"[成功] 导出成功！\n文件: {filename}\n记录数: {len(df_merged)}")



    if 'orders_no_df3' in df_merged.columns:

        print("df_merged.columns***************************")
        # 把后缀为df3的字段的数据，复制到后缀为df2
        df_merged.loc[df_merged['is_data_exists_df3'] != 2, keep_columns_df2] = df_merged.loc[df_merged['is_data_exists_df3'] != 2, keep_columns_df3].values


    # 只保留指定字段
    df_merged_new = df_merged[keep_columns]

    target_out_nos=df_merged_new['pono_new'].tolist()

    print("target_out_nos的列表",target_out_nos)

    wms_orders_by_out_nos= wms_orders.get_orders_by_out_nos(target_out_nos)


    df_wms_orders_by_out_nos = pd.DataFrame()

    print("左边表 df_merged_new 列名：", list(df_merged_new.columns))

    #把数据库返回的数据转成df列表
    df_wms_orders_by_out_nos = pd.DataFrame([vars(order) for order in wms_orders_by_out_nos])

    # 要新增的列名
    new_columns = ['out_no', 'shipper', 'shipDate', 'order_id','photos','total_quantity']


    if 'out_no' not in df_merged_new.columns:
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






    # print("df_merged的字段有",df_merged_new.columns.tolist())

    # 将jhdate_df2转换为Unix时间戳（秒）
    # 先将jhdate_df2转换为日期时间类型
    df_merged_new['jhdate_timestamp'] = (
            pd.to_datetime(df_merged_new['jhdate_df2'], errors='coerce')
            .dt.tz_localize('Asia/Shanghai', nonexistent='shift_forward')
            .astype('int64') // 10 ** 6
    )



    print("*******合成后的数据*********",df_merged_new[["jhdate_timestamp", "jhdate_df2","name_df2"]].head(20))



    # 把小于等于0的时间戳，替换为 pandas 专用空值 pd.NA
    df_merged_new.loc[df_merged_new['jhdate_timestamp'] <= 0, 'jhdate_timestamp'] = pd.NA
    #把所有 pandas 空值（pd.NA/np.nan）全局替换为 Python 原生空值 None
    # df_merged_new = df_merged_new.where(pd.notna(df_merged_new), None)
    df_merged_new = df_merged_new.where(pd.notna(df_merged_new))
    df_merged_new = df_merged_new.astype(object).where(pd.notna(df_merged_new), None)
    # 删除没用字段
    df_merged_new = df_merged_new.drop(['l_name_zh_df2', 'jhdate_df2','customer_phone_df1'], axis=1)

    # # 生成带时间戳的文件名
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




