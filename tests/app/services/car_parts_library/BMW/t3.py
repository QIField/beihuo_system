# =================================================================
# 【方案 3】subprocess + 系统 curl（最稳方案）
# 场景：当 t4_test.py 显示系统 curl 可以成功，而 Python 都失败时使用
# 特点：不依赖任何 Python HTTP 库，完全等同于在命令行运行 curl
# 依赖：系统必须安装 curl（Win11 自带；Win10 1803+ 也自带；或手动安装）
# =================================================================
import numpy as np
import pandas as pd
import json
import time
import datetime
import re
import sys
import random
import pymysql
import winreg
import tkinter as tk
from tkinter import filedialog
import js2py
from lxml import etree
from openpyxl import load_workbook
import subprocess
import urllib3
urllib3.disable_warnings()


# ========================================================
# ===== 工具函数 =====
# ========================================================
def _build_header_list(cookie_str, referer=None):
    """把 headers 组装成 curl -H 'Key: Value' 这样的列表参数"""
    url = "https://www.dwp.bmw-brilliance.cn/sap(bD16aCZjPTEwMA==)/bc/bsp/bmw/gis_tp_par_dev/spp05_stock_check.htm"
    headers = {
        'Connection': 'keep-alive',
        'Cache-Control': 'max-age=0',
        'Authorization': 'Basic NDc5ODhQQVI6MldTWDNFREM0UkZWNVRHQg==',
        'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="99", "Google Chrome";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'Upgrade-Insecure-Requests': '1',
        'Origin': 'https://www.dwp.bmw-brilliance.cn',
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.74 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-User': '?1',
        'Sec-Fetch-Dest': 'frame',
        'Referer': referer if referer else url,
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Cookie': cookie_str
    }
    # 按 Chrome 真实顺序返回
    return list(headers.items())


def _debug_print(step_name, rc, text_len, text_preview, stderr=None):
    """统一调试输出格式"""
    print(f'\n[DEBUG] === {step_name} ===')
    print(f'[DEBUG] curl exit code: {rc}')
    print(f'[DEBUG] 响应长度: {text_len} 字符')
    print(f'[DEBUG] 前300字: {text_preview[:300]}')
    if stderr and len(stderr.strip()) > 0:
        print(f'[DEBUG] stderr: {stderr.strip()[:200]}')
    if text_len == 0:
        print('[DEBUG] [失败] 空响应')
    elif 'logon' in text_preview.lower() or '登录' in text_preview:
        print('[DEBUG] [警告]  返回登录/Logon 页面 → Cookie 失效')
    elif '不存在或未激活' in text_preview:
        print('[DEBUG] [信息]  零件号不存在或未激活（正常业务响应）')
    elif '<!-- Header  -->' in text_preview:
        print('[DEBUG] [成功] 返回库存查询页面（成功！）')


# ========================================================
# ===== 核心业务函数：查询单个零件的库存 =====
# ========================================================
def start(OE):
    """
    通过 subprocess 调用系统 curl 查询库存
    :param OE: 零件号，如 '36121116326'
    :return: 解析后的 DataFrame，出错时返回 []
    """
    global cookie

    today = str(datetime.datetime.today())[:10]
    url = "https://www.dwp.bmw-brilliance.cn/sap(bD16aCZjPTEwMA==)/bc/bsp/bmw/gis_tp_par_dev/spp05_stock_check.htm"
    payload = (
        f'onInputProcessing=atp_all&contentClip=&req_date={today}'
        f'&material={OE}&x=7&y=5'
    )
    headers_list = _build_header_list(cookie)

    # 构造 curl 命令参数列表（避免 shell=True 的安全问题）
    curl_cmd = ['curl', url, '-X', 'POST', '--insecure', '--compressed', '--silent']
    for k, v in headers_list:
        curl_cmd.extend(['-H', f'{k}: {v}'])
    curl_cmd.extend(['--data-raw', payload, '--max-time', '30'])

    try:
        result = subprocess.run(
            curl_cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=35
        )
        resp_text = result.stdout

        _debug_print(f'curl POST {OE}', result.returncode, len(resp_text), resp_text, result.stderr)

        if '不存在或未激活' in resp_text:
            print(f'[INFO] 未查询到零件: {OE}')
            time.sleep(2)
            return []

        # 提取 HTML 表格核心部分
        try:
            bb = str(resp_text).split('<!-- Header  -->')[1].split('<table  border="0" cellpadding="0" cellspacing="0">')[0]
        except IndexError:
            print(f'[WARN] {OE} 返回的 HTML 结构不符合预期')
            return []

        html = etree.HTML(bb)
        trs = html.xpath('/html/body/table/tr')
        if not trs or len(trs) < 3:
            print(f'[WARN] {OE} 解析到的表格行数不足')
            return []

        name_list = []
        value_list = []

        # 第 3 行：表头
        if len(trs) > 3:
            titles = trs[3].xpath('td')
            for k1, v1 in enumerate(titles):
                if k1 in [0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 12, 13, 14, 16, 17, 18, 20, 21, 22, 24, 25, 26, 28, 29, 30, 32, 33, 34]:
                    name = v1.xpath('text()')
                elif k1 in [7, 11, 15, 19, 23, 27, 31]:
                    name = v1.xpath('b/i/text()')
                else:
                    continue
                name = str(name).replace('[', '').replace(']', '').replace(' ', '').replace("'", '')
                name = name.replace('SY01', '-北京').replace('SY02', '-上海').replace('SY03', '-佛山')
                name = name.replace('SY06', '-成都').replace('SY07', '-沈阳').replace('SY08', '-合肥')
                name = name.replace('SY09', '-宁波')
                name_list.append(name)

        # 第 4 行：数据值
        bz_list = []
        if len(trs) > 4:
            values = trs[4].xpath('td')
            for k1, v1 in enumerate(values):
                if k1 == 0:
                    continue
                if k1 == 1:
                    oe = v1.xpath('a/text()')
                    oe = oe[0] if oe else ''
                    value_list.append(str(oe).replace(' ', ''))
                    oe2 = v1.xpath('text()')
                    oe2 = oe2[0] if oe2 else ''
                    value_list.append(str(oe2).replace(' ', ''))
                    continue
                elif k1 in [2, 3, 4, 5, 6, 8, 9, 10, 12, 13, 14, 16, 17, 18, 20, 21, 22, 24, 25, 26, 28, 29, 30, 32, 33, 34]:
                    oe = v1.xpath('text()')
                elif k1 in [7, 11, 15, 19, 23, 27, 31]:
                    oe = [str(v1.xpath('a/@onmouseover')).replace(' ', '').replace("doTooltip(event,'可用库存overreorderpoint:", '').replace("')", '').replace('["', '').replace('"]', '')]
                else:
                    continue
                try:
                    oe_val = str(oe[0]).replace(' ', '')
                except (IndexError, TypeError):
                    oe_val = ''
                if 'RMB' in oe_val:
                    oe_val = round(float(oe_val.replace('RMB', '').replace(',', '')) * 1.13, 2)
                value_list.append(oe_val)

        # 第 5 行：备注
        if len(trs) > 5:
            values5 = trs[5].xpath('td')
            for k1, v1 in enumerate(values5):
                if k1 == 2:
                    bz_list.append(str(v1.xpath('text()')).replace('[', '').replace(']', '').replace("'", ''))
        if len(bz_list) == 0:
            bz_list.append('')

        # 构造 DataFrame
        df1 = pd.DataFrame({'OE': [OE], '备注': bz_list})
        min_len = min(len(name_list), len(value_list))
        for i in range(min_len):
            col_name = name_list[i] if name_list[i] else f'col_{i}'
            df1[col_name] = [value_list[i]]

        return df1

    except FileNotFoundError:
        print('[ERROR] 未找到系统 curl！请检查：')
        print('        1. 打开 cmd，输入 curl --version 看是否有输出')
        print('        2. 若没有，请安装 curl 或改用 t1.py / t2.py 方案')
        return []
    except subprocess.TimeoutExpired:
        print(f'[ERROR] curl 请求超时 (>35s)')
        return []
    except Exception as e:
        print(f'[DEBUG] subprocess curl start() 异常: {e}')
        import traceback
        traceback.print_exc()
        time.sleep(2)
        return []


# ========================================================
# ===== 入口 =====
# ========================================================
if __name__ == '__main__':

    # ========================================================
    # ⚠️  关键：从 Hoppscotch 复制最新的完整 Cookie 粘贴到这里
    # ========================================================
    cookie = "sap-contextid=SID%3aANON%3apcqpdi44_CQP_44%3aeeFVG31p0xe5jSWeLAUwHjGly13Lxx3So6XR8ZUJ-NEW; TS0190948c=014e90d2cd280c239bdc9c3e0f6764c394fdb66d93b8bf097ce6ecf5570bbeb013f04e9f86d5e06b3afdb85fbc001b6d79fc53c73638eafe55ef7d60e2f90c868751f85cf7895380bd8a851ce6ccf78cbff5761f5ce3056e90f74e9c9c96cc96b26c6f8af2fa3845a73ef7c3d58be012dc48de78376d48f68411319f498640d16d3be96218c08639c1fa1eb15c6cdd67acb55c26309e8d63ea1eb782f89f1e5a99d770b76c6be64b3ec4c32dd27866e6ac1c9bf539d4ce87660e98a68446ef38bb13426b38db334b10a2257e3797fe78c53032c75bb02ac2ab68668d141eca5d5cac2fa1a774087fd2a3fbbb68cb76a316e01adcb9; sap-appcontext=c2FwLXNlc3Npb25pZD1TSUQlM2FBTk9OJTNhcGNxcGRpNDRfQ1FQXzQ0JTNhZWVGVllSUkZMYkNHV3VudXltQk12WndIcUhmS3h4MnhvNlVFbGd2OS1BVFQ%3d; TS01d0dca4=014e90d2cd61c371f3a2354f3d98b5662872ca4924b8bf097ce6ecf5570bbeb013f04e9f86d5e06b3afdb85fbc001b6d79fc53c73638eafe55ef7d60e2f90c868751f85cf7895380bd8a851ce6ccf78cbff5761f5ce3056e90f74e9c9c96cc96b26c6f8af2fa3845a73ef7c3d58be012dc48de78376d48f68411319f498640d16d3be96218882fef96356b0e74bd9b22ec72d30313391978f0ee0c5cc4dafb6b5cafd50de2; SelectedMaterials=; Order_Selected_materials=; _qimei_uuid42=1991c0f1f091000dd09c5505067aa9f81ee3184806; _qimei_i_3=5cf845d4925301d89593fd395e8d75e6a5eaa5a416525585e1897a5f72c7216b67613e943989e283d4aa; _qimei_h38=c79cc6f2d09c5505067aa9f80200000f21991c; _qimei_fingerprint=54550af90219e3b56fc9224203a3db6d; sap-usercontext=sap-client=100; BIGipServercqpcn.bmwbrill.cn_pool_8443=2345587466.64288.0000; MYSAPSSO2=AjQxMDMBABhDAE0AMAA3ADcAOQAwACAAIAAgACAAIAACAAYxADAAMAADABBDAFEAUAAgACAAIAAgACAABAAYMgAwADIANgAwADYAMQAyADAAMwAwADQABQAEAAAACAkAAjEA%2fwFWMIIBUgYJKoZIhvcNAQcCoIIBQzCCAT8CAQExCzAJBgUrDgMCGgUAMAsGCSqGSIb3DQEHATGCAR4wggEaAgEBMG8wZDELMAkGA1UEBhMCREUxHDAaBgNVBAoTE1NBUCBUcnVzdCBDb21tdW5pdHkxEzARBgNVBAsTClNBUCBXZWIgQVMxFDASBgNVBAsTC0kwMDIwNDc0MjYxMQwwCgYDVQQDEwNDUVACByAVCQIJU1kwCQYFKw4DAhoFAKBdMBgGCSqGSIb3DQEJAzELBgkqhkiG9w0BBwEwHAYJKoZIhvcNAQkFMQ8XDTI2MDYxMjAzMDQwNVowIwYJKoZIhvcNAQkEMRYEFAOHVRIGlhbSImUxxWih54XnduPGMAkGByqGSM44BAMELzAtAhUAyDFZuUlfe%2fseAFh0dxEetv3C1ioCFBuc0on9uJbRjcT9iNk2UiBPOm7f; _qimei_i_1=27c72bd192530388c7c1fc645b8d20e5f2eea1f1145c52d3bdd920582493206c616361973980ebdd8588dce5; lf_actionspage=spp05_order_create.htm%3foninputprocessing(update); ordtype_create=; date_create=; po_create=; sppbasket=; back_page=SPP05_ORDER_CREATE_FRAME.htm; SAP_SESSIONID_CQP_100=i4iNfZI4pEVUlnEQn12URS74HlVmHBHxtBnVHinbDGY%3d; TS016675fd=014e90d2cda0799d420525b9f503f61d34e5f344e56131994b7bbc5e317db714f5d3ae8de1539f1dd1864e41944039910c580229182cb5bf497b108648c5c55ea04cfc4ae0903f7c20424b0496868ccf5511270642b03c14fadf7610988e7acbee16dba3bf18358233aec2246332bd7fea1ad2a14a68eaa4341473989d0b4b985b3c768accf20a866246b7181c1645ecab96a6a74fde3a349ee9c35ba34d9a361839a28d660692f7cf4e0cff978a5392c0defa22c52abec97c92b3605842027ca142fff1eed1494e5257856acc836f02e75bc40be60cb9e8a94c8cd7e2e5551c278e2bc1a8beafe8b9d6f86f98a965a2811e630c53384e1f13557f5965fa54026e2edbdbc0"

    if '粘贴' in cookie or 'Hoppscotch' in cookie or len(cookie) < 50:
        print('[失败] 请先把 cookie 变量替换成真实的 Cookie 值！')
        print('   打开 Hoppscotch → 成功发送请求 → 复制请求头里 Cookie 的完整值')
        sys.exit(1)

    # 测试：查询单个零件号
    test_oe = '51749879093'
    result = start(test_oe)

    print('\n' + '=' * 60)
    if isinstance(result, pd.DataFrame) and len(result) > 0:
        print(f'[成功] subprocess curl 查询成功！零件: {test_oe}')
        print(result)
    else:
        print(f'[失败] 查询失败或无数据，零件: {test_oe}')
    print('=' * 60)
