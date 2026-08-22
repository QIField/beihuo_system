# -*- coding:utf-8 -*-
"""
导出引擎实现

支持 Excel (.xlsx) 与 CSV (.csv) 两种格式，统一输出为 Flask Response。
"""

import csv
import io
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from flask import Response
from openpyxl.styles import Font, Alignment, PatternFill

from .excel_styles import (
    DATA_FONT,
    DATA_BORDER,
    DATA_HEIGHT,
    ALT_FILL,
)


class BaseExporter(ABC):
    """导出引擎基类。"""

    def __init__(self, fields: List[str], headers: Dict[str, str]):
        self.fields = fields
        self.headers = headers

    @abstractmethod
    def export(self, data: List[Dict[str, Any]], filename: str, **kwargs) -> Response:
        """执行导出并返回 Flask Response。"""
        pass

    def _build_header_row(self) -> List[str]:
        """根据字段顺序构建表头行。"""
        return [self.headers.get(field, field) for field in self.fields]

    def _build_data_rows(self, data: List[Dict[str, Any]]) -> List[List[Any]]:
        """根据字段顺序构建数据行。"""
        rows = []
        for item in data:
            row = []
            for field in self.fields:
                value = item.get(field)
                if value is None:
                    value = ''
                row.append(value)
            rows.append(row)
        return rows


class ExcelExporter(BaseExporter):
    """Excel 导出引擎，基于 openpyxl。"""

    def __init__(
        self,
        fields: List[str],
        headers: Dict[str, str],
        column_widths: Optional[Dict[str, float]] = None,
        freeze_header: bool = True,
        header_style: Optional[Dict[str, Any]] = None,
        data_font: Optional[Any] = None,
        data_border: Optional[Any] = None,
        data_alignment: Optional[Any] = None,
        data_height: Optional[int] = None,
        alt_fill: Optional[Any] = None,
        apply_alt_fill: bool = True,
    ):
        super().__init__(fields, headers)
        self.column_widths = column_widths or {}
        self.freeze_header = freeze_header
        self.header_style = header_style or {
            'bold': True,
            'fill_color': '0070C0',
            'font_color': 'FFFFFF',
            'alignment': {'horizontal': 'center', 'vertical': 'center', 'wrap_text': True},
        }
        # 数据行默认样式与比价模块统一
        self.data_font = data_font or DATA_FONT
        self.data_border = data_border or DATA_BORDER
        self.data_alignment = data_alignment or Alignment(vertical='center')
        self.data_height = data_height or DATA_HEIGHT
        self.alt_fill = alt_fill or ALT_FILL
        self.apply_alt_fill = apply_alt_fill

    def export(
        self,
        data: List[Dict[str, Any]],
        filename: str,
        sheet_name: str = '数据',
        **kwargs,
    ) -> Response:
        try:
            from openpyxl import Workbook
            from openpyxl.utils import get_column_letter
        except ImportError as e:
            raise RuntimeError('缺少 openpyxl 库，无法导出 Excel') from e

        wb = Workbook()
        ws = wb.active
        ws.title = sheet_name

        # 写入表头
        header_row = self._build_header_row()
        header_font_kwargs = {'bold': True}
        if self.header_style.get('font_color'):
            header_font_kwargs['color'] = self.header_style['font_color']
        for col_num, header in enumerate(header_row, 1):
            cell = ws.cell(row=1, column=col_num, value=header)
            cell.font = Font(**header_font_kwargs)
            fill_color = self.header_style.get('fill_color')
            if fill_color:
                cell.fill = PatternFill(
                    start_color=fill_color,
                    end_color=fill_color,
                    fill_type='solid',
                )
            align = self.header_style.get('alignment', {})
            cell.alignment = Alignment(
                horizontal=align.get('horizontal', 'center'),
                vertical=align.get('vertical', 'center'),
                wrap_text=align.get('wrap_text', False),
            )

        # 写入数据并应用统一样式
        for row_num, row_data in enumerate(data, 2):
            for col_num, field in enumerate(self.fields, 1):
                value = row_data.get(field)
                if value is None:
                    value = ''
                cell = ws.cell(row=row_num, column=col_num, value=value)
                cell.font = self.data_font
                cell.border = self.data_border
                cell.alignment = self.data_alignment

                # 交替行填色（偶数行浅蓝）
                if self.apply_alt_fill and row_num % 2 == 0:
                    cell.fill = self.alt_fill

            ws.row_dimensions[row_num].height = self.data_height

        # 冻结首行
        if self.freeze_header:
            ws.freeze_panes = 'A2'

        # 自动调整列宽
        for column in ws.columns:
            column_letter = get_column_letter(column[0].column)
            if column_letter in self.column_widths:
                ws.column_dimensions[column_letter].width = self.column_widths[column_letter]
                continue

            max_length = 0
            for cell in column:
                try:
                    if cell.value and len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except Exception:
                    pass
            adjusted_width = min(max_length + 2, 50)
            if adjusted_width > 0:
                ws.column_dimensions[column_letter].width = adjusted_width

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        return self._make_response(output.getvalue(), filename)

    def _make_response(self, data: bytes, filename: str) -> Response:
        encoded_filename = quote(filename)
        return Response(
            data,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={
                'Content-Disposition': f"attachment;filename*=UTF-8''{encoded_filename}"
            },
        )


class CsvExporter(BaseExporter):
    """CSV 导出引擎，带 UTF-8 BOM，兼容 Excel 中文打开。"""

    def __init__(
        self,
        fields: List[str],
        headers: Dict[str, str],
        delimiter: str = ',',
        newline_replacement: str = ' ',
    ):
        super().__init__(fields, headers)
        self.delimiter = delimiter
        self.newline_replacement = newline_replacement

    def export(
        self,
        data: List[Dict[str, Any]],
        filename: str,
        **kwargs,
    ) -> Response:
        output = io.StringIO()
        writer = csv.writer(output, delimiter=self.delimiter)

        # UTF-8 BOM
        output.write('\ufeff')

        # 表头
        writer.writerow(self._build_header_row())

        # 数据
        for item in data:
            row = []
            for field in self.fields:
                value = item.get(field)
                if value is None:
                    value = ''
                text = str(value)
                if self.newline_replacement:
                    text = text.replace('\r\n', self.newline_replacement) \
                               .replace('\n', self.newline_replacement) \
                               .replace('\r', self.newline_replacement)
                row.append(text)
            writer.writerow(row)

        encoded_filename = quote(filename)
        return Response(
            output.getvalue().encode('utf-8-sig'),
            mimetype='text/csv; charset=utf-8-sig',
            headers={
                'Content-Disposition': f"attachment;filename*=UTF-8''{encoded_filename}.csv"
            },
        )


def get_exporter(
    export_format: str,
    fields: List[str],
    headers: Dict[str, str],
    **options,
) -> BaseExporter:
    """
    根据格式获取对应导出引擎。

    当前标准导出组件仅支持 Excel (.xlsx) 格式。

    Args:
        export_format: 'xlsx'
        fields: 字段顺序列表
        headers: 字段→中文表头映射
        options: 额外配置，透传给具体 Exporter
    """
    fmt = (export_format or 'xlsx').lower()
    if fmt in ('xlsx', 'excel'):
        return ExcelExporter(fields, headers, **options)
    raise ValueError(f'标准导出组件当前仅支持 xlsx 格式，不支持: {export_format}')
