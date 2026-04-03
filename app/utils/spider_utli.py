# -*- coding:utf-8 -*-
# @Time    : 2026/3/30 11:05
# @Author  : xingkongtub
# @Project : overall_project
# @File    : spider_utli.py
# @Software: PyCharm

# 详细完整版 requests 爬虫
import requests


# 爬虫工具方法
def simple_spider(url, headers):
    """
    完整爬虫函数：带异常处理、请求头、超时、编码处理
    """

    # print(url)

    # headers = {
    #     # 模拟浏览器请求头（必须加，否则很多网站会拦截）
    #     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0",
    #     "authorization": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJjbGllbnQueGhhZG1pbiIsImF1ZCI6InNlcnZlci54aGFkbWluIiwiaWF0IjoxNzc0NDExMzY4LCJleHAiOjE3NzcwMDMzNjgsInVpZCI6IjYzNCIsIm5hbWUiOiJcdTVlYjdcdTRmMWZcdTYyNmMiLCJhZG1pbl9zd2l0Y2hfbG9naW4iOiIifQ.PJG68YIjRE02FvZUO18ODrb0QZGpbfv56axtcH50zmQ",
    # }

    try:

        # ===================== 2. 发送请求 =====================
        response = requests.get(
            url=url,
            headers=headers,  # 请求头
            timeout=100,  # 超时时间100秒
            allow_redirects=True  # 允许自动跳转
        )

        # ===================== 3. 状态码判断 =====================
        if response.status_code == 200:
            # 自动处理编码，解决中文乱码
            response.encoding = response.apparent_encoding

            # ===================== 4. 获取数据 =====================
            json = response.json()  # json数据
            # content = response.content  # 二进制数据（图片/文件）

            print("请求成功！")
            print("状态码：", response.status_code)
            print("网页编码：", response.encoding)

            return json
        else:
            print(f" 请求失败，状态码：{response.status_code}")
            return None

    # ===================== 异常处理 =====================
    except requests.exceptions.Timeout:
        print("请求超时！")
    except requests.exceptions.ConnectionError:
        print("连接失败！请检查网络或网址")
    except Exception as e:
        print(f"发生错误：{str(e)}")
