import requests
import json
import uuid
import time
from datetime import datetime, timedelta
import pandas as pd
from app.utils.logger_config import get_task_logger
from ..brands import normalize_brand
from ..persistence import save_changsheng_raw_data


logger = get_task_logger('virtual_inventory')



def shichedao_login(api_key, api_secret):
    """
    获取access_token
    :param api_key:
    :param api_secret:
    :return:
    """
    # 请求URL
    url = "https://erp.shichedao.com/erpapi/v2/login"
    # 请求头
    headers = {
        "Content-Type": "application/json"
    }
    # 生成请求参数
    request_data = {
        "head": {
            "time_stamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "request_no": str(uuid.uuid4()).replace("-", "").upper(),
            "platform": "0"  # 假设平台值为3，根据实际情况修改
        },
        "body": {
            "api_key": api_key,
            "api_secret": api_secret
        }
    }

    try:
        # 发送POST请求
        response = requests.post(url, headers=headers, data=json.dumps(request_data))
        result = json.loads(response.text)
        if result['head']['status'] == "200":
            access_token = result['body']['access_token']
            return access_token
        else:
            logger.error(f"请求失败，状态码: {response.status_code}")
            return None

    except Exception:
        logger.exception(f"获取 access_token 时发生异常")
        return None


def get_parts_list(access_token, page_index=1, page_size=1000, update_time=None):
    """
    获取配件信息分页数据
    :param access_token: 登录接口获取的访问令牌
    :param page_index: 分页序号，从1开始
    :param page_size: 每页大小，最大5000
    :param update_time: 更新时间，格式为"yyyy-MM-dd HH:mm:ss"，传None获取全量数据
    :return: 配件列表数据或None
    """
    url = "https://erp.shichedao.com/erpapi/v2/part/list"
    headers = {
        "Content-Type": "application/json",
        "Authorization": access_token
    }
    request_data = {
        "head": {
            "time_stamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "request_no": str(uuid.uuid4()).replace("-", "").upper(),
            "platform": "0"  # 假设平台值为0，根据实际情况修改
        },
        "body": {
            "page_index": page_index,
            "page_size": page_size
        }
    }
    # 如果有更新时间参数
    if update_time:
        request_data["body"]["update_time"] = update_time
    for attempt in range(3):
        try:
            response = requests.post(url, headers=headers, data=json.dumps(request_data), timeout=30)
            if response.status_code == 429:
                wait_time = 3 + attempt * 2
                logger.warning(f"获取第{page_index}页触发429限流，等待{wait_time}秒后重试({attempt + 1}/3)")
                time.sleep(wait_time)
                continue
            if response.status_code == 200:
                result = response.json()
                if result.get("head", {}).get("status") == '200':
                    logger.info(f"成功获取第{page_index}页数据，共{len(result['body']['parts'])}条记录")
                    return result["body"]['parts']
                else:
                    return []
            else:
                return []
        except Exception:
            logger.exception(f"获取配件列表第{page_index}页时发生异常")
            return []
    return []


def get_all_parts(api_key, api_secret, page_size=1000, update_time=None):
    """
    获取所有配件信息（自动分页）
    :param access_token: 登录接口获取的访问令牌
    :param page_size: 每页大小，最大5000
    :param update_time: 更新时间，格式为"yyyy-MM-dd HH:mm:ss"
    :return: 所有配件数据的列表
    """
    access_token = shichedao_login(api_key, api_secret)
    if update_time:
        # 时间戳转日期格式
        try:
            date_obj = datetime.fromtimestamp(int(update_time))
            update_time = date_obj.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            pass

    all_parts = []
    page_index = 1

    while True:
        # 获取当前页数据
        parts_list = get_parts_list(access_token, page_index, page_size, update_time)
        if len(parts_list) == 0:
            break
        # 添加当前页数据到总列表
        all_parts.extend(parts_list)
        # 如果当前页数据小于page_size，说明是最后一页
        if len(parts_list) < page_size:
            break
        # 下一页
        page_index += 1
        # 根据接口要求，每秒最多1次请求
        time.sleep(5)

    logger.info(f"共获取{len(all_parts)}条配件数据")
    all_parts = pd.DataFrame(all_parts)
    return all_parts


def remove_trailing_non_digit(oe_str):
    """去掉末尾非数字字符"""
    if pd.isna(oe_str):
        return oe_str
    oe_str = str(oe_str)
    while oe_str and not oe_str[-1].isdigit():
        oe_str = oe_str[:-1]
    return oe_str


def remove_trailing_sequence(oe_str):
    """12/13位编码去除末尾01-09"""
    if pd.isna(oe_str):
        return oe_str
    oe_str = str(oe_str)
    if len(oe_str) in (12, 13) and oe_str[-2:] in ('01', '02', '03', '04', '05', '06', '07', '08', '09'):
        return oe_str[:-2]
    return oe_str


def start():
    """
    广州昌盛库存数据
    :return:
    """
    df = get_all_parts('8364491E669A4E7BA272862935A60909', '2167511AE9734D7F80E5F010AF5A05B6', page_size=2000,
                       update_time=None)

    # 保存原始数据到 changsheng_raw_inventory（与清洗流程并行，失败不影响主流程）
    save_changsheng_raw_data(df.copy())

    df['stock_amount'] = df['stock_amount'].astype(int)
    df['供应商名称'] = '广州昌盛'
    # OE码处理：去空格 → 去掉末尾非数字 → 12/13位末尾01-09去除
    df['原厂OE码'] = df['part_number'].str.replace(' ', '')
    df['原厂OE码'] = df['原厂OE码'].apply(remove_trailing_non_digit)
    df['原厂OE码'] = df['原厂OE码'].apply(remove_trailing_sequence)
    df['品牌'] = df['brand_name']
    df['价格'] = df['sale_price']
    tomorrow_ts = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    df['失效时间'] = str(tomorrow_ts)
    df['仓库名称'] = '广州越秀仓'
    df['库存'] = df['stock_amount']
    df['备注'] = ''
    df = df[['供应商名称', '原厂OE码', '品牌', '价格', '失效时间', '仓库名称', '库存', '备注']]

    df['品牌'] = df['品牌'].apply(normalize_brand)

    # OE以80结尾且品牌为"原厂再制造"的，映射为"原厂国内4s件"，并在备注插入"是惠选件！！！"
    mask = (df['原厂OE码'].str.endswith('80')) & (df['品牌'] == '原厂再制造')
    df.loc[mask, '品牌'] = '原厂国内4s件'
    df.loc[mask, '备注'] = '是惠选件！！！'

    df.loc[df['库存'] > 30, '库存'] = 30

    # 库存为1的记录统一更新为12（原始数据表已在此之前保存，不受影响）
    stock_eq_1_count = int((df['库存'] == 1).sum())
    if stock_eq_1_count > 0:
        df.loc[df['库存'] == 1, '库存'] = 12
        logger.info(f"[昌盛库存] 库存为1的记录 {stock_eq_1_count} 条，已更新为12")
    else:
        logger.info("[昌盛库存] 无库存为1的记录，跳过更新")

    # 验证：确认库存为1的记录已清零，且更新数量正确
    remaining_eq_1 = int((df['库存'] == 1).sum())
    updated_eq_12 = int((df['库存'] == 12).sum())
    logger.info(f"[昌盛库存] 验证结果：库存为1剩余 {remaining_eq_1} 条，库存为12共 {updated_eq_12} 条")

    return df


if __name__ == "__main__":
    start()
