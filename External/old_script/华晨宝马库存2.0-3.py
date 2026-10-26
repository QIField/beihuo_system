import numpy as np
import requests
import pandas as pd
import json
import time
import datetime
import re
import sys
import random
import pymysql
import winreg
import tkinter as tk
from tkinter import filedialog
import js2py
from lxml import etree
from openpyxl import load_workbook
import urllib3
urllib3.disable_warnings()


def start(OE):
    global cookie
    today = datetime.datetime.today()
    today = str(today)[:10]
    url = "https://www.dwp.bmw-brilliance.cn/sap(bD16aCZjPTEwMA==)/bc/bsp/bmw/gis_tp_par_dev/spp05_stock_check.htm"
    payload = 'onInputProcessing=atp_all&contentClip=&req_date=' + today + '&material=' + OE + '&x=7&y=5'
    headers = {
        'Connection': 'keep-alive',
        'Cache-Control': 'max-age=0',
        'Authorization': 'Basic NDc5ODhQQVI6MldTWDNFREM0UkZWNVRHQg==',
        'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="99", "Google Chrome";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'Upgrade-Insecure-Requests': '1',
        'Origin': 'https://www.dwp.bmw-brilliance.cn',
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.74 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-User': '?1',
        'Sec-Fetch-Dest': 'frame',
        'Referer': 'https://www.dwp.bmw-brilliance.cn/sap(bD16aCZjPTEwMA==)/bc/bsp/bmw/gis_tp_par_dev/spp05_stock_check.htm',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Cookie': cookie
    }
    try:
        response = requests.request("POST", url, headers=headers, data=payload, verify=False)
        if '不存在或未激活' in response.text:
            time.sleep(3)
            print('未查询到：' + str(OE))
            return []
        bb = (str(str(response.text).split('<!-- Header  -->')[1]).split('<table  border="0" cellpadding="0" cellspacing="0">')[0])
    except:
        time.sleep(3)
        print('未查询到：' + str(OE))
        return []
    # print(bb)
    html = etree.HTML(bb)
    trs = html.xpath('/html/body/table/tr')
    OE_list = []
    name_list = []
    value_list = []
    bz_list = []
    for k, v in enumerate(trs):
        if k == 3:  # title
            titles = v.xpath('td')
            for k1, v1 in enumerate(titles):
                k_list = [0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 12, 13, 14, 16, 17, 18, 20, 21, 22, 24, 25, 26, 28, 29, 30, 32, 33, 34]
                if k1 in k_list:
                    name = v1.xpath('text()')
                elif k1 in [7, 11, 15, 19, 23, 27, 31]:
                    name = v1.xpath('b/i/text()')
                name = (str(name).replace('[', '').replace(']', '').replace(' ', '').replace('\\xa0', '').replace("','", '').replace("'", ''))
                name = name.replace('SY01', '-北京')
                name = name.replace('SY02', '-上海')
                name = name.replace('SY03', '-佛山')
                name = name.replace('SY06', '-成都')
                name = name.replace('SY07', '-沈阳')
                name = name.replace('SY08', '-合肥')
                name = name.replace('SY09', '-宁波')
                name_list.append(name)
                OE_list.append(OE)
        elif k == 4:  # values
            values = v.xpath('td')
            for k1, v1 in enumerate(values):
                if k1 == 0:
                    continue
                k_list = [1]
                oe = ''
                if k1 in k_list:
                    oe = v1.xpath('a/text()')
                    try:
                       oe = oe[0]
                       oe = str(oe).replace(' ', '')
                    except:
                        oe = ''
                    value_list.append(oe)
                    oe = v1.xpath('text()')
                    try:
                       oe = oe[0]
                       oe = str(oe).replace(' ', '')
                    except:
                        oe = ''
                    value_list.append(oe)
                    continue
                elif k1 in [2, 3, 4, 5, 6, 8, 9, 10, 12, 13, 14, 16, 17, 18, 20, 21, 22, 24, 25, 26, 28, 29, 30, 32, 33, 34]:
                    oe = v1.xpath('text()')
                elif k1 in [7, 11, 15, 19, 23, 27, 31]:
                    oe = [str(v1.xpath('a/@onmouseover')).replace(' ', '').replace("doTooltip(event,'可用库存overreorderpoint:", '').replace("')", '').replace('["', '').replace('"]', '')]
                try:
                    oe = oe[0]
                    oe = str(oe).replace(' ', '')
                except:
                    oe = ''
                if 'RMB' in oe:
                    oe = round(float(str(oe).replace('RMB', '').replace(',', '')) * 1.13, 2)
                value_list.append(oe)

        elif k == 5:
            values = v.xpath('td')
            for k1, v1 in enumerate(values):
                if k1 == 2:
                    bz_list.append(v1.xpath('text()'))
    if len(bz_list) == 0:
        bz_list.append('')

    df1 = pd.DataFrame({'OE': [OE],'备注': bz_list, name_list[0]:[value_list[0]], name_list[1]:[value_list[1]], name_list[2]:[value_list[2]]
                        , name_list[3]:[value_list[3]], name_list[4]:[value_list[4]], name_list[5]:[value_list[5]]
                        , name_list[6]:[value_list[6]], name_list[7]:[value_list[7]], name_list[8]:[value_list[8]]
                        , name_list[9]:[value_list[9]], name_list[10]:[value_list[10]], name_list[11]:[value_list[11]]
                        , name_list[12]:[value_list[12]], name_list[13]:[value_list[13]], name_list[14]:[value_list[14]]
                        , name_list[15]:[value_list[15]], name_list[16]:[value_list[16]], name_list[17]:[value_list[17]]
                        , name_list[18]:[value_list[18]], name_list[19]:[value_list[19]], name_list[20]:[value_list[20]]
                        , name_list[21]:[value_list[21]], name_list[22]:[value_list[22]], name_list[23]:[value_list[23]]
                        , name_list[24]:[value_list[24]], name_list[25]:[value_list[25]], name_list[26]:[value_list[26]]
                        , name_list[27]:[value_list[27]], name_list[28]:[value_list[28]], name_list[29]:[value_list[29]]
                        , name_list[30]:[value_list[30]], name_list[31]:[value_list[31]], name_list[32]:[value_list[32]]
                        , name_list[33]:[value_list[33]], name_list[34]:[value_list[34]]})
    return df1


def start2(OE):
    global cookie
    url = "https://www.dwp.bmw-brilliance.cn/sap(bD16aCZjPTEwMA==)/bc/bsp/bmw/gis_tp_par_dev/spp05_material_details.htm?if_material="+str(OE)
    payload = {}
    headers = {
        'Connection': 'keep-alive',
        'Authorization': 'Basic NDc5ODhQQVI6MldTWDNFREM0UkZWNVRHQg==',
        'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="99", "Google Chrome";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.74 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-User': '?1',
        'Sec-Fetch-Dest': 'frame',
        'Referer': 'https://www.dwp.bmw-brilliance.cn/sap(bD16aCZjPTEwMA==)/bc/bsp/bmw/gis_tp_par_dev/SPP05_Stock_RESULT.htm?sap-params=bGZfbWF0ZXJpYWw9MDAwMDAwMDMxMzM2NzYwOTQzJnJlcV9kYXRlPTIwMjItMDQtMzAmcmVxX3J1bGU9JmVycl9kYXRlPSZyZXN1bHRfZGlzcGxheT1YJmxmX3ZpZXdfYWx0cGFydHM9',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Cookie': cookie
    }
    response = requests.request("GET", url, headers=headers, data=payload, verify=False)
    html = etree.HTML(response.text)
    trs = html.xpath('/html/body/table[1]/tr/td[2]/table/tr')
    val_list = []
    for k, v in enumerate(trs):
        vv = v.xpath('td/text()')
        wq = ''
        for w in vv:
             wq = wq + str(w).replace(',', '').replace(" ", '').replace('\xa0', '').replace('\r\n', '') + ','
        val_list.append(str(wq[:-1]).replace(" ", '').replace('\\xa0', '').replace('\\r\\n', '').replace(':', ''))
    # print(val_list)
    ook_list = []
    for i in val_list:
        a = i.replace("'", '').replace('[', '').replace(']', '').split(',')
        if i == '新零件号':
            ook_list.append(['新零件号', ''])
        if len(a) > 1 and len(a[0]) > 0:
            ook_list.append(a)
    # print(ook_list)

    my_dict = {}
    for i in ook_list:
        aaa = i[0]
        if aaa in ['零售价', '经销商净值(Stock)', '经销商净值(Rush)']:
            if 'RMB' in i[1]:
                val = float(str(i[1]).replace('RMB', '').replace(',', '')) * 1.13
                my_dict[i[0]] = [round(val, 2)]
                continue
        my_dict[i[0]] = [i[1]]

    # print(my_dict)
    df2 = pd.DataFrame(my_dict)
    df2 = df2.rename(columns={'零售价': '4S含税售价', '经销商净值(Stock)': '4S含税进价'})
    return df2


def getOE():
    global cookie
    root = tk.Tk()
    root.withdraw()
    print("请选择Excel文件....")
    filepath = filedialog.askopenfilename()  # 获得选择好的文件
    print(filepath)
    data = pd.read_excel(filepath, converters={'OE': str})

    df_list = []
    df_list2 = []
    for k, v in enumerate(list(data['OE'])[36000:46000]):
        try:
            df1 = start(v)
        except:
            cookie = input('输入秘钥')
            continue
        if len(df1) > 0:
            df_list.append(df1)
            try:
                df2 = start2(v)
                df_list2.append(df2)
            except:
                print("由于连接方在一段时间后没有正确答复或连接的主机没有反应")
                continue
        print("第" + str(k + 1) + ' 个 ' + str(v) + ' 采集完成')
    df = pd.concat(df_list)

    tim = str(int(time.time()))
    writer = pd.ExcelWriter(get_desktop() + '\华晨宝马库存' + tim + '.xlsx')
    # 获取今天（现在时间）
    today = datetime.datetime.today()
    print(str(today)[:10])
    df['采集时间'] = str(today)[:19]

    mid = df['采集时间']  # 取备采集时间的值
    df.pop('采集时间')  # 删除备采集时间
    df.insert(0, '采集时间', mid)  # 插入采集时间列
    df = df.replace('[]', '')
    df.to_excel(writer, sheet_name='信息1', index=False, encoding='utf_8_sig')
    if len(df_list2) > 0:
        df2 = pd.concat(df_list2)
        df2['采集时间'] = str(today)[:19]
        df2 = df2[['采集时间', '零件','基本单元','族组','毛重','净重','体积','4S含税售价','经销商折扣(Stock)','经销商折扣(Rush)','4S含税进价','经销商净值(Rush)', '可用库存', '新零件号']]
        df2.to_excel(writer, sheet_name='信息2', index=False, encoding='utf_8_sig')
    df3 = df2[['零件', '4S含税进价', '可用库存']]
    df3 = df3.rename(columns={'零件': 'OE'})
    df = pd.merge(df, df3, left_on='OE', right_on='OE', how='left')
    writer.save()
    kk = input('是否把华晨宝马库存数据保存到数据库，是按 1')
    if int(kk) == 1:
        savedate(df)
        savedate2(df2)
    input("晨宝马库存查询完毕！已保存到桌面")


def savedate(df):
    df = df.replace(np.NaN, '')
    df = df.replace('[]', '')
    con_server = pymysql.connect(host='127.0.0.1', user='root', password='15699181808', db='ztbbr', port=3306)
    cur_server = con_server.cursor()
    # 编写插入数据的sql
    insert_sql = 'insert into `华晨宝马库存` values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)'

    # 执行sql  将pandas.DataFrame格式的数据，每一行转为元组tuple，所有数据以列表list输出
    df = df.apply(lambda x: tuple(x), axis=1).values.tolist()
    cur_server.executemany(insert_sql, df)
    # 提交事务
    con_server.commit()
    print('保存 华晨宝马库存数据成功...')


def savedate2(df):
    df = df[['采集时间', '零件','基本单元','族组','毛重','净重','体积','4S含税售价','经销商折扣(Stock)','经销商折扣(Rush)','4S含税进价','经销商净值(Rush)', '可用库存', '新零件号']]
    df = df.replace(np.NaN, '')
    df = df.replace('[]', '')
    con_server = pymysql.connect(host='127.0.0.1', user='root', password='15699181808', db='ztbbr', port=3306)
    cur_server = con_server.cursor()
    # 编写插入数据的sql
    insert_sql = 'insert into `bmw大库尺寸重量体积`(`采集时间`, `零件`,`基本单元`,`族组`,`毛重`,`净重`,`体积`,`4S含税售价`,`经销商折扣(Stock)`,`经销商折扣(Rush)`,`4S含税进价`,`经销商净值(Rush)`, `可用库存`, `新零件号`) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)'

    # 执行sql  将pandas.DataFrame格式的数据，每一行转为元组tuple，所有数据以列表list输出
    df = df.apply(lambda x: tuple(x), axis=1).values.tolist()
    cur_server.executemany(insert_sql, df)
    # 提交事务
    con_server.commit()
    print('保存 华晨宝马库存数据成功...')


def get_desktop():
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                         r'Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders')
    return winreg.QueryValueEx(key, "Desktop")[0]


if __name__ == '__main__':
    cookie ='sap-contextid=SID%3aANON%3apcqpdi46_CQP_46%3abbo2ItjCpkL7ZP0Qa5rHXUnqul9TMzz5nB5tqhVQ-NEW; TS0190948c=014e90d2cd939a5eadf13a300ee0b6a628615d9453b6499a10aa961f65a75942ccbf4ecbaa1bb28699f768a10276494fabcbdedd6742d377c430c2fa1a33b4df9b4371ac0a81a13ea27925b75af2aa9366f3857be1d2bca3758da2847e9b99be14e695ff33604fb3e7d86e42f161af85aa3989adf8fc54e5d0f5f921dc1c294f124ff2547b9549a84cf1b3b67dfec898f070ef1cafc14b9a4579cf3e1e7c6a405334c6d7a1eaf01e779cb45160d10e8e914b5c3607d1d60106d089a1c8b094022723316eef28c4a887592555d5fb89f45f7ea74d94092ccd8e3eab5ca71f51f14dd41fa7df39107687a891684b17305f6c56887358; sap-appcontext=c2FwLXNlc3Npb25pZD1TSUQlM2FBTk9OJTNhcGNxcGRpNDZfQ1FQXzQ2JTNhYmJvMnAydjZpcVFjVFdUVm1UT0xwSDJPZ3RkUk16em9uQjRFZ0ZkYi1BVFQ%3d; TS01d0dca4=014e90d2cdd7a6a52c157d505d022f80b4a3b3dea4b6499a10aa961f65a75942ccbf4ecbaa1bb28699f768a10276494fabcbdedd6742d377c430c2fa1a33b4df9b4371ac0a81a13ea27925b75af2aa9366f3857be1d2bca3758da2847e9b99be14e695ff33604fb3e7d86e42f161af85aa3989adf8fc54e5d0f5f921dc1c294f124ff2547b18b2f91b5f646846d7686342aafbe4719768d5bd200d59b160f38eebb9390929; SelectedMaterials=; Order_Selected_materials=; _qimei_uuid42=1991c0f1f091000dd09c5505067aa9f81ee3184806; _qimei_i_3=5cf845d4925301d89593fd395e8d75e6a5eaa5a416525585e1897a5f72c7216b67613e943989e283d4aa; _qimei_h38=c79cc6f2d09c5505067aa9f80200000f21991c; sap-usercontext=sap-client=100; BIGipServercqpcn.bmwbrill.cn_pool_8443=2379141898.64288.0000; MYSAPSSO2=AjQxMDMBABhDAE0AMAA3ADcAOQAwACAAIAAgACAAIAACAAYxADAAMAADABBDAFEAUAAgACAAIAAgACAABAAYMgAwADIANgAwADYAMAA1ADAAMQA1ADkABQAEAAAACAkAAjEA%2fwFXMIIBUwYJKoZIhvcNAQcCoIIBRDCCAUACAQExCzAJBgUrDgMCGgUAMAsGCSqGSIb3DQEHATGCAR8wggEbAgEBMG8wZDELMAkGA1UEBhMCREUxHDAaBgNVBAoTE1NBUCBUcnVzdCBDb21tdW5pdHkxEzARBgNVBAsTClNBUCBXZWIgQVMxFDASBgNVBAsTC0kwMDIwNDc0MjYxMQwwCgYDVQQDEwNDUVACByAVCQIJU1kwCQYFKw4DAhoFAKBdMBgGCSqGSIb3DQEJAzELBgkqhkiG9w0BBwEwHAYJKoZIhvcNAQkFMQ8XDTI2MDYwNTAxNTkxMFowIwYJKoZIhvcNAQkEMRYEFMtFmOugjonHN5eqUCVsUOTCNHu%2fMAkGByqGSM44BAMEMDAuAhUAy4qjddu3SzOdPoWfoXYcRjRuFr8CFQDkFJnSTRS%21kH0toJ%21vtB8RKQunAw%3d%3d; SAP_SESSIONID_CQP_100=OUrG_ffxbhqsi84nuwtKiyQCgKlgghHxk9EbCxCGLek%3d; lf_actionspage=spp05_order_create.htm%3foninputprocessing(update); ordtype_create=; date_create=; po_create=; sppbasket=; back_page=SPP05_ORDER_CREATE_FRAME.htm; TS016675fd=014e90d2cd363e04af588030c81fccebf065da130036175652515755ac3668b8f08ab838a03c099c2a8ce008c875541a0b4804e1af020a24516036c926ba83e50a7ca71cbb32a36f8d86031e9ad92db3afa92f598f222c0fe6878995092fc0e3ebc28b1e571800a5f071655d330a392638134f385376637a5c0d61199c43131f892f697dad7b0fcc9eeafe330ab383e0d9eecf0bbf7a4818b2afd38e6d3faf83d6be11da448701816c66c1bdc79e7e1af0c6dee3c3e71eeef2b2fea8920ad497801a0c6919eb7500e705fab7dfd1f80ba3bfd5c81cb3e3816fd6747e0fe238b9b6bc4bad090b4e800857fdf1fc050526d91ff4398b6c9994ae749f85ad043b13e66ef71528; _qimei_fingerprint=54550af90219e3b56fc9224203a3db6d; _qimei_i_1=43c44dd192530388c7c1fc645b8d20e5f2eea1f1145c52d3bdd920582493206c616361973980ebdd8595c0c4'
    getOE()
    # start2('36121116326')