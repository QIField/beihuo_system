# coding:utf-8
"""
v5_coupon_handler.py —— 开思券场景下推收款单/收款退款单。

包含两个具体处理函数：
  - execute_coupon_order: 开思券销售订单（平台已结算金额 ≥ 0）下推收款单
  - execute_coupon_return: 开思券退货单（平台已结算金额 < 0）下推收款退款单

「修改收款单/退款单明细网格」使用纯 HTML/Selenium；
其余填单/保存操作沿用 v5_automation.py 的模拟点击坐标。
"""
import time

import pyautogui
import pyperclip
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By

from v5_automation import (
    BANK_ACCOUNT_NO_INVOICE,
    BANK_ACCOUNT_INVOICED,
    SETTLE_TYPE_NAME,
    _click,
    _fill_field,
)


def _set_grid_cell_value(driver, data_field, row_uid, value):
    """Selenium 定位 + 模拟双击进入编辑，再用 pyautogui 粘贴写入。"""
    cell_span = driver.find_element(
        By.XPATH,
        f"//tr[@data-uid='{row_uid}']//span[@data-field='{data_field}']",
    )

    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", cell_span)
    time.sleep(0.3)
    ActionChains(driver).double_click(cell_span).perform()
    time.sleep(0.8)

    for xpath in [
        f"//tr[@data-uid='{row_uid}']//td[contains(@class,'k-edit-cell')]//input",
        "//div[contains(@class,'kd-grid-element')]//td[contains(@class,'k-edit-cell')]//input",
        "//div[contains(@class,'kd-grid-element')]//input[contains(@class,'k-textbox')]",
        "//div[contains(@class,'kd-grid-element')]//input[@data-role='kdtextfield']",
    ]:
        try:
            edit_input = driver.find_element(By.XPATH, xpath)
            if edit_input.is_displayed():
                break
        except Exception:
            edit_input = None
    else:
        raise RuntimeError(f"无法进入 {data_field}（uid={row_uid}）单元格的编辑状态")

    edit_input.click()
    time.sleep(0.3)
    pyperclip.copy(str(value))
    pyautogui.hotkey("ctrl", "a")
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.3)
    pyautogui.press("enter")
    time.sleep(0.8)


def _select_bank_account(invoice_type):
    """按发票类型返回我方银行账号。"""
    return (
        BANK_ACCOUNT_NO_INVOICE
        if invoice_type in ("无需发票", "不开票")
        else BANK_ACCOUNT_INVOICED
    )


def _to_float(value):
    """把金额列安全转成 float。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _parse_amount_text(text):
    s = str(text).replace("¥", "").replace(",", "").replace(" ", "").strip()
    try:
        return float(s)
    except (TypeError, ValueError):
        return 0.0


def _extract_part_number(material_text):
    s = str(material_text).strip()
    return s.split()[0] if s else ""


def _read_grid_rows(driver, amount_field="FREALRECAMOUNT", material_field="FSRCMATERIALID"):
    """读取源单明细网格：物料编码 + 当前本次收款金额。用 tr 的 data-uid 标识行。"""
    rows = []
    material_spans = driver.find_elements(
        By.XPATH,
        f"//div[contains(@class,'kd-grid-element')]//span[@data-field='{material_field}']",
    )
    print(f"[读取网页明细] 共 {len(material_spans)} 行")
    for span in material_spans:
        row_uid = span.find_element(By.XPATH, "./ancestor::tr").get_attribute("data-uid")
        material_text = span.text
        try:
            amount_span = driver.find_element(
                By.XPATH,
                f"//tr[@data-uid='{row_uid}']//span[@data-field='{amount_field}']",
            )
            current_amount = _parse_amount_text(amount_span.text)
        except Exception:
            current_amount = 0.0
        print(f"  行 uid={row_uid}: 物料编码='{material_text}', 当前金额={current_amount}")
        rows.append((row_uid, material_text, current_amount))
    return rows


def _fill_coupon_detail_rows(driver, bill_no, coupon_detail_df, settled_amount=None, coupon_amount=None, amount_field="FREALRECAMOUNT"):
    """按网页明细行匹配「开思卷明细」并写入金额。"""
    if coupon_detail_df is None or coupon_detail_df.empty:
        _fill_coupon_summary_rows(driver, settled_amount, coupon_amount, amount_field=amount_field)
        return

    detail = coupon_detail_df[coupon_detail_df["单据编号-金蝶"].astype(str).str.strip() == str(bill_no)].copy()
    if detail.empty:
        print(f"未找到 {bill_no} 的券明细")
        return

    detail["_subtotal"] = detail["小计(¥)"].apply(lambda x: round(_to_float(x), 2))
    detail["_coupon"] = detail["开思劵金额(¥)"].apply(lambda x: round(_to_float(x), 2))
    detail["_sum"] = (detail["_subtotal"].abs() + detail["_coupon"].abs()).round(2)

    print(f"[读取Excel明细] 单据 {bill_no} 共 {len(detail)} 行")
    for _, ex_row in detail.iterrows():
        print(f"  零件号={ex_row.get('零件号')}, 小计={ex_row['_subtotal']}, 券={ex_row['_coupon']}, 合计={ex_row['_sum']}")

    web_rows = _read_grid_rows(driver, amount_field=amount_field)
    if not web_rows:
        print("网页明细网格无数据")
        return

    updated_count = 0
    used_indices = set()
    for row_uid, material_text, current_amount in web_rows:
        current_abs = round(abs(current_amount), 2)
        part_no = _extract_part_number(material_text)

        candidates = detail[(~detail.index.isin(used_indices)) & (abs(detail["_sum"] - current_abs) <= 0.01)]
        if candidates.empty:
            print(f"  行 {row_uid} 当前金额={current_amount} 未匹配，跳过")
            continue

        mat_candidates = candidates[candidates["零件号"].astype(str).str.strip() == part_no]
        chosen = mat_candidates.iloc[0] if not mat_candidates.empty else candidates.iloc[0]

        used_indices.add(chosen.name)
        subtotal = abs(float(chosen["_subtotal"]))
        print(f"  明细行 {row_uid}: 物料编码='{material_text}', 本次{('收款' if amount_field == 'FREALRECAMOUNT' else '退款')}金额={subtotal}")
        _set_grid_cell_value(driver, amount_field, row_uid, subtotal)
        updated_count += 1

    if updated_count == 0:
        raise RuntimeError("未匹配到任何可更新的明细行")


def _fill_coupon_summary_rows(driver, settled_amount, coupon_amount, amount_field="FREALRECAMOUNT"):
    """无券明细时，把汇总金额写入第一行本次收款/退款金额。"""
    if settled_amount is None or coupon_amount is None:
        return

    web_rows = _read_grid_rows(driver, amount_field=amount_field)
    if not web_rows:
        return

    first_row_uid = web_rows[0][0]
    real_rec = round(abs(settled_amount), 2)
    label = "收款" if amount_field == "FREALRECAMOUNT" else "退款"
    print(f"  汇总写入行 {first_row_uid}: 本次{label}金额={real_rec}")
    _set_grid_cell_value(driver, amount_field, first_row_uid, real_rec)


def execute_coupon_order(driver, bill_no, skd_date, settled_amount, coupon_amount, invoice_type="已开票", coupon_detail_df=None):
    """开思券销售订单：下推收款单并写入券折扣。

    :return: 是否成功写入金蝶
    """
    print(
        f"开始处理开思券订单：{bill_no}，"
        f"业务日期：{skd_date}，"
        f"平台已结算金额：{settled_amount}，"
        f"开思券金额：{coupon_amount}，"
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

    # ---------- 3. 校验是否已收款完成 ----------
    if abs(total_amount - received_amount) <= 0.01:
        print(f"已收款金额（{received_amount}）等于 价税合计（{total_amount}），无需下推，跳过")
        return False

    # ---------- 4. 下推生成收款单 ----------
    _click(43, 392)
    time.sleep(1)
    pyautogui.moveTo(580, 123, duration=1)
    time.sleep(1)
    _click(588, 198)
    time.sleep(5)

    receive_bill_title = driver.find_elements(By.XPATH, "//span[contains(text(), '收款单 - 新增')]")
    if not receive_bill_title:
        print("不符合下推规则！")
        return False

    # ---------- 5. 填写业务日期、结算方式、银行账号 ----------
    bank_account = _select_bank_account(invoice_type)

    _click(1235, 322)
    time.sleep(1)
    pyperclip.copy(skd_date)
    pyautogui.hotkey("ctrl", "a")
    pyautogui.hotkey("ctrl", "v")
    time.sleep(1)
    _click(1387, 316)

    _fill_field((161, 627), SETTLE_TYPE_NAME)
    _fill_field((703, 624), bank_account)
    time.sleep(2)

    # ---------- 6. 纯 HTML 修改明细网格 ----------
    try:
        _fill_coupon_detail_rows(
            driver, bill_no, coupon_detail_df,
            settled_amount=settled_amount, coupon_amount=coupon_amount,
        )
    except Exception as e:
        print(f"按券明细逐行修改失败：{e}，尝试汇总金额写入")
        try:
            _fill_coupon_summary_rows(driver, settled_amount, coupon_amount)
        except Exception as e2:
            print(f"修改收款单明细金额失败：{e2}，跳过保存")
            _click(387, 79)
            time.sleep(2)
            _click(160,228)
            return False


    time.sleep(2)
    # ---------- 7. 保存 ----------
    _click(156, 123) #保存

  
    time.sleep(5)

  
    _click(387, 79) #关闭
    time.sleep(2)
    print("开思券订单收款单，保存成功！")
    return True


def execute_coupon_return(driver, bill_no, skd_date, settled_amount, coupon_amount, invoice_type="已开票", coupon_detail_df=None):
    """开思券退货单：下推收款退款单并写入券折扣。

    :return: 是否成功写入金蝶
    """
    refund_amount = abs(settled_amount)
    print(
        f"开始处理开思券退货单：{bill_no}，"
        f"业务日期：{skd_date}，"
        f"退款金额：{refund_amount}，"
        f"开思券金额：{coupon_amount}，"
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
        print(f"已收款/已退款金额（{received_amount}）等于 价税合计（{total_amount}），无需下推，跳过")
        return False

    # ---------- 4. 下推生成收款退款单 ----------
    _click(38, 385)
    time.sleep(1)
    pyautogui.moveTo(580, 123, duration=1)
    time.sleep(1)
    _click(636, 229)
    time.sleep(5)

    refund_bill_title = driver.find_elements(By.XPATH, "//span[contains(text(), '收款退款单 - 新增')]")
    if not refund_bill_title:
        print("不符合下推退款规则！")
        return False

    # ---------- 5. 填写业务日期、银行账号 ----------
    bank_account = _select_bank_account(invoice_type)

    _click(1196, 320)
    time.sleep(1)
    pyperclip.copy(skd_date)
    pyautogui.hotkey("ctrl", "a")
    pyautogui.hotkey("ctrl", "v")
    time.sleep(1)
    _click(1393, 227)

    _fill_field((992, 693), bank_account)
    time.sleep(2)

    # ---------- 6. 纯 HTML 修改明细网格 ----------
    try:
        _fill_coupon_detail_rows(
            driver, bill_no, coupon_detail_df,
            settled_amount=refund_amount, coupon_amount=coupon_amount,
            amount_field="FREALREFUNDAMOUNT_S",
        )
    except Exception as e:
        print(f"按券明细逐行修改失败：{e}，尝试汇总金额写入")
        try:
            _fill_coupon_summary_rows(driver, refund_amount, coupon_amount, amount_field="FREALREFUNDAMOUNT_S")
        except Exception as e2:
            print(f"修改收款退款单明细金额失败：{e2}，跳过保存")
            _click(424, 75)
            time.sleep(2)
            _click(156,225)
            return False

    time.sleep(2)
    # ---------- 7. 提交/审核 ----------
    _click(305, 117)

    time.sleep(5)
    _click(424, 75)
    time.sleep(2)
    print("开思券退货单退款单，提交成功！")
    return True


def execute_coupon_bill(driver, bill_no, skd_date, settled_amount, coupon_amount, invoice_type="已开票", coupon_detail_df=None):
    """开思券场景统一入口。"""
    if settled_amount < 0:
        return execute_coupon_return(
            driver, bill_no, skd_date, settled_amount, coupon_amount,
            invoice_type=invoice_type, coupon_detail_df=coupon_detail_df
        )
    return execute_coupon_order(
        driver, bill_no, skd_date, settled_amount, coupon_amount,
        invoice_type=invoice_type, coupon_detail_df=coupon_detail_df
    )
