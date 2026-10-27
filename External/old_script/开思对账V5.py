# coding:utf-8
import datetime
import numpy as np
import pandas as pd
import time
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
import pyautogui
import pyperclip


def dologin(skd_date):
    chrome_options = Options()
    chrome_options.add_argument('--log-level=1')  # 忽略错误
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
    chrome_options.add_argument('--ignore-certificate-errors')  # 忽略证书错误
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--window-size=1920x1080")  # I added this
    chrome_options.add_experimental_option('w3c', False)
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

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

    url = "http://erp.gzbbr.com/K3Cloud/"
    driver.get(url)

    time.sleep(3)
    input_box = driver.find_element_by_xpath('//*[@id="user"]')
    input_box.send_keys('张锐')
    input_box = driver.find_element_by_xpath('//*[@id="password"]')
    input_box.send_keys('ABC1234.')
    time.sleep(2)
    button = driver.find_element_by_xpath('//*[@id="btnLogin"]')
    button.click()

    try:
        time.sleep(3)
        # pyautogui.click(x=1762, y=335)  # abcd关闭提示你保存密码
        pyautogui.click(x=3606, y=502)  # 关闭提示你保存密码
        time.sleep(8)
        button = driver.find_element_by_xpath('//*[@id="FSEARCH"]/..')
        button.click()
        time.sleep(3)
        input_box = driver.find_element_by_xpath('//*[@id="FSEARCH"]/span[1]/span/input')
        input_box.send_keys('应收单列表')
    except:
        button = driver.find_element_by_xpath('//*[@id="FSEARCH"]/..')
        button.click()
        time.sleep(3)
        input_box = driver.find_element_by_xpath('//*[@id="FSEARCH"]/span[1]/span/input')
        input_box.send_keys('应收单列表')

    time.sleep(2)
    input_box.click()
    time.sleep(2)
    input_box.send_keys(Keys.ENTER)
    time.sleep(3)
    input_box = driver.find_elements_by_xpath("//input[contains(@title, '客户')]")[0]
    input_box.click()
    time.sleep(3)
    input_box.send_keys('.客户编码')
    input_box.send_keys(Keys.ENTER)
    time.sleep(3)
    # 以上是初始化++++++++++++++++++++++

    df = pd.read_excel("开思对账-模板.xlsx", converters={"平台已结算金额（¥）": float})
    df['平台已结算金额（¥）'] = df['平台已结算金额（¥）'].replace('#N/A', 0).replace(np.nan, 0)
    wxcbm_list = list(set(list(df['客户代码'])))
    wxcbm_list.sort()

    zx_logs_list = []
    for k, wxcbm in enumerate(wxcbm_list):
        try:
            zx_logs = k3_main_process(df, wxcbm, driver, skd_date)
            zx_logs_list.append(zx_logs)
        except Exception as e:
            time.sleep(5)
            print('发生异常：' + str(e))

    df11 = pd.DataFrame(zx_logs_list)
    df11 = df11.rename(columns={'wxcbm': '客户代码', 'cur_kehu_je': '小计(¥)', 'cur_ksq_je': '开思劵金额(¥)',
                                'cur_jd_je': '总计(¥)=等于金蝶的开单金额', 'cur_label': '对账类型', 'ss_ysd_res': '查询结果',
                                'jd_sf_yz': '备注', 'yjs_je': '合计-已收款金额', 'cz_type': '本次收款类型',
                                'dis_res': '执行结果'})

    df11['操作时间'] = str(datetime.datetime.now())
    current_datetime = datetime.now().strftime("%Y-%m-%d %H%M")
    df11.to_excel( f"{current_datetime}操作结果.xlsx", index=False)


def k3_main_process(df, wxcbm, driver, skd_date):
    """
    :param df:
    :param wxcbm: 客户代码
    :param driver:
    :param skd_date:收款单业务日期
    :return:
    """
    # abcd
    # pyautogui.click(x=1000, y=271)
    # time.sleep(1)
    # pyautogui.click(x=1000, y=271)
    # time.sleep(1)

    pyautogui.click(x=1395, y=406)
    time.sleep(1)
    pyautogui.click(x=1395, y=406)
    time.sleep(1)

    cur_df = df[df['客户代码'] == wxcbm]
    cur_kehu_je = sum(list(cur_df['求和项:小计(¥)']))
    cur_ksq_je = sum(list(cur_df['求和项:开思劵金额(¥)']))
    cur_jd_je = sum(list(cur_df['求和项:总计(¥)=等于金蝶的开单金额']))

    cur_yjs_je = sum(list(cur_df['平台已结算金额（¥）']))
    cur_kp_zt = list(cur_df['开票状态'])[0]

    # 判断 平台已结算金额 = （小计 | 开思劵金额 | 等于金蝶的开单金额）
    cur_label = ''
    if cur_yjs_je == cur_jd_je:
        cur_label = '平台已结算金额 = 等于金蝶的开单金额'
    elif cur_yjs_je == cur_ksq_je:
        cur_label = '平台已结算金额 = 开思劵金额'
    elif cur_yjs_je == cur_kehu_je:
        cur_label = '平台已结算金额 = 小计'
    else:
        cur_label = '平台已结算金额 != （小计 | 开思劵金额 | 等于金蝶的开单金额）'
        print('客户代码：' + wxcbm + ' ' + f'平台已结算金额({cur_yjs_je}) != 小计({cur_kehu_je}) | 开思劵金额({cur_ksq_je}) | 等于金蝶的开单金额({cur_jd_je})')
        res = {'wxcbm': wxcbm, 'cur_kehu_je': cur_kehu_je, 'cur_ksq_je': cur_ksq_je, 'cur_jd_je': cur_jd_je,
               'cur_label': cur_label, 'ss_ysd_res' : '', 'jd_sf_yz': '', 'yjs_je': '', 'cz_type': '', 'dis_res': ''}
        return res


    pyperclip.copy(wxcbm)
    pyautogui.hotkey('ctrl', 'a')
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(2)
    pyautogui.press('enter')
    time.sleep(10)

    try:
        # 合计-价税合计
        FALLAMOUNTFOR = driver.find_elements_by_xpath("//div[contains(@data-field, 'FALLAMOUNTFOR')]")
        texts1 = [element.text for element in FALLAMOUNTFOR][0]
        texts1 = float(str(texts1).replace(',', ''))
    except:
        res = {'wxcbm': wxcbm, 'cur_kehu_je': cur_kehu_je, 'cur_ksq_je': cur_ksq_je, 'cur_jd_je': cur_jd_je,
               'cur_label': cur_label, 'ss_ysd_res' : '应收单查询没记录', 'jd_sf_yz': '', 'yjs_je': '', 'cz_type': '', 'dis_res': ''}
        return res

    # 合计-客户名称
    FCUSTOMERID_FNAME = driver.find_elements_by_xpath("//span[contains(@data-field, 'FCUSTOMERID_FNAME')]")
    texts2 = [element.text for element in FCUSTOMERID_FNAME][0]

    # 合计-已收款金额
    FYSKJE = driver.find_elements_by_xpath("//div[contains(@data-field, 'FYSKJE')]")
    yjs_je = [element.text for element in FYSKJE][0]
    yjs_je = float(str(yjs_je).replace(',', ''))


    if cur_jd_je == texts1:
        pass
    else:
        print(f"编码：{wxcbm} 客户名称：{texts2} 金额不一致 开思：{cur_jd_je}  金蝶：{texts1}")
        res = {'wxcbm': wxcbm, 'cur_kehu_je': cur_kehu_je, 'cur_ksq_je': cur_ksq_je, 'cur_jd_je': cur_jd_je,
               'cur_label': cur_label, 'ss_ysd_res': '', 'jd_sf_yz' : f'金额不一致 开思：{cur_jd_je}  金蝶：{texts1}', 'yjs_je': ''
               , 'cz_type': '', 'dis_res': ''}
        return res

    # 检查 合计-已收款金额 是否已经收款完了
    if texts1 == yjs_je:
        res = {'wxcbm': wxcbm, 'cur_kehu_je': cur_kehu_je, 'cur_ksq_je': cur_ksq_je, 'cur_jd_je': cur_jd_je,
               'cur_label': cur_label, 'ss_ysd_res': '', 'jd_sf_yz': '', 'yjs_je': f'已收款金额（{yjs_je}）等于 金蝶金额（{texts1}） 不下推'
               , 'cz_type': '', 'dis_res': ''}
        return res

    # 未收款金额
    wsk_je = texts1 - yjs_je
    # 一次性全部完成收款  1、平台已结算金额 等于 合计-价税合计。 2、平台已结算金额 等于 未收款金额
    # 不需要修改收款单明细金额
    if cur_yjs_je == texts1:
        cz_type = "一次性全部完成收款  1、平台已结算金额 等于 合计-价税合计。"
        dis_res = disposable(driver, skd_date, cur_kp_zt)
    elif cur_yjs_je == wsk_je:
        cz_type = "一次性全部完成收款  2、平台已结算金额 等于 未收款金额。"
        dis_res = disposable(driver, skd_date, cur_kp_zt)
    else:
        # 需要修改收款单明细金额
        cz_type = "不是一次性收款，本次收-> " + str(cur_label).split(' = ')[1]
        dis_res = not_disposable(driver, skd_date, cur_kp_zt, cur_yjs_je)

    res = {'wxcbm': wxcbm, 'cur_kehu_je': cur_kehu_je, 'cur_ksq_je': cur_ksq_je, 'cur_jd_je': cur_jd_je,
           'cur_label': cur_label, 'ss_ysd_res': '', 'jd_sf_yz': '', 'yjs_je': '', 'cz_type': cz_type, 'dis_res': dis_res}

    return res


def disposable(driver, skd_date, cur_kp_zt):
    """
    一次性收款
    :return:
    """
    # abcd全选
    # pyautogui.click(x=31, y=314)
    pyautogui.click(x=46, y=468)
    time.sleep(1)

    # 下推 - 生成收款单
    # abcd将鼠标移动到(100, 100)位置，移动过程持续2秒
    # pyautogui.moveTo(464, 169, duration=1)
    pyautogui.moveTo(697, 252, duration=1)

    # abcd
    # pyautogui.moveTo(464, 231, duration=1)
    pyautogui.moveTo(712, 348, duration=1)
    time.sleep(1)

    # abcd生成收款单
    # pyautogui.click(x=464, y=231)
    pyautogui.click(x=712, y=348)
    time.sleep(5)

    # 检查有没有打开 收款单 - 新增
    elements = driver.find_elements_by_xpath("//span[contains(text(), '收款单 - 新增')]")
    # 检查是否找到元素
    if elements:
        # print("【收款单 - 新增】已打开。 ")
        # 如果需要操作第一个元素
        t = elements[0].text

        # 收款单业务日期 改成 2025/9/30
        # pyautogui.click(x=1120, y=328)
        pyautogui.click(x=2774, y=451)
        time.sleep(1)

        # abcd
        # pyautogui.click(x=1120, y=328)
        pyautogui.click(x=2774, y=451)
        pyperclip.copy(skd_date)

        pyautogui.hotkey('ctrl', 'a')
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(1)

        # abcd
        # pyautogui.click(x=1344, y=328)
        pyautogui.click(x=3065, y=451)

        # abcd结算方式：电汇
        # pyautogui.click(x=154, y=573)
        pyautogui.click(x=316, y=778)
        time.sleep(1)

        # abcd
        # pyautogui.click(x=154, y=573)
        pyautogui.click(x=316, y=778)
        pyperclip.copy('电汇')
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(1)
        pyautogui.press('enter')

        # 我方银行帐号
        # 无需发票 6214860209811922
        # 已开票  44428301040011286
        if cur_kp_zt == '无需发票':
            yhk = '6214860209811922'
        else:
            yhk = '44428301040011286'

        # abcd
        # pyautogui.click(x=154, y=573)
        pyautogui.click(x=1455, y=780)
        time.sleep(1)
        # pyautogui.click(x=721, y=575)
        pyautogui.click(x=1455, y=780)

        pyperclip.copy(yhk)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(1)
        pyautogui.press('enter')

        # pyautogui.click(x=800, y=680)
        pyautogui.click(x=1511, y=962)
        # 然后 提交
        # pyautogui.click(x=193, y=169)
        pyautogui.click(x=288, y=260)
        time.sleep(2)
        # 关闭
        # pyautogui.click(x=309, y=133)
        pyautogui.click(x=464, y=201)

        return f'提交成功！'

    else:
        # print("【收款单 - 新增】未打开！！！ ")
        # pyautogui.click(x=1884, y=212)
        pyautogui.click(x=3788, y=316)
        time.sleep(1)
        # pyautogui.click(x=1884, y=212)
        pyautogui.click(x=3788, y=316)
        time.sleep(1)

        return '不符合下推规则！'


def not_disposable(driver, skd_date, cur_kp_zt, cur_yjs_je):
    """
    非一次性收款
    :return:
    """
    # abcd全选
    # pyautogui.click(x=31, y=314)
    pyautogui.click(x=46, y=468)
    time.sleep(1)

    # 下推 - 生成收款单
    # abcd将鼠标移动到(100, 100)位置，移动过程持续2秒
    # pyautogui.moveTo(464, 169, duration=1)
    pyautogui.moveTo(697, 252, duration=1)

    # abcd
    # pyautogui.moveTo(464, 231, duration=1)
    pyautogui.moveTo(712, 348, duration=1)
    time.sleep(1)

    # abcd生成收款单
    # pyautogui.click(x=464, y=231)
    pyautogui.click(x=712, y=348)
    time.sleep(5)

    # 检查有没有打开 收款单 - 新增
    elements = driver.find_elements_by_xpath("//span[contains(text(), '收款单 - 新增')]")
    # 检查是否找到元素
    if elements:
        # print("【收款单 - 新增】已打开。 ")
        # 如果需要操作第一个元素
        t = elements[0].text

        # 收款单业务日期 改成 2025/9/30
        # pyautogui.click(x=1120, y=328)
        pyautogui.click(x=2774, y=451)
        time.sleep(1)

        # abcd
        # pyautogui.click(x=1120, y=328)
        pyautogui.click(x=2774, y=451)
        pyperclip.copy(skd_date)

        pyautogui.hotkey('ctrl', 'a')
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(1)

        # abcd
        # pyautogui.click(x=1344, y=328)
        pyautogui.click(x=3065, y=451)

        # abcd结算方式：电汇
        # pyautogui.click(x=154, y=573)
        pyautogui.click(x=316, y=778)
        time.sleep(1)

        # abcd
        # pyautogui.click(x=154, y=573)
        pyautogui.click(x=316, y=778)
        pyperclip.copy('电汇')
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(1)
        pyautogui.press('enter')

        # 我方银行帐号
        # 无需发票 6214860209811922
        # 已开票  44428301040011286
        if cur_kp_zt == '无需发票':
            yhk = '6214860209811922'
        else:
            yhk = '44428301040011286'

        # abcd
        # pyautogui.click(x=154, y=573)
        pyautogui.click(x=1455, y=780)
        time.sleep(1)
        # pyautogui.click(x=721, y=575)
        pyautogui.click(x=1455, y=780)

        pyperclip.copy(yhk)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(1)
        pyautogui.press('enter')

        # pyautogui.click(x=800, y=680)
        pyautogui.click(x=1511, y=962)

        # 先获取 本次收款金额，然后再修改
        pyautogui.scroll(-500)
        time.sleep(2)
        # 本次收款金额
        bcsk_je_list = driver.find_elements_by_xpath("//span[contains(@data-field, 'FREALRECAMOUNT')]")
        bcsk_je_list = [float(str(element.text).replace(',', '').replace('¥', '')) for element in bcsk_je_list][1:]
        if len(bcsk_je_list) > 8:
            # 产品太多了，处理不了！
            return f'{len(bcsk_je_list)} 个产品太多了，请手工处理！'
        else:
            # 最多处理8个产品明细
            new_bcsk_list = get_bcskje_fun(bcsk_je_list, cur_yjs_je)  # 本次收款金额
            for k, bcsk in enumerate(new_bcsk_list):
                time.sleep(1)
                pyautogui.click(x=720, y=608)  # 空白
                # pyautogui.click(x=, y=)
                time.sleep(1)
                # abcd
                if k == 0:
                    pyautogui.click(x=720, y=712)
                elif k == 1:
                    pyautogui.click(x=720, y=746)
                elif k == 2:
                    pyautogui.click(x=720, y=782)
                elif k == 3:
                    pyautogui.click(x=720, y=818)
                elif k == 4:
                    pyautogui.click(x=720, y=852)
                elif k == 5:
                    pyautogui.click(x=720, y=888)
                elif k == 6:
                    pyautogui.click(x=720, y=922)
                elif k == 7:
                    pyautogui.click(x=720, y=958)

                pyperclip.copy(bcsk)
                pyautogui.hotkey('ctrl', 'v')
                time.sleep(1)
                pyautogui.press('enter')

            time.sleep(2)
            # 再次获取 本次收款金额 是否已经修改完成！
            update_bcsk_je_list = driver.find_elements_by_xpath("//span[contains(@data-field, 'FREALRECAMOUNT')]")
            update_bcsk_je_list = [(str(element.text).replace(',', '').replace('¥', '')) for element in update_bcsk_je_list]
            if round(float(update_bcsk_je_list[0]), 2) == cur_yjs_je:
                # 然后 提交
                # pyautogui.click(x=193, y=169)
                pyautogui.click(x=288, y=260)
                time.sleep(2)
                # 关闭
                # pyautogui.click(x=309, y=133)
                pyautogui.click(x=464, y=201)
                return f'提交成功！平台已结算金额：{cur_yjs_je} ，修改后 本次收款金额：{round(float(update_bcsk_je_list[0]), 2)} ，修改行明细：{new_bcsk_list}'

            else:
                return f'提交失败！修改后与平台已结算金额对不上'

    else:
        # print("【收款单 - 新增】未打开！！！ ")
        # pyautogui.click(x=1884, y=212)
        pyautogui.click(x=3788, y=316)
        time.sleep(1)
        # pyautogui.click(x=1884, y=212)
        pyautogui.click(x=3788, y=316)
        time.sleep(1)

        return '不符合下推规则！'


def get_bcskje_fun(bcsk_je_list, remaining):
    """
    本次收款金额
    :param bcsk_je_list:
    :param remaining:
    :return:
    """
    # bcsk_je_list = [300, 200, 200, 169.99]
    # remaining = 566.99
    new_aa = []
    for amount in bcsk_je_list:
        if remaining <= 0:
            # 到账金额已用完，剩余应收款保持不变
            new_aa.append(amount)
        else:
            if amount <= remaining:
                # 应收款全额被覆盖，剩余到账金额减少相应数额
                new_aa.append(0.0)
                remaining -= amount
            else:
                # 应收款部分被覆盖，剩余应收款为差额
                new_aa.append(amount - remaining)
                remaining = 0
    # print(new_aa)
    new_bcsk_list = [round(bcsk_je_list[k] - a, 2) for k, a in enumerate(new_aa)]
    # print(new_bcsk_list)
    return new_bcsk_list



if __name__ == '__main__':
    skd_date = '2025/9/30'
    dologin(skd_date)









