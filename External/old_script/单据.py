# -*- coding: utf-8 -*-
import numpy as np
import pyperclip
import cv2
import json
import pandas as pd
import os
import secrets
import string
import pyautogui
import os
import pymysql
import requests
import time
from datetime import datetime, date, timedelta


def get_today_timestamp_range(emergency_mode=False, fixed_start_ts=None):
    """
    获取当日的起始和结束毫秒级时间戳
    参数：
        emergency_mode - True为紧急模式（从当前时间开始），False为普通模式（从00:00:00开始）
        fixed_start_ts - 紧急模式下固定的起始时间戳（毫秒），不传则使用当前时间
    返回：(当日起始时间戳, 当日结束时间戳)
    """
    # 1. 获取今日日期（年-月-日）
    today = date.today()

    # 2. 构造起始时间的datetime对象
    if emergency_mode:
        # 紧急模式：使用固定的时间戳，如果没有则使用当前时间
        if fixed_start_ts:
            start_timestamp = fixed_start_ts
        else:
            start_time = datetime.now().replace(microsecond=0)
            start_timestamp = int(start_time.timestamp() * 1000)
    else:
        # 普通模式：从今日00:00:00开始
        start_time = datetime.combine(today, datetime.min.time())
        start_timestamp = int(start_time.timestamp() * 1000)

    # 3. 构造今日23:59:59的datetime对象
    end_time = datetime.combine(today, datetime.max.time())
    end_timestamp = int(end_time.timestamp() * 1000)

    return start_timestamp, end_timestamp


def deliveryView(delivery_id, headers):
    """
    调单先
    :param delivery_id:
    :return:
    """
    url = f"https://crm.gzbbr.com/api/Crm.Delivery/deliveryView?page=1&limit=30&delivery_id={delivery_id}"
    payload = {}
    response = requests.request("GET", url, headers=headers, data=payload)
    res = json.loads(response.text)
    orders_no = res['data']['TableHeader']['orders_no']
    wms_orders_no = res['data']['wms_orders_no']

    # 调单
    url = f"https://crm.gzbbr.com/api/Wms.Orders/get_orders_save?type=3&pono={orders_no}&orders_no={wms_orders_no}"
    response = requests.request("GET", url, headers=headers)
    print(response.text)


def orders_view(orders_id, headers):
    """
    订单界面
https://crm.gzbbr.com/#/pack/pick_bbr?delivery_id=1683222&type=3&preview=false&is_transfer_customer=0    :param orders_id:
    :return:
    """
    url = f"https://crm.gzbbr.com/api/Crm.Orders/orders_view?orders_id={orders_id}&page=1&limit=50"
    response = requests.request("GET", url, headers=headers)
    res = json.loads(response.text)
    if res['status'] == 200:
        delivery_id = res['data']['delivery_id']  # 打包单
        deliveryView(delivery_id, headers)  # 调单
        dy_url = f"https://crm.gzbbr.com/#/pack/pick_bbr?delivery_id={delivery_id}&type=3&preview=false&is_transfer_customer=0"
        try:
            web_llq(url=dy_url)
            return True
        except Exception as e:
            print("失败1次：" + str(e))
            try:
                web_llq(url=dy_url)
                return True
            except Exception as e:
                print("失败2次：" + str(e))
                try:
                    web_llq(url=dy_url)
                    return True
                except Exception as e:
                    print("失败3次：" + str(e))
        return False


def web_llq(url):
    """
    打印流程
    :param url:
    :return:
    """
    try:
        search_page = pyautogui.locateOnScreen("E:\\dayin\\web.png", confidence=0.8)
    except:
        search_page = pyautogui.locateOnScreen("E:\\dayin\\web2.png", confidence=0.8)
        # 关闭
        pyautogui.moveTo(int(1890), int(20), 0.5)
        pyautogui.click(int(1890), int(20))
        time.sleep(1)
        pyautogui.moveTo(int(1688), int(360), 0.5)
        pyautogui.click(int(1688), int(360))
        time.sleep(1)
        search_page = pyautogui.locateOnScreen("E:\\dayin\\web.png", confidence=0.8)

    time.sleep(0.2)
    pyautogui.moveTo(int(search_page.left), int(search_page.top), 0.5)
    pyautogui.click(int(search_page.left), int(search_page.top))
    time.sleep(1)

    # 搜索框
    pyautogui.moveTo(182, 52, 0.5)
    pyautogui.click(182, 52)
    time.sleep(0.2)
    pyautogui.press('delete')
    time.sleep(1)
    # 输入网址
    pyperclip.copy(url)
    time.sleep(0.5)
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(1)
    pyautogui.press('enter')
    time.sleep(1)
    pyautogui.press('F5')
    time.sleep(2)

    # 预览打印
    search_page = pyautogui.locateOnScreen("E:\\dayin\\yl_dy.png", confidence=0.8)
    pyautogui.moveTo(int(search_page.left), int(search_page.top) - 50, 0.5)
    pyautogui.click(int(search_page.left), int(search_page.top) - 50)
    time.sleep(2)

    # dayin
    pyautogui.moveTo(int(457), int(41), 0.5)
    pyautogui.click(int(457), int(41))
    time.sleep(2)

    # 确定
    pyautogui.press('enter')
    time.sleep(3)

    # 关闭
    pyautogui.moveTo(int(1890), int(20), 0.5)
    pyautogui.click(int(1890), int(20))
    time.sleep(1)
    pyautogui.moveTo(int(1688), int(360), 0.5)
    pyautogui.click(int(1688), int(360))


def get_crm_cookies():
    url = "http://113.45.176.129:8001/get_crm_cookies?key=fs"
    payload = {}
    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36'
    }
    response = requests.request("GET", url, headers=headers, data=payload)
    cookies = json.loads(response.text)['cookie']
    headers = cookies

    return cookies, headers


def get_dd(emergency_mode=False, fixed_start_ts=None):
    # 获取当日时间戳范围
    start_ts, end_ts = get_today_timestamp_range(emergency_mode, fixed_start_ts)
    cttt = str(datetime.now())[:10]
    if cttt == '2026-02-07':
        start_ts = 1770462043000

    # 动态拼接URL
    url = f"https://crm.gzbbr.com/api/Crm.Orders/mergeOrderList?page=1&limit=1000&orderdate[]={start_ts}&orderdate[]={end_ts}&order_type_id=1"
    payload = {}
    cookies, headers = get_crm_cookies()
    response = requests.request("GET", url, headers=headers, data=payload)
    res = json.loads(response.text)
    if res['status'] == 200:
        data = res['data']['list']['data']
        df = pd.DataFrame(data)
        df = df[['orders_id', 'orders_no', 'd_sap_no']]
        df['d_sap_no'] = df['d_sap_no'].astype(str)
        df = df[df['d_sap_no'].str[:2] == 'CK']
        df = df.sort_values(by='orders_id')
        write_to_mysql(df, headers)


def write_to_mysql(df, headers):
    """
    不存在的就打印
    """
    DB_CONFIG = {
        'host': '113.45.176.129',
        'port': 3306,
        'user': 'fsbbr_data',
        'password': 'n3Mepj4JD4JxWCJM',
        'database': 'fsbbr_data',
        'charset': 'utf8mb4'
    }

    # 过滤需要的字段（确保和数据表字段对应）
    df = df[['orders_id', 'orders_no', 'd_sap_no']].copy()

    # 1. 连接数据库
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()
    # 2. 遍历 DataFrame 逐行处理
    for index, row in df.iterrows():
        # 获取当前行数据
        orders_id = row['orders_id']
        orders_no = row['orders_no']
        d_sap_no = row['d_sap_no']
        createdate = datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # 格式化时间

        # 3. 先查询该 orders_id 是否存在
        check_sql = "SELECT 1 FROM dayin_orders WHERE orders_id = %s LIMIT 1"
        cursor.execute(check_sql, (orders_id,))
        exists = cursor.fetchone()

        if exists:
            print(f"orders_id {orders_id} 已存在，跳过插入")
            continue
        # 打印操作！！！！！！！！！！！
        okkk = orders_view(orders_id, headers)
        if okkk:
            # 4. 不存在则执行插入
            insert_sql = """
                         INSERT INTO dayin_orders
                             (createdate, orders_id, orders_no, d_sap_no, wl_dayin)
                         VALUES (%s, %s, %s, %s, %s) \
                         """
            cursor.execute(insert_sql, (createdate, orders_id, orders_no, d_sap_no, None))
            # 5. 提交事务
            conn.commit()
            print("数据写入完成！")
        else:
            print("打印失败：" + str(orders_no))


if __name__ == '__main__':
    # 模式选择
    print("请选择运行模式：")
    print("1 - 普通模式（查询当天00:00:00开始的所有订单）")
    print("2 - 紧急模式（查询从当前时间开始的订单）")
    mode = input("请输入选项(1或2): ").strip()
    emergency_mode = (mode == "2")

    # 紧急模式下，固定起始时间戳为启动时的当前时间
    fixed_start_ts = None
    if emergency_mode:
        fixed_start_ts = int(datetime.now().replace(microsecond=0).timestamp() * 1000)
        start_time_str = datetime.fromtimestamp(fixed_start_ts / 1000).strftime('%Y-%m-%d %H:%M:%S')
        print(f"已选择紧急模式，将固定从 {start_time_str} 开始查询订单")
    else:
        print("已选择普通模式，将从当天00:00:00开始查询订单")

    while True:
        time.sleep(5)
        try:
            get_dd(emergency_mode=emergency_mode, fixed_start_ts=fixed_start_ts)
        except Exception as e:
            print(e)


