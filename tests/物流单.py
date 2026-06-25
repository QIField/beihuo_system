import json
from datetime import datetime, time
import time as t
import requests
import qrcode
import base64
from io import BytesIO
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from playwright.sync_api import sync_playwright
import os
import pymysql


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


cookies, headers = get_crm_cookies()


def generate_fixed_width_pdf(html_path, output_path, width_px=300):
    """生成固定宽度的 PDF（390px）"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 设置视口宽度为 390px（高度自动）
        page.set_viewport_size({
            "width": width_px,
            "height": 300  # 初始高度（足够显示内容）
        })

        # 加载 HTML 文件
        page.goto(f'file://{os.path.abspath(html_path)}')

        # 获取实际内容高度（动态调整视口）
        content_height = page.evaluate("document.body.scrollHeight")
        page.set_viewport_size({
            "width": width_px,
            "height": 300  # 增加 10% 留白
        })

        # 生成 PDF（关键参数）
        page.pdf(
            path=output_path,
            width=f"{width_px}px",  # 固定宽度
            height="300px",  # 高度自适应
            margin={
                "top": "0px",
                "bottom": "0px",
                "left": "0px",
                "right": "0px"
            },
            print_background=True,  # 保留背景色
            scale=1.0,  # 100% 缩放
            page_ranges="1",  # 仅第一页
            # omit_background=True  # 隐藏默认背景
        )

        browser.close()


def generate_qrcode(data):
    """生成二维码并返回 base64 编码"""
    qr = qrcode.make(data)
    buffer = BytesIO()
    qr.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode('utf-8')


def render_template(template_path, context):
    """渲染 Jinja2 模板"""
    template_dir = Path(template_path).parent
    template_name = Path(template_path).name

    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=True
    )

    template = env.get_template(template_name)
    return template.render(context)


def generate_label_pdf(data):
    print('生成pdf')
    """生成带动态数据的 PDF（包含二维码）"""
    # 1. 生成二维码
    if "orders_no" in data:
        qrcode_base64 = generate_qrcode(data["orders_no"])
        data["qrcode_data"] = qrcode_base64

    # 2. 渲染模板
    html_content = render_template("1.html", data)

    # 3. 保存为临时 HTML 文件
    with open("temp_label.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    # 4. 生成 PDF
    generate_fixed_width_pdf("temp_label.html", f"wl_pdf/{data['barcode_data']}.pdf")
    return f"wl_pdf/{data['barcode_data']}.pdf"


def get_label_data(ddm, did):
    print('获取物流信息')
    params = {
        'delivery_id': did,
    }

    response = requests.get('https://crm.gzbbr.com/api/Wms.Logistics/view', params=params, cookies=cookies,
                            headers=headers).json()['data']
    response['barcode_data'] = ddm
    orders_no = get_orders_no(did)
    response['orders_no'] = orders_no
    if not response['pack_send_num']:
        response['pack_send_num'] = 1
    for c in response.keys():
        if not response[c]:
            response[c] = ''
    return response


def get_today_timestamps():
    # 获取今天的日期
    today = datetime.now().date()

    # 今日 00:00:00
    start_of_day = datetime.combine(today, time(0, 0, 0))

    # 今日 23:59:59
    end_of_day = datetime.combine(today, time(23, 59, 59))

    # 转换为毫秒时间戳
    start_timestamp = int(start_of_day.timestamp() * 1000)
    end_timestamp = int(end_of_day.timestamp() * 1000)

    return start_timestamp, end_timestamp


def get_did(orid):
    print('获取打包单')
    params = {
        'orders_id': orid,
        'page': '1',
        'limit': '50',
    }
    cookies, headers = get_crm_cookies()
    response = requests.get('https://crm.gzbbr.com/api/Crm.Orders/orders_view', params=params, cookies=cookies,
                            headers=headers).json()['data']
    logistics_name = response['TableHeader']['logistics_name']
    if logistics_name == None:
        return 123456789

    return response['delivery_id']


def get_dds11(tt):
    print('获取订单')
    start_timestamp, end_timestamp = get_today_timestamps()
    dds = []
    page = 1
    page_max = 1
    date = t.strftime('%Y%m%d')
    try:
        with open(f'wl_rz/{date}.json', 'r', encoding='utf-8') as f:
            rz = json.load(f)
    except FileNotFoundError:
        rz ={}
    while page <= page_max:
        print(page)
        response = requests.get(
            f'https://crm.gzbbr.com/api/Crm.Orders/mergeOrderList?page=1&limit=200&create_date[]={start_timestamp}&create_date[]={end_timestamp}&status=1&order_type_id=1&is_wms=1',
            cookies=cookies,
            headers=headers,
        ).json()['data']
        # print(response)
        page_max = response['list']['last_page']
        for i in response['list']['data']:
            if i['create_date'] > tt and i['logistics_name'] and i['d_sap_no'] not in rz.keys():
                dds.append([
                    i['d_sap_no'],i['orders_id']
                ])
        page += 1
    return dds


def get_dds(tt):
    DB_CONFIG = {
        'host': '113.45.176.129',
        'port': 3306,
        'user': 'fsbbr_data',
        'password': 'wRCA8AGn3a568f4X',
        'database': 'fsbbr_data',
        'charset': 'utf8mb4'
    }
    # 初始化存储结果的列表
    dds = []
    conn = None
    cursor = None

    try:
        # 1. 建立数据库连接
        conn = pymysql.connect(**DB_CONFIG)
        # 使用 DictCursor，查询结果会以字典形式返回（方便按字段名取值）
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # 2. 执行查询：筛选 wl_dayin 为 NULL 的数据
        query_sql = """
                    SELECT d_sap_no, orders_id
                    FROM dayin_orders
                    WHERE wl_dayin IS NULL or wl_dayin = ''
                    """
        cursor.execute(query_sql)

        # 3. 获取所有查询结果
        results = cursor.fetchall()

        # 4. 整理数据到 dds 列表
        for i in results:
            # 按 [d_sap_no, orders_id] 格式添加
            dds.append([i['d_sap_no'], i['orders_id']])

        # 提取所有需要更新的 orders_id
        orders_ids = [item[1] for item in dds]
        print(f"共查询到 {len(orders_ids)} 条需要更新的数据，orders_id 列表：{orders_ids}")

        # -------------------------- 第二步：批量更新 wl_dayin 为 "已获取" --------------------------
        # 构造批量更新的 SQL（使用 IN 语句，效率更高）
        # 注意：用 %s 占位符，避免 SQL 注入
        placeholders = ', '.join(['%s'] * len(orders_ids))
        update_sql = f"""
                    UPDATE dayin_orders 
                    SET wl_dayin = '已获取' 
                    WHERE orders_id IN ({placeholders})
                """

        # 执行更新
        affected_rows = cursor.execute(update_sql, orders_ids)
        conn.commit()

        print(f"更新完成！共修改 {affected_rows} 条数据")

    except Exception as e:
        print(f"查询数据出错：{str(e)}")
    finally:
        # 5. 关闭游标和连接
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return dds


def get_orders_no(did):
    print('获取打包单号')
    params = {
        'delivery_id': did,
        'page': '1',
        'limit': '20',
    }

    response = requests.get('https://crm.gzbbr.com/api/Crm.Delivery/deliveryView', params=params, cookies=cookies,
                            headers=headers).json()['data']['TableHeader']['orders_no']
    return response


def print_file_windows(file_path):
    try:
        file_path = 'C:\\Users\Administrator\Desktop\weixin\\' + file_path
        if file_path == r'C:\Users\Administrator\Desktop\weixin\wl_pdf/.pdf':
            return
        os.startfile(file_path, "print")


        print(f"文件 {file_path} 已发送到打印机")
        t.sleep(1)
        return True
    except Exception as e:
        print(f"打印失败: {e}")
        return False


def get_rz(ddm):
    date = t.strftime('%Y%m%d')
    try:
        with open(f'wl_rz/{date}.json', 'r', encoding='utf-8') as f:
            rz = json.load(f)
    except FileNotFoundError:
        rz = {}
    rz[ddm] = t.strftime('%Y%m%d %H:%M:%S')
    with open(f'wl_rz/{date}.json', 'w', encoding='utf-8') as f:
        json.dump(rz, f, ensure_ascii=False, indent=4)


def get_orid(ddm):
    print('查找',ddm)
    cookies, headers = get_crm_cookies()
    start_timestamp, end_timestamp = get_today_timestamps()
    response = requests.get(
        f'https://crm.gzbbr.com/api/Crm.Orders/mergeOrderList?page=1&limit=200&create_date[]={start_timestamp}&create_date[]={end_timestamp}&orders_no={ddm}',
        cookies=cookies,
        headers=headers,
    ).json()
    print(response)
    response = response['data']['list']['data']
    if len(response) > 0:
        return response[0]['orders_id']
    else:
        return None


def aaa(ddm,orid):
    if os.path.exists(f'/wl_pdf\\{ddm}.pdf'):
        pdf = f'wl_pdf\\{ddm}.pdf'
    else:
        did = get_did(orid)
        if did == 123456789:
            return None

        dd_data = get_label_data(ddm, did)
        pdf = generate_label_pdf(dd_data)
    if print_file_windows(pdf):
        get_rz(ddm)
        return ddm
    else:
        return None


if __name__ == "__main__":
    tt = int(t.time())

    while True:
        try:
            cookies, headers = get_crm_cookies()
            current_time = datetime.now()
            hour = current_time.hour  # 当前小时（0-23，24小时制）
            if hour <= 5:
                cookies, headers = get_crm_cookies()
                t.sleep(60*60*1)

            dds = get_dds(tt)
            if not dds:
                print('未获取到新订单')
                print(datetime.now())
                t.sleep(5)
                continue

            for x in dds:
                did = get_did(x[1])
                if did == 123456789:
                    print("自提。。。。。。。。。。。。。")
                    continue

                dd_data = get_label_data(x[0], did)
                wl_pdf = generate_label_pdf(dd_data)
                if print_file_windows(wl_pdf):
                    get_rz(x[0])
            t.sleep(5)

        except Exception as e:
            print(e)
            continue


