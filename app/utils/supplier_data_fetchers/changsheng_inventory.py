import requests
import json
import uuid
import time
from datetime import datetime, timedelta
import pandas as pd


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
            print(f"请求失败，状态码: {response.status_code}")
            return None

    except Exception as e:
        print(f"发生异常: {str(e)}")
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
    try:
        response = requests.post(url, headers=headers, data=json.dumps(request_data))
        if response.status_code == 200:
            result = response.json()
            if result["head"]["status"] == '200':
                print(f"成功获取第{page_index}页数据，共{len(result['body']['parts'])}条记录")
                return result["body"]['parts']
            else:
                return []
        else:
            return []

    except Exception as e:
        print(f"发生异常: {str(e)}")
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
        time.sleep(2)

    print(f"共获取{len(all_parts)}条配件数据")
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


def start():
    """
    广州昌盛库存数据
    :return:
    """
    df = get_all_parts('8364491E669A4E7BA272862935A60909', '39119D4F8B344124AEE6D20C90829034', page_size=2000,
                       update_time=None)
    df['stock_amount'] = df['stock_amount'].astype(int)
    df['供应商名称'] = '广州昌盛'
    # OE码处理：去空格 → 去掉末尾非数字
    df['原厂OE码'] = df['part_number'].str.replace(' ', '')
    df['原厂OE码'] = df['原厂OE码'].apply(remove_trailing_non_digit)
    df['品牌'] = df['brand_name']
    df['价格'] = df['sale_price']
    tomorrow_ts = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    df['失效时间'] = str(tomorrow_ts)
    df['仓库名称'] = '广州越秀仓'
    df['库存'] = df['stock_amount']
    df['备注'] = ''
    df = df[['供应商名称', '原厂OE码', '品牌', '价格', '失效时间', '仓库名称', '库存', '备注']]

    df.loc[df['品牌'] == '原厂国外', '品牌'] = '原厂'
    df.loc[df['品牌'] == '原厂大库', '品牌'] = '原厂国内4s件'
    df.loc[df['品牌'] == '赛多夫', '品牌'] = '巴博瑞'
    df.loc[df['品牌'] == '猫头鹰', '品牌'] = '伦福德(猫)'

    # OE以80结尾且品牌为"原厂再制造"的，映射为"原厂国内4s件"，并在备注插入"是惠选件！！！"
    mask = (df['原厂OE码'].str.endswith('80')) & (df['品牌'] == '原厂再制造')
    df.loc[mask, '品牌'] = '原厂国内4s件'
    df.loc[mask, '备注'] = '是惠选件！！！'

    df.loc[df['库存'] > 30, '库存'] = 30

    return df


if __name__ == "__main__":
    start()



