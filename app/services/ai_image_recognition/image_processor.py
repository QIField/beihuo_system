import json
import os

from typing import Any, Dict, List, Union


import requests

from app.dao.external_system_dao.wx_chat_image import get_image_list



###临时加载.env文件
from pathlib import Path
from dotenv import load_dotenv
BASE_DIR = Path(__file__).resolve().parent.parent
# .env 文件路径（项目根目录下的 .env）
ENV_PATH = BASE_DIR / ".env"

# 加载 .env 文件中的环境变量
load_dotenv(dotenv_path=ENV_PATH)


ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
ARK_ENDPOINT_ID = os.getenv("ARK_ENDPOINT_ID", "")
ARK_API_KEY = os.getenv("ARK_API_KEY", "")
ARK_MODEL = ARK_ENDPOINT_ID




# 汽配行业常用品牌词表 —— 用于正确切分「价格+品牌连写」的边界（如 41尼盛斯、60费比）。
# 只保留高频中文/中文(英文)形式，去掉纯英文重复项，避免提示词过长。
# 业务中发现新品牌时按需补充中文形式即可。
COMMON_PARTS_BRANDS = (
    "原厂件",
    "博世", "博世(BOSCH)",
    "曼牌", "曼牌(MANN)",
    "马勒", "马勒(MAHLE)",
    "海拉", "海拉(HELLA)", "海拉(HELLA)HL",
    "费比", "费比(febi)",
    "尼盛斯", "尼盛斯(NISSENS)",
    "布雷博", "布雷博(brembo)",
    "泰明顿", "泰明顿(TEXTAR)",
    "曼克马利", "曼克马利(MENKMARI)",
    "依纳", "依纳(INA)", "依纳(INA)INA",
    "舍弗勒",
    "盖茨",
    "大陆", "马牌",
    "皮尔博格",
    "法雷奥",
    "电装",
    "德尔福",
    "爱信",
    "采埃孚",
    "博格华纳",
    "霍尼韦尔",
    "爱尔铃克铃尔",
    "辉门",
)

# 把品牌列表拼接成提示词里可直接嵌入的一行字符串
COMMON_BRANDS_TEXT = "、".join([f"「{b}」" for b in COMMON_PARTS_BRANDS])


# 报价记录 JSON Schema —— 方舟 json_schema(strict:true) 严格约束输出
# 同一条询价 + 同一报价人返回的多条报价，合并放入"报价信息"数组
QUOTATION_JSON_SCHEMA = {
    "name": "quotation_records",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "records": {
                "type": "array",
                "description": "从聊天截图中按顺序提取出的每一条询价-报价记录列表。",
                "items": {
                    "type": "object",
                    "properties": {
                        "序号": {"type": "integer", "description": "记录的顺序编号，从 1 开始递增。"},
                        "询价人": {"type": "string", "description": "发出 OE 询价的联系人昵称。"},
                        "询价OE": {"type": "string", "description": "被询价的 OE / 配件编号。"},
                        "报价人": {"type": "string", "description": "给出报价的联系人昵称。"},
                        "报价信息": {
                            "type": "array",
                            "description": "该报价人针对该询价 OE 给出的全部报价条目（可能是多条，如主件/替代件）。",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "报价OE": {"type": "string", "description": "本条报价的 OE / 替代号。"},
                                    "品质": {"type": "string", "description": "本条报价的品质 / 品牌信息，如原厂件、海拉(HELLA)HL。"},
                                    "价格": {"type": "number", "description": "本条报价数值，取不到填 0。"},
                                },
                                "required": ["报价OE", "品质", "价格"],
                                "additionalProperties": False,
                            },
                        },
                    },
                    "required": ["序号", "询价人", "询价OE", "报价人", "报价信息"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["records"],
        "additionalProperties": False,
    },
}


QUOTATION_PROMPT = (
    "你是汽配微信报价聊天截图解析助手，输出结构化报价 records 数组。\n"
    "## 角色与边界\n"
    "- 本图是聊天片段截图，可能上下被截断。只提取**在本图内能完整配对**的「询价消息 + 其后面的报价消息」。\n"
    "- 系统通知（撤回/入群等）、时间戳、日期、星期行、闲聊（如「稍等」「ok」「@某某 下班了吗」）**绝对不能打断配对**，跳过即可。\n\n"
    "## 核心配对规则（最重要）\n"
    "1. **询价人 ≠ 报价人**：一条记录中，询价人是发出 OE 询价的人，报价人是**另一个人**（发出报价气泡回复的人）。"
    "询价人自己后来发的任何消息（哪怕含 OE+价格+品牌），都**不算报价**，不能放进报价信息数组。\n"
    "2. 询价消息：某人气泡里只发一个 OE 号（或以 OE 号为主、几乎无其它文字）的消息。\n"
    "3. 报价消息：该询价之后、下一条不同询价之前，由**其他联系人**发出的、对该 OE 的回复气泡。"
    "报价门槛 = 报价OE + 价格；没写品牌时品质填「品牌没写」，仍算有效报价。\n"
    "4. 同一报价人对同一询价 OE 在同一气泡给出的多条报价（气泡内多行 / 以「=OE号」开头的行），"
    "合并进入同一条 record 的「报价信息」数组。\n"
    "5. **报价人去重**：报价人字段只填一个昵称（就是报价气泡发送者）。"
    "绝对不能把询价人名字用逗号拼接进报价人字段；如多人分别报价，应分成多条不同序号的 record。\n"
    "6. **报价条目去重**：同一 record 的报价信息数组内，若出现「同一报价OE + 同一品质 + 同一价格」的重复条目，只保留一条。\n\n"
    "## 字段填写规则\n"
    "- 询价人/报价人昵称：按气泡旁可识别文字原样填；无法识别的特殊图标/表情/贴纸/自定义字体填「用户名为特殊图标」，不能为空，不能猜名字。\n"
    "- 序号：从 1 开始递增。\n"
    "- OE 编号：大小写、前后缀与图片完全一致。\n"
    "- 品质：图片有文字则原样（如「原厂件」「海拉(HELLA)HL」「曼克马利(MENKMARI)」）；没写填「品牌没写」。**品质里不能残留价格数字前缀**（如「41尼盛斯」是错误写法，必须拆开）。\n"
    "- 价格：只取数字；明确写 0 填 0；缺价格填 0；不编造。\n\n"
    "## 汽配品牌白名单（用于切分价格与品牌边界）\n"
    "遇到 " + COMMON_BRANDS_TEXT + " 中任意一个词，优先识别为品牌名。\n\n"
    "## 报价气泡拆解规则\n"
    "a) 单行一条：「OE 价格 品牌」空格分隔，如「2642003201 41 尼盛斯」。\n"
    "b) 价格品牌连写：汽配经常价格+品牌连写无空格，如「41尼盛斯」「60费比」。用白名单切分：数字前缀做价格，后面品牌名作品质。**禁止把数字写进品质**。\n"
    "c) 品牌价格交替：同一气泡内「品牌 价格 品牌 价格 …」如「布雷博 232 泰明顿 245」，按品牌+价格成对拆分，OE 统一用该行开头的报价OE。\n"
    "d) OE + 多组连写：如「2642003201 41尼盛斯 60费比」，开头是报价OE，之后按(价格+品牌连写)或(品牌 价格)顺序成对拆分，每条独立。\n"
    "e) 数量后缀（非品牌）：如「曼克马利*1」「依纳*2」「法雷奥*3」，`*数字` 部分去掉，品质只留品牌名（如「曼克马利」）。\n\n"
    "## 忽略条件\n"
    "只有以下情况忽略：气泡里只有一个「=」号；或只有问候语/表情，无 OE 也无价格；或报价只有 OE 无价格且无法推断。其余一律按上述规则提取。"
)


def ai_call(
    image_url: str,
    prompt: str = "",
    json_schema: Union[Dict[str, Any], None] = None,
    thinking: str = "disabled",
) -> List[Dict[str, Any]]:
    """调用 doubao 视觉模型识别图片，并以 json_schema(strict:true) 输出结构化报价记录列表。

    Args:
        image_url: 图片访问 URL。
        prompt: 自定义识别指令；为空时使用默认报价提示词。
        json_schema: 严格输出的 JSON Schema；为空时使用默认报价 Schema。
        thinking: 深度思考模式，用于速度/质量权衡：
            - "disabled": 关闭思维链，响应最快、最省 token（结构化抽取任务推荐）
            - "enabled":   强制开启思维链，最慢但可能更准
            - "auto":      让模型自行判断是否思考（折中）
    """
    payload = {
        "model": ARK_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": prompt or QUOTATION_PROMPT},
                ],
            }
        ],
        "max_tokens": 2048,
        "response_format": {
            "type": "json_schema",
            "json_schema": json_schema or QUOTATION_JSON_SCHEMA,
        },
        # 深度思考模式开关（doubao-seed-2.0 系列支持）
        "thinking_type": thinking,
    }
    headers = {
        "Authorization": f"Bearer {ARK_API_KEY}",
        "Content-Type": "application/json",
    }
    response = requests.post(ARK_BASE_URL, json=payload, headers=headers, timeout=120)
    response.raise_for_status()

    content = response.json()["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    records = parsed.get("records", [])
    return records


def ai_look(url: str, thinking: str = "disabled") -> List[Dict[str, Any]]:
    """对图片 URL 调用视觉模型，打印并返回结构化报价记录。"""
    print(url)
    records = ai_call(url, thinking=thinking)
    print(json.dumps(records, ensure_ascii=False, indent=2))
    return records


def image_processor(data):
    image_name = data.get("图片名称")
    if not image_name:
        print("图片名称为空")
        return None
    url = f"http://113.45.176.129:8001/static/wxImage/{image_name}"
    records = ai_look(url, thinking="enabled")
    return records


# if __name__ == "__main__":
#     from app.utils.orm.session import orm_session

#     with orm_session() as session:
#         data_list = [item for item in get_image_list(session)]

#     for data in data_list:
#         image_processor(data)


#     # while True:
#     #     image_processor(data_list[0])
