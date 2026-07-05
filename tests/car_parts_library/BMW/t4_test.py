# =================================================================
# 【步骤 1：诊断测试】——对比 Python requests vs 系统 curl 的差异
# 先跑这个文件，确认到底是 Cookie 问题 / 参数问题 / 还是环境（TLS 指纹）问题
# =================================================================
import requests
import subprocess
import sys
import urllib3
urllib3.disable_warnings()

# ================================================================
# ⚠️  关键步骤：从 Hoppscotch 复制最新的完整 Cookie 值粘贴到下面
#     1. 在 Hoppscotch 中成功发送一次请求
#     2. 找到请求头里的 Cookie 那一整行
#     3. 复制所有内容，替换下面引号里的文字
# ================================================================
cookie = "sap-contextid=SID%3aANON%3apcqpdi44_CQP_44%3aeeFVG31p0xe5jSWeLAUwHjGly13Lxx3So6XR8ZUJ-NEW; TS0190948c=014e90d2cd280c239bdc9c3e0f6764c394fdb66d93b8bf097ce6ecf5570bbeb013f04e9f86d5e06b3afdb85fbc001b6d79fc53c73638eafe55ef7d60e2f90c868751f85cf7895380bd8a851ce6ccf78cbff5761f5ce3056e90f74e9c9c96cc96b26c6f8af2fa3845a73ef7c3d58be012dc48de78376d48f68411319f498640d16d3be96218c08639c1fa1eb15c6cdd67acb55c26309e8d63ea1eb782f89f1e5a99d770b76c6be64b3ec4c32dd27866e6ac1c9bf539d4ce87660e98a68446ef38bb13426b38db334b10a2257e3797fe78c53032c75bb02ac2ab68668d141eca5d5cac2fa1a774087fd2a3fbbb68cb76a316e01adcb9; sap-appcontext=c2FwLXNlc3Npb25pZD1TSUQlM2FBTk9OJTNhcGNxcGRpNDRfQ1FQXzQ0JTNhZWVGVllSUkZMYkNHV3VudXltQk12WndIcUhmS3h4MnhvNlVFbGd2OS1BVFQ%3d; TS01d0dca4=014e90d2cd61c371f3a2354f3d98b5662872ca4924b8bf097ce6ecf5570bbeb013f04e9f86d5e06b3afdb85fbc001b6d79fc53c73638eafe55ef7d60e2f90c868751f85cf7895380bd8a851ce6ccf78cbff5761f5ce3056e90f74e9c9c96cc96b26c6f8af2fa3845a73ef7c3d58be012dc48de78376d48f68411319f498640d16d3be96218882fef96356b0e74bd9b22ec72d30313391978f0ee0c5cc4dafb6b5cafd50de2; SelectedMaterials=; Order_Selected_materials=; _qimei_uuid42=1991c0f1f091000dd09c5505067aa9f81ee3184806; _qimei_i_3=5cf845d4925301d89593fd395e8d75e6a5eaa5a416525585e1897a5f72c7216b67613e943989e283d4aa; _qimei_h38=c79cc6f2d09c5505067aa9f80200000f21991c; _qimei_fingerprint=54550af90219e3b56fc9224203a3db6d; sap-usercontext=sap-client=100; BIGipServercqpcn.bmwbrill.cn_pool_8443=2345587466.64288.0000; MYSAPSSO2=AjQxMDMBABhDAE0AMAA3ADcAOQAwACAAIAAgACAAIAACAAYxADAAMAADABBDAFEAUAAgACAAIAAgACAABAAYMgAwADIANgAwADYAMQAyADAAMwAwADQABQAEAAAACAkAAjEA%2fwFWMIIBUgYJKoZIhvcNAQcCoIIBQzCCAT8CAQExCzAJBgUrDgMCGgUAMAsGCSqGSIb3DQEHATGCAR4wggEaAgEBMG8wZDELMAkGA1UEBhMCREUxHDAaBgNVBAoTE1NBUCBUcnVzdCBDb21tdW5pdHkxEzARBgNVBAsTClNBUCBXZWIgQVMxFDASBgNVBAsTC0kwMDIwNDc0MjYxMQwwCgYDVQQDEwNDUVACByAVCQIJU1kwCQYFKw4DAhoFAKBdMBgGCSqGSIb3DQEJAzELBgkqhkiG9w0BBwEwHAYJKoZIhvcNAQkFMQ8XDTI2MDYxMjAzMDQwNVowIwYJKoZIhvcNAQkEMRYEFAOHVRIGlhbSImUxxWih54XnduPGMAkGByqGSM44BAMELzAtAhUAyDFZuUlfe%2fseAFh0dxEetv3C1ioCFBuc0on9uJbRjcT9iNk2UiBPOm7f; _qimei_i_1=27c72bd192530388c7c1fc645b8d20e5f2eea1f1145c52d3bdd920582493206c616361973980ebdd8588dce5; lf_actionspage=spp05_order_create.htm%3foninputprocessing(update); ordtype_create=; date_create=; po_create=; sppbasket=; back_page=SPP05_ORDER_CREATE_FRAME.htm; SAP_SESSIONID_CQP_100=i4iNfZI4pEVUlnEQn12URS74HlVmHBHxtBnVHinbDGY%3d; TS016675fd=014e90d2cda0799d420525b9f503f61d34e5f344e56131994b7bbc5e317db714f5d3ae8de1539f1dd1864e41944039910c580229182cb5bf497b108648c5c55ea04cfc4ae0903f7c20424b0496868ccf5511270642b03c14fadf7610988e7acbee16dba3bf18358233aec2246332bd7fea1ad2a14a68eaa4341473989d0b4b985b3c768accf20a866246b7181c1645ecab96a6a74fde3a349ee9c35ba34d9a361839a28d660692f7cf4e0cff978a5392c0defa22c52abec97c92b3605842027ca142fff1eed1494e5257856acc836f02e75bc40be60cb9e8a94c8cd7e2e5551c278e2bc1a8beafe8b9d6f86f98a965a2811e630c53384e1f13557f5965fa54026e2edbdbc0"

url = "https://www.dwp.bmw-brilliance.cn/sap(bD16aCZjPTEwMA==)/bc/bsp/bmw/gis_tp_par_dev/spp05_stock_check.htm"
payload = "onInputProcessing=atp_all&contentClip=&req_date=2026-06-12&material=36121116326&x=7&y=5"

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
    'Referer': 'https://www.dwp.bmw-brilliance.cn/sap(bD16aCZjPTEwMA==)/bc/bsp/bmw/gis_tp_par_dev/spp05_stock_check.htm',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Cookie': cookie
}


def _analyze_response(text):
    """简单分析响应内容，判断是否成功"""
    if len(text) == 0:
        return "❌ 空响应"
    if 'logon' in text.lower() or '登录' in text.lower() or 'MYSAPSSO2' in text:
        return "⚠️  返回登录页面 / Cookie 可能无效"
    if '不存在或未激活' in text:
        return "⚠️  零件号不存在或未激活（请求成功，但该号无库存）"
    if '<!-- Header  -->' in text:
        return "✅ 成功！返回库存 HTML 页面"
    if 'html' in text.lower() and 'body' in text.lower():
        return "✅ 返回 HTML 页面（需进一步解析是否为库存页）"
    return f"ℹ️  返回 {len(text)} 字符，需人工判断"


# ========== 测试 1：Python requests ==========
print("=" * 60)
print("[工具] 测试 1 / 2：Python requests 库")
try:
    r = requests.post(url, headers=headers, data=payload,
                      verify=False, timeout=30, allow_redirects=True)
    status = f"状态码 {r.status_code}, 长度 {len(r.text)} 字符"
    result = _analyze_response(r.text)
    print(f"  {status}")
    print(f"  分析结果: {result}")
    if len(r.text) > 0:
        print(f"  前 300 字: {r.text[:300]}")
    if r.status_code != 200:
        print(f"  [警告]  响应头: {dict(r.headers)}")
except Exception as e:
    print(f"  [失败] 异常: {e}")


# ========== 测试 2：系统 curl 命令 ==========
print("\n" + "=" * 60)
print("[测试] 测试 2 / 2：系统 curl 命令")
try:
    curl_cmd = ['curl', url, '-X', 'POST', '--insecure', '-s', '--compressed']
    for k, v in headers.items():
        curl_cmd.extend(['-H', f'{k}: {v}'])
    curl_cmd.extend(['--data-raw', payload, '--max-time', '30'])

    print(f"  (curl 命令长度: {len(' '.join(curl_cmd))} 字符)")
    r = subprocess.run(curl_cmd, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=35)
    status = f"exit={r.returncode}, 长度 {len(r.stdout)} 字符"
    result = _analyze_response(r.stdout)
    print(f"  {status}")
    print(f"  分析结果: {result}")
    if len(r.stdout) > 0:
        print(f"  前 300 字: {r.stdout[:300]}")
    # 如果有 stderr 也打印（方便排查 SSL 等问题）
    if r.stderr and len(r.stderr.strip()) > 0:
        print(f"  stderr: {r.stderr.strip()[:200]}")
except FileNotFoundError:
    print("  [失败] 系统没有安装 curl 或 curl 不在 PATH 中")
except Exception as e:
    print(f"  [失败] 异常: {e}")


# ========== 总结 ==========
print("\n" + "=" * 60)
print("[统计] 结论建议：")
print("  · 如果两个测试都失败 → Cookie 过期了，去 Hoppscotch 重新抓一份")
print("  · 如果测试1( requests )失败，测试2( curl )成功 → 是 Python 环境/TLS指纹问题")
print("       → 下一步运行: t2.py (curl_cffi 方案) 或 t3.py (subprocess 方案)")
print("  · 如果两个测试都成功 → 可以用最简单的 t1.py (requests Session 方案)")
print("=" * 60)
