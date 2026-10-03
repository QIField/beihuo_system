import json
import time
import requests
import winreg
import tkinter as tk
from tkinter import filedialog, simpledialog
import pandas as pd
import datetime
from lxml import etree
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities


def dologin():
    global myauthorization
    global mycookiestr
    global mydriver
    print("正在登录.....")
    chrome_options = Options()
    chrome_options.add_argument('--log-level=1')  # 忽略错误
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
    chrome_options.add_argument('--ignore-certificate-errors')  # 忽略证书错误
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--window-size=1920x1080")  # I added this
    prefs = {'profile.managed_default_content_settings.images': 2}  # 不加载图片
    chrome_options.add_experimental_option('prefs', prefs)
    chrome_options.add_experimental_option('w3c', False)

    caps = {
        'browserName': 'chrome',
        'loggingPrefs': {
            'browser': 'ALL',
            'driver': 'ALL',
            'performance': 'ALL',
        },
        'goog:chromeOptions': {
            'perfLoggingPrefs': {
                'enableNetwork': True,
            },
            'w3c': False,
        },
    }
    driver = webdriver.Chrome(desired_capabilities=caps, chrome_options=chrome_options)
    url = "https://e.etc-parts.com/#/login"
    driver.get(url)
    # driver.minimize_window()

    try:
        time.sleep(5)
        input_box = driver.find_element_by_xpath('//*[@placeholder="请输入手机号"]')
        input_box.send_keys('13316969123')
        input_box = driver.find_element_by_xpath('//*[@placeholder="请输入密码"]')
        input_box.send_keys('Aa123456')
        time.sleep(3)
        button = driver.find_element_by_xpath('//*[@class="el-button login-in el-button--primary"]')
        button.click()
        time.sleep(8)
    except Exception as e:
        driver.quit()
        print('重新登录....')
        dologin()
        return

    driver.get("https://e.etc-parts.com/#/order/order_quotation?code=A1662405817&codeType=OE&codeValue=140")
    time.sleep(8)
    logs = [json.loads(log['message'])['message'] for log in driver.get_log('performance')]
    for i in logs:
        method = i['method']
        if method == 'Network.requestWillBeSentExtraInfo':
            try:
                myauthorization = i['params']['headers']['authorization']
            except:
                pass
    listCookies = driver.get_cookies()
    cookie = [item["name"] + "=" + item["value"] for item in listCookies]
    cookiestr = '; '.join(item for item in cookie)
    print("登录成功！")
    mycookiestr = cookiestr
    mydriver = driver


# def login():
#     global authorization
#     url = "https://gateway.etc-parts.com/web-emall/account/anon/login"
#     payload = "{\"loginName\":\"15367473628\",\"password\":\"PvEm6uyI04hlOOGj4Rrxdaw6bp0jLOYh2HQjmCQtvFcvWQyslxcpiy5J4HP0vroTvkGQzRvW9MeYvjbkz/AyNHuuhDlfyaLvVwQ6oYKaEhZLUQXbKBoBlqjHA2xW7bQ81K4YDjG4l3cGEurl2NVh8PzTVM7L7wGVhPecSyQytFQ=\",\"captcha\":\"\",\"checkKey\":\"\"}"
#     headers = {
#       'authority': 'gateway.etc-parts.com',
#       'accept': 'application/json, text/plain, */*',
#       'accept-language': 'zh-CN,zh;q=0.9',
#       'content-type': 'application/json;charset=UTF-8',
#       'isprompt': 'true',
#       'origin': 'https://e.etc-parts.com',
#       'referer': 'https://e.etc-parts.com/',
#       'sec-ch-ua': '"Google Chrome";v="111", "Not(A:Brand";v="8", "Chromium";v="111"',
#       'sec-ch-ua-mobile': '?0',
#       'sec-ch-ua-platform': '"Windows"',
#       'sec-fetch-dest': 'empty',
#       'sec-fetch-mode': 'cors',
#       'sec-fetch-site': 'same-site',
#       'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36',
#       'x-auth-sign': '210b93924a614a95a44c54ceed04da04',
#       'x-page-code': 'undefined',
#       'x-page-url': '/login',
#       'x-request-id': 'a487884c5a69e54b975b03b5b1d1eb0e',
#       'x-uid': ''
#     }
#     response = requests.request("POST", url, headers=headers, data=payload)
#     res = json.loads(response.text)
#
#     authorization = res['data']['authorization']


def search(OE):
    global myauthorization
    url = "https://gateway.etc-parts.com/web-emall/advanced/search"
    payload = "{\"ids\":[\""+str(OE)+"\"],\"type\":\"OE\",\"pageNum\":1,\"pageSize\":50}"
    headers = {
        'authority': 'gateway.etc-parts.com',
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'zh-CN,zh;q=0.9',
        'authorization': myauthorization,
        'content-type': 'application/json;charset=UTF-8',
        'isprompt': 'false',
        'origin': 'https://e.etc-parts.com',
        'referer': 'https://e.etc-parts.com/',
        'sec-ch-ua': '"Google Chrome";v="111", "Not(A:Brand";v="8", "Chromium";v="111"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36',
        'x-auth-sign': '1b301e8915e4d6cdcb6c053b8576a32b',
        'x-page-code': 'M1571312351599A3WYJQ',
        'x-page-url': '/search/search_advanced',
        'x-request-id': '42aa955b5aae354bb0587685cc99353a',
        'x-uid': '789875573647347712'
    }

    response = requests.request("POST", url, headers=headers, data=payload)
    re_js = json.loads(response.text)
    vehicleSeriesCode = re_js['data']['list']['list'][0]['vehicleSeriesCode']

    return vehicleSeriesCode


def queryChecked():
    global dyoe_list
    global dypph_df_list
    global tzmx_df_list
    global myauthorization
    global mycookiestr
    global mydriver
    root = tk.Tk()
    root.withdraw()
    codeValue = simpledialog.askstring('品牌选择', '请输入品牌代码：\n130.宝马\n140.奔驰')
    if not codeValue:
        print('未选择品牌，退出程序')
        return
    print("请选择Excel文件....")
    filepath = filedialog.askopenfilename()  # 获得选择好的文件
    print(filepath)
    oe_list = pd.read_excel(filepath, converters={'OE': str})
    oe_list = list(oe_list['OE'])
    myoe_list = []
    numberType_list = []  # 编号类型
    skuCode_list = []  # ETC/OE/品牌件编号
    skuName_list = []  # 名称
    applyCarType_list = []  # 适用车系
    brandName_list = []  # 品牌
    unitPrice_list = []  # 含税单价
    orderMin_list = []  # 最小起订量
    packageMin_list = []  # 最小包装量
    hasActualInventory_list = []  # 库存
    cur_date_list = []
    ppjh_list = []

    dologin()
    cur_date = str(datetime.datetime.now())[:19]
    if str(codeValue) == '130':
        for k, oe in enumerate(oe_list):
            url = "https://gateway.etc-parts.com/web-emall/demandBasket/queryChecked?pageSize=20&pageNum=1&code="+str(oe)+"&codeType=OE&codeValue=130"
            payload = {}
            headers = {
                'authority': 'gateway.etc-parts.com',
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'zh-CN,zh;q=0.9',
                'authorization': myauthorization,
                'isprompt': 'false',
                'origin': 'https://e.etc-parts.com',
                'referer': 'https://e.etc-parts.com/',
                'sec-ch-ua': '"Google Chrome";v="111", "Not(A:Brand";v="8", "Chromium";v="111"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-site',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36',
                'x-page-code': 'M1571312315868XRFBX',
                'x-page-url': '/order/order_quotation',
                'x-request-id': 'ba341000664c86423d6a9b361ab9e02d',
                'x-uid': '789875573647347712'
            }
            try:
                response = requests.request("GET", url, headers=headers, data=payload)
            except:
                print(' Max retries exceeded with ')
                continue
            if '用户未登录' in response.text:
                dologin()
                print('掉线。。。。已重新登录！！！！')
                print('掉线。。。。已重新登录！！！！')
                print('掉线。。。。已重新登录！！！！')
                continue
            res = json.loads(response.text)
            quotePartResDTOList = res['data']['list'][0]['quotePartResDTOList']
            for k111, v in enumerate(quotePartResDTOList):
                try:
                    ppjh = getdyoeh_dyppjh_tzmx(v['id'], oe)
                except:
                    ppjh = ''
                ppjh_list.append(ppjh)
                numberType = v['numberType']  # 编号类型
                skuCode = v['skuCode']  # ETC/OE/品牌件编号
                skuName = v['skuName']  # 名称
                applyCarType = v['applyCarType']  # 适用车系
                brandName = v['brandName']  # 品牌
                unitPrice = v['unitPrice']  # 含税单价
                orderMin = v['orderMin']  # 最小起订量
                packageMin = v['packageMin']  # 最小包装量
                hasActualInventory = str(v['hasActualInventory'])  # 库存
                if hasActualInventory == 'True':
                    hasActualInventory = '有'
                else:
                    hasActualInventory = '无'

                cur_date_list.append(cur_date)
                myoe_list.append(oe)
                numberType_list.append(numberType)  # 编号类型
                skuCode_list.append(skuCode)  # ETC/OE/品牌件编号
                skuName_list.append(skuName)  # 名称
                applyCarType_list.append(applyCarType)  # 适用车系
                brandName_list.append(brandName)  # 品牌
                unitPrice_list.append(unitPrice)  # 含税单价
                orderMin_list.append(orderMin)  # 最小起订量
                packageMin_list.append(packageMin)  # 最小包装量
                hasActualInventory_list.append(hasActualInventory)  # 库存

                print(str(k) + ' ' + str(oe) + ' ---> ' + str(v))
                current_handle = mydriver.current_window_handle
                all_handles = mydriver.window_handles
                for handle in all_handles:
                    if handle != current_handle:
                        mydriver.switch_to.window(handle)
                        mydriver.close()

                mydriver.switch_to.window(current_handle)

    else:
        for k, oe in enumerate(oe_list):
            if str(oe)[:1] != 'A':
                oe = 'A' + oe
            url = "https://gateway.etc-parts.com/web-emall/demandBasket/queryChecked?pageSize=20&pageNum=1&code="+str(oe)+"&codeType=OE&codeValue=140"
            payload = {}
            headers = {
                'authority': 'gateway.etc-parts.com',
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'zh-CN,zh;q=0.9',
                'authorization': myauthorization,
                'isprompt': 'false',
                'origin': 'https://e.etc-parts.com',
                'referer': 'https://e.etc-parts.com/',
                'sec-ch-ua': '"Google Chrome";v="111", "Not(A:Brand";v="8", "Chromium";v="111"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-site',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36',
                'x-page-code': 'M1571312315868XRFBX',
                'x-page-url': '/order/order_quotation',
                'x-request-id': '72be35454525244e03481e6479655f26',
                'x-uid': '789875573647347712'
            }
            try:
                response = requests.request("GET", url, headers=headers, data=payload)
            except:
                print(' Max retries exceeded with ')
                continue
            if '用户未登录' in response.text:
                dologin()
                print('掉线。。。。已重新登录！！！！')
                print('掉线。。。。已重新登录！！！！')
                print('掉线。。。。已重新登录！！！！')
                continue
            res = json.loads(response.text)
            quotePartResDTOList = res['data']['list'][0]['quotePartResDTOList']
            for k111, v in enumerate(quotePartResDTOList):
                try:
                    ppjh = getdyoeh_dyppjh_tzmx(v['id'], oe)
                except:
                    ppjh = ''
                ppjh_list.append(ppjh)
                numberType = v['numberType']  # 编号类型
                skuCode = v['skuCode']  # ETC/OE/品牌件编号
                skuName = v['skuName']  # 名称
                applyCarType = v['applyCarType']  # 适用车系
                brandName = v['brandName']  # 品牌
                unitPrice = v['unitPrice']  # 含税单价
                orderMin = v['orderMin']  # 最小起订量
                packageMin = v['packageMin']  # 最小包装量
                hasActualInventory = str(v['hasActualInventory'])  # 库存
                if hasActualInventory == 'True':
                    hasActualInventory = '有'
                else:
                    hasActualInventory = '无'

                cur_date_list.append(cur_date)
                myoe_list.append(oe)
                numberType_list.append(numberType)  # 编号类型
                skuCode_list.append(skuCode)  # ETC/OE/品牌件编号
                skuName_list.append(skuName)  # 名称
                applyCarType_list.append(applyCarType)  # 适用车系
                brandName_list.append(brandName)  # 品牌
                unitPrice_list.append(unitPrice)  # 含税单价
                orderMin_list.append(orderMin)  # 最小起订量
                packageMin_list.append(packageMin)  # 最小包装量
                hasActualInventory_list.append(hasActualInventory)  # 库存

                print(str(k) + ' ' + str(oe) + ' ---> ' + str(v))
                current_handle = mydriver.current_window_handle
                all_handles = mydriver.window_handles
                for handle in all_handles:
                    if handle != current_handle:
                        mydriver.switch_to.window(handle)
                        mydriver.close()

                mydriver.switch_to.window(current_handle)

    df = pd.DataFrame({'采集时间': cur_date_list, 'OE': myoe_list, '编号类型': numberType_list, 'ETC/OE/品牌件编号': skuCode_list,
                       '名称': skuName_list, '适用车系': applyCarType_list,'品牌': brandName_list, '含税单价': unitPrice_list,
                       '最小起订量': orderMin_list, '最小包装量': packageMin_list, '库存': hasActualInventory_list, '品牌件号': ppjh_list})
    if len(dyoe_list) >0:
        df1 = pd.concat(dyoe_list)
    else:
        df1 = pd.DataFrame()
    # if len(dypph_df_list) > 0:
    #     df2 = pd.concat(dypph_df_list)
    # else:
    #     df2 = pd.DataFrame()

    if len(tzmx_df_list) > 0:
        df3 = pd.concat(tzmx_df_list)
    else:
        df3 = pd.DataFrame()

    t = str(int(time.time()))
    writer = pd.ExcelWriter(get_desktop() + '\一体系'+t+'.xlsx')
    df.to_excel(writer, index=False, sheet_name='报价列表', encoding='utf_8_sig')
    df1.to_excel(writer, index=False, sheet_name='对应OE', encoding='utf_8_sig')
    # df2.to_excel(writer, index=False, sheet_name='对应品牌号', encoding='utf_8_sig')
    df3.to_excel(writer, index=False, sheet_name='套装明细', encoding='utf_8_sig')
    writer.save()


def getdyoeh_dyppjh_tzmx(id, oe):
    global myauthorization
    global mycookiestr
    global mydriver
    # mydriver.get("https://e.etc-parts.com/#/search/search_advanced/" + str(id))
    url = "https://e.etc-parts.com/#/search/search_advanced/" + str(id)
    mydriver.execute_script("window.open('"+url+"', '"+str(id)+"')")

    latest_handle = mydriver.window_handles[-1]
    mydriver.switch_to.window(latest_handle)
    time.sleep(5)
    logdata = mydriver.get_log('performance')
    for k, v in enumerate(logdata):
        message = json.loads(v['message'])

        try:
            path = message['message']['params']['headers'][':path']
            headers = message['message']['params']['headers']
            if path == '/web-emall/advanced/search/goods/detail/tab' or path == '/web-emall/advanced/search/goods/detail/main':
                sign = message['message']['params']['headers']['x-auth-sign']
                ppjh = tab(id, sign, myauthorization, oe)
                return ppjh
        except:
            pass


def tab(id, sign, myauthorization, oe):
    global dyoe_list
    global dypph_df_list
    global tzmx_df_list
    url = "https://gateway.etc-parts.com/web-emall/advanced/search/goods/detail/tab"
    payload = "{\"id\":\"yryr\"}"
    payload = payload.replace('yryr', str(id))
    headers = {
        'authority': 'gateway.etc-parts.com',
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'zh-CN,zh;q=0.9',
        'authorization': myauthorization,
        'content-type': 'application/json;charset=UTF-8',
        'isprompt': 'false',
        'origin': 'https://e.etc-parts.com',
        'referer': 'https://e.etc-parts.com/',
        'sec-ch-ua': '"Not/A)Brand";v="99", "Google Chrome";v="115", "Chromium";v="115"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
        'x-auth-sign': sign,
        'x-page-code': 'M15713123811533KEVI',
        'x-page-url': '/search/search_advanced/866709390265552910',
        'x-request-id': '87618f731052e14ade1ae4917502be0b',
        'x-uid': '789875573647347712'
    }

    response = requests.request("POST", url, headers=headers, data=payload)
    re_js = json.loads(response.text)
    exchangeOE = re_js['data']['exchangeOE']
    dyoe_df = pd.DataFrame(exchangeOE)
    if len(dyoe_df) > 0:
        dyoe_df.insert(0, 'OE', oe)
        dyoe_df = dyoe_df.rename(columns={'vehicleBrandName': '品牌', 'oe': 'OE号', 'vehicleBrandNameEn': '品牌代码', 'oeToPartBrandRemark': '备注'})
        dyoe_list.append(dyoe_df)

    exchangePartBrand = re_js['data']['exchangePartBrand']
    ppjh = ''
    for k, v in enumerate(exchangePartBrand):
        ppjh = ppjh + str(v['partBrandBrandNameEtc']) + '：' + str(v['partBrandCode']) + ','

    # dypph_df = pd.DataFrame(exchangePartBrand)
    # if len(dypph_df) > 0:
    #     dypph_df.insert(0, 'OE', oe)
    #     dypph_df = dypph_df.rename(columns={'partBrandBrandNameEtc': '品牌', 'partBrandCode': '品牌件号', 'OE': 'OE'})
    #     dypph_df_list.append(dypph_df)

    packageDetailsList = re_js['data']['packageDetailsList']
    tzmx_df = pd.DataFrame(packageDetailsList)
    if len(tzmx_df) > 0:
        tzmx_df.insert(0, 'OE', oe)
        tzmx_df = tzmx_df.rename(columns={'partBrandBrandNameEtc': '品牌', 'partBrandNumber': '套装号', 'childPartBrandNumber': '单品号',
                                          'childPartBrandName': '单品名称', 'childQty': '数量', 'oe': '单品适配OE'})
        tzmx_df_list.append(tzmx_df)
    return ppjh[:-1]


def get_desktop():
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                         r'Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders')
    return winreg.QueryValueEx(key, "Desktop")[0]


if __name__ == '__main__':
    dyoe_list = []
    dypph_df_list = []
    tzmx_df_list = []
    myauthorization = ''
    mycookiestr = ''
    mydriver = ''
    authorization = ''
    queryChecked()
    mydriver.quit()