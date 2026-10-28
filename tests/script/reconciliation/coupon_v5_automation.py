# coding:utf-8
"""
coupon_v5_automation.py —— 开思券下推金蝶自动化（独立脚本）

输入：ks_coupon_reconcile.py 生成的最新「开思券对账_*.xlsx」中的「金蝶写入数据源」sheet。
      该 sheet 仅包含「对账状态 == 只缺开思卷」的行。

流程：
  1. 读取待下推数据（过滤掉「已写入金蝶」的行）；
  2. 登录金蝶并进入应收单列表；
  3. 逐单按「应收单-单据编号」搜索；
  4. 根据「对账单-开思劵(¥)」正负判断下推方向：
       - 正数 → 下推收款单
       - 负数 → 下推收款退款单
     由于源单剩余金额就是开思券，金蝶会自动填明细，本脚本只填业务日期和银行账号；
  5. 成功后回写「是否写入金蝶 = 已写入金蝶」。

依赖：selenium、pyautogui、pyperclip、webdriver（Chrome）
运行环境：1920x1080 高分屏（坐标与 v5_automation.py 一致）
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

SETTLE_TYPE_NAME = "电汇"
BANK_ACCOUNT_NO_INVOICE = "6214860209811922"   # 无需发票
BANK_ACCOUNT_INVOICED = "44428301040011286"    # 已开票

INPUT_SHEET = "金蝶写入数据源"
STATUS_COLUMN = "是否写入金蝶"
STATUS_DONE = "已写入金蝶"

SKIP_THRESHOLD = 10
MAX_RESTART = 3

CHROMEDRIVER_PATH = None
KILL_STALE_PROCESSES = True


# ======================================================================
# 通用/辅助函数
# ======================================================================

def _click(x, y):
    """pyautogui 点击指定坐标。"""
    pyautogui.click(x=x, y=y)


def _create_driver():
    """创建并返回 Chrome WebDriver（适配 Selenium 4 + ChromeDriver 153）。"""
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
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_experimental_option(
        "excludeSwitches", ["enable-logging", "enable-automation"]
    )
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--no-first-run")
    chrome_options.add_argument("--no-default-browser-check")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--start-fullscreen")

    if CHROMEDRIVER_PATH:
        service = Service(executable_path=CHROMEDRIVER_PATH)
    else:
        service = Service()

    driver = webdriver.Chrome(service=service, options=chrome_options)
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


def _save_excel(excel_path, df):
    """把更新后的 DataFrame 写回 Excel，保留其它 sheet。"""
    try:
        with pd.ExcelWriter(excel_path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
            df.to_excel(writer, sheet_name=INPUT_SHEET, index=False)
        print(f"已更新 {INPUT_SHEET} 状态到 {excel_path}")
    except Exception as e:
        print(f"保存状态到 Excel 失败：{e}")


# ======================================================================
# 步骤 1：登录并进入应收单列表
# ======================================================================

def login_and_enter_receivable_list(url=None, username=None, password=None):
    """初始化浏览器、登录金蝶并进入「应收单列表」。"""
    url = url or DEFAULT_K3_URL
    username = username or DEFAULT_USERNAME
    password = password or DEFAULT_PASSWORD

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

    driver.find_element(By.XPATH, "//a[@title='应收单列表']").click()
    time.sleep(5)

    return driver


# ======================================================================
# 步骤 2：单张应收单下推（仅填日期+银行账号，明细由金蝶自动填）
# ======================================================================

def execute_coupon_push(driver, bill_no, skd_date, coupon_amount, invoice_type="已开票"):
    """
    为一张应收单下推收款单/收款退款单（只缺开思券场景）。

    :param driver: 已打开应收单列表的 WebDriver
    :param bill_no: 应收单编号（应收单-单据编号）
    :param skd_date: 业务日期（字符串，如 "2026/9/13"）
    :param coupon_amount: 开思券金额（对账单-开思劵(¥)）
    :param invoice_type: 开票类型；"无需发票"/"不开票" 用无需发票账户，其余用已开票账户
    :return: 是否成功写入金蝶
    """
    direction = "收款单" if coupon_amount > 0 else "收款退款单"
    print(
        f"开始处理应收单：{bill_no}，"
        f"业务日期：{skd_date}，"
        f"开思券金额：{coupon_amount}，"
        f"下推方向：{direction}，"
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
        time.sleep(10)
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
        print(f"已收款金额（{received_amount}）等于 价税合计（{total_amount}），无需下推，跳过")
        return False

    # ---------- 4. 下推 ----------
    is_receipt = coupon_amount > 0
    if is_receipt:
        # 收款单
        _click(43, 392)
        time.sleep(1)
        pyautogui.moveTo(580, 123, duration=1)
        time.sleep(1)
        _click(588, 198)
        expected_title = "收款单 - 新增"
        date_coord = (1235, 322)
        blur_coord = (1387, 316)
        settle_coord = (161, 627)
        bank_coord = (703, 624)
        save_coord = (156, 123)
        close_coord = (387, 79)
    else:
        # 收款退款单
        _click(38, 385)
        time.sleep(1)
        pyautogui.moveTo(580, 123, duration=1)
        time.sleep(1)
        _click(636, 229)
        expected_title = "收款退款单 - 新增"
        date_coord = (1196, 320)
        blur_coord = (1393, 227)
        settle_coord = None
        bank_coord = (992, 693)
        save_coord = (305, 117)
        close_coord = (424, 75)

    time.sleep(5)

    # ---------- 5. 确认新增界面已打开 ----------
    bill_title = driver.find_elements(By.XPATH, f"//span[contains(text(), '{expected_title}')]")
    if not bill_title:
        print("不符合下推规则！")
        return False

    # ---------- 6. 填写业务日期、结算方式、银行账号并保存 ----------
    bank_account = (
        BANK_ACCOUNT_NO_INVOICE
        if str(invoice_type).strip() in ("无需发票", "不开票")
        else BANK_ACCOUNT_INVOICED
    )

    _click(*date_coord)
    time.sleep(1)
    pyperclip.copy(skd_date)
    pyautogui.hotkey("ctrl", "a")
    pyautogui.hotkey("ctrl", "v")
    time.sleep(1)
    _click(*blur_coord)

    if settle_coord:
        _fill_field(settle_coord, SETTLE_TYPE_NAME)
    _fill_field(bank_coord, bank_account)
    time.sleep(2)

    _click(*save_coord)
    time.sleep(5)
    _click(*close_coord)
    time.sleep(2)

    print(f"{direction}，提交成功！")
    return True


# ======================================================================
# 批量入口
# ======================================================================

def load_coupon_excel(skd_date=None):
    """读取 ks_coupon_reconcile.py 生成的最新 Excel 中的「金蝶写入数据源」sheet。"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, "data")
    os.makedirs(data_dir, exist_ok=True)

    files = glob.glob(os.path.join(data_dir, "开思券对账_*.xlsx"))
    if not files:
        raise FileNotFoundError(f"{data_dir} 下未找到 开思券对账_*.xlsx，请先运行 ks_coupon_reconcile.py")
    latest = sorted(files)[-1]
    print(f"读取对账文件 -> {latest}")

    df = pd.read_excel(latest, sheet_name=INPUT_SHEET)
    df[STATUS_COLUMN] = df[STATUS_COLUMN].fillna("").astype(str)
    pending_df = df[df[STATUS_COLUMN] != STATUS_DONE].copy()
    print(f"{INPUT_SHEET} {len(df)} 行，待处理 {len(pending_df)} 行")

    if skd_date is None:
        now = datetime.datetime.now()
        skd_date = f"{now.year}/{now.month}/{now.day}"
    print(f"业务日期 -> {skd_date}")

    return df, pending_df, skd_date, latest


def process_coupon_bills(driver, pending_df, original_df, excel_path, skd_date):
    """遍历待处理行，逐单下推并回写状态。"""
    consecutive_skips = 0

    for idx, row in pending_df.iterrows():
        bill_no = str(row.get("应收单-单据编号", "")).strip()
        if not bill_no or bill_no.lower() in ("nan", "none"):
            continue

        coupon_amount = float(row.get("对账单-开思劵(¥)", 0) or 0)
        if abs(coupon_amount) <= 0.01:
            print(f"{bill_no} 开思券金额为 0，跳过")
            continue

        invoice_type = str(row.get("开票类型", "已开票")).strip()

        success = execute_coupon_push(
            driver, bill_no, skd_date, coupon_amount, invoice_type
        )

        if success:
            consecutive_skips = 0
            original_df.at[idx, STATUS_COLUMN] = STATUS_DONE
            _save_excel(excel_path, original_df)
        else:
            consecutive_skips += 1
            if consecutive_skips >= SKIP_THRESHOLD:
                print(f"连续跳过达到 {SKIP_THRESHOLD} 条，终止本轮处理并返回重启")
                break

    return consecutive_skips


def run_coupon_v5_automation(url=None, username=None, password=None, skd_date=None):
    """全流程：读取 Excel → 登录金蝶 → 逐单下推。"""
    restart_count = 0
    while restart_count <= MAX_RESTART:
        original_df, pending_df, skd_date, excel_path = load_coupon_excel(skd_date=skd_date)
        if pending_df.empty:
            print("没有待处理的金蝶写入数据，结束执行")
            break

        driver = login_and_enter_receivable_list(url=url, username=username, password=password)
        try:
            consecutive_skips = process_coupon_bills(
                driver, pending_df, original_df, excel_path, skd_date
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
    # 在这里修改业务日期，如 "2025/9/30"
    skd_date = "2026/10/22"
    run_coupon_v5_automation(skd_date=skd_date)
