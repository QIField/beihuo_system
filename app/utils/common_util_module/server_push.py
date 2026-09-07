import requests

from app.utils.logger_config import get_task_logger

logger = get_task_logger('server_push')


def message_push(type: str, message: str):
    """
    推送信息到微信服务器

    :param type: 信息类型
    :param message: 信息内容
    :return: 接口返回的 JSON 数据，失败时返回包含 error 的字典
    """

    url = f"http://113.45.176.129:8001/wx/wx_warning_msg/write?type={type}&message={message}"

    payload = {}
    headers = {}

    logger.info(f"[消息推送] type={type}, url={url}")
    try:
        response = requests.request("GET", url, headers=headers, data=payload, timeout=10)
        response.raise_for_status()
        result = response.json()
        logger.info(f"[消息推送] 成功，响应：{result}")
        return result
    except requests.exceptions.Timeout:
        logger.error(f"[消息推送] 请求超时，type={type}")
        return {"error": "timeout"}
    except requests.exceptions.RequestException as e:
        logger.error(f"[消息推送] 请求异常，type={type}, 异常：{e}")
        return {"error": str(e)}
    except Exception as e:
        logger.exception(f"[消息推送] 解析响应失败，type={type}")
        return {"error": str(e)}

# if __name__ == "__main__":
#     result = message_push("test", "测试信息1")
#     print(result)
