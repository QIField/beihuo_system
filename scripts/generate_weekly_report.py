"""
根据 Git 提交记录自动生成工作周报 Excel。

通用用途：
    读取一个周报模板 Excel，拉取指定作者在指定日期范围内的 Git 提交，
    将提交内容整理成「已完成工作」列表并写入新 Excel。

运行示例：
    # 1. 使用 Git 自动生成的条目（简单模式）
    python generate_weekly_report.py \
        --template "G:/path/to/周报.xlsx" \
        --author "QIField" \
        --start-date 2026-06-15 \
        --end-date 2026-07-07 \
        --output "G:/path/to/周报_输出.xlsx" \
        --reporter "QIField" \
        --department "IT部/研发部"

    # 2. 使用人工整理好的条目 JSON（推荐：内容更精准，可达 40~60 条）
    python generate_weekly_report.py \
        --template "G:/path/to/周报.xlsx" \
        --author "QIField" \
        --start-date 2026-06-15 \
        --end-date 2026-07-07 \
        --output "G:/path/to/周报_输出.xlsx" \
        --reporter "QIField" \
        --department "IT部/研发部" \
        --items-json "items.json"

items.json 格式示例：
    [
        {"content": "完成 XXX 功能", "result": "已上线", "priority": "高", "note": ""},
        ...
    ]
"""

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timedelta

import openpyxl
from openpyxl.styles import Alignment


def parse_args():
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="根据 Git 提交生成周报 Excel")
    parser.add_argument("--template", required=True, help="周报模板 Excel 路径")
    parser.add_argument("--author", required=True, help="Git 作者名（支持模糊匹配）")
    parser.add_argument("--start-date", required=True, help="开始日期，格式 YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="结束日期，格式 YYYY-MM-DD（不含当天）")
    parser.add_argument("--output", required=True, help="输出 Excel 路径")
    parser.add_argument("--reporter", required=True, help="汇报人姓名")
    parser.add_argument("--department", default="IT部/研发部", help="所属部门")
    parser.add_argument(
        "--items-json",
        default=None,
        help="可选：人工整理的已完成工作条目 JSON 文件路径",
    )
    parser.add_argument(
        "--repo",
        default=".",
        help="Git 仓库路径，默认当前目录",
    )
    return parser.parse_args()


def format_period(start_date: str, end_date: str) -> str:
    """将 YYYY-MM-DD 格式化为中文周报周期字符串（首尾均包含）。"""
    s = datetime.strptime(start_date, "%Y-%m-%d")
    e = datetime.strptime(end_date, "%Y-%m-%d")
    return f"{s.year}年{s.month:02d}月{s.day:02d}日 - {e.year}年{e.month:02d}月{e.day:02d}日"


def next_day(date_str: str) -> str:
    """返回 date_str 的下一天，用于 git --until（该参数为排除式）。"""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return (d + timedelta(days=1)).strftime("%Y-%m-%d")


def run_git_log(repo: str, author: str, start_date: str, end_date: str) -> list[dict]:
    """
    调用 git log 获取指定作者在日期范围内的提交。

    返回列表，每个元素为：
        {
            "hash": 提交哈希,
            "date": 提交日期,
            "subject": 提交标题,
            "files": [(状态, 文件路径), ...]
        }
    """
    # git log 命令说明：
    # --author 按作者名过滤
    # --since/--until 按日期范围过滤（until 为结束日期的下一天）
    # --pretty 输出提交分隔符、哈希、日期、标题
    # --name-status 输出每次提交变更的文件及状态（A/M/D/R）
    cmd = [
        "git",
        "-C", repo,
        "log",
        f"--author={author}",
        f"--since={start_date}",
        f"--until={end_date}",
        "--all",
        "--pretty=format:---COMMIT---%n%H%n%ad%n%s",
        "--date=short",
        "--name-status",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"git log 执行失败: {result.stderr}")

    raw = result.stdout
    commits = []
    blocks = raw.split("---COMMIT---")
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if len(lines) < 3:
            continue
        commit_hash = lines[0]
        commit_date = lines[1]
        subject = lines[2]
        files = []
        for line in lines[3:]:
            parts = line.split("\t", 1)
            if len(parts) == 2:
                files.append((parts[0], parts[1]))
        commits.append({
            "hash": commit_hash,
            "date": commit_date,
            "subject": subject,
            "files": files,
        })
    return commits


def auto_generate_items(commits: list[dict]) -> list[dict]:
    """
    根据 Git 提交自动生成「已完成工作」条目。

    规则：
    1. 跳过 Merge 提交。
    2. 如果提交标题包含多个逗号分隔的改动，尝试拆分成多条。
    3. 工作内容 = 提交标题（去除末尾标点）。
    4. 完成情况 = 涉及的主要文件数/模块（用于量化）。
    5. 优先级按关键词启发式判断（高/中/低）。
    6. 备注留空。
    """
    items = []
    for c in commits:
        subject = c["subject"]
        if subject.lower().startswith("merge"):
            continue

        # 拆分提交标题：按「，」「、」「；」分隔的多个改动
        parts = re.split(r"[,，、；;]", subject)
        parts = [p.strip("。 \t") for p in parts if p.strip()]
        if not parts:
            parts = [subject]

        file_count = len(c["files"])
        modules = sorted({os.path.dirname(f[1]).split("/")[0] for f in c["files"] if "/" in f[1]})
        module_str = "/".join(modules[:3]) if modules else "代码"

        for part in parts:
            priority = "中"
            if any(k in part for k in ["完成", "新增", "修复", "重构", "设计", "上线"]):
                priority = "高"
            elif any(k in part for k in ["调整", "修改", "优化", "完善", "改为"]):
                priority = "中"
            elif any(k in part for k in ["删除", "清理", "注释", "格式"]):
                priority = "低"

            items.append({
                "content": part,
                "result": f"涉及 {module_str}，共 {file_count} 个文件变更",
                "priority": priority,
                "note": "",
            })
    return items


def load_manual_items(json_path: str) -> list[dict]:
    """从 JSON 文件读取人工整理好的条目。"""
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_row_by_text(ws, text: str, start_row: int = 1, col: int = 1) -> int | None:
    """在工作表中按 A 列文本查找行号。"""
    for row in range(start_row, ws.max_row + 1):
        cell_value = ws.cell(row=row, column=col).value
        if cell_value and text in str(cell_value):
            return row
    return None


def fill_excel(template_path: str, output_path: str, period: str, reporter: str,
               department: str, items: list[dict]) -> None:
    """
    读取模板并写入周报内容。

    模板结构假设（基于常见周报模板）：
    - A 列包含标题文字，如「汇报周期」「本周核心摘要」「本周已完成工作」等。
    - 「汇报周期」所在行的 B 列填周期，D 列填汇报人，F 列填部门。
    - 「本周核心摘要」下一行用于填写摘要。
    - 「本周已完成工作」下一行为表头（序号/工作内容/完成情况/耗时/备注）。
    - 表头下一行开始填充具体条目，条目不够时插入新行。
    - 「进行中未完工任务」「下周工作计划」「需要协同/上级支持事项」默认留空。
    """
    wb = openpyxl.load_workbook(template_path)
    ws = wb.active

    # 0. 处理合并单元格
    # openpyxl 的 insert_rows 不会自动更新合并区域，若直接插入行，
    # 原合并区域（如 A13:F13）会覆盖新插入的数据行。
    # 因此先记录并解除所有合并，数据写入后再按章节标题文本重新合并。
    section_keywords = [
        "工作周报",
        "本周核心摘要",
        "本周已完成工作",
        "进行中未完工任务",
        "下周工作计划",
        "需要协同/上级支持事项",
    ]
    for merged_range in list(ws.merged_cells.ranges):
        ws.unmerge_cells(str(merged_range))

    # 1. 填充表头区（汇报周期 / 汇报人 / 所属部门）
    period_row = find_row_by_text(ws, "汇报周期")
    if period_row:
        ws.cell(row=period_row, column=2, value=period)
        ws.cell(row=period_row, column=4, value=reporter)
        ws.cell(row=period_row, column=6, value=department)

    # 2. 填充本周核心摘要
    summary_row = find_row_by_text(ws, "本周核心摘要")
    if summary_row:
        summary_text = (
            f"本周期（{period}）主要围绕开思询价单、汽配龙报价、仓位/虚拟库存、"
            f"数据爬取与日志优化展开，累计完成 {len(items)} 项工作。"
        )
        ws.cell(row=summary_row + 1, column=1, value=summary_text)

    # 3. 定位「本周已完成工作」表头
    completed_header_row = find_row_by_text(ws, "本周已完成工作")
    if not completed_header_row:
        raise ValueError("模板中未找到『本周已完成工作』标题")

    # 表头通常在标题下一行，列名为：序号 工作内容 完成情况/成果数据 耗时/优先级 备注
    header_row = completed_header_row + 1
    data_start_row = header_row + 1

    # 4. 找到下一个章节标题（如「进行中未完工任务」），确定当前数据区可用行数
    next_section_row = find_row_by_text(ws, "进行中未完工任务", start_row=completed_header_row + 1)
    if not next_section_row:
        next_section_row = ws.max_row + 1
    existing_data_rows = next_section_row - header_row - 1

    # 5. 如果当前数据区行数不足，在下一章节前插入新行
    rows_needed = len(items)
    if existing_data_rows < rows_needed:
        rows_to_insert = rows_needed - existing_data_rows
        # 在下一章节标题前插入行，避免破坏已完成工作表头，也不影响后续章节结构
        ws.insert_rows(next_section_row, rows_to_insert)

    # 6. 填充条目
    for idx, item in enumerate(items, start=1):
        row = data_start_row + idx - 1
        ws.cell(row=row, column=1, value=idx)
        ws.cell(row=row, column=2, value=item.get("content", ""))
        ws.cell(row=row, column=3, value=item.get("result", ""))
        ws.cell(row=row, column=4, value=item.get("priority", "中"))
        ws.cell(row=row, column=5, value=item.get("note", ""))

        # 设置自动换行，提升可读性
        for col in range(1, 6):
            cell = ws.cell(row=row, column=col)
            cell.alignment = Alignment(wrap_text=True, vertical="top")

    # 7. 重新合并章节标题行（按文本定位，因为插入行后位置已变化）
    for keyword in section_keywords:
        row = find_row_by_text(ws, keyword)
        if row:
            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)

    # 8. 设置列宽（根据模板可调整）
    ws.column_dimensions["A"].width = 8
    ws.column_dimensions["B"].width = 40
    ws.column_dimensions["C"].width = 35
    ws.column_dimensions["D"].width = 15
    ws.column_dimensions["E"].width = 20

    # 9. 保存输出
    wb.save(output_path)
    print(f"周报已生成: {output_path}")
    print(f"已完成工作条目数: {len(items)}")


def main():
    """主流程入口。"""
    args = parse_args()

    # 步骤 1：计算汇报周期
    period = format_period(args.start_date, args.end_date)

    # 步骤 2：获取 Git 提交
    # 注意：git --until 为排除式，因此传入 end_date 的下一天，
    # 以便包含 end_date 当天的提交。
    git_until = next_day(args.end_date)
    print(f"正在拉取 {args.author} 在 {args.start_date} ~ {args.end_date} 的提交...")
    commits = run_git_log(args.repo, args.author, args.start_date, git_until)
    print(f"共获取到 {len(commits)} 条提交")

    # 步骤 3：生成已完成工作条目
    if args.items_json and os.path.exists(args.items_json):
        print(f"使用人工整理条目: {args.items_json}")
        items = load_manual_items(args.items_json)
    else:
        print("根据 Git 提交自动生成条目...")
        items = auto_generate_items(commits)

    # 步骤 4：写入 Excel
    fill_excel(
        template_path=args.template,
        output_path=args.output,
        period=period,
        reporter=args.reporter,
        department=args.department,
        items=items,
    )


if __name__ == "__main__":
    main()
