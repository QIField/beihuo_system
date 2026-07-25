"""
QQ 聊天消息解析器

将各供应商的报价回复文本解析为结构化结果。
每个 parse_xxx 函数统一接收：
- search_numbers: 搜索号码列表
- result_text: 供应商回复文本
返回：[{search_oe, result_oe, price, brand}, ...]
"""

import re
from typing import List, Dict, Any


def clean_oe(raw_oe: str) -> str:
    return raw_oe.replace(" ", "").strip()


def trim_note(text: str) -> str:
    return re.sub("\u300E.*$", "", text).strip()


def drop_serial(line: str) -> str:
    return re.sub(r"^\d+、", "", line).strip()


def drop_indent(line: str) -> str:
    return line.lstrip("　").strip()


def is_ad_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if "模板" in stripped:
        return True
    if stripped.startswith("【") and ("," not in stripped or not re.search(r"\d", stripped)):
        return True
    if "编码" in stripped and "售价" in stripped and "--" in stripped and not re.search(r"\d", stripped):
        return True
    if stripped.startswith("『"):
        return True
    return False


def is_pure_number_line(line: str) -> bool:
    stripped = line.strip()
    return bool(re.match(r"^[A-Za-z0-9]+$", stripped)) and bool(re.search(r"\d", stripped))


def split_paragraphs(lines: List[str]) -> List[List[str]]:
    paragraphs = []
    current = []
    for line in lines:
        if line.strip():
            current.append(line)
        else:
            if current:
                paragraphs.append(current)
                current = []
    if current:
        paragraphs.append(current)
    return paragraphs


def _format_result(row: Dict[str, str]) -> str:
    brand = row["brand"] if row["brand"] else ""
    return f"OE={row['oe']} 价格={row['price']} 品牌={brand}"


def _flatten_results(results_by_num: Dict[str, List[Dict[str, str]]]) -> List[Dict[str, str]]:
    """将按搜索号分组的结果展开为统一列表。"""
    flattened = []
    for search_num, items in results_by_num.items():
        for item in items:
            flattened.append({
                "search_oe": search_num,
                "result_oe": item["oe"],
                "price": item["price"],
                "brand": item["brand"],
            })
    return flattened


# ====================== 德上行 ======================
def _parse_deshang_segment(text: str) -> List[Dict[str, str]]:
    text = text.lstrip("=").strip()
    main_pattern = r"([A-Za-z]?\d+)\s+0\s*(?:原厂)?"
    results = []

    segments = text.split("=")
    for idx, segment in enumerate(segments):
        segment = segment.strip()
        if not segment:
            continue

        if idx == 0:
            for m in re.finditer(main_pattern, segment):
                results.append({"oe": clean_oe(m.group(1)), "price": "0", "brand": ""})
            continue

        main_match = re.search(main_pattern, segment)
        if main_match:
            sub_part = segment[: main_match.start()].strip()
            main_part = segment[main_match.start():]
        else:
            sub_part = segment.strip()
            main_part = ""

        cols = [c.strip() for c in sub_part.split("\t") if c.strip()]
        if len(cols) >= 3:
            raw_oe, price, brand = cols[0], cols[1], cols[2]
            results.append({"oe": clean_oe(raw_oe), "price": price, "brand": brand})

        for m in re.finditer(main_pattern, main_part):
            results.append({"oe": clean_oe(m.group(1)), "price": "0", "brand": ""})

    return results


def process_deshang_paragraph(para: List[str], search_numbers: List[str]) -> Dict[str, List[Dict[str, str]]]:
    unique_search_numbers = list(dict.fromkeys(search_numbers))

    result_texts = []
    for line in para:
        stripped = line.rstrip("\n").strip()
        if not stripped or is_ad_line(stripped):
            continue
        if is_pure_number_line(stripped):
            continue
        result_texts.append(stripped)

    if not result_texts or not unique_search_numbers:
        return {num: [] for num in unique_search_numbers}

    result_text = " ".join(result_text)

    positions = []
    sorted_by_length = sorted(unique_search_numbers, key=len, reverse=True)
    i = 0
    while i < len(result_text):
        matched = None
        for num in sorted_by_length:
            if result_text.startswith(num, i):
                if i > 0 and result_text[i - 1] == "=":
                    continue
                matched = num
                break
        if matched:
            positions.append((i, matched))
            i += len(matched)
        else:
            i += 1

    results = {num: [] for num in unique_search_numbers}
    if not positions:
        return results

    for idx, (pos, num) in enumerate(positions):
        start = pos
        end = positions[idx + 1][0] if idx + 1 < len(positions) else len(result_text)
        segment = result_text[start:end]
        parsed = _parse_deshang_segment(segment)
        parsed = [r for r in parsed if r["price"] not in ("0", "0.00")]
        results[num].extend(parsed)

    return results


# ====================== 腾隆 ======================
def _parse_tenglong_line(stripped: str):
    patterns = [
        r"^(\d+)、\s*(\S+(?:\s+\S+)*?)\s+(\d+(?:\.\d+)?)(?:\s+(.+?))?(?:\u300E|$)",
        r"^(\S+(?:\s+\S+)*?)\s+(\d+(?:\.\d+)?)\s+(.+?)(?:\u300E|$)",
    ]
    for pat in patterns:
        m = re.match(pat, drop_indent(stripped))
        if m:
            groups = m.groups()
            if len(groups) == 4:
                raw_oe, price, brand = groups[1], groups[2], groups[3]
            else:
                raw_oe, price, brand = groups[0], groups[1], groups[2]
            return clean_oe(raw_oe), price, trim_note(brand) if brand else "原厂"
    return None


def process_tenglong_paragraph(para: List[str], search_numbers: List[str]) -> Dict[str, List[Dict[str, str]]]:
    unique_search_numbers = list(dict.fromkeys(search_numbers))

    result_lines = []
    for line in para:
        stripped = line.rstrip("\n").strip()
        if is_ad_line(stripped):
            continue
        if is_pure_number_line(stripped):
            continue
        result_lines.append(drop_serial(drop_indent(stripped)))

    if not result_lines or not unique_search_numbers:
        return {num: [] for num in unique_search_numbers}

    result_text = " \n ".join(result_lines)
    positions = []
    sorted_by_length = sorted(unique_search_numbers, key=len, reverse=True)
    i = 0
    while i < len(result_text):
        matched = None
        for num in sorted_by_length:
            if result_text.startswith(num, i):
                matched = num
                break
        if matched:
            positions.append((i, matched))
            i += len(matched)
        else:
            i += 1

    results = {num: [] for num in unique_search_numbers}
    if not positions:
        return results

    for idx, (pos, num) in enumerate(positions):
        start = pos
        end = positions[idx + 1][0] if idx + 1 < len(positions) else len(result_text)
        segment = result_text[start:end]

        for raw_line in segment.split("\n"):
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            parsed = _parse_tenglong_line(raw_line)
            if not parsed:
                continue
            raw_oe, price, brand = parsed
            if price not in ("0", "0.00"):
                results[num].append({"oe": raw_oe, "price": price, "brand": brand})

    return results


# ====================== 昌盛 ======================
def _parse_changsheng_line(stripped: str):
    patterns = [
        r"^(\d+)、\s*([A-Za-z]?\d+(?:\s+[A-Za-z]?\d+)*?)\s+(\d+(?:\.\d+)?)(?:\s+(.+?))?(?:\u300E|$)",
        r"^([A-Za-z]?\d+(?:\s+[A-Za-z]?\d+)*?)\s+(\d+(?:\.\d+)?)\s+(.+?)(?:\u300E|$)",
    ]
    for pat in patterns:
        m = re.match(pat, drop_indent(stripped))
        if m:
            groups = m.groups()
            if len(groups) == 4:
                raw_oe, price, brand = groups[1], groups[2], groups[3]
            else:
                raw_oe, price, brand = groups[0], groups[1], groups[2]
            return clean_oe(raw_oe), price, trim_note(brand) if brand else "原厂"
    return None


def process_changsheng_paragraph(para: List[str], search_numbers: List[str]) -> Dict[str, List[Dict[str, str]]]:
    unique_search_numbers = list(dict.fromkeys(search_numbers))

    result_lines = []
    for line in para:
        stripped = line.rstrip("\n").strip()
        if is_ad_line(stripped):
            continue
        if is_pure_number_line(stripped):
            continue
        result_lines.append(drop_serial(drop_indent(stripped)))

    if not result_lines or not unique_search_numbers:
        return {num: [] for num in unique_search_numbers}

    result_text = " \n ".join(result_lines)
    positions = []
    sorted_by_length = sorted(unique_search_numbers, key=len, reverse=True)
    i = 0
    while i < len(result_text):
        matched = None
        for num in sorted_by_length:
            if result_text.startswith(num, i):
                matched = num
                break
        if matched:
            positions.append((i, matched))
            i += len(matched)
        else:
            i += 1

    results = {num: [] for num in unique_search_numbers}
    if not positions:
        return results

    for idx, (pos, num) in enumerate(positions):
        start = pos
        end = positions[idx + 1][0] if idx + 1 < len(positions) else len(result_text)
        segment = result_text[start:end]

        for raw_line in segment.split("\n"):
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            parsed = _parse_changsheng_line(raw_line)
            if not parsed:
                continue
            raw_oe, price, brand = parsed
            if price not in ("0", "0.00"):
                results[num].append({"oe": raw_oe, "price": price, "brand": brand})

    return results


# ====================== 丰驰 ======================
def _parse_fengchi_line(stripped: str):
    patterns = [
        r"^(\d+)、\s*([A-Za-z0-9]+)\s+(\d+(?:\.\d+)?)(?:\s+(.+?))?(?:\u300E|$)",
        r"^([A-Za-z0-9]+)\s+(\d+(?:\.\d+)?)(?:\s+(.+?))?(?:\u300E|$)",
    ]
    clean_line = drop_indent(stripped)
    for pat in patterns:
        match = re.match(pat, clean_line)
        if not match:
            continue
        groups = match.groups()
        if len(groups) == 4:
            raw_oe, price, brand = groups[1], groups[2], groups[3]
        else:
            raw_oe, price, brand = groups[0], groups[1], groups[2]

        oe = clean_oe(raw_oe)
        brand = trim_note(brand) if brand else "原厂"
        brand = brand.split("-")[0].strip()
        return oe, price, brand
    return None


def process_fengchi_paragraph(para: List[str], search_numbers: List[str]) -> Dict[str, List[Dict[str, str]]]:
    unique_search_numbers = list(dict.fromkeys(search_numbers))
    result_lines = []
    for line in para:
        stripped = line.rstrip("\n").strip()
        if is_ad_line(stripped):
            continue
        if is_pure_number_line(stripped):
            continue
        result_lines.append(drop_indent(stripped))

    if not result_lines or not unique_search_numbers:
        return {num: [] for num in unique_search_numbers}

    result_text = " \n ".join(result_lines)
    positions = []
    sorted_by_length = sorted(unique_search_numbers, key=len, reverse=True)
    i = 0
    while i < len(result_text):
        matched = None
        for num in sorted_by_length:
            if result_text.startswith(num, i):
                matched = num
                break
        if matched:
            positions.append((i, matched))
            i += len(matched)
        else:
            i += 1

    results = {num: [] for num in unique_search_numbers}
    if not positions:
        return results

    for idx, (pos, num) in enumerate(positions):
        start = pos
        end = positions[idx + 1][0] if idx + 1 < len(positions) else len(result_text)
        segment = result_text[start:end]
        for raw_line in segment.split("\n"):
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            line_data = _parse_fengchi_line(raw_line)
            if not line_data:
                continue
            oe, price, brand = line_data
            if price not in ("0", "0.00"):
                results[num].append({"oe": oe, "price": price, "brand": brand})
    return results


# ====================== 恒业 ======================
def _parse_hengye_record_line(line: str):
    if "编码" in line and "售价" in line:
        line = re.sub(r".*售价.*?(?=\d)", "", line)

    fields = [f.strip() for f in line.split(",")]
    if len(fields) < 2:
        return None

    raw_oe = fields[0]
    price = fields[1]
    brand = fields[2] if len(fields) > 2 else ""

    oe = clean_oe(raw_oe)
    if not oe:
        return None

    return {"oe": oe, "price": price, "brand": brand}


def process_hengye_paragraph(para: List[str], search_numbers: List[str]) -> Dict[str, List[Dict[str, str]]]:
    unique_search_numbers = list(dict.fromkeys(search_numbers))
    results = {num: [] for num in unique_search_numbers}

    text_parts = []
    for line in para:
        stripped = line.rstrip("\n").strip()
        if is_ad_line(stripped):
            continue
        if is_pure_number_line(stripped):
            continue
        text_parts.append(stripped)

    if not text_parts or not unique_search_numbers:
        return results

    full_text = " ".join(text_parts)

    oe_candidate_pattern = r"[A-Za-z]?\d+(?:\s+[A-Za-z]?\d+)*"
    positions = []
    for m in re.finditer(oe_candidate_pattern, full_text):
        candidate = clean_oe(m.group(0))
        if candidate in unique_search_numbers:
            positions.append((m.start(), candidate, m.end()))

    seen = set()
    unique_positions = []
    for pos, num, end in positions:
        if num not in seen:
            seen.add(num)
            unique_positions.append((pos, num, end))

    for idx, (pos, num, end) in enumerate(unique_positions):
        if idx >= len(unique_search_numbers):
            break
        target_num = unique_search_numbers[idx]
        next_start = unique_positions[idx + 1][0] if idx + 1 < len(unique_positions) else len(full_text)
        segment = full_text[end:next_start]

        price_match = re.search(r"(\d+(?:\.\d+)?)", segment)
        price = price_match.group(1) if price_match else ""

        brand = segment
        if price:
            brand = brand.replace(price, "", 1)
        brand = re.sub(r"[,\-\s]+", "", brand).strip()

        if price and price not in ("0", "0.00") and brand:
            results[target_num].append({"oe": target_num, "price": price, "brand": brand})

    return results


# ====================== 玉和 ======================
def _parse_yuhe_line(stripped: str):
    m = re.match(r"^([A-Za-z]?\d+(?:\s+[A-Za-z]?\d+)*)\s+(\d+(?:\.\d+)?)\s*(.*)$", stripped)
    if not m:
        return None
    raw_oe, price, brand = m.groups()
    return clean_oe(raw_oe), price, trim_note(brand).strip()


def process_yuhe_paragraph(para: List[str], search_numbers: List[str]) -> Dict[str, List[Dict[str, str]]]:
    unique_search_numbers = list(dict.fromkeys(search_numbers))
    results = {num: [] for num in unique_search_numbers}

    result_lines = []
    for line in para:
        stripped = line.rstrip("\n").strip()
        if is_ad_line(stripped):
            continue
        if is_pure_number_line(stripped):
            continue
        result_lines.append(stripped)

    if not result_lines or not unique_search_numbers:
        return results

    current_search = None
    for raw_line in result_lines:
        parsed = _parse_yuhe_line(raw_line)
        if not parsed:
            continue
        raw_oe, price, brand = parsed

        if raw_oe in unique_search_numbers:
            current_search = raw_oe

        if current_search and price not in ("0", "0.00"):
            results[current_search].append({"oe": raw_oe, "price": price, "brand": brand})

    return results


# ====================== 盛旻 ======================
def process_shengmin_paragraph(para: List[str], search_numbers: List[str]) -> Dict[str, List[Dict[str, str]]]:
    unique_search_numbers = list(dict.fromkeys(search_numbers))
    results = {num: [] for num in unique_search_numbers}

    text_parts = []
    for line in para:
        stripped = line.rstrip("\n").strip()
        if is_ad_line(stripped):
            continue
        if is_pure_number_line(stripped):
            continue
        text_parts.append(stripped)

    if not text_parts or not unique_search_numbers:
        return results

    full_text = " ".join(text_parts)

    sorted_nums = sorted(unique_search_numbers, key=len, reverse=True)
    num_alts = [re.escape(num) + r"[A-Za-z0-9]*" for num in sorted_nums]
    token_pattern = r"=[A-Za-z0-9]+" + "|" + "|".join(num_alts)
    tokens = [(m.start(), m.end(), m.group(0))
              for m in re.finditer(token_pattern, full_text)]
    if not tokens:
        return results

    last_search_num = None
    for idx, (start, end, oe_token) in enumerate(tokens):
        clean_oe = oe_token.lstrip("=")
        is_sub = oe_token.startswith("=")

        if is_sub:
            if not last_search_num:
                continue
            associated = last_search_num
        else:
            associated = None
            for num in sorted_nums:
                if clean_oe.startswith(num):
                    associated = num
                    last_search_num = num
                    break
            if not associated:
                continue

        next_start = tokens[idx + 1][0] if idx + 1 < len(tokens) else len(full_text)
        segment = full_text[end:next_start]

        price_match = re.search(r"\d+(?:\.\d+)?", segment)
        if not price_match:
            continue
        price = price_match.group(0)

        brand = segment.replace(price, "", 1)
        brand = re.sub(r"[,\-\s=]+", "", brand).strip()

        if price not in ("0", "0.00") and brand:
            results[associated].append({"oe": clean_oe, "price": price, "brand": brand})

    return results


# ====================== 对外入口 ======================
def parse_tenglong(search_numbers: List[str], result_text: str) -> List[Dict[str, str]]:
    return _flatten_results(process_tenglong_paragraph(result_text.splitlines(), search_numbers))


def parse_deshang(search_numbers: List[str], result_text: str) -> List[Dict[str, str]]:
    return _flatten_results(process_deshang_paragraph(result_text.splitlines(), search_numbers))


def parse_changsheng(search_numbers: List[str], result_text: str) -> List[Dict[str, str]]:
    return _flatten_results(process_changsheng_paragraph(result_text.splitlines(), search_numbers))


def parse_hengye(search_numbers: List[str], result_text: str) -> List[Dict[str, str]]:
    return _flatten_results(process_hengye_paragraph(result_text.splitlines(), search_numbers))


def parse_yuhe(search_numbers: List[str], result_text: str) -> List[Dict[str, str]]:
    return _flatten_results(process_yuhe_paragraph(result_text.splitlines(), search_numbers))


def parse_shengmin(search_numbers: List[str], result_text: str) -> List[Dict[str, str]]:
    return _flatten_results(process_shengmin_paragraph(result_text.splitlines(), search_numbers))


def parse_fengchi(search_numbers: List[str], result_text: str) -> List[Dict[str, str]]:
    return _flatten_results(process_fengchi_paragraph(result_text.splitlines(), search_numbers))
