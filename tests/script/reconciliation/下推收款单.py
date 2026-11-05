# coding:utf-8
"""
下推收款单.py —— 用 Selenium + pyautogui 模拟人工从金蝶应收单下推生成收款单。

复用思路来自 tests/External/old_script/开思对账V5.py，但做如下改进：
- 不再按客户代码搜索，而是按对账结果里的「单据编号-金蝶」（应收单号）
  在应收单列表的「单据编号」筛选框定位到那一张单，再逐单下推；
- 登录信息、URL、业务日期、坐标等参数化；
- 仅处理一次性收款：生成对账Excel.py 已排除非一次性场景，下推时不再修改源单明细金额；
- 银行账号按发票类型选择：无需发票/不开票 → 无需发票账户；其余 → 已开票账户；
- 收款/退款不区分：下推时金蝶根据源单蓝字/红字自动生成销售收款单或收款退款单。

输入：对账 DataFrame（读取「开思对账_行合并_*.xlsx」的「对账」sheet），至少包含列：
  - 单据编号-金蝶            （应收单号，用于搜索定位）
  - 平台已结算金额（¥）-开思   （仅用于日志记录）
  - 发票类型-开思             （选银行账号；缺省按已开票）

依赖：selenium、pyautogui、pyperclip、webdriver（Chrome）
运行环境：1920x1080 高分屏（坐标与 V5 一致）
"""
import datetime
import glob
import os
import subprocess
import time

import pandas as pd
import pyautogui
import pyperclip
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By


# ======================================================================
# 默认配置
# ======================================================================

DEFAULT_K3_URL = "http://erp.gzbbr.com/K3Cloud/"
DEFAULT_USERNAME = "张锐"
DEFAULT_PASSWORD = "FREY8088."

# 结算方式、银行账户与 V5 保持一致
SETTLE_TYPE_NAME = "电汇"
BANK_ACCOUNT_NO_INVOICE = "6214860209811922"   # 无需发票
BANK_ACCOUNT_INVOICED = "44428301040011286"    # 已开票

# Excel 状态列配置
SIMULATION_SHEET = "模拟点击数据源"
STATUS_COLUMN = "是否模拟点击状态"
STATUS_DONE = "已写入金蝶"

# 浏览器重启恢复配置
SKIP_THRESHOLD = 10   # 连续跳过达到该值则触发重启
MAX_RESTART = 3       # 最多重启次数

# ChromeDriver 配置
# CHROMEDRIVER_PATH 指向 chromedriver.exe（驱动程序，不是 Chrome 浏览器本身）
# 若 chromedriver 已在系统 PATH 中，保持 None 即可让 Selenium 自动查找；
# 若不知道路径，可在命令行执行：where chromedriver.exe
CHROMEDRIVER_PATH = None
# 启动前是否强制结束残留的 Chrome/ChromeDriver 进程（可解决端口占用导致的偶发卡死）
KILL_STALE_PROCESSES = True


# ======================================================================
# 通用/辅助函数
# ======================================================================

def _click(x, y):
    """pyautogui 点击指定坐标。"""
    pyautogui.click(x=x, y=y)


def _create_driver():
    """创建并返回 Chrome WebDriver（适配 Selenium 4 + ChromeDriver 153）。"""
    # 先清理残留进程，避免上次失败运行留下的 chrome/chromedriver 占用端口/临时目录
    if KILL_STALE_PROCESSES:
        for proc in ("chrome.exe", "chromedriver.exe"):
            try:
                subprocess.run(
                    ["taskkill", "/F", "/IM", proc],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            except Exception:
                pass
        time.sleep(1)

    chrome_options = Options()
    # 只保留 Error 级日志，减少控制台输出阻塞
    chrome_options.add_argument("--log-level=3")
    # 关键：必须排除 enable-logging，否则新版 Chrome 在 Windows 上启动即崩
    # （session not created: DevToolsActivePort file doesn't exist）。
    # 注意：excludeSwitches 只能设置一次，重复 add_experimental_option 会互相覆盖
    chrome_options.add_experimental_option(
        "excludeSwitches", ["enable-logging", "enable-automation"]
    )
    # 隐藏 "自动测试软件正在控制 Chrome" 提示
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--no-first-run")
    chrome_options.add_argument("--no-default-browser-check")
    chrome_options.add_argument("--disable-extensions")
    # 浏览器启动后直接进入全屏（F11），比 driver.fullscreen_window() 更稳定
    chrome_options.add_argument("--start-fullscreen")
    # 注意：w3c:False（旧版协议）和裸 loggingPrefs 能力在新版 ChromeDriver 已废弃/无效，
    # 若设置会导致 "Missing or invalid capabilities"，故不再设置

    if CHROMEDRIVER_PATH:
        service = Service(executable_path=CHROMEDRIVER_PATH)
    else:
        service = Service()

    t0 = time.time()
    driver = webdriver.Chrome(service=service, options=chrome_options)
    print("webdriver.Chrome() 耗时: %.2fs", time.time() - t0)
    return driver


def _handle_login_popup(driver):
    """处理「该帐号已登录在线，确认让对方下线」弹窗。"""
    try:
        time.sleep(3)
        ok_btn = driver.find_element(
            By.XPATH,
            "//div[contains(@class, 'k-window-title')]//span[contains(text(), '警告提示')]"
            "/ancestor::div[contains(@class, 'k-window')]//a[contains(text(), '确认')]",
        )
        ok_btn.click()
        time.sleep(3)
    except Exception:
        pass





def _fill_field(coord, value):
    """在指定坐标输入框中粘贴值并回车确认。"""
    _click(*coord)
    time.sleep(1)
    _click(*coord)
    pyperclip.copy(value)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(1)
    pyautogui.press("enter")


def _save_reconcile_excel(excel_path, df, sheet_name=SIMULATION_SHEET):
    """把更新后的 DataFrame 写回 Excel，保留其它 sheet。"""
    try:
        with pd.ExcelWriter(  # pyright: ignore[reportAbstractUsage]
            excel_path, engine="openpyxl", mode="a", if_sheet_exists="replace"
        ) as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
        print(f"已更新 {sheet_name} 状态到 {excel_path}")
    except Exception as e:
        print(f"保存状态到 Excel 失败：{e}")


# ======================================================================
# 步骤 1：登录并进入应收单列表
# ======================================================================

def login_and_enter_receivable_list(url=None, username=None, password=None):
    """
    初始化浏览器、登录金蝶并进入「应收单列表」。

    :param url: 金蝶 URL，默认 DEFAULT_K3_URL
    :param username: 用户名，默认 DEFAULT_USERNAME
    :param password: 密码，默认 DEFAULT_PASSWORD
    :return: 已打开应收单列表的 WebDriver
    """
    url = url or DEFAULT_K3_URL
    username = username or DEFAULT_USERNAME
    password = password or DEFAULT_PASSWORD
    time.sleep(1)
    driver = _create_driver()
    print(f"登录金蝶云星空：{url}")
    driver.get(url)
    time.sleep(2)

    




    driver.find_element(By.XPATH, '//*[@id="user"]').send_keys(username)
    driver.find_element(By.XPATH, '//*[@id="password"]').send_keys(password)
    time.sleep(2)
    driver.find_element(By.XPATH, '//*[@id="btnLogin"]').click()

    _handle_login_popup(driver)
    
    time.sleep(3)
    _click(392, 153)
   
    time.sleep(2)
    
    _click(1594, 145)
    time.sleep(2)
    _click(1872, 40)
   
    

    time.sleep(3)



    # 打开应收单列表（直接点击首页常用功能图标，避免全局搜索排序误点）
    driver.find_element(By.XPATH, "//a[@title='应收单列表']").click()
    time.sleep(5)

    return driver


# ======================================================================
# 步骤 2：循环单号，逐单执行下推
# ======================================================================

def process_bills(driver, reconcile_df, original_df, excel_path, skd_date, coupon_detail_df=None):
    """
    遍历对账结果，逐单调用 execute_push / execute_refund /
    execute_coupon_order / execute_coupon_return 下推收款单或收款退款单。

    成功后将 original_df 中对应行的 "是否模拟点击状态" 标记为 "已写入金蝶" 并保存 Excel。

    :param driver: 已打开应收单列表的 WebDriver
    :param reconcile_df: 待处理的对账 DataFrame（已过滤掉已写入金蝶行），至少包含列：
                         单据编号-金蝶、平台已结算金额（¥）-开思、发票类型-开思、开思劵(¥)-开思
    :param original_df: 原始的完整对账 DataFrame，用于回写状态
    :param excel_path: 对账 Excel 文件路径
    :param skd_date: 收款单业务日期
    :param coupon_detail_df: 开思券明细 DataFrame（「开思卷明细」sheet），用于券场景逐行填单
    :return: 本次处理结束时的连续跳过次数
    """
    # 局部导入，避免与 v5_coupon_handler.py 产生循环依赖
    from v5_coupon_handler import execute_coupon_bill

    consecutive_skips = 0

    for idx, row in reconcile_df.iterrows():
        bill_no = str(row.get("单据编号-金蝶", "")).strip()
        if not bill_no or bill_no.lower() in ("nan", "none"):
            continue
        settled = float(row.get("平台已结算金额（¥）-开思", 0) or 0)
        invoice_type = str(row.get("发票类型-开思", "已开票")).strip()

        # 开思券金额列兼容两种列名
        coupon_amount = float(row.get("开思劵(¥)-开思", 0) or 0)
        if coupon_amount == 0:
            coupon_amount = float(row.get("开思劵(¥)", 0) or 0)

        success = False
        if coupon_amount != 0:
            success = execute_coupon_bill(
                driver, bill_no, skd_date, settled, coupon_amount,
                invoice_type, coupon_detail_df=coupon_detail_df
            )
        elif settled < 0:
            success = execute_refund(driver, bill_no, skd_date, abs(settled), invoice_type)
        else:
            success = execute_push(driver, bill_no, skd_date, settled, invoice_type)

        if success:
            consecutive_skips = 0
            original_df.at[idx, STATUS_COLUMN] = STATUS_DONE
            _save_reconcile_excel(excel_path, original_df)
        else:
            consecutive_skips += 1
            if consecutive_skips >= SKIP_THRESHOLD:
                print(f"连续跳过达到 {SKIP_THRESHOLD} 条，终止本轮处理并返回重启")
                break

    return consecutive_skips


# ======================================================================
# 步骤 3：单张应收单执行核销
# ======================================================================

def execute_push(driver, bill_no, skd_date, settled_amount, invoice_type="已开票"):
    """
    为一张应收单下推收款单/退款单（仅一次性收款）。

    流程：搜索定位 → 读取金额 → 校验是否已收款 → 下推 → 检查收款单窗口 → 填单保存。
    所有坐标均基于 1920x1080 高分屏；分辨率/缩放/浏览器布局变化时，
    用 pyautogui.displayMousePosition() 重新标定后修改本函数内的坐标。

    :param driver: 已打开应收单列表的 WebDriver
    :param bill_no: 应收单编号（单据编号-金蝶）
    :param skd_date: 收款单业务日期（字符串，如 "2026/9/13"）
    :param settled_amount: 平台已结算金额（¥）-开思（仅用于打印）
    :param invoice_type: "无需发票" 或 其他（使用已开票账户）
    :return: 是否成功写入金蝶
    """
    print(
        f"开始处理应收单：{bill_no}，"
        f"业务日期：{skd_date}，"
        f"平台已结算金额：{settled_amount}，"
        f"发票类型：{invoice_type}"
    )

    # ---------- 1. 按单据编号定位应收单 ----------
    search_inputs = driver.find_elements(
        By.XPATH,
        "//input[@data-role='kdtextfield' and contains(@placeholder, '请输入关键字后回车查询')]",
    )
    if not search_inputs:
        search_inputs = driver.find_elements(
            By.XPATH,
            "//div[contains(@class, 'kd-filtercontent-container')]//input[@data-role='kdtextfield']",
        )
    if not search_inputs:
        print("未找到单据编号筛选框，跳过")
        return False

    try:
        search_box = search_inputs[0]
        search_box.click()
        time.sleep(1)
        pyperclip.copy(str(bill_no))
        pyautogui.hotkey("ctrl", "a")
        pyautogui.hotkey("ctrl", "v")
        time.sleep(1)
        pyautogui.press("enter")
        time.sleep(10)  # 等待列表刷新
    except Exception:
        print("搜索单据编号时出错，跳过")
        return False

    # ---------- 2. 读取价税合计与已收款金额 ----------
    try:
        total_amount_cells = driver.find_elements(By.XPATH, "//div[contains(@data-field, 'FALLAMOUNTFOR')]")
        total_amount = float(str(total_amount_cells[0].text).replace(",", ""))
    except Exception:
        print("应收单查询没记录，跳过")
        return False

    try:
        received_amount_cells = driver.find_elements(By.XPATH, "//div[contains(@data-field, 'FYSKJE')]")
        received_amount = float(str(received_amount_cells[0].text).replace(",", ""))
    except Exception:
        received_amount = 0.0

    # ---------- 3. 校验是否已收款完成 ----------
    if abs(total_amount - received_amount) <= 0.01:
        print(f"已收款金额（{received_amount}）等于 价税合计（{total_amount}），无需下推，跳过")
        return False

    # ---------- 4. 下推生成收款单 ----------
    # 以下坐标为应收单列表页的硬编码坐标；
    # 若列表行高、工具栏位置、下推菜单项位置变化，需用 pyautogui.displayMousePosition() 重新标定。
    _click(43, 392)              # 勾选列表第一行复选框
    time.sleep(1)
    pyautogui.moveTo(580, 123, duration=1)  # 悬停「下推」主按钮
    time.sleep(1)
    _click(588, 198)             # 点击「下推收款单」子菜单项
    time.sleep(5)

    # ---------- 5. 确认收款单新增界面已打开 ----------
    receive_bill_title = driver.find_elements(By.XPATH, "//span[contains(text(), '收款单 - 新增')]")
    if not receive_bill_title:
        print("不符合下推规则！")
        return False

    # ---------- 6. 填写业务日期、结算方式、银行账号并保存 ----------
    # 我方银行账号（无需发票 / 不开票 → 无需发票账户；其余 → 已开票账户）
    bank_account = (
        BANK_ACCOUNT_NO_INVOICE
        if invoice_type in ("无需发票", "不开票")
        else BANK_ACCOUNT_INVOICED
    )

    # 收款单业务日期（参考旧脚本 2774,451 / 3065,451，按本脚本坐标体系换算）
    # TODO: 若界面缩放/分辨率不同，请用 pyautogui.displayMousePosition() 重新标定
    _click(1235, 322)
    time.sleep(1)
    
    # _click(1235, 322)
    pyperclip.copy(skd_date)
    pyautogui.hotkey("ctrl", "a")
    pyautogui.hotkey("ctrl", "v")
    time.sleep(1)
    _click(1387, 316)  # 点空白处失焦

    _fill_field((161, 627), SETTLE_TYPE_NAME)   # 结算方式输入框
    _fill_field((703, 624), bank_account)       # 我方银行账号输入框
    time.sleep(2)
    _click(156, 123)                            # 保存按钮

    # ===== 测试模式：暂不提交/审核，保留收款单草稿 =====
    # 如需正式提交，取消下面三行注释
    # _click(236, 234)  # 提交/审核按钮
    # time.sleep(2)

    time.sleep(5)
    _click(387, 79)  # 关闭按钮

    time.sleep(2)
    print("一次性收款，提交成功！")
    return True


# ==============================================================================
# 步骤 3b：单张应收单执行退款（平台已结算金额 < 0）
# ==============================================================================

def execute_refund(driver, bill_no, skd_date, refund_amount, invoice_type="已开票"):
    """
    为一张应收单下推收款退款单（退款）。

    流程与 execute_push 类似，但进入「下推收款退款单」分支。
    所有坐标均基于 1920x1080 高分屏；分辨率/缩放/浏览器布局变化时，
    用 pyautogui.displayMousePosition() 重新标定后修改本函数内的坐标。

    :param driver: 已打开应收单列表的 WebDriver
    :param bill_no: 应收单编号（单据编号-金蝶）
    :param skd_date: 收款退款单业务日期（字符串，如 "2026/9/13"）
    :param refund_amount: 退款金额（已取绝对值，仅用于打印）
    :param invoice_type: "无需发票" 或 其他（使用已开票账户）
    :return: 是否成功写入金蝶
    """
    print(
        f"开始处理应收单退款：{bill_no}，"
        f"业务日期：{skd_date}，"
        f"退款金额：{refund_amount}，"
        f"发票类型：{invoice_type}"
    )

    # ---------- 1. 按单据编号定位应收单 ----------
    search_inputs = driver.find_elements(
        By.XPATH,
        "//input[@data-role='kdtextfield' and contains(@placeholder, '请输入关键字后回车查询')]",
    )
    if not search_inputs:
        search_inputs = driver.find_elements(
            By.XPATH,
            "//div[contains(@class, 'kd-filtercontent-container')]//input[@data-role='kdtextfield']",
        )
    if not search_inputs:
        print("未找到单据编号筛选框，跳过")
        return False

    try:
        search_box = search_inputs[0]
        search_box.click()
        time.sleep(1)
        pyperclip.copy(str(bill_no))
        pyautogui.hotkey("ctrl", "a")
        pyautogui.hotkey("ctrl", "v")
        time.sleep(1)
        pyautogui.press("enter")
        time.sleep(10)  # 等待列表刷新
    except Exception:
        print("搜索单据编号时出错，跳过")
        return False

    # ---------- 2. 读取价税合计与已收款金额 ----------
    try:
        total_amount_cells = driver.find_elements(By.XPATH, "//div[contains(@data-field, 'FALLAMOUNTFOR')]")
        total_amount = float(str(total_amount_cells[0].text).replace(",", ""))
    except Exception:
        print("应收单查询没记录，跳过")
        return False

    try:
        received_amount_cells = driver.find_elements(By.XPATH, "//div[contains(@data-field, 'FYSKJE')]")
        received_amount = float(str(received_amount_cells[0].text).replace(",", ""))
    except Exception:
        received_amount = 0.0

    # ---------- 3. 校验是否已收款/已退款完成 ----------
    if abs(total_amount - received_amount) <= 0.01:
        print(f"已收款/已退款金额（{received_amount}）等于 价税合计（{total_amount}），无需下推，跳过")
        return False

    # ---------- 4. 下推生成收款退款单 ----------
    # 以下坐标为应收单列表页的硬编码坐标；
    # 若列表行高、工具栏位置、下推菜单项位置变化，需用 pyautogui.displayMousePosition() 重新标定。
    # TODO: "下推收款退款单"子菜单项坐标需根据实际金蝶界面确认，当前沿用收款单坐标占位。
    _click(38, 385)              # 勾选列表第一行复选框
    time.sleep(1)
    pyautogui.moveTo(580, 123, duration=1)  # 悬停「下推」主按钮
    time.sleep(1)
    _click(636, 229)             # 点击「下推收款退款单」子菜单项（坐标待确认）
    time.sleep(5)

    # ---------- 5. 确认收款退款单新增界面已打开 ----------
    refund_bill_title = driver.find_elements(By.XPATH, "//span[contains(text(), '收款退款单 - 新增')]")
    if not refund_bill_title:
        print("不符合下推退款规则！")
        return False

    # ---------- 6. 填写业务日期、银行账号并保存 ----------
    # 我方银行账号（无需发票 / 不开票 → 无需发票账户；其余 → 已开票账户）
    bank_account = (
        BANK_ACCOUNT_NO_INVOICE
        if invoice_type in ("无需发票", "不开票")
        else BANK_ACCOUNT_INVOICED
    )

    # 收款退款单业务日期（参考收款单坐标，退款单布局可能不同，需验证）
    # TODO: 若界面缩放/分辨率不同，请用 pyautogui.displayMousePosition() 重新标定
    _click(1196, 320)
    time.sleep(1)
    
    # _click(1196, 320)
    pyperclip.copy(skd_date)
    pyautogui.hotkey("ctrl", "a")
    pyautogui.hotkey("ctrl", "v")
    time.sleep(1)
    _click(1393, 227)  # 点空白处失焦

    # _fill_field((158, 808), SETTLE_TYPE_NAME)   # 结算方式输入框
    _fill_field((992, 693), bank_account)       # 我方银行账号输入框
    time.sleep(2)


    # _click(215, 220)  # 保存按钮
    # time.sleep(2)

    _click(305,117)  # 提交/审核按钮

    time.sleep(5)
    _click(424, 75)  # 关闭按钮

    time.sleep(2)
    print("退款单，提交成功！")
    return True


# ======================================================================
# 批量入口
# ======================================================================

def load_reconcile_excel(skd_date=None):
    """读取 生成对账Excel.py 生成的最新对账 Excel。

    同时读取「模拟点击数据源」和「开思卷明细」两个 sheet，后者用于券场景逐行填单。
    自动新增「是否模拟点击状态」列，并过滤掉已标记为「已写入金蝶」的行。

    :param skd_date: 收款单业务日期；None 则使用当天日期
    :return: (original_df, pending_df, coupon_detail_df, skd_date, excel_path)
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    files = glob.glob(os.path.join(data_dir, "开思对账_行合并_*.xlsx"))
    if not files:
        raise FileNotFoundError(f"{data_dir} 下未找到 开思对账_行合并_*.xlsx，请先运行 生成对账Excel.py")
    latest = sorted(files)[-1]  # 按文件名（含时间戳）升序，取最后一个
    print(f"读取对账文件 -> {latest}")

    df = pd.read_excel(latest, sheet_name=SIMULATION_SHEET)
    if STATUS_COLUMN not in df.columns:
        df[STATUS_COLUMN] = ""
    pending_df = df[df[STATUS_COLUMN] != STATUS_DONE].copy()
    print(f"模拟点击数据源 {len(df)} 行，待处理 {len(pending_df)} 行")

    try:
        coupon_detail_df = pd.read_excel(latest, sheet_name="开思卷明细")
        print(f"开思卷明细 {len(coupon_detail_df)} 行")
    except ValueError:
        print("警告：对账文件中未找到「开思卷明细」sheet，券场景将使用汇总金额填单")
        coupon_detail_df = pd.DataFrame()

    if skd_date is None:
        now = datetime.datetime.now()
        skd_date = f"{now.year}/{now.month}/{now.day}"
    print(f"收款单业务日期 -> {skd_date}")

    return df, pending_df, coupon_detail_df, skd_date, latest


def run_v5_automation(url=None, username=None, password=None, skd_date=None):
    """
    全流程：读取对账 Excel → 登录金蝶 → 逐单下推收款单。
    当本次处理结束时连续跳过超过阈值，会自动关闭浏览器、重新读取 Excel 并重新登录，
    以恢复页面并 retry 之前未成功的行。

    :param url: 金蝶 URL
    :param username: 用户名
    :param password: 密码
    :param skd_date: 收款单业务日期；None 则使用当天日期
    """
    restart_count = 0
    while restart_count <= MAX_RESTART:
        original_df, reconcile_df, coupon_detail_df, skd_date, excel_path = load_reconcile_excel(
            skd_date=skd_date
        )
        if reconcile_df.empty:
            print("没有待处理的模拟点击数据，结束执行")
            break

        driver = login_and_enter_receivable_list(url=url, username=username, password=password)
        try:
            consecutive_skips = process_bills(
                driver, reconcile_df, original_df, excel_path, skd_date,
                coupon_detail_df=coupon_detail_df,
            )
        finally:
            try:
                driver.quit()
            except Exception as e:
                print(f"关闭浏览器失败：{e}")

        if consecutive_skips < SKIP_THRESHOLD:
            print("本次处理正常结束")
            break

        if restart_count >= MAX_RESTART:
            raise RuntimeError(
                f"连续跳过达到 {SKIP_THRESHOLD} 条，且已重启 {MAX_RESTART} 次，终止执行"
            )
        restart_count += 1
        print(
            f"本次处理结束时连续跳过 {consecutive_skips} 条，"
            f"准备第 {restart_count} 次重启浏览器并重新加载待处理数据..."
        )


if __name__ == "__main__":
    # 在这里修改收款单/退款单的业务日期，如 "2025/9/30"
    skd_date = "2026/11/4"
    run_v5_automation(skd_date=skd_date)
