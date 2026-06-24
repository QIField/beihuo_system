import requests
import json

def fetch_realtime_part_info_bmw(part_number, cookie=None, base_url="http://x.fsbbr.net"):
    """
    实时获取宝马零件信息
    
    Args:
        part_number (str): 零件编号
        cookie (str, optional): BMW Brilliance 登录态 Cookie，不传时使用配置中的 Cookie
        base_url (str): 基础URL，默认为 http://x.fsbbr.net
    
    Returns:
        dict: 响应结果
    """
    url = f"{base_url}/new/api/car-parts/bmw/fetch-realtime"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    payload = {
        "key": "7Y4Y6RNdkDCwTJDJEBWz",
        "part_number": part_number
    }
    
    if cookie:
        payload["cookie"] = cookie
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()  # 检查HTTP错误
        return response.json()
    except requests.exceptions.RequestException as e:
        return {
            "code": 500,
            "msg": f"请求失败: {str(e)}",
            "data": None
        }

# 使用示例
if __name__ == "__main__":
    # 调用函数（使用系统配置中的 Cookie）
    
    cookie = "sap-contextid=SID%3aANON%3apcqpdi45_CQP_45%3a_Kg1E8l4lLNOmcctW8NR0HozJhC-TFMmOuAkjvmx-NEW; TS0190948c=014e90d2cd21cbb8a51ffc28beda15c054243d04cab8ffaea2d614ff93d05c3001ea7df0e55b7238dcb8037bb5eeb49504e9cac767891059d24aecfc75f0f7854373c3ba26d5ff65560a2de2c7c2b9f7053e8a131db950e841a92af8baf703644f713418c7ef5ea607f4ecf3b1d7e443ba1c70d6dc5a310cf11af843f51dea1aab934f5156920337b769a4abd0ae1f931d6dbae53096a031ede7786fcfe6a98bfb450a184b5e79e8852e8153412705648aace485235138f0ba4956b4866e3c61f84fc24a93d7c11d190acdadd6835e54737064afec781270b6bf62f78b8213d97212335e18; sap-appcontext=c2FwLXNlc3Npb25pZD1TSUQlM2FBTk9OJTNhcGNxcGRpNDVfQ1FQXzQ1JTNhX0tnMVpZS3hNRmsyN2hoRkVSTnJ5Y2RKRzZTX1RGTlhPdUR4bnpkZC1BVFQ%3d; TS01d0dca4=014e90d2cd386108b5935fd9f9ba081f9349634aa0b8ffaea2d614ff93d05c3001ea7df0e55b7238dcb8037bb5eeb49504e9cac767891059d24aecfc75f0f7854373c3ba26d5ff65560a2de2c7c2b9f7053e8a131db950e841a92af8baf703644f713418c7ef5ea607f4ecf3b1d7e443ba1c70d6dc8269fb6c504b678909570c50a2cdc036cb65990e9f07f6889479f88de9ca8195; SelectedMaterials=; Order_Selected_materials=; _qimei_uuid42=1991c0f1f091000dd09c5505067aa9f81ee3184806; _qimei_i_3=5cf845d4925301d89593fd395e8d75e6a5eaa5a416525585e1897a5f72c7216b67613e943989e283d4aa; _qimei_h38=c79cc6f2d09c5505067aa9f80200000f21991c; _qimei_fingerprint=54550af90219e3b56fc9224203a3db6d; BIGipServercqpcn.bmwbrill.cn_pool_8443=2362364682.64288.0000; sap-usercontext=sap-client=100; MYSAPSSO2=AjQxMDMBABhDAE0AMAA3ADcAOQAwACAAIAAgACAAIAACAAYxADAAMAADABBDAFEAUAAgACAAIAAgACAABAAYMgAwADIANgAwADYAMQA3ADAAMgA0ADcABQAEAAAACAkAAjEA%2fwFXMIIBUwYJKoZIhvcNAQcCoIIBRDCCAUACAQExCzAJBgUrDgMCGgUAMAsGCSqGSIb3DQEHATGCAR8wggEbAgEBMG8wZDELMAkGA1UEBhMCREUxHDAaBgNVBAoTE1NBUCBUcnVzdCBDb21tdW5pdHkxEzARBgNVBAsTClNBUCBXZWIgQVMxFDASBgNVBAsTC0kwMDIwNDc0MjYxMQwwCgYDVQQDEwNDUVACByAVCQIJU1kwCQYFKw4DAhoFAKBdMBgGCSqGSIb3DQEJAzELBgkqhkiG9w0BBwEwHAYJKoZIhvcNAQkFMQ8XDTI2MDYxNzAyNDc1MFowIwYJKoZIhvcNAQkEMRYEFM%2fYZ2QjqPW5KrEgjO8TXsCwzO68MAkGByqGSM44BAMEMDAuAhUAwlEhJs9iMBvuN%2fSTkaVheuEmhOkCFQCyJmEMo5mUVYodt9tw30UceFmCTA%3d%3d; SAP_SESSIONID_CQP_100=i3GLOSqq61RKnxoczv3_rO5WTI9p9hHxhn9zrUlrRiU%3d; lf_actionspage=spp05_order_create.htm%3foninputprocessing(update); ordtype_create=; date_create=; po_create=; sppbasket=; back_page=SPP05_ORDER_CREATE_FRAME.htm; TS016675fd=014e90d2cd8ba86a8949baba6af8dc176dc4e1baa5b8ffaea2d614ff93d05c3001ea7df0e55b7238dcb8037bb5eeb49504e9cac767891059d24aecfc75f0f7854373c3ba26d5ff65560a2de2c7c2b9f7053e8a131db950e841a92af8baf703644f713418c7ef5ea607f4ecf3b1d7e443ba1c70d6dc5a310cf11af843f51dea1aab934f5156920337b769a4abd0ae1f931d6dbae53096a031ede7786fcfe6a98bfb450a184b5e79e8852e8153412705648aace485235138f0ba4956b4866e3c61f84fc24a9310eca868ca23cf7862781fbb15de11956b459f4d2d2361fd3d8865bc01aa9e4b4aa40a088ba5fb48e0d6448c26c18d45; _qimei_i_1=73dd7fd192530388c7c1fc645b8d20e5f2eea1f1145c52d3bdd920582493206c616361973980ebdd8597c5e6"
    cookie = None
    result = fetch_realtime_part_info_bmw("16117474991",cookie=cookie)
    
    # 处理结果
    if result.get('code') == 200:
        for key, value in result.get('data', {}).get('detail', {}).items():
           print(f"  {key}: {value}")
        print("=" * 50)
        for key, value in result.get('data', {}).get('stock', {}).items():
            print(f"  {key}: {value}")
        print("=" * 50)
    else:
        print(f"获取失败: {result.get('msg')}")