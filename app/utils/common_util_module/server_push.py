import requests


def message_push(type: str, message: str):
    """
    推送信息到微信服务器

    :param type: 信息类型
    :param message: 信息内容
    :return: None
    """

    url = f"http://113.45.176.129:8001/wx/wx_warning_msg/write?type={type}&message={message}"

    payload = {}
    headers = {}

    response = requests.request("GET", url, headers=headers, data=payload)

    return response.json()

# if __name__ == "__main__":
#     result = message_push("test", "测试信息1")
#     print(result)
